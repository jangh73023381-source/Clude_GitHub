#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regime_shadow.py — Rule DR · Rule IL shadow 트래커 (2026-08-01 신설).

사용자 문제제기(2026-08-01):
  ① "상승장이면 그에 맞는 종목선정이 되어야 하는데 지금은 방어주 위주다."
  ② "레버리지 청산이 원인이면 인버스·레버리지 보유량으로 증시를 예측할 수 있지 않나."

Rule DR (Drawdown Rotation) — 지수가 60일 고점 대비 -10% 이하인 '낙폭 국면'에는 단기 선정축을
  mom20 에서 **60일 고점 대비 낙폭 최대 5종**으로 전환한다. mom20 은 '덜 빠진 것'을 고르므로
  V자 반등에서 구조적으로 뒤진다(2026-07-31 실측: mom20 픽 +0.46% vs KODEX200 +24.17%).

Rule IL (Inverse-Leverage sentiment gate) — 인버스계 거래대금 비중의 20일 z-score(ILZ)가
  +2.0 이상이면 '비관 극단'으로 보고 지수 반등 게이트를 발동한다.

**둘 다 shadow 전용 — 실제 추천을 바꾸지 않는다.** 실패해도 아침 루틴을 중단시키지 않는다.
조회 전용이며 주문·매매 기능은 없다.
"""
import argparse
import csv
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from universe_filters import is_cash, is_deriv  # noqa: E402
import safe_io  # noqa: E402

PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
LEVPANEL = os.path.join(LOOP, 'backtest', 'panel_lev_inv.csv')
DR_TRACKER = os.path.join(LOOP, 'references', 'dr_shadow.csv')
IL_TRACKER = os.path.join(LOOP, 'references', 'il_shadow.csv')

BENCH = '069500'
NPICK = 5
COST = 0.0  # 2026-11-01: v2.8(2026-08-14) 무비용 전환 때 누락됐던 곳 — CLAUDE.md §5 "채점 비용"대로 0으로 정정(이 스크립트는 종결된 Rule DR/IL 계열이지만 morning_run.py가 지금도 매일 호출한다)
DD_TH = -0.10      # 동결 — 낙폭 국면 임계
ILZ_TH = 2.0       # 동결 — 비관 극단 임계
LEV = ['122630', '233740']
INV = ['114800', '252670', '251340']

DR_COLS = ['date', 'score_date', 'status', 'fired', 'dd60', 'base_codes', 'dr_codes',
           'base_ret', 'dr_ret', 'bench_ret', 'base_excess', 'dr_excess',
           'dr_minus_base', 'note']
IL_COLS = ['date', 'score_date', 'status', 'ilz', 'fired', 'bench_ret_d1',
           'bench_ret_d5', 'note']


# ---------------------------------------------------------------- 공통
def load_panel():
    px, nm = defaultdict(dict), {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                c = float(r['close'])
            except (ValueError, KeyError):
                continue
            if c > 0:
                px[r['code']][r['date']] = c
                nm[r['code']] = r['name']
    return px, nm, sorted({d for v in px.values() for d in v})


def read(path, cols):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write(path, cols, rows):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in cols})
    safe_io.safe_replace(tmp, path)


def _port(px, codes, d, dn):
    rs = []
    for c in codes:
        v = px.get(c) or {}
        if d in v and dn in v and v[d]:
            rs.append(v[dn] / v[d] - 1)
    return (sum(rs) / len(rs) - COST) if rs else None


# ---------------------------------------------------------------- Rule DR
def eligible(px, nm, d):
    return [c for c, v in px.items()
            if d in v and not is_deriv(nm.get(c, '')) and not is_cash(nm.get(c, ''))]


def dd60(px, dates, i):
    v = px.get(BENCH) or {}
    if i < 60:
        return None
    w = [v[dates[k]] for k in range(i - 60, i + 1) if dates[k] in v]
    if len(w) < 40 or dates[i] not in v:
        return None
    return v[dates[i]] / max(w) - 1.0


def pick_mom20(px, nm, dates, i):
    d, d1, d3, d20 = dates[i], dates[i - 1], dates[i - 3], dates[i - 20]
    sc = []
    for c in eligible(px, nm, d):
        v = px[c]
        if not all(x in v for x in (d1, d3, d20)) or not v[d20]:
            continue
        if v[d] / v[d1] - 1 > 0.10 or v[d] / v[d3] - 1 > 0.20:      # Rule H
            continue
        sc.append((v[d] / v[d20] - 1, c))
    sc.sort(reverse=True)
    return [c for _, c in sc[:NPICK]]


def pick_dd(px, nm, dates, i):
    """60일 고점 대비 낙폭이 가장 큰 5종."""
    d = dates[i]
    sc = []
    for c in eligible(px, nm, d):
        v = px[c]
        w = [v[dates[k]] for k in range(max(0, i - 60), i + 1) if dates[k] in v]
        if len(w) < 40 or not max(w):
            continue
        sc.append((-(v[d] / max(w) - 1.0), c))
    sc.sort(reverse=True)
    return [c for _, c in sc[:NPICK]]


def dr_record(D=None):
    px, nm, dates = load_panel()
    D = D or dates[-1]
    if D not in dates:
        print(f'  [dr] {D} 패널에 없음')
        return 1
    rows = read(DR_TRACKER, DR_COLS)
    if any(r['date'] == D for r in rows):
        print(f'  [dr] {D} 이미 기록됨(멱등)')
        return 0
    i = dates.index(D)
    if i < 60:
        print('  [dr] 워밍업 부족')
        return 1
    dd = dd60(px, dates, i)
    fired = dd is not None and dd <= DD_TH
    base = pick_mom20(px, nm, dates, i)
    dr = pick_dd(px, nm, dates, i) if fired else base
    rows.append({'date': D, 'status': 'pending', 'fired': int(fired),
                 'dd60': f'{dd*100:.2f}' if dd is not None else '',
                 'base_codes': ';'.join(base), 'dr_codes': ';'.join(dr)})
    rows.sort(key=lambda r: r['date'])
    write(DR_TRACKER, DR_COLS, rows)
    print(f'  [dr] {D} 기록 — 낙폭 {dd*100:.1f}% · 발동 {fired}')
    return 0


def dr_score():
    px, nm, dates = load_panel()
    rows = read(DR_TRACKER, DR_COLS)
    n = 0
    for r in rows:
        if r['status'] == 'scored' or r['date'] not in dates:
            continue
        i = dates.index(r['date'])
        if i + 1 >= len(dates):
            continue
        d, dn = dates[i], dates[i + 1]
        bv = px.get(BENCH) or {}
        if d not in bv or dn not in bv:
            continue
        br = bv[dn] / bv[d] - 1
        a = _port(px, [c for c in r['base_codes'].split(';') if c], d, dn)
        b = _port(px, [c for c in r['dr_codes'].split(';') if c], d, dn)
        r.update({'score_date': dn, 'status': 'scored',
                  'bench_ret': f'{br*100:.4f}',
                  'base_ret': f'{a*100:.4f}' if a is not None else '',
                  'dr_ret': f'{b*100:.4f}' if b is not None else '',
                  'base_excess': f'{(a-br)*100:.4f}' if a is not None else '',
                  'dr_excess': f'{(b-br)*100:.4f}' if b is not None else '',
                  'dr_minus_base': (f'{(b-a)*100:.4f}'
                                    if None not in (a, b) else '')})
        n += 1
    if n:
        write(DR_TRACKER, DR_COLS, rows)
    print(f'  [dr] {n}건 채점')
    return 0


# ---------------------------------------------------------------- Rule IL
def load_lev():
    if not os.path.exists(LEVPANEL):
        return None, None
    amt, px = defaultdict(dict), defaultdict(dict)
    with open(LEVPANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                c, v = float(r['close']), float(r['volume'])
            except ValueError:
                continue
            if c > 0:
                amt[r['code']][r['date']] = c * v
                px[r['code']][r['date']] = c
    return amt, px


def ilz_at(amt, dates, i, k=20):
    def share(d):
        a = sum(amt[c].get(d, 0.0) for c in LEV)
        b = sum(amt[c].get(d, 0.0) for c in INV)
        return b / (a + b) if (a + b) > 0 else None
    if i < k:
        return None
    w = [share(dates[j]) for j in range(i - k, i)]
    w = [x for x in w if x is not None]
    cur = share(dates[i])
    if len(w) < k or cur is None:
        return None
    m = sum(w) / len(w)
    sd = math.sqrt(sum((x - m) ** 2 for x in w) / (len(w) - 1))
    return (cur - m) / sd if sd > 0 else None


def il_record(D=None):
    amt, px = load_lev()
    if amt is None:
        print('  [il] panel_lev_inv.csv 없음 — 건너뜀')
        return 1
    dates = sorted(px[BENCH])
    D = D or dates[-1]
    if D not in dates:
        print(f'  [il] {D} 레버리지 패널에 없음 — 건너뜀')
        return 1
    rows = read(IL_TRACKER, IL_COLS)
    if any(r['date'] == D for r in rows):
        print(f'  [il] {D} 이미 기록됨(멱등)')
        return 0
    i = dates.index(D)
    z = ilz_at(amt, dates, i)
    if z is None:
        print('  [il] 워밍업 부족')
        return 1
    rows.append({'date': D, 'status': 'pending', 'ilz': f'{z:.3f}',
                 'fired': int(z >= ILZ_TH)})
    rows.sort(key=lambda r: r['date'])
    write(IL_TRACKER, IL_COLS, rows)
    print(f'  [il] {D} 기록 — ILZ {z:+.2f} · 발동 {z >= ILZ_TH}')
    return 0


def il_score():
    amt, px = load_lev()
    if amt is None:
        return 1
    dates = sorted(px[BENCH])
    rows = read(IL_TRACKER, IL_COLS)
    n = 0
    for r in rows:
        if r['status'] == 'scored' or r['date'] not in dates:
            continue
        i = dates.index(r['date'])
        if i + 5 >= len(dates):
            continue
        v = px[BENCH]
        r.update({'score_date': dates[i + 5], 'status': 'scored',
                  'bench_ret_d1': f'{(v[dates[i+1]]/v[dates[i]]-1)*100:.4f}',
                  'bench_ret_d5': f'{(v[dates[i+5]]/v[dates[i]]-1)*100:.4f}'})
        n += 1
    if n:
        write(IL_TRACKER, IL_COLS, rows)
    print(f'  [il] {n}건 채점 (D+5 기준)')
    return 0


def report():
    rows = [r for r in read(DR_TRACKER, DR_COLS)
            if r['status'] == 'scored' and r['fired'] == '1' and r['dr_minus_base']]
    if rows:
        v = [float(r['dr_minus_base']) for r in rows]
        m = sum(v) / len(v)
        jk = min((sum(v) - x) / (len(v) - 1) for x in v) if len(v) > 2 else None
        print(f'  [dr] 발동 OOS {len(v)}건 · DR-base 평균 {m:+.4f}%p · '
              f'잭나이프 {jk if jk is None else round(jk, 4)}')
    else:
        print('  [dr] 발동·채점 완료 0건')
    rows = [r for r in read(IL_TRACKER, IL_COLS)
            if r['status'] == 'scored' and r['fired'] == '1']
    if rows:
        v = [float(r['bench_ret_d5']) for r in rows]
        print(f'  [il] 발동 OOS {len(v)}건 · D+5 지수 평균 {sum(v)/len(v):+.3f}%')
    else:
        print('  [il] 발동·채점 완료 0건')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', nargs='?', const=True)
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    rc = 0
    D = None if a.record is True else a.record
    if a.record:
        dr_record(D)
        il_record(D)
    if a.score:
        dr_score()
        il_score()
    if a.report:
        report()
    if not (a.record or a.score or a.report):
        ap.print_help()
    return rc


if __name__ == '__main__':
    sys.exit(main())
