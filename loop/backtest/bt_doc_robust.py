# -*- coding: utf-8 -*-
"""후보 규칙 견고성 검정 — 임계값 스윕 + 오프셋 잭나이프 + 후보수 확인.

대상: (1) 중기 mom150 + 거래대금 증가(M6), (2) 단기 박스권 상단돌파(A12).
스파이크(특정 임계값에서만 좋음)인지 고원(넓은 구간에서 좋음)인지 본다.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doc_engine as E  # noqa: E402

COST = 0.0010
H = 20
WARM_M, WARM_S = 170, 160


def mid_run(cache, name, dates, cond=None, split=None):
    be = cache[E.BENCH]
    mid_k = (WARM_M + len(dates) - H - 1) // 2
    per, allobs, ncand = [], [], []
    for off in range(H):
        obs = []
        k = WARM_M + off
        while k + H < len(dates):
            if split == 'train' and k > mid_k:
                break
            if split == 'test' and k <= mid_k:
                k += H
                continue
            d, dn = dates[k], dates[k + H]
            bi, bj = be['idx'].get(d), be['idx'].get(dn)
            if bi is None or bj is None:
                k += H
                continue
            bench = be['px'][bj] / be['px'][bi] - 1.0
            sc = []
            for c, i in E.eligible(cache, name, d):
                e = cache[c]
                m = e['mom150'][i]
                if m is None or (cond and not cond(e, i)):
                    continue
                sc.append((m, c))
            ncand.append(len(sc))
            rets = []
            for c in E.topn(sc):
                e = cache[c]
                i, j = e['idx'][d], e['idx'].get(dn)
                if j is not None:
                    rets.append(e['px'][j] / e['px'][i] - 1.0)
            obs.append((sum(rets) / len(rets) - COST - bench) if rets else -bench)
            k += H
        if obs:
            per.append(sum(obs) / len(obs))
            allobs += obs
    n = len(per)
    m = sum(per) / n
    var = sum((x - m) ** 2 for x in per) / (n - 1)
    se = math.sqrt(var / n) if var > 0 else 0
    jk = min((sum(per) - x) / (n - 1) for x in per)   # 오프셋 1개 제거 하한
    return dict(mean=m * 100, t=(m / se if se else 0), jk=jk * 100,
                pos=sum(1 for x in per if x > 0), noff=n, lo=min(per) * 100,
                win=sum(1 for x in allobs if x > 0) / len(allobs) * 100,
                cand=sum(ncand) / len(ncand) if ncand else 0)


def short_run(cache, name, dates, cond=None, split=None):
    be = cache[E.BENCH]
    mid_k = (WARM_S + len(dates) - 2) // 2
    obs, ncand = [], []
    for k in range(WARM_S, len(dates) - 1):
        if split == 'train' and k > mid_k:
            break
        if split == 'test' and k <= mid_k:
            continue
        d, dn = dates[k], dates[k + 1]
        bi, bj = be['idx'].get(d), be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        sc = []
        for c, i in E.eligible(cache, name, d):
            e = cache[c]
            m = e['mom20'][i]
            if m is None or not E.rule_h_ok(e, i):
                continue
            if cond and not cond(e, i):
                continue
            sc.append((m, c))
        ncand.append(len(sc))
        rets = []
        for c in E.topn(sc):
            e = cache[c]
            i, j = e['idx'][d], e['idx'].get(dn)
            if j is not None:
                rets.append(e['px'][j] / e['px'][i] - 1.0)
        if rets:
            obs.append(sum(rets) / len(rets) - COST - bench)
    n = len(obs)
    m = sum(obs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in obs) / (n - 1))
    jk = min((sum(obs) - x) / (n - 1) for x in obs)
    return dict(mean=m * 100, t=m / (sd / math.sqrt(n)) if sd else 0,
                jk=jk * 100, n=n,
                win=sum(1 for x in obs if x > 0) / n * 100,
                cand=sum(ncand) / len(ncand) if ncand else 0)


def main():
    cache, name, dates = E.build()

    print('■ 중기 M6 — 거래대금 급증 임계값 스윕 (mom150 상위5)\n')
    print(f'{"임계":<10}{"전체%":>9}{"t":>7}{"train%":>9}{"test%":>9}'
          f'{"오프셋양수":>10}{"오프셋잭나이프%":>15}{"평균후보수":>10}')
    print('-' * 80)
    for th in [None, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0]:
        cond = None if th is None else (
            lambda e, i, t=th: e['amtsurge'][i] is not None and e['amtsurge'][i] >= t)
        a = mid_run(cache, name, dates, cond)
        tr = mid_run(cache, name, dates, cond, 'train')
        te = mid_run(cache, name, dates, cond, 'test')
        lbl = '없음(기준선)' if th is None else f'>={th}'
        print(f'{lbl:<10}{a["mean"]:>9.3f}{a["t"]:>7.2f}{tr["mean"]:>9.3f}'
              f'{te["mean"]:>9.3f}{(str(a["pos"])+"/"+str(a["noff"])):>10}'
              f'{a["jk"]:>15.3f}{a["cand"]:>10.1f}')

    print('\n■ 단기 A12 — 채널위치·거래대금 임계값 스윕 (mom20+RuleH 상위5)\n')
    print(f'{"조건":<22}{"전체%":>10}{"t":>7}{"train%":>9}{"test%":>9}'
          f'{"잭나이프%":>11}{"평균후보수":>10}')
    print('-' * 78)
    combos = [('없음(기준선)', None)]
    for cp in (0.95, 0.98):
        for at in (1.0, 1.2, 1.5):
            combos.append((f'ch>={cp} & amt>={at}',
                           lambda e, i, c=cp, a=at: (
                               e['chpos60'][i] is not None and e['chpos60'][i] >= c
                               and e['amtsurge'][i] is not None
                               and e['amtsurge'][i] >= a)))
    for lbl, cond in combos:
        a = short_run(cache, name, dates, cond)
        tr = short_run(cache, name, dates, cond, 'train')
        te = short_run(cache, name, dates, cond, 'test')
        print(f'{lbl:<22}{a["mean"]:>10.4f}{a["t"]:>7.2f}{tr["mean"]:>9.4f}'
              f'{te["mean"]:>9.4f}{a["jk"]:>11.4f}{a["cand"]:>10.1f}')


if __name__ == '__main__':
    main()
