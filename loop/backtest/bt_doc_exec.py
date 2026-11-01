# -*- coding: utf-8 -*-
"""집행 레이어 — 문서의 손절·청산 규칙 검정.

문서 근거: 「-3~-5% 또는 지지선 이탈 시 즉시 손절」(주식매매기법_2026 4절),
「20일선 이탈 + 거래량 증가 시 스윙 포지션 청산 우선」(조사보고서 12절 표),
「예상보다 빠른 급등은 일부 익절 후 추세 추종」(같은 표).

선정 로직은 건드리지 않는다 — 확정 픽(단기 mom20+RuleH / 중기 mom150)에
청산 규칙만 덧씌워 KODEX200 대비 초과수익을 비교한다.
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


# ---------------- 단기(1일 보유) 손절 ----------------

def short_picks(cache, name, d, univ):
    sc = []
    for c, i in univ:
        e = cache[c]
        m = e['mom20'][i]
        if m is not None and E.rule_h_ok(e, i):
            sc.append((m, c))
    return E.topn(sc)


def short_run(cache, name, dates, stop=None, take=None):
    """익일 종가 청산. stop: 장중 저가가 -stop 이하면 -stop 에 손절.
    take: 장중 고가가 +take 이상이면 +take 에 익절."""
    be = cache[E.BENCH]
    obs = []
    for k in range(WARM_S, len(dates) - 1):
        d, dn = dates[k], dates[k + 1]
        bi, bj = be['idx'].get(d), be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        rets = []
        for c in short_picks(cache, name, d, E.eligible(cache, name, d)):
            e = cache[c]
            i = e['idx'][d]
            j = e['idx'].get(dn)
            if j is None:
                continue
            ent = e['px'][i]
            r = e['px'][j] / ent - 1.0
            if stop is not None and e['lo'][j] / ent - 1.0 <= -stop:
                r = -stop
            elif take is not None and e['hi'][j] / ent - 1.0 >= take:
                r = take
            rets.append(r)
        if rets:
            obs.append(sum(rets) / len(rets) - COST - bench)
    return obs


# ---------------- 중기(20일 보유) 청산 ----------------

def mid_picks(cache, name, d, univ):
    sc = []
    for c, i in univ:
        m = cache[c]['mom150'][i]
        if m is not None:
            sc.append((m, c))
    return E.topn(sc)


def mid_path(e, i, hold, stop=None, exit_ma=None):
    """진입 i(종가) → 최대 hold 일 보유. 조기청산 규칙 적용 후 실현수익률."""
    ent = e['px'][i]
    end = min(i + hold, len(e['px']) - 1)
    for j in range(i + 1, end + 1):
        if stop is not None and e['lo'][j] / ent - 1.0 <= -stop:
            return -stop
        if exit_ma is not None:
            m = e[f'ma{exit_ma}'][j]
            if m is not None and e['px'][j] < m:
                return e['px'][j] / ent - 1.0      # 종가 이탈 확인 후 청산
    return e['px'][end] / ent - 1.0


def mid_run(cache, name, dates, stop=None, exit_ma=None):
    be = cache[E.BENCH]
    per, allobs = [], []
    for off in range(H):
        obs = []
        k = WARM_M + off
        while k + H < len(dates):
            d, dn = dates[k], dates[k + H]
            bi, bj = be['idx'].get(d), be['idx'].get(dn)
            if bi is None or bj is None:
                k += H
                continue
            bench = be['px'][bj] / be['px'][bi] - 1.0
            rets = []
            for c in mid_picks(cache, name, d, E.eligible(cache, name, d)):
                e = cache[c]
                i = e['idx'][d]
                if i + H < len(e['px']):
                    rets.append(mid_path(e, i, H, stop, exit_ma))
            obs.append((sum(rets) / len(rets) - COST - bench) if rets else -bench)
            k += H
        if obs:
            per.append(sum(obs) / len(obs))
            allobs += obs
    return per, allobs


def s1(v):
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    t = m / (sd / math.sqrt(n)) if sd else 0
    win = sum(1 for x in v if x > 0) / n * 100
    half = n // 2
    jk = min((sum(v) - x) / (n - 1) for x in v)
    return (m * 100, t, win, sum(v[:half]) / half * 100,
            sum(v[half:]) / (n - half) * 100, jk * 100, n)


def main():
    cache, name, dates = E.build()
    print('■ 단기(1일 보유) — 확정 픽 mom20+RuleH 에 손절·익절만 추가\n')
    print(f'{"집행안":<26}{"평균초과%":>10}{"t":>7}{"승률%":>7}{"train%":>9}'
          f'{"test%":>9}{"잭나이프%":>11}{"일수":>6}')
    print('-' * 88)
    for lbl, kw in [('S0 청산규칙 없음(현행)', {}),
                    ('S1 손절 -3%', {'stop': 0.03}),
                    ('S2 손절 -5%', {'stop': 0.05}),
                    ('S3 손절 -2%', {'stop': 0.02}),
                    ('S4 익절 +3%', {'take': 0.03}),
                    ('S5 손절-3% 익절+3%', {'stop': 0.03, 'take': 0.03}),
                    ('S6 손절-5% 익절+5%', {'stop': 0.05, 'take': 0.05})]:
        m, t, w, tr, te, jk, n = s1(short_run(cache, name, dates, **kw))
        print(f'{lbl:<26}{m:>10.4f}{t:>7.2f}{w:>7.1f}{tr:>9.4f}{te:>9.4f}'
              f'{jk:>11.4f}{n:>6}')

    print('\n■ 중기(최대 20일 보유) — 확정 픽 mom150 에 청산규칙만 추가\n')
    print(f'{"집행안":<26}{"평균 H일초과%":>13}{"t(오프셋)":>10}{"승률%":>7}'
          f'{"오프셋양수":>10}{"최저%":>9}{"관측":>7}')
    print('-' * 84)
    for lbl, kw in [('M0 만기청산(현행)', {}),
                    ('M1 손절 -5%', {'stop': 0.05}),
                    ('M2 손절 -8%', {'stop': 0.08}),
                    ('M3 손절 -10%', {'stop': 0.10}),
                    ('M4 20일선 이탈 청산', {'exit_ma': 20}),
                    ('M5 5일선 이탈 청산', {'exit_ma': 5}),
                    ('M6 60일선 이탈 청산', {'exit_ma': 60}),
                    ('M7 20일선이탈+손절8%', {'exit_ma': 20, 'stop': 0.08})]:
        per, allobs = mid_run(cache, name, dates, **kw)
        n = len(per)
        m = sum(per) / n
        var = sum((x - m) ** 2 for x in per) / (n - 1)
        se = math.sqrt(var / n) if var > 0 else 0
        t = m / se if se else 0
        win = sum(1 for x in allobs if x > 0) / len(allobs) * 100
        pos = sum(1 for x in per if x > 0)
        print(f'{lbl:<26}{m*100:>13.3f}{t:>10.2f}{win:>7.1f}'
              f'{(str(pos)+"/"+str(n)):>10}{min(per)*100:>9.3f}{len(allobs):>7}')


if __name__ == '__main__':
    main()
