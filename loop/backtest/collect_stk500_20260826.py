# -*- coding: utf-8 -*-
"""collect_stk500_20260826.py — Rule CHB ETF 트랙 검정용 개별주 일봉 수집 (조회 전용·재개 가능).

배경: 2026-08-25 로그가 iteration 10 지정 가설로 'Rule CHB ETF 트랙'을 남겼는데,
8/22 개별주 검정에 쓴 시총 상위 500 일봉 패널이 디스크에 없다(스크립트·산출물 모두 부재).
KRX 패널(`krx_stock_panel.csv`)은 20260303~20260814 **114일**뿐이라 채널 룩백 120일을
채우지 못한다. 따라서 키움 ka10081(조회 전용, 수정주가)로 다시 받는다.

유니버스: `krx_stock_panel.csv` 최종일 시가총액 상위 500 (API 호출 0회로 확정).
산출:    `backtest/stk500_ohlc.csv`  (code,date,open,high,low,close,volume)
재개:    같은 명령을 반복 실행하면 남은 종목만 이어서 받는다(멱등).
"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from ensure_data import settled  # noqa: E402

KRX = os.path.join(HERE, 'krx_stock_panel.csv')
OUT = os.path.join(HERE, 'stk500_ohlc.csv')
FIELDS = ['code', 'date', 'open', 'high', 'low', 'close', 'volume']
NTOP = 500


def universe():
    last, rows = '', []
    for r in csv.DictReader(open(KRX, encoding='utf-8')):
        if r['date'] > last:
            last = r['date']
    for r in csv.DictReader(open(KRX, encoding='utf-8')):
        if r['date'] != last:
            continue
        try:
            mc = float(r['mktcap'] or 0)
        except ValueError:
            mc = 0.0
        if mc > 0:
            rows.append((mc, r['code']))
    rows.sort(reverse=True)
    return [c for _, c in rows[:NTOP]], last


def main(budget=140.0):
    uni, asof = universe()
    done = set()
    if os.path.exists(OUT):
        done = {r['code'] for r in csv.DictReader(open(OUT, encoding='utf-8'))}
    todo = [c for c in uni if c not in done]
    print(f'유니버스 {len(uni)}종 (시총 기준일 {asof}) · 완료 {len(done)} · 남은 {len(todo)}')
    if not todo:
        print('[완료] 수집 종료')
        return 0

    new = os.path.exists(OUT)
    f = open(OUT, 'a', newline='', encoding='utf-8')
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if not new:
        w.writeheader()

    t0, cnt = time.time(), 0
    for c in todo:
        if time.time() - t0 > budget:
            break
        try:
            time.sleep(0.22)
            resp = k.get_daily_chart(c)
            bars = resp.get('stk_dt_pole_chart_qry') or []
        except Exception as e:                                # noqa: BLE001
            print(f'  [skip] {c} {e}')
            continue
        n = 0
        for b in bars:
            d = str(b.get('dt') or b.get('date') or '')[:8]
            # 미확정 봉 유입 금지 — 키움은 장중에도 당일 봉을 돌려준다(실측 20260826 거래량 0).
            if not d or not settled(d):
                continue
            try:
                w.writerow({
                    'code': c, 'date': d,
                    'open': abs(float(b.get('open_pric') or b.get('open') or 0)),
                    'high': abs(float(b.get('high_pric') or b.get('high') or 0)),
                    'low': abs(float(b.get('low_pric') or b.get('low') or 0)),
                    'close': abs(float(b.get('cur_prc') or b.get('close') or 0)),
                    'volume': abs(float(b.get('trde_qty') or b.get('volume') or 0)),
                })
                n += 1
            except (TypeError, ValueError):
                continue
        if n:
            cnt += 1
    f.close()
    left = len(todo) - cnt
    print(f'이번 실행 {cnt}종 · {time.time() - t0:.1f}초 · 남은 {left}')
    return 0 if left <= 0 else 3


if __name__ == '__main__':
    b = float(sys.argv[1]) if len(sys.argv) > 1 else 140.0
    sys.exit(main(b))
