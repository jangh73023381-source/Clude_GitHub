# -*- coding: utf-8 -*-
"""점수 개편안 백테스트 (2026-07-05).
룩어헤드 금지: 선정은 D종가까지 정보만, 채점은 D+1 (ETF 유니버스 대체 채점, 기존 관행).
지표: 평균적중(0~5, 상위10%), 평균백분위, KODEX200 대비 초과수익, >=1/>=3/5-5 비율.
train/test 분할은 기존 bt_select.py와 동일(20일 워밍업 후 절반 분할).
"""
import csv, math, statistics as st
from collections import defaultdict

BASE = '/sessions/lucid-keen-gauss/mnt/loop/backtest'
BENCH = '069500'

def load():
    px = defaultdict(dict); name = {}
    for r in csv.DictReader(open(BASE + '/prices_long.csv', encoding='utf-8')):
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

def vol20(c, d):
    """20거래일 일간수익률 표준편차 (D까지 정보만)."""
    i = DIDX[d]
    if i < 20: return None
    rs = []
    for j in range(i - 19, i + 1):
        a = px[c].get(dates[j - 1]); b = px[c].get(dates[j])
        if a and b: rs.append(b / a - 1.0)
    return st.pstdev(rs) if len(rs) >= 15 else None

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
    """{code: 0~1 백분위(1=최상)} — 동점은 순위 평균 아님(단순)."""
    s = sorted(vals.items(), key=lambda x: x[1])
    n = len(s)
    return {c: (i + 1) / n for i, (c, _) in enumerate(s)}

def candidates(d):
    return [c for c in px if px[c].get(d) and px[c][d] >= 10000 and is_spot(name[c])]

def sel(d, strat, n=5):
    cs = candidates(d)
    feats = {}
    for c in cs:
        m20 = ret(c, d, 20); m5 = ret(c, d, 5); m1 = ret(c, d, 1); m2 = ret(c, d, 2)
        m3 = ret(c, d, 3)
        feats[c] = dict(m20=m20, m5=m5, m1=m1, m2=m2, m3=m3)
    def top_by(key_fn, filt=lambda c: True):
        sc = [(c, key_fn(feats[c])) for c in cs if filt(c) and key_fn(feats[c]) is not None]
        sc.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in sc[:n]]

    def nospike(c):  # 전일 단일세션 +10% 초과 급등 제외 (RuleE 협의형)
        m1 = feats[c]['m1']; return not (m1 is not None and m1 > 0.10)
    def no3d20(c):   # 3거래일 누적 +20% 초과 제외 (과열 컷 후보)
        m3 = feats[c]['m3']; return not (m3 is not None and m3 > 0.20)

    if strat == 'mom20':
        return top_by(lambda f: f['m20'])
    if strat == 'mom20_nospike':
        return top_by(lambda f: f['m20'], nospike)
    if strat == 'mom20_no3d20':
        return top_by(lambda f: f['m20'], no3d20)
    if strat == 'mom20_nospike_no3d20':
        return top_by(lambda f: f['m20'], lambda c: nospike(c) and no3d20(c))
    if strat == 'mom2':  # RuleG 유사: 직전 2거래일 수익률
        return top_by(lambda f: f['m2'])
    if strat == 'mom2_nospike':
        return top_by(lambda f: f['m2'], nospike)
    if strat == 'mom20_volcap':  # 20일 변동성 상위 10% 제외
        vols = {c: vol20(c, d) for c in cs}
        vv = {c: v for c, v in vols.items() if v is not None}
        if not vv: return top_by(lambda f: f['m20'])
        cut = sorted(vv.values())[int(len(vv) * 0.90)] if len(vv) > 10 else max(vv.values())
        return top_by(lambda f: f['m20'], lambda c: vv.get(c) is not None and vv[c] <= cut)
    if strat in ('composite', 'composite_ns'):
        # 개편안 종합점수: mom20 50% + mom2 30% + mom5 20% (백분위 합산)
        p20 = pctile_map({c: feats[c]['m20'] for c in cs if feats[c]['m20'] is not None})
        p2 = pctile_map({c: feats[c]['m2'] for c in cs if feats[c]['m2'] is not None})
        p5 = pctile_map({c: feats[c]['m5'] for c in cs if feats[c]['m5'] is not None})
        sc = []
        for c in cs:
            if c in p20 and c in p2 and c in p5:
                if strat == 'composite_ns' and not nospike(c): continue
                sc.append((c, 0.5 * p20[c] + 0.3 * p2[c] + 0.2 * p5[c]))
        sc.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in sc[:n]]
    raise ValueError(strat)

def run(strat, lo, hi):
    H = []; P = []; E = []
    for i in range(max(20, lo), min(hi, len(dates) - 1)):
        d, dn = dates[i], dates[i + 1]
        p = sel(d, strat)
        if len(p) < 5: continue
        s = score(d, dn, p)
        if not s: continue
        H.append(s[0]); P.append(s[1]); E.append(s[2] * 100)
    if not H: return None
    ge1 = sum(1 for h in H if h >= 1) / len(H) * 100
    ge3 = sum(1 for h in H if h >= 3) / len(H) * 100
    p55 = sum(1 for h in H if h == 5) / len(H) * 100
    return dict(days=len(H), hit=st.mean(H), pct=st.mean(P), ex=st.mean(E), ge1=ge1, ge3=ge3, p55=p55)

if __name__ == '__main__':
    n = len(dates); mid = 20 + (n - 1 - 20) // 2
    strats = ['mom20', 'mom20_nospike', 'mom20_no3d20', 'mom20_nospike_no3d20',
              'mom2', 'mom2_nospike', 'mom20_volcap', 'composite', 'composite_ns']
    print(f"데이터: {len(px)}종목, {n}일 ({dates[0]}~{dates[-1]}), train={mid-20}일/test={n-1-mid}일\n")
    hdr = f"{'전략':<22}{'tr적중':>7}{'tr초과%':>8}{'te적중':>7}{'te초과%':>8}{'전체':>6}{'초과%':>7}{'>=1%':>6}{'>=3%':>6}{'5/5%':>6}"
    print(hdr)
    for s in strats:
        a = run(s, 20, mid); b = run(s, mid, n - 1); f = run(s, 20, n - 1)
        if not (a and b and f):
            print(f"{s:<22}  데이터 부족"); continue
        print(f"{s:<22}{a['hit']:>7.2f}{a['ex']:>8.2f}{b['hit']:>7.2f}{b['ex']:>8.2f}"
              f"{f['hit']:>6.2f}{f['ex']:>7.2f}{f['ge1']:>6.0f}{f['ge3']:>6.0f}{f['p55']:>6.1f}")
