"""VCP 스킬 7년 백테스트 — 신호일 D 종가 진입, D+20 종가 청산.
기준선 = 같은 날 유동성 유니버스(거래대금20일>=10억, 주가>=1000) 동일가중 20일 수익률.
python3 bt.py <stride> <shard> <nshard>"""
import sys, pickle, numpy as np
from kr_adapter import to_hist, prefilter, run_one

STRIDE, SHARD, NSH = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
H = 20
D = pickle.load(open('px.pkl', 'rb'))
bd, bo, bh, bl, bc, bv = D['069500']
bidx = {int(x): i for i, x in enumerate(bd)}
idx = {k: {int(x): i for i, x in enumerate(v[0])} for k, v in D.items()}

dates = [int(x) for x in bd]
test_dates = dates[260:len(dates) - H][::STRIDE][SHARD::NSH]
rows = []
for dt in test_dates:
    bi = bidx[dt]
    bench = to_hist(bd, bo, bh, bl, bc, bv, bi)
    fwd_date = dates[bi + H]
    kodex = bc[bi + H] / bc[bi] - 1
    for code, (d, o, h, l, c, v) in D.items():
        if code == '069500':
            continue
        m = idx[code]
        e = m.get(dt); f = m.get(fwd_date)
        if e is None or f is None or e < 252:
            continue
        if c[e] < 1000 or (c[e-19:e+1] * v[e-19:e+1]).mean() < 1e9:
            continue
        ret = c[f] / c[e] - 1
        yh = h[e-249:e+1].max()
        nh = c[e] >= 0.95 * yh
        pf = prefilter(c, h, l, v, e)
        r = run_one(code, d, o, h, l, c, v, e, bench) if pf else None
        rows.append((dt, code, ret, kodex, int(nh), int(pf), int(r is not None),
                     int(bool(r and r['valid_vcp'])),
                     r['state'] if r else '', r['score'] if r else np.nan,
                     float(l[e+1:f+1].min() / c[e] - 1)))
pickle.dump(rows, open(f'bt_{STRIDE}_{SHARD}.pkl', 'wb'))
print('done', len(test_dates), len(rows))
