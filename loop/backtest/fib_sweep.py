# -*- coding: utf-8 -*-
"""3단계 — 최적 피보나치 지점 탐색.

되돌림 비율(retr)을 구간으로 나눠 익일 초과수익(vs KODEX200) 분포를 본다.
표준오차는 일자 클러스터(같은 날 종목 간 상관 흡수) 기준.
"""
import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fib_engine import (load, fib_state, is_excluded, is_cashlike,
                        date_clustered_t, jackknife_low, BENCH, FIB_LEVELS)

MINP = 10000
LOOKBACKS = [20, 40, 60, 120]
HOLD = 1     # 익일 종가 청산


def build_obs(P, L, hold=1):
    """(date, code, regime, retr, chpos, amp, excess) 관측 생성. 룩어헤드 없음."""
    ds = P['dates']; c = P['c']; nm = P['name']
    obs = []
    for i in range(L - 1, len(ds) - hold):
        d = ds[i]; dn = ds[i + hold]
        bp = c[BENCH].get(d); bn = c[BENCH].get(dn)
        if not bp or not bn:
            continue
        bench = bn / bp - 1.0
        for code in c:
            name = nm[code]
            if is_excluded(name) or is_cashlike(name):
                continue
            p = c[code].get(d); pn = c[code].get(dn)
            if not p or not pn or p < MINP:
                continue
            st = fib_state(P, code, i, L)
            if st is None:
                continue
            regime, retr, chpos, H, Lo, C, amp = st
            obs.append((d, code, regime, retr, chpos, amp, pn / p - 1.0 - bench))
    return obs


def bucket_report(obs, key_fn, labels, title):
    by = defaultdict(lambda: defaultdict(list))   # label -> date -> [excess]
    for d, code, regime, retr, chpos, amp, ex in obs:
        lab = key_fn(regime, retr, chpos, amp)
        if lab is None:
            continue
        by[lab][d].append(ex)
    rows = []
    for lab in labels:
        if lab not in by:
            continue
        dd = by[lab]
        daily = [sum(v) / len(v) for v in dd.values()]
        n_obs = sum(len(v) for v in dd.values())
        m, t, ndays = date_clustered_t(daily)
        jk = jackknife_low(daily)
        wins = sum(1 for v in dd.values() for x in v if x > 0)
        rows.append((lab, n_obs, ndays, m, t, jk, wins / n_obs if n_obs else None))
    print(f'\n=== {title} ===')
    print(f'{"구간":<18}{"관측":>7}{"일수":>6}{"평균초과%":>11}{"t":>8}{"잭나이프하한%":>13}{"승률%":>8}')
    for lab, n, nd, m, t, jk, wr in rows:
        print(f'{lab:<18}{n:>7}{nd:>6}{m*100:>11.4f}{(t if t else 0):>8.2f}'
              f'{(jk*100 if jk is not None else 0):>13.4f}{wr*100:>8.1f}')
    return rows


def main():
    P = load()
    print(f'유니버스 {len(P["name"])}종 / 거래일 {len(P["dates"])}일 '
          f'({P["dates"][0]}~{P["dates"][-1]})')

    for L in LOOKBACKS:
        obs = build_obs(P, L)
        print(f'\n\n############ 룩백 L={L}거래일 · 관측 {len(obs):,}건 ############')

        # (1) 방향별 되돌림 10분위
        for reg in ('UP', 'DOWN'):
            edges = [round(x * 0.1, 1) for x in range(11)]
            labels = [f'{reg} {edges[i]:.1f}~{edges[i+1]:.1f}' for i in range(10)]

            def kf(regime, retr, chpos, amp, _reg=reg, _e=edges):
                if regime != _reg:
                    return None
                for i in range(10):
                    if _e[i] <= retr < _e[i + 1] or (i == 9 and retr >= 1.0):
                        return f'{_reg} {_e[i]:.1f}~{_e[i+1]:.1f}'
                return None
            bucket_report(obs, kf, labels,
                          f'L={L} · {reg} 국면 되돌림 10분위 (익일 초과수익)')

        # (2) 피보나치 레벨 ±0.03 근접 밴드
        for reg in ('UP', 'DOWN'):
            labels = [f'{reg} fib{lv}' for lv in FIB_LEVELS]

            def kf2(regime, retr, chpos, amp, _reg=reg):
                if regime != _reg:
                    return None
                for lv in FIB_LEVELS:
                    if abs(retr - lv) <= 0.03:
                        return f'{_reg} fib{lv}'
                return None
            bucket_report(obs, kf2, labels,
                          f'L={L} · {reg} 국면 피보나치 레벨 ±0.03 밴드')


if __name__ == '__main__':
    main()
