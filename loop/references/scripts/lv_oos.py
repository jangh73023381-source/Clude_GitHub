#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lv_oos.py — Rule LV(v2.9) OOS 트래커 (2026-08-22 신설, 조회 전용).

Rule LV 는 2026-08-22 확정 승격됐지만 승격 근거는 in-sample(7년 패널 1,779일)이다.
**방법 확정 이후의 실증 지표는 OOS 누적**이라는 CLAUDE.md §4-3 에 따라, 매일
LV 픽5 와 종전 MOM 픽5 를 **페어로** 기록하고 익일 종가로 채점한다.

왜 페어로 재는가
  LV 는 수익이 아니라 위험을 줄이는 규칙이다(7년: ΔCAGR +0.7%p · ΔMDD +11.2%p ·
  ΔSharpe +0.52, 일평균 초과는 -0.0086%p 로 무차별). 같은 날 같은 유니버스에서 두 정렬을
  나란히 돌려야 잡음이 상쇄되고 **MDD·Sharpe 차이**가 보인다. 일평균 %p 하나로는 판정할 수 없다.

강등 조건 (CLAUDE.md §5 Rule LV 절)
  N* 도달 시 (a) 누적 MDD 가 MOM 대비 개선 (b) Sharpe 가 MOH 대비 개선.
  **2회 연속 미달이면 '검증 대기'로 강등**하고 선정을 mom20 순서로 되돌린다.

사용:
  python3 lv_oos.py --record            # 오늘 morning_state 의 픽을 1행 누적(멱등)
  python3 lv_oos.py --score             # 익일 종가가 확보된 행을 채점(멱등)
  python3 lv_oos.py --report            # 누적 현황·N* 잔여
주의: 조회 전용. 주문·매매 기능 없음.
"""
import argparse
import csv
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(HERE, '..'))
LOOP = os.path.abspath(os.path.join(REF, '..'))
TRACK = os.path.join(REF, 'lv_oos_tracker.csv')
BENCH = '069500'
FIELDS = ['date', 'lv_picks', 'mom_picks', 'lv_ret', 'mom_ret', 'bench_ret',
          'lv_minus_mom', 'lv_minus_bench', 'mom_minus_bench']


def panel():
    c = sorted(glob.glob(os.path.join(LOOP, 'backtest', 'panel_close_*.csv')))
    if not c:
        return {}, []
    px = {}
    for r in csv.DictReader(open(c[-1], encoding='utf-8')):
        try:
            px.setdefault(r['code'], {})[r['date']] = float(r['close'])
        except (KeyError, TypeError, ValueError):
            continue
    return px, sorted({d for v in px.values() for d in v})


def load():
    if not os.path.exists(TRACK):
        return []
    return list(csv.DictReader(open(TRACK, encoding='utf-8')))


def save(rows):
    sys.path.insert(0, HERE)
    import safe_io
    tmp = TRACK + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x['date']):
            w.writerow({k: r.get(k, '') for k in FIELDS})
    safe_io.safe_replace(tmp, TRACK)


def cmd_record():
    st = sorted(glob.glob(os.path.join(HERE, 'morning_state_*.json')))
    if not st:
        print('morning_state 없음'); return 2
    s = json.load(open(st[-1], encoding='utf-8'))
    p = s.get('picks') or {}
    lv = p.get('lv') or {}
    d = p.get('D_for_selection')
    if not d or not p.get('picks5') or not lv.get('mom_picks5'):
        print('picks 또는 lv 블록 없음 — morning_run.py 가 v2.9 패치본인지 확인'); return 2
    rows = load()
    if any(r['date'] == d for r in rows):
        print(f'{d}: 이미 기록됨 (멱등)'); return 0
    rows.append({'date': d, 'lv_picks': p['picks5'], 'mom_picks': lv['mom_picks5']})
    save(rows)
    print(f'{d} 기록 · LV {p["picks5"]} | MOM {lv["mom_picks5"]}')
    return 0


def cmd_score():
    px, dates = panel()
    rows = load()
    n = 0
    for r in rows:
        if r.get('lv_ret'):
            continue
        d = r['date']
        if d not in dates or dates.index(d) + 1 >= len(dates):
            continue
        nx = dates[dates.index(d) + 1]

        def ew(codes):
            v = []
            for c in codes.split(','):
                a, b = px.get(c, {}).get(d), px.get(c, {}).get(nx)
                if a and b:
                    v.append((b / a - 1) * 100)
            return sum(v) / len(v) if len(v) == len(codes.split(',')) else None
        lv, mo = ew(r['lv_picks']), ew(r['mom_picks'])
        bm = ew(BENCH)
        if lv is None or mo is None or bm is None:
            continue
        r.update(lv_ret=f'{lv:.4f}', mom_ret=f'{mo:.4f}', bench_ret=f'{bm:.4f}',
                 lv_minus_mom=f'{lv - mo:.4f}', lv_minus_bench=f'{lv - bm:.4f}',
                 mom_minus_bench=f'{mo - bm:.4f}')
        n += 1
    if n:
        save(rows)
    print(f'채점 {n}행 · 누적 {sum(1 for r in rows if r.get("lv_ret"))}일')
    return 0


def _mdd(vals):
    x, pk, w = 1.0, 1.0, 0.0
    for v in vals:
        x *= (1 + v / 100)
        pk = max(pk, x)
        w = min(w, x / pk - 1)
    return w * 100, (x - 1) * 100


def cmd_report():
    rows = [r for r in load() if r.get('lv_ret')]
    if len(rows) < 2:
        print(f'Rule LV OOS — 누적 {len(rows)}일 (표본 부족)'); return 0
    lv = [float(r['lv_ret']) for r in rows]
    mo = [float(r['mom_ret']) for r in rows]
    bm = [float(r['bench_ret']) for r in rows]
    dif = [float(r['lv_minus_mom']) for r in rows]
    print(f'Rule LV OOS — 누적 {len(rows)}일 ({rows[0]["date"]}~{rows[-1]["date"]})')
    for nm, v in (('LV ', lv), ('MOM', mo), ('벤치', bm)):
        m, c = _mdd(v)
        sh = statistics.mean(v) / statistics.stdev(v) * 252 ** 0.5 if len(v) > 2 else float('nan')
        print(f'  {nm:4s} 누적 {c:+7.2f}% · MDD {m:7.2f}% · Sharpe {sh:5.2f}')
    mm, _ = _mdd(lv)
    mo_mdd, _ = _mdd(mo)
    print(f'  → (a) MDD 개선 {mm - mo_mdd:+.2f}%p  '
          f'{"충족" if mm > mo_mdd else "미달"}')
    print(f'  일평균 LV−MOM {statistics.mean(dif):+.4f}%p · 승 '
          f'{sum(1 for x in dif if x > 0)}/{len(dif)}')
    # N* — judge_ready.py 와 같은 식 (CLAUDE.md §4). 식을 바꾸면 네 곳을 함께 고칠 것.
    if len(dif) > 2:
        m, sd = statistics.mean(dif), statistics.stdev(dif)
        if m:
            ns = min(60, max(8, int((1.28 * sd / abs(m)) ** 2 + 0.999)))
            print(f'  N* {ns}일 — 잔여 {max(0, ns - len(dif))}일')
    return 0


def main():
    ap = argparse.ArgumentParser()
    for f in ('record', 'score', 'report'):
        ap.add_argument('--' + f, action='store_true')
    a = ap.parse_args()
    rc = 0
    if a.record:
        rc |= cmd_record()
    if a.score:
        rc |= cmd_score()
    if a.report or not (a.record or a.score):
        rc |= cmd_report()
    return rc


if __name__ == '__main__':
    sys.exit(main())
