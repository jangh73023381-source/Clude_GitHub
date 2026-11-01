# -*- coding: utf-8 -*-
"""mom120(장기모멘텀) 최종 견고성 — 벤치마크·테마제외·표본기간 대조.

PANEL_FILE 환경변수로 2년/장기 패널을 바꿔가며 같은 검정을 돌린다.
"""
import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, mk_rank, eligible, BENCH, COST, NPICK)


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


def detail(cache, name, dates, picker, H=20, warm=300, bench_mode='kodex',
           exclude_kw=None):
    be = cache[BENCH]
    out = []
    for off in range(H):
        k = warm + off
        while k + H < len(dates):
            d = dates[k]; dn = dates[k + H]
            bi = be['idx'].get(d); bj = be['idx'].get(dn)
            if bi is None or bj is None:
                k += H; continue
            univ = eligible(cache, name, d)
            if exclude_kw:
                univ = [(c, i) for c, i in univ
                        if not any(w in name[c] for w in exclude_kw)]
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
            out.append((d, ex, picks))
            k += H
    out.sort()
    return out


def summ(det):
    ex = [x[1] for x in det]
    m = sum(ex) / len(ex) * 100
    win = sum(1 for x in ex if x > 0) / len(ex) * 100
    return m, win, len(ex)


def main():
    panel = os.environ.get('PANEL_FILE', 'panel_ohlc_2y.csv')
    cache, name, dates = build()
    warm = 300 if 'long' in panel else 160
    print(f'패널 {panel} · {len(cache)}종 · {len(dates)}일 ({dates[0]}~{dates[-1]}) warm={warm}')
    for lb in (120, 150):
        add_mom(cache, lb)

    print('\n### 벤치마크 대조 (H=20) ###')
    for lb in (20, 120, 150):
        for bm in ('kodex', 'basket'):
            m, w, n = summ(detail(cache, name, dates, mk_rank(f'mom{lb}', True),
                                  H=20, warm=warm, bench_mode=bm))
            print(f'  mom{lb:<4} vs {bm:<7} {m:+.3f}%  승률 {w:.1f}%  관측 {n}')

    print('\n### 테마 제외 견고성 (mom120, H=20, vs KODEX200) ###')
    tests = [
        (None, '전체'),
        (['반도체', 'HBM', 'AI반도체', '비메모리', '전공정'], '반도체 계열 제외'),
        (['방산', '우주'], '방산 계열 제외'),
        (['원자력', '원전'], '원자력 계열 제외'),
        (['반도체', 'HBM', 'AI반도체', '비메모리', '전공정', '방산', '우주',
          '원자력', '원전'], '반도체+방산+원자력 전부 제외'),
    ]
    for kw, lbl in tests:
        m, w, n = summ(detail(cache, name, dates, mk_rank('mom120', True),
                              H=20, warm=warm, exclude_kw=kw))
        print(f'  {lbl:<26}{m:+.3f}%  승률 {w:.1f}%  관측 {n}')

    print('\n### 연도별 (mom120, H=20, vs KODEX200) ###')
    det = detail(cache, name, dates, mk_rank('mom120', True), H=20, warm=warm)
    y = defaultdict(list)
    for d, ex, p in det:
        y[d[:4]].append(ex)
    for k in sorted(y):
        v = y[k]
        print(f'  {k}  {sum(v)/len(v)*100:+.3f}%  ({len(v)}관측, '
              f'승률 {sum(1 for x in v if x>0)/len(v)*100:.0f}%)')

    print('\n### 픽 집중도 (mom120, H=20) ###')
    cnt = Counter()
    for d, ex, picks in det:
        for c in picks:
            cnt[name[c]] += 1
    tot = sum(cnt.values())
    print(f'  총 {tot}회 · {len(cnt)}종 · 상위5종 점유 '
          f'{sum(c for _, c in cnt.most_common(5))/tot*100:.1f}%')
    for nm, c in cnt.most_common(8):
        print(f'    {nm:<32}{c:>5}회 ({c/tot*100:>5.1f}%)')


if __name__ == '__main__':
    main()
