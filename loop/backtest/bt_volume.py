# -*- coding: utf-8 -*-
"""Rule AA — 거래량 급증 신호 백테스트. 룩어헤드 금지: 선정은 D종가까지 정보만.
mom20+RuleH baseline vs 거래량비율(D일거래량/20일평균거래량) 오버레이 비교."""
import csv, math
from collections import defaultdict

BASE = '/sessions/affectionate-practical-mendel/mnt/loop'
BENCH = '069500'

def load():
    px = defaultdict(dict); vol = defaultdict(dict); name = {}
    with open(BASE + '/backtest/panel_vol.csv', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            c = r['code']
            try:
                px[c][r['date']] = float(r['close'])
                vol[c][r['date']] = float(r['volume'])
            except (ValueError, KeyError):
                continue
            name[c] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, vol, name, dates

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
    """RuleH v2.1 이중 과열필터: 단일세션>+10% 또는 3일누적>+20% 제외."""
    s = single_session_ret(px, c, d, dates)
    c3 = cum3(px, c, d, dates)
    if s is not None and s > 0.10:
        return False
    if c3 is not None and c3 > 0.20:
        return False
    return True

def vol_ratio(vol, c, d, dates, k=20):
    i = dates.index(d)
    if i < k:
        return None
    window = dates[i - k:i]  # prior k days, excludes D itself
    vs = [vol[c].get(dd) for dd in window]
    vs = [v for v in vs if v and v > 0]
    if len(vs) < 10:
        return None
    avg = sum(vs) / len(vs)
    vd = vol[c].get(d)
    if not vd or avg <= 0:
        return None
    return vd / avg

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

def sel_ruleAA_override(px, vol, name, d, dates, pool_n=15, n=5):
    """풀(mom20 top pool_n, RuleH 필터 후) 내에서 거래량비율 상위 n개로 재정렬."""
    pool = candidate_pool(px, name, d, dates, pool_n=pool_n)
    scored = []
    for c, m in pool:
        vr = vol_ratio(vol, c, d, dates)
        scored.append((c, m, vr if vr is not None else 0.0))
    scored.sort(key=lambda x: x[2], reverse=True)
    return [c for c, _, _ in scored[:n]]

def sel_ruleAA_blend(px, vol, name, d, dates, pool_n=15, n=5, w=0.5):
    pool = candidate_pool(px, name, d, dates, pool_n=pool_n)
    if not pool:
        return []
    moms = [m for _, m in pool]
    mn, mx = min(moms), max(moms)
    scored = []
    for c, m in pool:
        vr = vol_ratio(vol, c, d, dates)
        mom_pct = (m - mn) / (mx - mn) if mx > mn else 0.5
        scored.append((c, mom_pct, vr))
    vrs = [x[2] for x in scored if x[2] is not None]
    vmn, vmx = (min(vrs), max(vrs)) if vrs else (0, 1)
    out = []
    for c, mom_pct, vr in scored:
        vr_pct = (vr - vmn) / (vmx - vmn) if (vr is not None and vmx > vmn) else 0.0
        blend = (1 - w) * mom_pct + w * vr_pct
        out.append((c, blend))
    out.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in out[:n]]

def main():
    px, vol, name, dates = load()
    print('codes', len(px), 'days', len(dates), dates[0], '~', dates[-1])
    results = []
    for i in range(21, len(dates) - 1):
        d = dates[i]; dnext = dates[i + 1]
        base = sel_baseline(px, name, d, dates)
        aa1 = sel_ruleAA_override(px, vol, name, d, dates)
        aa2 = sel_ruleAA_blend(px, vol, name, d, dates, w=0.5)
        sb = score(px, name, d, dnext, base)
        sa1 = score(px, name, d, dnext, aa1)
        sa2 = score(px, name, d, dnext, aa2)
        if sb is None or sa1 is None or sa2 is None:
            continue
        results.append((d, dnext, base, aa1, aa2, sb, sa1, sa2))

    n = len(results)
    print(f'\n총 {n}개 결정일 백테스트')
    avg_hit_b = sum(r[5]['hit'] for r in results) / n
    avg_hit_a1 = sum(r[6]['hit'] for r in results) / n
    avg_hit_a2 = sum(r[7]['hit'] for r in results) / n
    print(f'전체 평균 적중수(5종 중): baseline={avg_hit_b:.3f}  AA1(override)={avg_hit_a1:.3f}  AA2(blend50)={avg_hit_a2:.3f}')

    changed = [r for r in results if set(r[2]) != set(r[3])]
    print(f'\nAA1이 baseline과 다른 picks를 낸 날: {len(changed)}일')
    if changed:
        avg_hit_b_c = sum(score(px, name, r[0], r[1], r[2])['hit'] for r in changed) / len(changed)
        avg_hit_a1_c = sum(r[6]['hit'] for r in changed) / len(changed)
        print(f'  발동일 한정 평균적중: baseline={avg_hit_b_c:.3f}  AA1={avg_hit_a1_c:.3f}')

    changed2 = [r for r in results if set(r[2]) != set(r[4])]
    print(f'\nAA2(blend)가 baseline과 다른 picks를 낸 날: {len(changed2)}일')
    if changed2:
        avg_hit_b_c2 = sum(score(px, name, r[0], r[1], r[2])['hit'] for r in changed2) / len(changed2)
        avg_hit_a2_c2 = sum(r[7]['hit'] for r in changed2) / len(changed2)
        print(f'  발동일 한정 평균적중: baseline={avg_hit_b_c2:.3f}  AA2={avg_hit_a2_c2:.3f}')

    # train/test split
    half = n // 2
    tr, te = results[:half], results[half:]
    for label, seg in [('train', tr), ('test', te)]:
        bb = sum(r[5]['hit'] for r in seg) / len(seg)
        a1 = sum(r[6]['hit'] for r in seg) / len(seg)
        a2 = sum(r[7]['hit'] for r in seg) / len(seg)
        print(f'{label}: baseline={bb:.3f} AA1={a1:.3f} AA2={a2:.3f} (n={len(seg)})')

    # today's decision (D=7/13)
    print('\n--- 오늘(D=7/13->7/14) 상세 ---')
    for r in results:
        if r[0] == '20260713':
            d, dnext, base, aa1, aa2, sb, sa1, sa2 = r
            print('baseline picks:', base, '-> hit', sb['hit'], sb)
            print('AA1(volume override) picks:', aa1, '-> hit', sa1['hit'], sa1)
            print('AA2(blend50) picks:', aa2, '-> hit', sa2['hit'], sa2)

if __name__ == '__main__':
    main()

def sel_ruleAA3_exclude_extreme(px, vol, name, d, dates, pool_n=15, n=5, vr_max=5.0):
    """AA3: mom20 top pool 중 거래량비율이 비정상적으로 큰(>vr_max, 노이즈성 의심) 종목 제외 후 mom20 순위 그대로 top n."""
    pool = candidate_pool(px, name, d, dates, pool_n=pool_n)
    kept = []
    for c, m in pool:
        vr = vol_ratio(vol, c, d, dates)
        if vr is not None and vr > vr_max:
            continue
        kept.append((c, m))
    return [c for c, _ in kept[:n]]

def main3():
    px, vol, name, dates = load()
    results = []
    for i in range(21, len(dates) - 1):
        d = dates[i]; dnext = dates[i + 1]
        base = sel_baseline(px, name, d, dates)
        aa3 = sel_ruleAA3_exclude_extreme(px, vol, name, d, dates)
        sb = score(px, name, d, dnext, base)
        sa3 = score(px, name, d, dnext, aa3)
        if sb is None or sa3 is None:
            continue
        results.append((d, dnext, base, aa3, sb, sa3))
    n = len(results)
    avg_b = sum(r[4]['hit'] for r in results) / n
    avg_a3 = sum(r[5]['hit'] for r in results) / n
    print(f'AA3(고거래량비율 제외, vr_max=5.0): 총{n}일 baseline={avg_b:.3f} AA3={avg_a3:.3f}')
    changed = [r for r in results if set(r[2]) != set(r[3])]
    if changed:
        bb = sum(r[4]['hit'] for r in changed) / len(changed)
        aa = sum(r[5]['hit'] for r in changed) / len(changed)
        print(f'  발동일({len(changed)}일) 한정: baseline={bb:.3f} AA3={aa:.3f}')
    half = n // 2
    tr, te = results[:half], results[half:]
    for label, seg in [('train', tr), ('test', te)]:
        bb = sum(r[4]['hit'] for r in seg) / len(seg)
        aa = sum(r[5]['hit'] for r in seg) / len(seg)
        print(f'{label}: baseline={bb:.3f} AA3={aa:.3f} (n={len(seg)})')
    for r in results:
        if r[0] == '20260713':
            print('오늘 baseline:', r[2], r[4]['hit'], ' AA3:', r[3], r[5]['hit'])

if __name__ == '__main__':
    main()
    print()
    main3()
