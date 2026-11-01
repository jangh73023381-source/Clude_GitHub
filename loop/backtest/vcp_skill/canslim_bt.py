"""CANSLIM 원본 계산기(C·A·N·S·L·M)를 한국 데이터로. I(기관)는 데이터 없음 → 중립 50.
EPS 대신 분기 영업이익 YoY(fund.csv, PIT=법정 공시기한 다음날)를 쓴다.
python3 canslim_bt.py <stride> <shard> <nshard>"""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/ext/claude-trading-skills/skills/canslim-screener/scripts')
from calculators.earnings_calculator import score_current_earnings
from calculators.growth_calculator import score_annual_growth
from calculators.new_highs_calculator import calculate_newness
from calculators.supply_demand_calculator import calculate_supply_demand
from calculators.leadership_calculator import calculate_leadership
from calculators.market_calculator import calculate_market_direction
from scorer import calculate_composite_score_phase3, check_minimum_thresholds_phase3

ST, SH, NS = map(int, sys.argv[1:4])
Z = np.load('dense.npz'); dates, codes, bench = Z['dates'], Z['codes'], Z['bench']
O, H, L, C, V = (Z[k] for k in 'OHLCV'); T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
liq = (C >= 1000) & (val20 >= 1e9)

f = pd.read_csv('/mnt/user-data/uploads/loop/backtest/sjh/fund.csv', dtype={'code': str})
q = {c: g.sort_values('avail') for c, g in f.groupby('code')}
ann = {c: g[g.reprt == 11011].sort_values('year') for c, g in f.groupby('code')}


def c_score(code, d):
    g = q.get(code)
    if g is None: return None
    g = g[g.avail <= d]
    if not len(g): return None
    r = g.iloc[-1]
    if not (r.op_p == r.op_p) or not (r.sa_p == r.sa_p) or r.sa_p <= 0: return None
    eg = 100.0 if (r.op > 0 and r.op_p <= 0) else (r.op / r.op_p - 1) * 100 if r.op_p > 0 else -100.0
    return score_current_earnings(eg, (r.sa / r.sa_p - 1) * 100)


def a_score(code, d):
    g = ann.get(code)
    if g is None: return None
    g = g[g.avail <= d]
    if len(g) < 4: return 0
    g = g.iloc[-4:]; op, sa = g.op.values, g.sa.values
    if op[0] <= 0 or op[-1] <= 0 or sa[0] <= 0: return 0
    eps_cagr = ((op[-1] / op[0]) ** (1 / 3) - 1) * 100
    rev_cagr = ((sa[-1] / sa[0]) ** (1 / 3) - 1) * 100
    return score_annual_growth(eps_cagr, rev_cagr, bool(np.all(np.diff(op) > 0)))


def hist(j, t, n=260):
    s = max(0, t - n + 1)
    return [{"date": str(dates[i]), "open": O[i, j], "high": H[i, j], "low": L[i, j], "close": C[i, j],
             "adjClose": C[i, j], "volume": V[i, j]} for i in range(t, s - 1, -1) if C[i, j] == C[i, j]]


rows = []
for t in list(range(260, T - 20, ST))[SH::NS]:
    d = int(dates[t])
    bh = [{"date": str(dates[i]), "close": float(bench[i])} for i in range(t, t - 260, -1)]
    m = calculate_market_direction({"price": float(bench[t])}, bh)["score"]
    for j in np.where(liq[t])[0]:
        code = codes[j]
        cs_ = c_score(code, d)
        if cs_ is None: continue
        hs = hist(j, t)
        if len(hs) < 252: continue
        quote = {"price": C[t, j], "yearHigh": np.nanmax(H[t-251:t+1, j]), "yearLow": np.nanmin(L[t-251:t+1, j]),
                 "volume": V[t, j], "avgVolume": np.nanmean(V[t-50:t, j])}
        n_ = calculate_newness(quote)["score"]
        s_ = calculate_supply_demand({"historical": hs[:90]})["score"]
        l_ = calculate_leadership(hs, bh, rs_benchmark="069500")["score"]
        a_ = a_score(code, d)
        comp = calculate_composite_score_phase3(cs_, a_, n_, s_, l_, 50, m)["composite_score"]
        ok = check_minimum_thresholds_phase3(cs_, a_, n_, s_, l_, 50, m)["passes_all"]
        rows.append((d, code, comp, int(ok), cs_, a_, n_, s_, l_, m))
pickle.dump(rows, open(f'cs_{ST}_{SH}.pkl', 'wb'))
print('done', SH, len(rows))
