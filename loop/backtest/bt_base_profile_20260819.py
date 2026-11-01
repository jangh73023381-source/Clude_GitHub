#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_base_profile_20260819.py — 확정방법(baseline) 자체의 2년 실측 프로파일.

왜 이걸 먼저 하나
  2026-08-18 하루에 11축 127변형을 돌려 승격 0건이었고, 마지막 후보 Rule TVQ 는
  **이득의 63%가 하루에서 나온다**는 이유로 기각했다(관문 R5 신설). 그렇다면 당연히 물어야 한다 —
  **baseline 자신은 꼬리에 의존하지 않는가?** baseline 의 초과수익도 몇 일이 만든 것이라면,
  "+0.07%p 개선"을 좇는 일 자체가 잡음 사냥이고, 진짜 문제는 선정 규칙이 아니라 위험 관리다.

산출
  ① 픽5 절대손익·KODEX200 대비 초과의 누적/연율/MDD/승률
  ② **R5 를 baseline 에 적용** — 상위·하위 k일 제거 시 초과가 어떻게 변하는가
  ③ 국면(반기)별 분해
  ④ 최악·최고 일자 목록 (사후 점검용, 선정에는 무관)

패널 `panel_ohlc_2y.csv` 604일 · 채점 583일 · 무비용(v2.8) · 벤치 KODEX200(069500).
"""
import os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_krx2y_20260818 as M


def mdd(curve):
    peak, worst = curve[0], 0.0
    for x in curve:
        peak = max(peak, x)
        worst = min(worst, x / peak - 1)
    return worst * 100


def cum(rets):
    c, out = 1.0, []
    for r in rets:
        c *= (1 + r / 100)
        out.append(c)
    return out


def main():
    px, names = M.load_etf()
    dates = sorted({d for c in px for d in px[c]})
    cands, _ = M.build_cands(px, names, dates)

    rows = []
    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        bm = M.fwd(px, M.BENCH, d, nxt)
        cd = cands.get(d)
        if bm is None or not cd or len(cd) < M.NPICK:
            continue
        rs = [M.fwd(px, c, d, nxt) for _, c in cd[:M.NPICK]]
        rs = [x for x in rs if x is not None]
        if len(rs) < M.NPICK:
            continue
        rows.append((d, sum(rs) / len(rs), bm))

    n = len(rows)
    pick = [x for _, x, _ in rows]
    bench = [b for _, _, b in rows]
    ex = [p - b for p, b in zip(pick, bench)]
    cp, cb = cum(pick), cum(bench)
    yrs = n / 252

    print(f'=== 확정방법(mom20+RuleH) 2년 실측 · 채점 {n}일 ({rows[0][0]}~{rows[-1][0]}) ===\n')
    print(f'[절대] 픽5 누적 {(cp[-1]-1)*100:+.1f}%  (연율 {((cp[-1])**(1/yrs)-1)*100:+.1f}%)  '
          f'MDD {mdd(cp):.1f}%  일변동성 {statistics.stdev(pick):.2f}%')
    print(f'[벤치] KODEX200 누적 {(cb[-1]-1)*100:+.1f}%  (연율 {((cb[-1])**(1/yrs)-1)*100:+.1f}%)  '
          f'MDD {mdd(cb):.1f}%  일변동성 {statistics.stdev(bench):.2f}%')
    print(f'[초과] 평균 {statistics.mean(ex):+.4f}%p/일 · 합 {sum(ex):+.1f}%p · '
          f'승률 {sum(1 for x in ex if x>0)/n*100:.1f}% · sd {statistics.stdev(ex):.2f} · '
          f't {statistics.mean(ex)/(statistics.stdev(ex)/n**0.5):+.2f}')
    print(f'[누적비] 픽5/벤치 {cp[-1]/cb[-1]:.3f}  (1.0 이면 무승부)')

    print('\n=== ★ R5 를 baseline 초과수익에 적용 — 꼬리 의존도 ===')
    s = sorted(ex, reverse=True)
    tot = sum(s)
    print(f'  전체 평균 {tot/n:+.4f}%p · 중앙값 {statistics.median(ex):+.4f}%p')
    for k in (1, 3, 5, 10, 20, 30):
        print(f'  상위 {k:2d}일 제거 → 평균 {(tot-sum(s[:k]))/(n-k):+.4f}%p '
              f'(상위 {k}일 기여 {sum(s[:k])/tot*100:6.1f}%)   |   '
              f'하위 {k:2d}일 제거 → 평균 {(tot-sum(s[-k:]))/(n-k):+.4f}%p')
    import numpy as np
    a = np.array(ex)
    for t in (0.01, 0.02, 0.05):
        lo, hi = np.quantile(a, [t, 1 - t])
        print(f'  윈저화 {int(t*100)}% 평균 {np.clip(a, lo, hi).mean():+.4f}%p')

    print('\n=== 국면(반기)별 분해 ===')
    print(f'  {"구간":18s} {"일수":>4s} {"픽5누적":>9s} {"벤치누적":>9s} {"초과평균":>9s} {"승률":>6s}')
    buckets = {}
    for (d, p, b) in rows:
        key = d[:4] + ('H1' if d[4:6] <= '06' else 'H2')
        buckets.setdefault(key, []).append((p, b))
    for k in sorted(buckets):
        v = buckets[k]
        pp, bb = cum([x for x, _ in v]), cum([y for _, y in v])
        e = [x - y for x, y in v]
        print(f'  {k:18s} {len(v):4d} {(pp[-1]-1)*100:+8.1f}% {(bb[-1]-1)*100:+8.1f}% '
              f'{statistics.mean(e):+8.4f} {sum(1 for x in e if x>0)/len(e)*100:5.1f}%')

    print('\n=== 초과수익 최고·최악 10일 (사후 점검용) ===')
    srt = sorted(rows, key=lambda r: r[1] - r[2])
    print('  최악: ' + ' '.join(f'{d}({p-b:+.1f})' for d, p, b in srt[:10]))
    print('  최고: ' + ' '.join(f'{d}({p-b:+.1f})' for d, p, b in srt[-10:][::-1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
