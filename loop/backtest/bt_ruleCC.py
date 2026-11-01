# -*- coding: utf-8 -*-
"""Rule CC — 극단 반전 콤보: mom20 하위25%(20일 최대낙폭군) 이면서 D일 단일세션 수익률 상위25%
(직전 크래시 후 당일 강반등)인 종목을 우선 편입. 룩어헤드 금지(D종가까지 정보만).
신규 distinct 가설(2026-07-15 루프 도출) — 기존 N1(단일 mom1 랭킹)·N4(mom1>0&mom5>0)·
Rule Y(D일<-2% 제외, 반대방향)와 구별: '심한 20일 낙폭 + 당일 강반등'의 교집합만 표적."""
import csv, math
from collections import defaultdict

BASE = '/sessions/hopeful-affectionate-cerf/mnt/loop'
BENCH = '069500'

def load():
    px = defaultdict(dict); name = {}
    with open(BASE + '/backtest/panel_close_0715.csv', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            c = r['code']
            try:
                px[c][r['date']] = float(r['close'])
            except (ValueError, KeyError):
                continue
            name[c] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, name, dates

def is_short(nm):
    return '숏' in (nm or '').replace(' ', '')

def is_spot(nm):
    n = (nm or '').replace(' ', '')
    return not ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n or '숏' in n)

def universe(px, name, d, dnext, minp=10000):
    u = []
    for c in px:
        if is_short(name.get(c, '')):
            continue
        pc = px[c].get(d); nc = px[c].get(dnext)
        if pc and nc and pc >= minp:
            u.append((c, pc, nc, nc / pc - 1.0))
    return u

def score(px, name, d, dnext, picks):
    u = universe(px, name, d, dnext)
    if not u:
        return None
    u.sort(key=lambda x: x[3], reverse=True)
    N = len(u); cutoff = max(1, math.ceil(N * 0.10))
    rank = {c: i + 1 for i, (c, _, _, _) in enumerate(u)}
    ret = {c: r for c, _, _, r in u}
    bench = ret.get(BENCH, 0.0)
    hit = 0; pcts = []; exrs = []
    for c in picks:
        if c in rank:
            rk = rank[c]
            hit += 1 if rk <= cutoff else 0
            pcts.append((rk - 1) / N * 100); exrs.append(ret[c] - bench)
    return {'N': N, 'cutoff': cutoff, 'hit': hit, 'npick': len(picks),
            'avg_pct': sum(pcts) / len(pcts) if pcts else None,
            'avg_excess': sum(exrs) / len(exrs) if exrs else None}

def mom20(px, c, d, dates, k=20):
    i = dates.index(d)
    if i < k:
        return None
    d0 = dates[i - k]
    a = px[c].get(d0); b = px[c].get(d)
    return (b / a - 1.0) if (a and b) else None

def single_session_ret(px, c, d, dates):
    i = dates.index(d)
    if i < 1:
        return None
    d0 = dates[i - 1]
    a = px[c].get(d0); b = px[c].get(d)
    return (b / a - 1.0) if (a and b) else None

def cum3(px, c, d, dates):
    i = dates.index(d)
    if i < 3:
        return None
    d0 = dates[i - 3]
    a = px[c].get(d0); b = px[c].get(d)
    return (b / a - 1.0) if (a and b) else None

def rule_h_ok(px, c, d, dates):
    s = single_session_ret(px, c, d, dates)
    c3 = cum3(px, c, d, dates)
    if s is not None and s > 0.10:
        return False
    if c3 is not None and c3 > 0.20:
        return False
    return True

def candidate_pool(px, name, d, dates, minp=10000, pool_n=15):
    cand = []
    for c in px:
        pc = px[c].get(d)
        if not pc or pc < minp or not is_spot(name.get(c, '')):
            continue
        m = mom20(px, c, d, dates)
        if m is None:
            continue
        if not rule_h_ok(px, c, d, dates):
            continue
        cand.append((c, m))
    cand.sort(key=lambda x: x[1], reverse=True)
    return cand[:pool_n]

def sel_baseline(px, name, d, dates, n=5):
    pool = candidate_pool(px, name, d, dates, pool_n=n)
    return [c for c, _ in pool]

def sel_ruleCC(px, name, d, dates, n=5, mom20_q=0.25, mom1_q=0.75, minp=10000):
    """전체 후보(현물·10000원↑) 중 mom20 하위 mom20_q 분위, D일 단일세션수익률 상위(1-mom1_q) 분위
    둘 다 만족하는 종목을 D일 단일세션수익률 내림차순으로 n개 선정. RuleH는 적용하지 않음(반등 당일
    스파이크 자체가 선정 신호이므로 이중과열필터와 상충 — 이 규칙 고유의 설계)."""
    cand = []
    for c in px:
        pc = px[c].get(d)
        if not pc or pc < minp or not is_spot(name.get(c, '')):
            continue
        m20 = mom20(px, c, d, dates)
        s1 = single_session_ret(px, c, d, dates)
        if m20 is None or s1 is None:
            continue
        cand.append((c, m20, s1))
    if not cand:
        return []
    m20s = sorted(x[1] for x in cand)
    s1s = sorted(x[2] for x in cand)
    n_c = len(cand)
    m20_cut = m20s[int(n_c * mom20_q)] if n_c > 4 else m20s[0]
    s1_cut = s1s[int(n_c * mom1_q)] if n_c > 4 else s1s[-1]
    elig = [(c, m20, s1) for c, m20, s1 in cand if m20 <= m20_cut and s1 >= s1_cut]
    elig.sort(key=lambda x: x[2], reverse=True)
    picks = [c for c, _, _ in elig[:n]]
    if len(picks) < n:
        # fill remaining slots from baseline mom20 pool (avoid duplicates)
        pool = candidate_pool(px, name, d, dates, pool_n=n + 10)
        for c, _ in pool:
            if c not in picks:
                picks.append(c)
            if len(picks) >= n:
                break
    return picks[:n]

def main():
    px, name, dates = load()
    print('codes', len(px), 'days', len(dates), dates[0], '~', dates[-1])
    results = []
    for i in range(21, len(dates) - 1):
        d = dates[i]; dnext = dates[i + 1]
        base = sel_baseline(px, name, d, dates)
        cc = sel_ruleCC(px, name, d, dates)
        sb = score(px, name, d, dnext, base)
        scc = score(px, name, d, dnext, cc)
        if sb is None or scc is None:
            continue
        results.append((d, dnext, base, cc, sb, scc))

    n = len(results)
    print(f'\n총 {n}개 결정일 백테스트')
    avg_b = sum(r[4]['hit'] for r in results) / n
    avg_cc = sum(r[5]['hit'] for r in results) / n
    print(f'전체 평균 적중수(5종 중): baseline={avg_b:.3f}  RuleCC={avg_cc:.3f}')

    changed = [r for r in results if set(r[2]) != set(r[3])]
    print(f'\nRuleCC가 baseline과 다른 picks를 낸 날: {len(changed)}일')
    if changed:
        bb = sum(r[4]['hit'] for r in changed) / len(changed)
        cc_ = sum(r[5]['hit'] for r in changed) / len(changed)
        print(f'  발동일 한정 평균적중: baseline={bb:.3f}  RuleCC={cc_:.3f}')

    half = n // 2
    tr, te = results[:half], results[half:]
    for label, seg in [('train', tr), ('test', te)]:
        bb = sum(r[4]['hit'] for r in seg) / len(seg)
        cc_ = sum(r[5]['hit'] for r in seg) / len(seg)
        print(f'{label}: baseline={bb:.3f} RuleCC={cc_:.3f} (n={len(seg)})')

    print('\n--- 오늘(D=7/14->7/15) 상세 ---')
    for r in results:
        if r[0] == '20260714':
            d, dnext, base, cc, sb, scc = r
            print('baseline picks:', base, '-> hit', sb['hit'], sb)
            print('RuleCC picks:', cc, '-> hit', scc['hit'], scc)

    print('\n--- 발동일(픽 변경) 목록 ---')
    for r in changed:
        print(r[0], '->', r[1], 'base_hit', r[4]['hit'], 'cc_hit', r[5]['hit'])

if __name__ == '__main__':
    main()

# ==== Rule EE: 지수(069500) 3일 누적 급락 레짐 감지 시 mom20→mom5 전환 ====
def mom_k(px, c, d, dates, k):
    i = dates.index(d)
    if i < k:
        return None
    d0 = dates[i - k]
    a = px[c].get(d0); b = px[c].get(d)
    return (b / a - 1.0) if (a and b) else None

def index_cum3(px, d, dates, idx='069500'):
    return mom_k(px, idx, d, dates, 3)

def candidate_pool_k(px, name, d, dates, k, minp=10000, pool_n=15):
    cand = []
    for c in px:
        pc = px[c].get(d)
        if not pc or pc < minp or not is_spot(name.get(c, '')):
            continue
        m = mom_k(px, c, d, dates, k)
        if m is None:
            continue
        if not rule_h_ok(px, c, d, dates):
            continue
        cand.append((c, m))
    cand.sort(key=lambda x: x[1], reverse=True)
    return cand[:pool_n]

def sel_ruleEE(px, name, d, dates, n=5, thr=-0.05, k_alt=5):
    """지수 3일 누적수익률 <= thr(-5%)이면 레짐='크래시직후' → mom5 랭킹 사용, 아니면 mom20(baseline)."""
    ic3 = index_cum3(px, d, dates)
    k = k_alt if (ic3 is not None and ic3 <= thr) else 20
    pool = candidate_pool_k(px, name, d, dates, k, pool_n=n)
    return [c for c, _ in pool], (k != 20)

def main_ee():
    px, name, dates = load()
    results = []
    for i in range(21, len(dates) - 1):
        d = dates[i]; dnext = dates[i + 1]
        base = sel_baseline(px, name, d, dates)
        ee, gated = sel_ruleEE(px, name, d, dates)
        sb = score(px, name, d, dnext, base)
        se = score(px, name, d, dnext, ee)
        if sb is None or se is None:
            continue
        results.append((d, dnext, base, ee, sb, se, gated))
    n = len(results)
    avg_b = sum(r[4]['hit'] for r in results) / n
    avg_e = sum(r[5]['hit'] for r in results) / n
    print(f'\n[Rule EE] 총{n}일 baseline={avg_b:.3f} RuleEE={avg_e:.3f}')
    gated_days = [r for r in results if r[6]]
    print(f'레짐 발동일(지수3일누적<=-5%): {len(gated_days)}일')
    if gated_days:
        bb = sum(r[4]['hit'] for r in gated_days) / len(gated_days)
        ee_ = sum(r[5]['hit'] for r in gated_days) / len(gated_days)
        print(f'  발동일 한정: baseline={bb:.3f} RuleEE={ee_:.3f}')
        for r in gated_days:
            print('   ', r[0], '->', r[1], 'base_hit', r[4]['hit'], 'ee_hit', r[5]['hit'])
    half = n // 2
    tr, te = results[:half], results[half:]
    for label, seg in [('train', tr), ('test', te)]:
        bb = sum(r[4]['hit'] for r in seg) / len(seg)
        ee_ = sum(r[5]['hit'] for r in seg) / len(seg)
        print(f'{label}: baseline={bb:.3f} RuleEE={ee_:.3f} (n={len(seg)})')
    print('\n--- 오늘(D=7/14->7/15) ---')
    for r in results:
        if r[0] == '20260714':
            print('gated?', r[6], 'baseline', r[2], r[4]['hit'], 'RuleEE', r[3], r[5]['hit'])

if __name__ == '__main__':
    main_ee()
