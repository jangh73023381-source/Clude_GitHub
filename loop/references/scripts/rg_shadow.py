#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rg_shadow.py — Rule RG(리스크온 게이트) shadow 트래커 (2026-07-31 신설).

배경: 2026-07-31 검정에서 **미국 오버나잇 시장수익이 강한 날 방어형 mom20 픽이
구조적으로 열위**임이 확인됐다(발동 18일 절대 -0.201%/일 vs 비발동 64일 +0.227%/일).
7/31 이 극단 사례 — 픽5 +0.4% 인데 KODEX200 은 +11.05%(시가매수 기준)였다.

규칙: 한국장 개장 전 확정되는 **SPY 오버나잇 수익률 >= +0.8%** 이면 게이트 발동.
발동일에는 단기 ETF 5종 대신 대안 자산을 시가에 매수한다. 대안 2종을 **동시에 기록**한다.
  RG-B : KODEX200 벤치 보유   (백테스트 최선 — 82일 누적 +25.1%)
  RG-C : 현금 관망            (사용자 선택 — 82일 누적 +14.5%, 현행 +10.9%)

**shadow 전용 — 실제 추천을 바꾸지 않는다.** 20영업일 도달 시 승격 판정한다.
`mid_momentum_backfill.csv` 와 같은 이유로 **백테스트 82일치는 이 트래커에 넣지 않는다**
(in-sample 이고, 가설 자체가 7/31 관측에서 나와 표본 안에 동기가 들어 있다).

조회 전용 — 주문·매매 기능은 호출하지 않는다.
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
KST = timezone(timedelta(hours=9))
OUT = os.path.join(LOOP, 'references', 'rg_shadow.csv')
COLS = ['date', 'spy_overnight', 'gate', 'picks', 'pick_abs', 'bench_abs',
        'cash_abs', 'rg_b_excess', 'rg_c_excess', 'note']
THRESH = 0.008          # 동결 파라미터 — 20영업일 판정 전까지 변경 금지
BENCH = '069500'


def spy_overnight(dk):
    """한국 거래일 dk 개장 전에 확정된 마지막 미국 세션의 SPY 수익률."""
    import yfinance as yf
    h = yf.Ticker('SPY').history(period='2mo')
    ser = {ts.strftime('%Y%m%d'): float(r['Close']) for ts, r in h.iterrows()}
    days = sorted(ser)
    prior = [d for d in days if d < dk]
    if len(prior) < 2:
        return None
    i = days.index(prior[-1])
    return ser[days[i]] / ser[days[i - 1]] - 1


def load_prices():
    import collections
    cl, op = collections.defaultdict(dict), collections.defaultdict(dict)
    panel = sorted(f for f in os.listdir(os.path.join(LOOP, 'backtest'))
                   if f.startswith('panel_close_'))[-1]
    for r in csv.DictReader(open(os.path.join(LOOP, 'backtest', panel), encoding='utf-8')):
        try:
            cl[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError):
            pass
    p = os.path.join(LOOP, 'backtest', 'panel_open.csv')
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8')):
            op[r['code']][r['date']] = float(r['open'])
    return cl, op


def rows():
    return list(csv.DictReader(open(OUT, encoding='utf-8'))) if os.path.exists(OUT) else []


def record(D, picks):
    """채점일 D(=픽을 실제로 들고 있던 날) 1행을 멱등 누적한다."""
    have = {r['date'] for r in rows()}
    if D in have:
        print(f'  [rg_shadow] {D} 이미 기록됨 — 생략(멱등)')
        return 0
    m = spy_overnight(D)
    if m is None:
        print(f'  [rg_shadow] {D} SPY 오버나잇 확보 실패 — 기록 보류')
        return 1
    cl, op = load_prices()
    rs = [cl[c][D] / op[c][D] - 1 for c in picks
          if op.get(c, {}).get(D) and cl.get(c, {}).get(D)]
    bo, bc = op.get(BENCH, {}).get(D), cl.get(BENCH, {}).get(D)
    if not rs or not (bo and bc):
        print(f'  [rg_shadow] {D} 시가/종가 결손 — 기록 보류')
        return 1
    pick_abs = 100 * (sum(rs) / len(rs)) - 0.10
    bench_abs = 100 * (bc / bo - 1) - 0.10
    gate = m >= THRESH
    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow({'date': D, 'spy_overnight': round(m * 100, 3),
                    'gate': int(gate), 'picks': '|'.join(picks),
                    'pick_abs': round(pick_abs, 3), 'bench_abs': round(bench_abs, 3),
                    'cash_abs': 0.0,
                    'rg_b_excess': round((bench_abs - pick_abs) if gate else 0.0, 3),
                    'rg_c_excess': round((0.0 - pick_abs) if gate else 0.0, 3),
                    'note': 'OOS 실기록(시가매수→종가청산)'})
    print(f'  [rg_shadow] {D} 기록 — SPY {m * 100:+.2f}% · 게이트 '
          f'{"발동" if gate else "미발동"} · 픽 {pick_abs:+.2f}% · 벤치 {bench_abs:+.2f}%')
    return 0


def report():
    rr = rows()
    if not rr:
        print('  [rg_shadow] 기록 없음')
        return
    fired = [r for r in rr if r['gate'] == '1']
    b = sum(float(r['rg_b_excess']) for r in rr)
    c = sum(float(r['rg_c_excess']) for r in rr)
    print(f'  [rg_shadow] 누적 {len(rr)}일 · 게이트 발동 {len(fired)}일 · '
          f'20영업일까지 {max(0, 20 - len(rr))}일')
    print(f'    RG-B(벤치) 누적 개선 {b:+.2f}%p · RG-C(현금) 누적 개선 {c:+.2f}%p')
    if fired:
        print('    발동일: ' + ', '.join(
            f"{r['date'][4:]} 픽{float(r['pick_abs']):+.1f}/벤치{float(r['bench_abs']):+.1f}"
            for r in fired))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', metavar='D', help='채점일 YYYYMMDD')
    ap.add_argument('--picks', default='', help='그날 보유한 단기 ETF 5종 코드(쉼표)')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    rc = 0
    if a.record:
        rc = record(a.record, [c for c in a.picks.split(',') if c])
    if a.report or not a.record:
        report()
    sys.exit(rc)
