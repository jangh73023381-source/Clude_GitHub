#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rule DR 7년 패널 재검정 (2026-09-08).
2026-09-07 로그가 사전 등록한 축 ③. OOS 22건만으로는 승격 불가 판정이 났고,
승격 경로로 "7년 패널에서 R1 고원 · R2 3-fold · R5 중앙값 양수 + 상위3일 제거 부호 유지"를
명시했다. 그 검정을 여기서 수행한다.

규칙: KODEX200(069500) 종가가 최근 60거래일 고점 대비 -TH% 이하이면 '낙폭 국면'.
발동일에는 선정축을 mom20 상위5 → '60일 고점 대비 낙폭 최대 5종'으로 전면 전환.
지표 = 발동일의 (DR 픽5 익일수익 평균 - baseline 픽5 익일수익 평균), %p.
"""
import sys, csv, math, statistics as st
from collections import defaultdict
sys.path.insert(0, 'references/scripts')
from universe_filters import eligible

PANEL = 'backtest/panel_ohlc_long.csv'
BENCH = '069500'
LOOK = 60
POOL = 30          # baseline mom20 상위 pool (Rule H 근사: 전일 +10%·3일 +20% 초과 제외)
NPICK = 5

def load():
    px = defaultdict(dict); nm = {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            c = r['code'].strip()
            try: px[c][r['date']] = float(r['close'])
            except ValueError: continue
            nm[c] = r['name']
    return px, nm

def main():
    th_list = [float(x) for x in (sys.argv[1].split(',') if len(sys.argv) > 1
                                  else ['5','8','10','12','15'])]
    px, nm = load()
    dates = sorted({d for v in px.values() for d in v})
    bench = px[BENCH]
    bdates = sorted(bench)
    uni = [c for c in px if eligible(nm.get(c, ''))]

    # 날짜별 준비
    res = {th: [] for th in th_list}
    for i, d in enumerate(dates):
        if i < LOOK or i + 1 >= len(dates):
            continue
        nd = dates[i + 1]
        # 벤치 국면
        bi = [x for x in bdates if x <= d]
        if len(bi) < LOOK + 1 or d not in bench:
            continue
        win = [bench[x] for x in bi[-LOOK:]]
        dd = bench[d] / max(win) - 1.0

        # 후보 계산 (D 종가까지만)
        d20 = dates[i - 20]
        d1, d3 = dates[i - 1], dates[i - 3]
        cand = []
        for c in uni:
            p = px[c]
            if d not in p or nd not in p or d20 not in p or d1 not in p or d3 not in p:
                continue
            if p[d20] <= 0 or p[d] <= 0:
                continue
            hist = [p[x] for x in dates[i - LOOK:i + 1] if x in p]
            if len(hist) < LOOK * 0.8:
                continue
            mom20 = p[d] / p[d20] - 1.0
            r1 = p[d] / p[d1] - 1.0
            r3 = p[d] / p[d3] - 1.0
            if r1 > 0.10 or r3 > 0.20:      # Rule H
                continue
            cand.append({'c': c, 'mom20': mom20, 'dd': p[d] / max(hist) - 1.0,
                         'ret': p[nd] / p[d] - 1.0})
        if len(cand) < POOL:
            continue
        base = sorted(cand, key=lambda x: -x['mom20'])[:NPICK]
        base_ret = st.mean(x['ret'] for x in base) * 100
        drp = sorted(cand, key=lambda x: x['dd'])[:NPICK]
        dr_ret = st.mean(x['ret'] for x in drp) * 100
        for th in th_list:
            if dd <= -th / 100.0:
                res[th].append((d, dr_ret - base_ret))

    def stats(v):
        if len(v) < 3: return None
        m = st.mean(v); s = st.stdev(v); n = len(v)
        t = m / (s / math.sqrt(n))
        jk = min((sum(v) - x) / (n - 1) for x in v)
        return m, s, t, n, jk

    print('=== Rule DR 7년 재검정 (%s ~ %s) ===' % (dates[LOOK], dates[-1]))
    print('\n[R1] 임계 고원')
    print('%6s %6s %10s %8s %10s %12s' % ('임계', 'n', '평균%p', 't', '잭나이프', '최대일제외'))
    for th in th_list:
        v = [x[1] for x in res[th]]
        s = stats(v)
        if not s:
            print('%6s %6d  표본부족' % ('-%.0f%%' % th, len(v))); continue
        m, sd, t, n, jk = s
        vv = sorted(v)[:-1]
        print('%6s %6d %10.4f %8.2f %10.4f %12.4f'
              % ('-%.0f%%' % th, n, m, t, jk, st.mean(vv)))

    TH = 10.0
    v = [x[1] for x in res[TH]]
    ds = [x[0] for x in res[TH]]
    print('\n[R2] 3-fold (임계 -10%%, n=%d)' % len(v))
    k = len(v) // 3
    for j, seg in enumerate([v[:k], v[k:2*k], v[2*k:]], 1):
        print('  fold%d n=%3d 평균 %+.4f%%p  승률 %.1f%%'
              % (j, len(seg), st.mean(seg), 100*sum(1 for x in seg if x > 0)/len(seg)))

    print('\n[R5] 꼬리 기여도 (임계 -10%%)')
    sv = sorted(v, reverse=True)
    tot = sum(v)
    print('  평균 %+.4f · 중앙값 %+.4f · 승률 %.1f%%'
          % (st.mean(v), st.median(v), 100*sum(1 for x in v if x > 0)/len(v)))
    for k2 in (1, 3, 5, 10):
        rest = sv[k2:]
        print('  상위%2d일 제거 평균 %+.4f  (상위%d일 기여 %.1f%%)'
              % (k2, st.mean(rest), k2, 100*sum(sv[:k2])/tot if tot else float('nan')))
    q = sorted(v); c = max(1, int(len(q)*0.1))
    wz = q[c:len(q)-c] if len(q) > 2*c else q
    print('  윈저화(10%%) 평균 %+.4f' % st.mean(wz))
    print('\n  발동일 %d일 (전체 %d일 중 %.1f%%)' % (len(v), len(dates)-LOOK-1,
                                                100*len(v)/(len(dates)-LOOK-1)))
    print('  최근 발동일 5개:', ', '.join(ds[-5:]))

main()
