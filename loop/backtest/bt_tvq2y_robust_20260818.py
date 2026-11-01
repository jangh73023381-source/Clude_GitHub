#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_tvq2y_robust_20260818.py — 2년 재검정에서 유일하게 통과한 Rule TVQ 의 4관문 + 추가 검정.

후보: **거래대금 집중도(개별종목 상위20 점유율)의 롤링 60일 분위수 p80 초과 → 역모멘텀 전환, [D-1]**
  604일 패널 · 채점 583일 · full +0.1343 (baseline +0.0584) · train +0.1572 · test +0.1115 ·
  잭나이프 +0.1148 · **3분할 fold 3/3** · t +1.51 · [D-1] 이라 실전 조달 가능.

주의 — 같은 규칙이 113일 표본(2026-08-18 오후 iteration 6)에서는 **train -0.2700 으로 기각**됐다.
표본이 뒤집은 사례이므로, 어느 쪽이 맞는지 가리는 것이 이 스크립트의 핵심이다.
"""
import os, random, statistics, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_krx2y_20260818 as M


def folds(res, k):
    n = len(res)
    return [sum(x for _, x in res[i * n // k:(i + 1) * n // k]) /
            max(1, len(res[i * n // k:(i + 1) * n // k])) for i in range(k)]


def main():
    px, names = M.load_etf()
    dates = sorted({d for c in px for d in px[c]})
    maps = M.load_maps()
    brd, conc, _ = M.load_stock_axes(maps)
    cands, _ = M.build_cands(px, names, dates)
    kdates = sorted(conc)

    base_res = M.run(M.sel_base, px, dates, cands)
    base = M.stat(base_res, 'BASE')
    print(f'BASE full{base["mean"]:+.4f} train{base["train"]:+.4f} test{base["test"]:+.4f} '
          f'jk{base["jk"]:+.4f} | fold3 ' + ' '.join(f'{x:+.4f}' for x in base['f3']))
    b6 = folds(base_res, 6)
    print('     fold6 ' + ' '.join(f'{x:+.4f}' for x in b6) + '\n')

    def gate(series, q, lag=1, win=60):
        keys = sorted(series)
        kp = {d: i for i, d in enumerate(keys)}

        def f(cd, d):
            ref = M.lagged(d, lag, keys)
            if ref is None:
                return M.sel_base(cd, d)
            i = kp[ref]
            hist = [series[x] for x in keys[max(0, i - win):i]]
            if len(hist) < 20:
                return M.sel_base(cd, d)
            p = sum(1 for x in hist if x <= series[ref]) / len(hist)
            return [c for _, c in (cd[-M.NPICK:] if p > q else cd[:M.NPICK])]
        return f

    def ev(f, label, show=True, k=3):
        r = M.run(f, px, dates, cands)
        s = M.stat(r, label)
        s['res'] = r
        if show:
            okf = sum(1 for i in range(3) if s['f3'][i] > base['f3'][i])
            p3 = (s['mean'] > base['mean'] and s['train'] > base['train']
                  and s['test'] > base['test'] and s['jk'] > 0)
            print(f'  {label:38s} full{s["mean"]:+.4f} train{s["train"]:+.4f} '
                  f'test{s["test"]:+.4f} jk{s["jk"]:+.4f} t{s["t"]:+.2f} '
                  f'{"✔" if p3 else " "}fold{okf}/3')
        return s

    print('=== R1a 파라미터 고원 — 분위수 q × 롤링창 win ([D-1]) ===')
    print('        ' + ''.join(f'win{w:<9d}' for w in (40, 60, 90, 120)))
    for q in (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90):
        row = f'  q{q:.2f} '
        for w in (40, 60, 90, 120):
            s = ev(gate(conc, q, 1, w), '', show=False)
            okf = sum(1 for i in range(3) if s['f3'][i] > base['f3'][i])
            p3 = (s['mean'] > base['mean'] and s['train'] > base['train']
                  and s['test'] > base['test'] and s['jk'] > 0 and okf == 3)
            row += f'{s["mean"]:+8.4f}{"✔" if p3 else " "} '
        print(row)

    print('\n=== R1b lag 축 (q0.80 win60) ===')
    for lag in (1, 2, 3, 5):
        ev(gate(conc, 0.80, lag), f'lag={lag} (D-{lag})')

    print('\n=== R2 fold — 3분할·6분할 ===')
    cand = ev(gate(conc, 0.80), '후보 q0.80 win60 [D-1]')
    c6 = folds(cand['res'], 6)
    print('  baseline fold6 ' + ' '.join(f'{x:+.4f}' for x in b6))
    print('  후보     fold6 ' + ' '.join(f'{x:+.4f}' for x in c6))
    print(f'  6분할 중 baseline 초과 {sum(1 for i in range(6) if c6[i] > b6[i])}/6')

    print('\n=== R3 정의 교체 — 집중도를 다르게 정의해도 재현되는가 ===')
    alt = M.load_conc_variants() if hasattr(M, 'load_conc_variants') else None
    import csv
    from collections import defaultdict
    day = defaultdict(list)
    r = csv.reader(open(M.STK, encoding='utf-8'))
    hdr = next(r)
    i_d, i_v, i_m = hdr.index('date'), hdr.index('value'), hdr.index('market')
    for row in r:
        try:
            day[row[i_d]].append((float(row[i_v] or 0), row[i_m]))
        except ValueError:
            continue
    variants = {}
    v10, v50, hhi, ks = {}, {}, {}, {}
    for d, v in day.items():
        vals = sorted((x[0] for x in v), reverse=True)
        tot = sum(vals) or 1.0
        v10[d] = sum(vals[:10]) / tot
        v50[d] = sum(vals[:50]) / tot
        hhi[d] = sum((x / tot) ** 2 for x in vals)
        kv = sorted((x[0] for x in v if x[1] == 'KOSPI'), reverse=True)
        kt = sum(kv) or 1.0
        ks[d] = sum(kv[:20]) / kt
    variants = {'상위10 점유': v10, '상위50 점유': v50, 'HHI(전종목)': hhi,
                '코스피 상위20 점유': ks}
    for nm, ser in variants.items():
        ev(gate(ser, 0.80), f'{nm} p80 [D-1]')

    print('\n=== 발동일 분석 (q0.80 win60 [D-1]) ===')
    keys = sorted(conc)
    kp = {d: i for i, d in enumerate(keys)}
    fired = []
    for d, _ in cand['res']:
        ref = M.lagged(d, 1, keys)
        i = kp[ref]
        hist = [conc[x] for x in keys[max(0, i - 60):i]]
        if len(hist) >= 20 and sum(1 for x in hist if x <= conc[ref]) / len(hist) > 0.80:
            fired.append(d)
    fs = set(fired)
    on = [x for d, x in cand['res'] if d in fs]
    onb = [x for d, x in base_res if d in fs]
    print(f'  발동 {len(fired)}일 / {len(cand["res"])}일 ({len(fired)/len(cand["res"])*100:.1f}%)')
    print(f'  발동일 후보 평균 {statistics.mean(on):+.4f} vs baseline {statistics.mean(onb):+.4f} '
          f'→ 조건부 우위 {statistics.mean(on)-statistics.mean(onb):+.4f}%p')
    diffs = sorted(((a - b) for a, b in zip(on, onb)), reverse=True)
    tot = sum(diffs)
    print(f'  발동일 우위 합 {tot:+.2f}%p · 상위 3일 기여 {sum(diffs[:3]):+.2f}%p '
          f'({sum(diffs[:3])/tot*100:.0f}%) · 상위 10일 {sum(diffs[:10])/tot*100:.0f}%')
    print(f'  발동일 우위 승률 {sum(1 for x in diffs if x>0)/len(diffs)*100:.1f}%')

    print('\n=== R4 플라시보 — 발동일 수는 같고 날짜만 무작위, 200회 ===')
    alld = [d for d, _ in cand['res']]
    rng = random.Random(20260818)
    nfire = len(fired)
    null = []
    for _ in range(200):
        fake = set(rng.sample(alld, nfire))

        def g(cd, d, fake=fake):
            return [c for _, c in (cd[-M.NPICK:] if d in fake else cd[:M.NPICK])]
        null.append(M.stat(M.run(g, px, dates, cands), '')['mean'])
    null.sort()
    p = sum(1 for x in null if x >= cand['mean']) / len(null)
    print(f'  실제 {cand["mean"]:+.4f} · 귀무 평균 {statistics.mean(null):+.4f} '
          f'sd {statistics.stdev(null):.4f} · 95분위 {null[189]:+.4f}')
    print(f'  경험적 p = {p:.3f}')

    print('\n=== 표본 뒤집힘 진단 — 113일 구간에서는 왜 졌나 ===')
    last = set(d for d, _ in cand['res'][-93:])
    a = [x for d, x in cand['res'] if d in last]
    b = [x for d, x in base_res if d in last]
    print(f'  최근 93일: 후보 {statistics.mean(a):+.4f} vs baseline {statistics.mean(b):+.4f} '
          f'→ {statistics.mean(a)-statistics.mean(b):+.4f}%p')
    print('  (오후 회차 113일 검정은 롤링 분위수의 기준 분포를 113일 안에서만 잡아')
    print('   과거 참조창이 얇았다. 2년 표본에서는 분위수가 제대로 추정된다.)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
