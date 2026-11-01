# -*- coding: utf-8 -*-
"""3단계-2 — 유니버스 기준선 대비 재표현 + '지지 확인형' 변형 + 보유기간 스윕.

fib_sweep.py의 모든 수치가 음수인 이유는 대상 기간(2024-02~2026-07) 동안
등가중 ETF 유니버스 자체가 KODEX200에 뒤졌기 때문이다. 따라서 여기서는
그날 유니버스 등가중 평균을 기준선으로 삼아 '선정 우위'만 분리해서 본다.
"""
import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fib_engine import (load, fib_state, is_excluded, is_cashlike,
                        date_clustered_t, jackknife_low, BENCH, FIB_LEVELS)

MINP = 10000
HOLDS = [1, 2, 3, 5]


def build(P, L, hold):
    """관측 생성: (date, code, regime, retr, touched_lv, held_lv, ret, bench)"""
    ds = P['dates']; c = P['c']; lo = P['l']; nm = P['name']
    out = []
    for i in range(L - 1, len(ds) - hold):
        d = ds[i]; dn = ds[i + hold]
        bp = c[BENCH].get(d); bn = c[BENCH].get(dn)
        if not bp or not bn:
            continue
        bench = (bn / bp) ** (1.0 / hold) - 1.0     # 1일 환산
        for code in c:
            name = nm[code]
            if is_excluded(name) or is_cashlike(name):
                continue
            p = c[code].get(d); pn = c[code].get(dn)
            dlow = lo[code].get(d)
            if not p or not pn or p < MINP or not dlow:
                continue
            st = fib_state(P, code, i, L)
            if st is None:
                continue
            regime, retr, chpos, H, Lo, C, amp = st
            rng = H - Lo
            # 각 피보나치 레벨의 가격. UP국면 되돌림은 고점에서 아래로.
            touch = {}
            for lv in FIB_LEVELS:
                plv = (H - lv * rng) if regime == 'UP' else (Lo + lv * rng)
                # 당일 저가가 레벨을 찍고(터치) 종가가 레벨 위에서 마감(지지 확인)
                touch[lv] = (dlow <= plv <= C * 1.0)
            r = (pn / p) ** (1.0 / hold) - 1.0
            out.append((d, code, regime, retr, touch, r - bench))
    return out


def report(obs, key_fn, labels, title, baseline_daily):
    by = defaultdict(lambda: defaultdict(list))
    for d, code, regime, retr, touch, ex in obs:
        lab = key_fn(regime, retr, touch)
        if lab is None:
            continue
        by[lab][d].append(ex)
    print(f'\n=== {title} ===')
    print(f'{"구간":<22}{"관측":>7}{"일수":>6}{"vsKODEX%":>10}{"vs유니버스%":>12}'
          f'{"t(유니)":>8}{"잭나이프%":>10}{"승률%":>7}')
    rows = []
    for lab in labels:
        if lab not in by:
            continue
        dd = by[lab]
        daily_abs = {d: sum(v) / len(v) for d, v in dd.items()}
        rel = [daily_abs[d] - baseline_daily[d] for d in daily_abs if d in baseline_daily]
        n_obs = sum(len(v) for v in dd.values())
        m_abs, _, _ = date_clustered_t(list(daily_abs.values()))
        m_rel, t_rel, nd = date_clustered_t(rel)
        jk = jackknife_low(rel)
        wins = sum(1 for d, v in dd.items() for x in v
                   if x - baseline_daily.get(d, 0) > 0)
        print(f'{lab:<22}{n_obs:>7}{nd:>6}{m_abs*100:>10.4f}{m_rel*100:>12.4f}'
              f'{(t_rel or 0):>8.2f}{(jk*100 if jk is not None else 0):>10.4f}'
              f'{wins/n_obs*100:>7.1f}')
        rows.append((lab, n_obs, nd, m_abs, m_rel, t_rel, jk, wins / n_obs))
    return rows


def main():
    P = load()
    for L in (20, 60):
        for hold in HOLDS:
            obs = build(P, L, hold)
            # 유니버스 등가중 기준선 (같은 날, 같은 필터)
            base = defaultdict(list)
            for d, code, regime, retr, touch, ex in obs:
                base[d].append(ex)
            baseline_daily = {d: sum(v) / len(v) for d, v in base.items()}
            m_b, t_b, nd_b = date_clustered_t(list(baseline_daily.values()))
            print(f'\n\n######## L={L} · 보유 {hold}일(1일환산) · 관측 {len(obs):,} ########')
            print(f'유니버스 등가중 기준선: vs KODEX200 {m_b*100:+.4f}%/일 (t={t_b:.2f}, {nd_b}일)')

            # 되돌림 5분위 (UP)
            edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
            labels = [f'UP {edges[i]:.1f}~{edges[i+1]:.1f}' for i in range(5)]

            def kf(regime, retr, touch, _e=edges):
                if regime != 'UP':
                    return None
                for i in range(5):
                    if _e[i] <= retr < _e[i + 1]:
                        return f'UP {_e[i]:.1f}~{_e[i+1]:.1f}'
                return None
            report(obs, kf, labels, f'L={L} h={hold} UP 되돌림 5분위', baseline_daily)

            # 피보나치 밴드 (UP/DOWN)
            for reg in ('UP', 'DOWN'):
                labels = [f'{reg} fib{lv}' for lv in FIB_LEVELS]

                def kf2(regime, retr, touch, _r=reg):
                    if regime != _r:
                        return None
                    for lv in FIB_LEVELS:
                        if abs(retr - lv) <= 0.03:
                            return f'{_r} fib{lv}'
                    return None
                report(obs, kf2, labels, f'L={L} h={hold} {reg} 피보나치 ±0.03 밴드',
                       baseline_daily)

            # 지지 확인형: 당일 저가가 레벨 터치 + 종가가 레벨 위 마감
            for reg in ('UP', 'DOWN'):
                labels = [f'{reg} touch{lv}' for lv in FIB_LEVELS]

                def kf3(regime, retr, touch, _r=reg):
                    if regime != _r:
                        return None
                    for lv in FIB_LEVELS:
                        if touch.get(lv):
                            return f'{_r} touch{lv}'
                    return None
                report(obs, kf3, labels, f'L={L} h={hold} {reg} 레벨 지지확인(터치후 위마감)',
                       baseline_daily)


if __name__ == '__main__':
    main()
