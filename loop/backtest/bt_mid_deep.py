# -*- coding: utf-8 -*-
"""중기 트랙 심층검증 — mom120(장기모멘텀)이 진짜인지 파고든다.

점검: (1) 룩백×보유 고원, (2) 3분할 시기 안정성, (3) 유니버스 등가중 대비,
      (4) 거래비용 민감도, (5) 테마 집중도.
"""
import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, run_h, stat, show, mk_rank, eligible,
                        rule_h_ok, BENCH, NPICK)


def run_h_detail(cache, name, dates, picker, H=20, warm=140, cost=0.0010,
                 bench_mode='kodex'):
    """오프셋별 평가 + 시점별 상세(날짜·초과수익·픽) 반환."""
    be = cache[BENCH]
    per = []; allobs = []; detail = []
    for off in range(H):
        obs = []
        k = warm + off
        while k + H < len(dates):
            d = dates[k]; dn = dates[k + H]
            bi = be['idx'].get(d); bj = be['idx'].get(dn)
            if bi is None or bj is None:
                k += H; continue
            univ = eligible(cache, name, d)
            if bench_mode == 'basket':
                br = []
                for c, i in univ:
                    e = cache[c]; j = e['idx'].get(dn)
                    if j is not None:
                        br.append(e['px'][j] / e['px'][i] - 1.0)
                bench = sum(br) / len(br) if br else 0.0
            else:
                bench = be['px'][bj] / be['px'][bi] - 1.0
            picks = picker(cache, name, d, univ)
            rets = []
            for c in picks:
                e = cache[c]; i = e['idx'][d]; j = e['idx'].get(dn)
                if j is not None:
                    rets.append(e['px'][j] / e['px'][i] - 1.0)
            ex = (sum(rets) / len(rets) - cost - bench) if rets else -bench
            obs.append(ex); detail.append((d, ex, picks))
            k += H
        if obs:
            per.append(sum(obs) / len(obs)); allobs += obs
    return per, allobs, detail


def main():
    cache, name, dates = build()
    print(f'유니버스 {len(cache)}종 · {dates[0]}~{dates[-1]}')

    print('\n\n########## (1) 룩백 × 보유기간 고원 (평균 H일 초과수익 %, vs KODEX200) ##########')
    print(f'{"룩백":<10}' + ''.join(f'{"H="+str(h):>12}' for h in (5, 10, 20, 40, 60)))
    for lb in (20, 60, 100, 120, 150, 200, 250):
        key = f'mom{lb}'
        if key not in cache[BENCH]:
            # 필요한 룩백 즉석 계산
            for code, e in cache.items():
                px = e['px']; a = [None] * len(px)
                for i in range(lb, len(px)):
                    if px[i - lb]:
                        a[i] = px[i] / px[i - lb] - 1.0
                e[key] = a
        line = f'{"mom"+str(lb):<10}'
        for h in (5, 10, 20, 40, 60):
            _, per, allobs = run_h(cache, name, dates, mk_rank(key, True),
                                   key, H=h, warm=max(140, lb + 20))
            s = stat(per, allobs)
            line += f'{s["mean"]:>9.3f}({s["npos"]:>2})'
        print(line)
    print('괄호 = 오프셋 H개 중 양수 개수')

    print('\n\n########## (2) mom120 / H=20 — 3분할 시기 안정성 ##########')
    for lbl, key in (('BASE mom20', 'mom20'), ('mom120', 'mom120'),
                     ('mom200', 'mom200'), ('mom250', 'mom250')):
        per, allobs, detail = run_h_detail(cache, name, dates,
                                           mk_rank(key, True), H=20, warm=280)
        detail.sort()
        k = len(detail) // 3
        seg = []
        for a, b in ((0, k), (k, 2 * k), (2 * k, len(detail))):
            ex = [x[1] for x in detail[a:b]]
            seg.append(sum(ex) / len(ex) * 100)
        rng = (detail[0][0], detail[k][0], detail[2 * k][0], detail[-1][0])
        print(f'{lbl:<12} 전체 {sum(x[1] for x in detail)/len(detail)*100:+.3f}%  '
              f'│ 1구간 {seg[0]:+.3f}  2구간 {seg[1]:+.3f}  3구간 {seg[2]:+.3f}   '
              f'({rng[0]}~{rng[1]}~{rng[2]}~{rng[3]})')

    print('\n\n########## (3) 벤치마크 교체 — 유니버스 등가중 바스켓 대비 ##########')
    for lbl, key in (('BASE mom20', 'mom20'), ('mom120', 'mom120'), ('mom250', 'mom250')):
        for bm in ('kodex', 'basket'):
            per, allobs, _ = run_h_detail(cache, name, dates, mk_rank(key, True),
                                           H=20, warm=280, bench_mode=bm)
            s = stat(per, allobs)
            print(f'{lbl:<12} vs {bm:<7} {s["mean"]:+.3f}%  t={s["t"]:>6.2f}  '
                  f'오프셋양수 {s["npos"]}/{s["noff"]}  승률 {s["win"]:.1f}%')

    print('\n\n########## (4) 거래비용 민감도 (mom120, H=20) ##########')
    for c in (0.0005, 0.0010, 0.0030, 0.0060):
        per, allobs, _ = run_h_detail(cache, name, dates, mk_rank('mom120', True),
                                       H=20, warm=280, cost=c)
        s = stat(per, allobs)
        print(f'  왕복 {c*10000:>4.0f}bp → {s["mean"]:+.3f}%  t={s["t"]:.2f}  '
              f'오프셋양수 {s["npos"]}/{s["noff"]}')

    print('\n\n########## (5) 테마·종목 집중도 (mom120, H=20) ##########')
    per, allobs, detail = run_h_detail(cache, name, dates, mk_rank('mom120', True),
                                        H=20, warm=280)
    cnt = Counter()
    for d, ex, picks in detail:
        for c in picks:
            cnt[name[c]] += 1
    tot = sum(cnt.values())
    print(f'  총 픽 {tot}회 · 등장 종목 {len(cnt)}종')
    for nm, c in cnt.most_common(12):
        print(f'    {nm:<34}{c:>4}회 ({c/tot*100:>5.1f}%)')
    # 최다 종목 제외 잭나이프
    top = [nm for nm, _ in cnt.most_common(5)]
    for drop in top:
        obs = []
        for d, ex, picks in detail:
            if any(name[c] == drop for c in picks):
                continue
            obs.append(ex)
        if obs:
            print(f'  [{drop} 포함 시점 제외] 남은 {len(obs)}시점 평균 '
                  f'{sum(obs)/len(obs)*100:+.3f}%')


if __name__ == '__main__':
    main()
