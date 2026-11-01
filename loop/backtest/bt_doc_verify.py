# -*- coding: utf-8 -*-
"""검증 — (1) 손절폭 곡선 + 갭하락 현실화, (2) 중기 후보 train/test 분할.

손절 체결 현실화: 시가가 이미 손절선 아래면 손절가가 아니라 **시가**에 체결된다.
장중 저가만 보고 -stop 에 체결됐다고 가정하면 갭하락 손실을 과소평가한다.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doc_engine as E  # noqa: E402

COST = 0.0010
WARM_S, WARM_M = 160, 170
H = 20


def short_picks(cache, name, d, univ):
    sc = []
    for c, i in univ:
        e = cache[c]
        m = e['mom20'][i]
        if m is not None and E.rule_h_ok(e, i):
            sc.append((m, c))
    return E.topn(sc)


def short_run(cache, name, dates, stop=None, realistic=True):
    be = cache[E.BENCH]
    obs, nstop = [], 0
    for k in range(WARM_S, len(dates) - 1):
        d, dn = dates[k], dates[k + 1]
        bi, bj = be['idx'].get(d), be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        rets = []
        for c in short_picks(cache, name, d, E.eligible(cache, name, d)):
            e = cache[c]
            i, j = e['idx'][d], e['idx'].get(dn)
            if j is None:
                continue
            ent = e['px'][i]
            r = e['px'][j] / ent - 1.0
            if stop is not None:
                trig = ent * (1 - stop)
                if e['lo'][j] <= trig:
                    nstop += 1
                    if realistic and e['op'][j] <= trig:
                        r = e['op'][j] / ent - 1.0     # 갭하락 → 시가 체결
                    else:
                        r = -stop
            rets.append(r)
        if rets:
            obs.append(sum(rets) / len(rets) - COST - bench)
    return obs, nstop


def s1(v):
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    t = m / (sd / math.sqrt(n)) if sd else 0
    half = n // 2
    jk = min((sum(v) - x) / (n - 1) for x in v)
    win = sum(1 for x in v if x > 0) / n * 100
    return m * 100, t, win, sum(v[:half]) / half * 100, \
        sum(v[half:]) / (n - half) * 100, jk * 100, n


def mid_run(cache, name, dates, cond=None, split=None):
    """split: None=전체, 'train'=앞 절반, 'test'=뒤 절반 (선정일 기준)."""
    be = cache[E.BENCH]
    lo_k, hi_k = WARM_M, len(dates) - H - 1
    mid = (lo_k + hi_k) // 2
    per, allobs = [], []
    for off in range(H):
        obs = []
        k = WARM_M + off
        while k + H < len(dates):
            if split == 'train' and k > mid:
                break
            if split == 'test' and k <= mid:
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
    return dict(mean=m * 100, t=(m / se if se else 0),
                pos=sum(1 for x in per if x > 0), noff=n,
                lo=min(per) * 100, nobs=len(allobs),
                win=sum(1 for x in allobs if x > 0) / len(allobs) * 100)


def c_above150(e, i):
    m = e['ma150'][i]
    return m is not None and e['px'][i] > m


def c_flow20(e, i):
    f = e['for20'][i]
    return f is not None and f > 0


def c_amt(e, i):
    a = e['amtsurge'][i]
    return a is not None and a >= 1.0


def main():
    cache, name, dates = E.build()

    print('■ 단기 손절폭 곡선 (갭하락 시 시가 체결 — 현실화)\n')
    print(f'{"손절폭":<12}{"평균초과%":>10}{"t":>7}{"승률%":>7}{"train%":>9}'
          f'{"test%":>9}{"잭나이프%":>11}{"손절발동":>9}')
    print('-' * 76)
    for s in [None, 0.010, 0.015, 0.020, 0.025, 0.030, 0.040, 0.050, 0.070]:
        obs, ns = short_run(cache, name, dates, s, realistic=True)
        m, t, w, tr, te, jk, n = s1(obs)
        lbl = '없음' if s is None else f'-{s*100:.1f}%'
        print(f'{lbl:<12}{m:>10.4f}{t:>7.2f}{w:>7.1f}{tr:>9.4f}{te:>9.4f}'
              f'{jk:>11.4f}{ns:>9}')

    print('\n■ 낙관적 가정(항상 -stop 체결) 대비 — 갭하락 과소평가 폭 확인\n')
    for s in [0.020, 0.030]:
        o1, _ = short_run(cache, name, dates, s, realistic=False)
        o2, _ = short_run(cache, name, dates, s, realistic=True)
        print(f'  -{s*100:.0f}% : 낙관 {sum(o1)/len(o1)*100:+.4f}%  '
              f'현실 {sum(o2)/len(o2)*100:+.4f}%  '
              f'차이 {(sum(o1)-sum(o2))/len(o1)*100:+.4f}%p')

    print('\n■ 중기 후보 train/test 분할 (선정일 앞·뒤 절반)\n')
    print(f'{"규칙":<26}{"전체%":>9}{"t":>7}{"train%":>9}{"test%":>9}'
          f'{"오프셋양수":>10}{"최저%":>9}')
    print('-' * 74)
    for lbl, cond in [('M0 기준선 mom150', None),
                      ('M1 +150일선 위', c_above150),
                      ('M6 +거래대금 증가', c_amt),
                      ('M4 +외국인20일 순매수', c_flow20),
                      ('M11 +150선위 & 수급',
                       lambda e, i: c_above150(e, i) and c_flow20(e, i))]:
        a = mid_run(cache, name, dates, cond)
        tr = mid_run(cache, name, dates, cond, 'train')
        te = mid_run(cache, name, dates, cond, 'test')
        print(f'{lbl:<26}{a["mean"]:>9.3f}{a["t"]:>7.2f}{tr["mean"]:>9.3f}'
              f'{te["mean"]:>9.3f}{(str(a["pos"])+"/"+str(a["noff"])):>10}'
              f'{a["lo"]:>9.3f}')


if __name__ == '__main__':
    main()
