# -*- coding: utf-8 -*-
"""중기 트랙 장기표본 검증 (panel_ohlc_long.csv, 1,800거래일 2019-04~2026-07).

주의 — 생존편의: 유니버스는 '2026-07-28 현재 거래대금 상위 201종'이다. 과거로
거슬러 올라갈수록 "그때 살아남아 지금 상위인 ETF"만 남으므로 성과가 과대평가된다.
따라서 장기표본은 '2년 결과가 우연인지'를 보는 보조 근거로만 쓴다.
"""
import sys, os
os.environ.setdefault('PANEL_FILE', 'panel_ohlc_long.csv')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, run_h, stat, show, mk_rank, eligible, BENCH, COST)


def add_mom(cache, lb):
    key = f'mom{lb}'
    for code, e in cache.items():
        if key in e:
            continue
        px = e['px']; a = [None] * len(px)
        for i in range(lb, len(px)):
            if px[i - lb]:
                a[i] = px[i] / px[i - lb] - 1.0
        e[key] = a
    return key


def run_detail(cache, name, dates, picker, H=20, warm=300, bench_mode='kodex'):
    be = cache[BENCH]
    detail = []
    for off in range(H):
        k = warm + off
        while k + H < len(dates):
            d = dates[k]; dn = dates[k + H]
            bi = be['idx'].get(d); bj = be['idx'].get(dn)
            if bi is None or bj is None:
                k += H; continue
            univ = eligible(cache, name, d)
            if bench_mode == 'basket':
                br = [cache[c]['px'][cache[c]['idx'][dn]] / cache[c]['px'][i] - 1.0
                      for c, i in univ if dn in cache[c]['idx']]
                bench = sum(br) / len(br) if br else 0.0
            else:
                bench = be['px'][bj] / be['px'][bi] - 1.0
            picks = picker(cache, name, d, univ)
            rets = []
            for c in picks:
                e = cache[c]; i = e['idx'][d]; j = e['idx'].get(dn)
                if j is not None:
                    rets.append(e['px'][j] / e['px'][i] - 1.0)
            ex = (sum(rets) / len(rets) - COST - bench) if rets else -bench
            detail.append((d, ex, len(univ)))
            k += H
    detail.sort()
    return detail


def yearly(detail):
    from collections import defaultdict
    y = defaultdict(list)
    for d, ex, n in detail:
        y[d[:4]].append(ex)
    return {k: (sum(v) / len(v) * 100, len(v)) for k, v in sorted(y.items())}


def main():
    cache, name, dates = build()
    print(f'장기표본 {len(cache)}종 · {len(dates)}거래일 ({dates[0]}~{dates[-1]})')
    for lb in (100, 120, 150, 200):
        add_mom(cache, lb)

    print('\n\n########## 룩백 × 보유 (vs KODEX200, 평균 H일 초과 %) ##########')
    print(f'{"룩백":<10}' + ''.join(f'{"H="+str(h):>13}' for h in (10, 20, 40, 60)))
    for lb in (20, 60, 100, 120, 150, 200):
        key = f'mom{lb}'
        line = f'{"mom"+str(lb):<10}'
        for h in (10, 20, 40, 60):
            _, per, allobs = run_h(cache, name, dates, mk_rank(key, True), key,
                                   H=h, warm=max(300, lb + 30))
            s = stat(per, allobs)
            line += f'{s["mean"]:>10.3f}({s["npos"]:>2})'
        print(line)

    print('\n\n########## 연도별 안정성 (H=20, vs KODEX200) ##########')
    for lb in (20, 120, 150):
        det = run_detail(cache, name, dates, mk_rank(f'mom{lb}', True), H=20, warm=300)
        yr = yearly(det)
        print(f'mom{lb:<4} 전체 {sum(x[1] for x in det)/len(det)*100:+.3f}% │ ' +
              '  '.join(f'{k} {v[0]:+.2f}({v[1]})' for k, v in yr.items()))

    print('\n\n########## 벤치마크 교체 (H=20) ##########')
    for lb in (20, 120, 150):
        for bm in ('kodex', 'basket'):
            det = run_detail(cache, name, dates, mk_rank(f'mom{lb}', True),
                             H=20, warm=300, bench_mode=bm)
            m = sum(x[1] for x in det) / len(det) * 100
            win = sum(1 for x in det if x[1] > 0) / len(det) * 100
            print(f'  mom{lb:<4} vs {bm:<7} {m:+.3f}%  승률 {win:.1f}%  관측 {len(det)}')


if __name__ == '__main__':
    main()
