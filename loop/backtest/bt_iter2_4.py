# -*- coding: utf-8 -*-
"""2026-07-28 루프 iteration 2~4 — 세 개의 구별되는(distinct) 신규 가설 동시 검증.

배경: 7/27 채점 0/5. 승자는 반도체(9종)·코스닥150(3종)·IT 계열이 상위16위를 독식했고,
추천 5종(은행·고배당 7일 고착)은 +0.68~+1.71%로 컷오프 +1.97%에 전부 미달했다.
iteration 1(Rule XC 실현상관 중복제거)은 full/train/test 전부 baseline 미달로 기각.

iteration 2 — Rule LAG1 (전일 상위10% 승자군 편입)
   기존 Rule N(우리 픽의 모멘텀 지속)·PN1(mom5 상시)과 구별: 모멘텀 '창'이 아니라
   전일 상위10% '컷오프 통과 집합'을 직접 신호로 쓴다(승자 로테이션 1일 지연 추종).

iteration 3 — Rule NMC (종목명 토큰 클러스터 상한)
   기존 Rule Q(사전 정의 섹터 taxonomy)·XC(실현상관)와 구별: ETF 명칭 토큰(은행·고배당·
   반도체 등)으로 클러스터를 만들어 동일 클러스터 최대 k종으로 제한. 7/27 픽 5종은
   taxonomy 라벨은 전부 달랐지만 명칭 토큰은 금융/은행/고배당으로 겹친다.

iteration 4 — Rule MRV (모멘텀 상위 내 전일 역전 우선)
   기존 Rule CC(극단 반전 콤보)와 구별: 반전을 '편입 조건'이 아니라 mom20 상위 N0 풀
   안에서의 '재정렬 키'로만 쓴다(유니버스는 바꾸지 않음).

과최적화 가드: 채택은 1차지표(P&L 초과수익) full·train·test 모두 baseline 초과일 때만.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bt_ruleXC import (  # noqa: E402
    load, rank_candidates, sel_baseline, track, avg, day_hits, is_spot,
    mom, PANEL, CASH_KW,
)

TOKENS = ['은행', '고배당', '금융', '반도체', '조선', '방산', '원자력', '2차전지',
          '바이오', '증권', '건설', '자동차', '로봇', '태양광', '코스닥', 'AI', '금현물']


def cluster_of(nm):
    n = (nm or '').replace(' ', '')
    hits = [t for t in TOKENS if t in n]
    return hits[0] if hits else nm[:4]


# ------------------------------------------------ iteration 2: Rule LAG1
def make_lag1(nwin):
    """전일(D-1→D) 상위10% 승자 집합을 우선 편입, 부족분은 mom20 순."""
    def sel(px, name, d, dates, n=5):
        i = dates.index(d)
        order = rank_candidates(px, name, d, dates)
        win = set()
        if i >= 1:
            dp = dates[i - 1]
            uni = []
            for c in px:
                a, b = px[c].get(dp), px[c].get(d)
                if not a or not b or a < 10000 or not is_spot(name.get(c, '')):
                    continue
                if any(k in (name.get(c, '')).replace(' ', '') for k in CASH_KW):
                    continue
                uni.append((c, b / a - 1.0))
            uni.sort(key=lambda x: -x[1])
            cut = max(1, round(len(uni) * 0.10))
            win = {c for c, _ in uni[:cut]}
        picks = [c for c in order if c in win][:nwin]
        for c in order:
            if len(picks) >= n:
                break
            if c not in picks:
                picks.append(c)
        return picks[:n]
    return sel


# ------------------------------------------------ iteration 3: Rule NMC
def make_nmc(k):
    def sel(px, name, d, dates, n=5):
        order = rank_candidates(px, name, d, dates)
        cnt, picks = {}, []
        for c in order:
            if len(picks) >= n:
                break
            cl = cluster_of(name.get(c, ''))
            if cnt.get(cl, 0) >= k:
                continue
            cnt[cl] = cnt.get(cl, 0) + 1
            picks.append(c)
        for c in order:
            if len(picks) >= n:
                break
            if c not in picks:
                picks.append(c)
        return picks[:n]
    return sel


# ------------------------------------------------ iteration 4: Rule MRV
def make_mrv(pool):
    def sel(px, name, d, dates, n=5):
        order = rank_candidates(px, name, d, dates)[:pool]
        scored = []
        for c in order:
            r1 = mom(px, c, d, dates, 1)
            scored.append((c, r1 if r1 is not None else 0.0))
        scored.sort(key=lambda x: x[1])  # 전일 수익률 낮은 순(역전 우선)
        return [c for c, _ in scored[:n]]
    return sel


def main():
    px, name, dates = load()
    print(f'패널 {os.path.basename(PANEL)} · 거래일 {len(dates)} '
          f'({dates[0]}~{dates[-1]})\n')

    variants = [('baseline mom20+RuleH', sel_baseline)]
    for w in (2, 3):
        variants.append((f'[it2] LAG1 win={w}', make_lag1(w)))
    for k in (1, 2):
        variants.append((f'[it3] NMC cap={k}', make_nmc(k)))
    for p in (10, 15):
        variants.append((f'[it4] MRV pool={p}', make_mrv(p)))

    res = {}
    for lbl, fn in variants:
        ex, hi = track(px, name, dates, fn)
        half, hh = len(ex) // 2, len(hi) // 2
        res[lbl] = {
            'full': avg([v for _, v in ex]),
            'train': avg([v for _, v in ex[:half]]),
            'test': avg([v for _, v in ex[half:]]),
            'win': sum(1 for _, v in ex if v > 0), 'n': len(ex),
            'bfull': avg([v for _, v in hi]),
        }
        r = res[lbl]
        print('%-22s [P&L] 평균 %+.3f%%p | train %+.3f%%p test %+.3f%%p | '
              '이김 %d/%d  [이진] %.3f종'
              % (lbl, r['full'], r['train'], r['test'], r['win'], r['n'], r['bfull']))

    print('\n=== 과최적화 가드 (채택 = full·train·test 모두 baseline 초과) ===')
    b = res['baseline mom20+RuleH']
    passed = []
    for lbl in res:
        if lbl.startswith('baseline'):
            continue
        r = res[lbl]
        m = lambda k: '▲' if r[k] > b[k] else '▼'  # noqa: E731
        ok = all(r[k] > b[k] for k in ('full', 'train', 'test'))
        if ok:
            passed.append(lbl)
        print('%-22s full %s train %s test %s | 이진 %.3f -> %.3f | %s'
              % (lbl, m('full'), m('train'), m('test'),
                 b['bfull'], r['bfull'], '통과' if ok else '미통과'))
    print('\n가드 통과:', passed or '없음 — 전부 기각, 확정방법 유지')


if __name__ == '__main__':
    main()
