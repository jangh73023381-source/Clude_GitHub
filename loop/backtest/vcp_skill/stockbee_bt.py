"""Stockbee Momentum Burst / Exhaustion Hammer 원본 analyze_symbol 로 7년 신호 생성.
python3 stockbee_bt.py mb|eh <shard> <nshard>"""
import sys, pickle, numpy as np
SK = '/tmp/claude-0/ext/claude-trading-skills/skills/'
which, SH, NS = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
if which == 'mb':
    sys.path.insert(0, SK + 'stockbee-momentum-burst-screener/scripts')
    import screen_momentum_burst as M
    sys.argv = ['x', '--min-price', '1000', '--min-volume', '0',
                '--dollar-threshold', '1e15', '--nine-million-volume', '1000000000000000']
    NB = 80
else:
    sys.path.insert(0, SK + 'stockbee-exhaustion-hammer-screener/scripts')
    import screen_exhaustion_hammer as M
    sys.argv = ['x', '--min-price', '1000', '--min-volume', '0',
                '--min-avg-dollar-volume', '1e9', '--min-market-cap', '0']
    NB = 120
args = M.parse_arguments()
Z = np.load('dense.npz')
dates, codes = Z['dates'], Z['codes']
O, H, L, C, V = (Z[k] for k in 'OHLCV')
T, N = C.shape
val20 = np.full((T, N), np.nan)
cv = np.nan_to_num(C * V)
cs = np.cumsum(cv, 0)
val20[20:] = (cs[20:] - cs[:-20]) / 20
liq = (C >= 1000) & (val20 >= 1e9)
Cp = np.vstack([np.full((1, N), np.nan), C[:-1]])
Vp = np.vstack([np.full((1, N), np.nan), V[:-1]])
rng = H - L
with np.errstate(invalid='ignore', divide='ignore'):
    if which == 'mb':
        r3 = np.full((T, N), np.nan)
        for k in range(1, 4):
            r3 = np.fmax(r3, np.vstack([np.full((k, N), np.nan), rng[:-k]]))
        Cp2 = np.vstack([np.full((2, N), np.nan), C[:-2]])
        pre = liq & (V > Vp) & ((C / Cp >= 1.04) | ((rng > r3) & (Cp / Cp2 - 1 <= 0.02)))
    else:
        lw = (np.minimum(O, C) - L) / rng
        pre = liq & (rng > 0) & (lw >= 0.40) & ((C - L) / rng >= 0.60)
rows = []
for t in range(260, T)[SH::NS]:
    for j in np.where(pre[t])[0]:
        s = max(0, t - NB + 1)
        seg = slice(s, t + 1)
        if np.isnan(C[seg, j]).any():
            continue
        bars = [M.Bar(date=str(dates[i]), open=O[i, j], high=H[i, j], low=L[i, j],
                      close=C[i, j], volume=int(V[i, j])) for i in range(t, s - 1, -1)]
        r = M.analyze_symbol(codes[j], bars, args)
        if r.get('state') not in (None, 'REJECTED'):
            rows.append((int(dates[t]), codes[j], r['state'], r['setup_score'],
                         r.get('primary_trigger', r.get('setup_type', '')), r.get('risk_pct_to_stop')))
pickle.dump(rows, open(f'sb_{which}_{SH}.pkl', 'wb'))
print(which, SH, len(rows))
