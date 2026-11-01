"""px.pkl -> 날짜×종목 dense 배열 (dense.npz)."""
import pickle, numpy as np
D = pickle.load(open('px.pkl', 'rb'))
dates = D['069500'][0].astype(int)
codes = sorted(k for k in D if k != '069500')
pos = {d: i for i, d in enumerate(dates)}
T, N = len(dates), len(codes)
A = {k: np.full((T, N), np.nan) for k in 'OHLCV'}
for j, c in enumerate(codes):
    d, o, h, l, cl, v = D[c]
    ix = np.array([pos.get(int(x), -1) for x in d]); m = ix >= 0
    for k, arr in zip('OHLCV', (o, h, l, cl, v)):
        A[k][ix[m], j] = arr[m]
bc = D['069500'][4]
np.savez('dense.npz', dates=dates, codes=np.array(codes), bench=bc, **A)
print(T, N)
