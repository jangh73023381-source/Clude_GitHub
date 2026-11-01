# -*- coding: utf-8 -*-
"""맞대결 백테스트: 기존 확정(v1.2+v1.9) vs 잠정(v1.2+v2.1 RuleH / RuleH+I).
v1.2는 2026-07-05 사용자 개정에 따라 '레버리지·인버스 제외'만 적용(증권 하향·반도체 대형집중 우선 삭제).
표본: (a) in-sample 82일(2026-03-03~06-30), (b) out-of-sample 신규 3영업일(7/1·7/2·7/3, 키움 수집).
룩어헤드 금지, ETF 유니버스 대체 채점, 벤치마크 KODEX200. 페어(일자별) 비교 포함.
"""
import csv, math, statistics as st
from collections import defaultdict

LOOP = '/sessions/lucid-keen-gauss/mnt/loop/backtest'
OUTD = '/sessions/lucid-keen-gauss/mnt/outputs'
BENCH = '069500'

def load():
    px = defaultdict(dict); name = {}
    for fp in (LOOP + '/prices_long.csv', OUTD + '/prices_july.csv'):
        for r in csv.DictReader(open(fp, encoding='utf-8')):
            try: px[r['code']][r['date']] = float(r['close'])
            except: pass
            name[r['code']] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, name, dates

def is_spot(nm):
    n = nm.replace(' ', '')
    return not ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n)

px, name, dates = load()
DIDX = {d: i for i, d in enumerate(dates)}

def ret(c, d, k):
    i = DIDX[d]
    if i < k: return None
    a = px[c].get(dates[i - k]); b = px[c].get(d)
    return (b / a - 1.0) if (a and b) else None

def score(d, dnext, picks):
    u = []
    for c in px:
        pc = px[c].get(d); nc = px[c].get(dnext)
        if pc and nc and pc >= 10000:
            u.append((c, nc / pc - 1.0))
    if not u: return None
    u.sort(key=lambda x: x[1], reverse=True)
    N = len(u); cutoff = max(1, math.ceil(N * 0.10))
    rank = {c: i + 1 for i, (c, _) in enumerate(u)}
    r = dict(u); bench = r.get(BENCH, 0.0)
    hit = 0; pcts = []; ex = []
    for c in picks:
        if c in rank:
            hit += 1 if rank[c] <= cutoff else 0
            pcts.append((rank[c] - 1) / N * 100); ex.append(r[c] - bench)
    if not pcts: return None
    return hit, st.mean(pcts), st.mean(ex)

def pctile_map(vals):
    s = sorted(vals.items(), key=lambda x: x[1]); n = len(s)
    return {c: (i + 1) / n for i, (c, _) in enumerate(s)}

def candidates(d):
    return [c for c in px if px[c].get(d) and px[c][d] >= 10000 and is_spot(name[c])]

def sel(d, method, n=5):
    cs = candidates(d)
    f = {c: dict(m20=ret(c, d, 20), m2=ret(c, d, 2), m1=ret(c, d, 1), m3=ret(c, d, 3)) for c in cs}
    def okH(c):
        m1, m3 = f[c]['m1'], f[c]['m3']
        if m1 is not None and m1 > 0.10: return False
        if m3 is not None and m3 > 0.20: return False
        return True
    if method == 'A_v19':      # 기존 확정: mom20 top5
        sc = [(c, f[c]['m20']) for c in cs if f[c]['m20'] is not None]
    elif method == 'B_ruleH':  # 잠정 RuleH: mom20 + 이중 과열필터
        sc = [(c, f[c]['m20']) for c in cs if f[c]['m20'] is not None and okH(c)]
    elif method == 'C_ruleHI': # 잠정 RuleH+I: 0.8*m20pct + 0.2*m2pct + 필터
        p20 = pctile_map({c: f[c]['m20'] for c in cs if f[c]['m20'] is not None})
        p2 = pctile_map({c: f[c]['m2'] for c in cs if f[c]['m2'] is not None})
        sc = [(c, 0.8 * p20[c] + 0.2 * p2[c]) for c in cs if c in p20 and c in p2 and okH(c)]
    else: raise ValueError(method)
    sc.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in sc[:n]]

def daily(method, lo, hi):
    out = []
    for i in range(max(20, lo), min(hi, len(dates) - 1)):
        d, dn = dates[i], dates[i + 1]
        p = sel(d, method)
        if len(p) < 5: continue
        s = score(d, dn, p)
        if s: out.append((d, dn, s[0], s[1], s[2] * 100, p))
    return out

def summ(rows):
    H = [r[2] for r in rows]; P = [r[3] for r in rows]; E = [r[4] for r in rows]
    return dict(days=len(H), hit=st.mean(H), pct=st.mean(P), ex=st.mean(E),
                ge1=100 * sum(1 for h in H if h >= 1) / len(H),
                ge3=100 * sum(1 for h in H if h >= 3) / len(H),
                p55=100 * sum(1 for h in H if h == 5) / len(H))

if __name__ == '__main__':
    n = len(dates)
    js = DIDX['20260630']  # in-sample 끝: 6/30 선정 → 7/1 채점부터가 OOS
    print(f"데이터: {len(px)}종목 × {n}일 ({dates[0]}~{dates[-1]})\n")
    res = {}
    for m in ('A_v19', 'B_ruleH', 'C_ruleHI'):
        res[m] = dict(ins=daily(m, 20, js), oos=daily(m, js, n - 1))
    lab = {'A_v19': '기존 v1.2+v1.9', 'B_ruleH': '잠정 v2.1 RuleH', 'C_ruleHI': '잠정 v2.1 RuleH+I'}
    for seg, ttl in (('ins', 'in-sample 61일(3/31~6/30 채점)'), ('oos', '표본 밖 신규 3일(7/1·7/2·7/3 채점)')):
        print(f"== {ttl} ==")
        print(f"{'방법':<20}{'평균적중':>8}{'평균백분위':>10}{'초과%':>8}{'>=1%':>6}{'>=3%':>6}{'5/5%':>6}")
        for m in res:
            s = summ(res[m][seg])
            print(f"{lab[m]:<20}{s['hit']:>8.2f}{s['pct']:>10.1f}{s['ex']:>8.2f}{s['ge1']:>6.0f}{s['ge3']:>6.0f}{s['p55']:>6.1f}")
        print()
    # 페어 비교 (전 기간)
    for mb in ('B_ruleH', 'C_ruleHI'):
        allA = res['A_v19']['ins'] + res['A_v19']['oos']
        allB = res[mb]['ins'] + res[mb]['oos']
        dA = {r[0]: r for r in allA}; dB = {r[0]: r for r in allB}
        common = sorted(set(dA) & set(dB))
        diff = [dB[d][2] - dA[d][2] for d in common]
        w = sum(1 for x in diff if x > 0); l = sum(1 for x in diff if x < 0); t = sum(1 for x in diff if x == 0)
        print(f"페어 비교 {lab[mb]} vs 기존: {len(common)}일, 승 {w} / 무 {t} / 패 {l}, 평균 적중 차 {st.mean(diff):+.3f}")
    # OOS 일자별 상세
    print("\n== OOS 일자별 상세 ==")
    for m in res:
        for r in res[m]['oos']:
            names = ', '.join(f"{name[c][:14]}" for c in r[5])
            print(f"{lab[m]:<18} {r[0]}→{r[1]}: 적중 {r[2]}/5, 백분위 {r[3]:.1f}, 초과 {r[4]:+.2f}% | {names}")
