"""GTJA 191 알파 (HKUDS/Vibe-Trading agent/src/factors/zoo/gtja191 — 수식 함수만 AST 검사 후 사용, 연산자는 gtja_ops 자체 구현) 개별주 횡단면 검정.
qlib158.py 와 같은 규칙: 유동 종목(종가>=1000, 20일 평균 거래대금>=10억), 5거래일 간격 표본일,
상위 10% − 유동 평균(5일·20일 보유). 방향은 앞 절반(~2023-06-30) IC 부호로 정하고 뒤 절반에서 확인.
입력 대체: amount = 종가×거래량, vwap = (O+H+L+C)/4 (저장소 base.vwap 의 equity_kr 정의), benchmark_close = KODEX200.
python3 gtja191.py <shard> <nshard>"""
import sys, os, glob, time, pickle, signal, numpy as np, pandas as pd
sys.path.insert(1, '/tmp/claude-0/vcpkr')
from gh_stats import nw_se
from gtja_ops import load_compute
SH, NS = int(sys.argv[1]), int(sys.argv[2])
Z = np.load('/tmp/claude-0/vcpkr/dense.npz'); dates = Z['dates'].astype(int)
O, H, L, C, V = (Z[k].astype(float) for k in 'OHLCV'); T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
keep = LIQ.any(0)                      # 한 번이라도 유동 조건을 만족한 종목만 계산(속도)
O, H, L, C, V, LIQ = O[:, keep], H[:, keep], L[:, keep], C[:, keep], V[:, keep], LIQ[:, keep]; N = C.shape[1]
idx = pd.to_datetime(dates.astype(str)); cols = [str(i) for i in range(N)]
D = lambda A: pd.DataFrame(A, index=idx, columns=cols)
bench = Z['bench'].astype(float)
panel = dict(open=D(O), high=D(H), low=D(L), close=D(C), volume=D(V), amount=D(C * V), vwap=D((O + H + L + C) / 4),
             benchmark_close=D(np.repeat(bench[:, None], N, 1)))
F5 = np.vstack([C[5:] / C[:-5] - 1, np.full((5, N), np.nan)]) * 100
F20 = np.vstack([C[20:] / C[:-20] - 1, np.full((20, N), np.nan)]) * 100
SPLIT = 20230630
ts = list(range(260, T - 20, 5))


def run(X):
    out = {5: [], 20: []}; ic = []
    for t in ts:
        m = LIQ[t] & np.isfinite(X[t]) & np.isfinite(F20[t])
        if m.sum() < 200: continue
        x = X[t, m]
        if np.unique(x).size < 5: continue
        q = x >= np.quantile(x, .9); qb = x <= np.quantile(x, .1)
        for h, FF in ((5, F5), (20, F20)):
            r = FF[t, m]; out[h].append((t, r[q].mean() - r.mean(), r[qb].mean() - r.mean()))
        ic.append((t, pd.Series(x).corr(pd.Series(F20[t, m]), method='spearman')))
    return out, ic


def ev(k, X):
    out, ic = run(X)
    if len(ic) < 100: return None
    icd = pd.DataFrame(ic, columns=['t', 'ic']); tr = icd[dates[icd.t] <= SPLIT]; sign = 1 if tr.ic.mean() >= 0 else -1
    row = dict(알파=k, 방향=('높을수록' if sign > 0 else '낮을수록'), 앞_IC=tr.ic.mean(), 뒤_IC=icd[dates[icd.t] > SPLIT].ic.mean())
    for h in (5, 20):
        a = pd.DataFrame(out[h], columns=['t', 'top', 'bot']); a['x'] = a.top if sign > 0 else a.bot
        te = a[dates[a.t] > SPLIT].x.values; trx = a[dates[a.t] <= SPLIT].x.values; lag = h // 5 - 1
        row[f'앞_{h}일'] = trx.mean(); row[f'뒤_{h}일'] = te.mean(); row[f'뒤_{h}일_t'] = te.mean() / nw_se(te, lag)
        if h == 20:
            sr = np.sort(te)[::-1]; row['뒤_20일_상위5%제거'] = sr[max(2, int(len(te) * .05)):].mean()
            k3 = len(te) // 3; row['뒤_3분할'] = '/'.join(f'{te[i*k3:(i+1)*k3].mean():.2f}' for i in range(3))
    return row


class TO(Exception): pass
def _alarm(*_): raise TO()
signal.signal(signal.SIGALRM, _alarm)
files = sorted(glob.glob('/tmp/claude-0/ext/HKUDS_Vibe-Trading/agent/src/factors/zoo/gtja191/alpha_*.py'))[SH::NS]
outp = f'/tmp/claude-0/vcpkr/gtja_{SH}.pkl'
rows = pickle.load(open(outp, 'rb')) if os.path.exists(outp) else []
done = {r["알파"] for r in rows if "알파" in r}
for f in files:
    k = os.path.basename(f)[:-3]
    if k in done: continue
    t0 = time.time()
    try:
        signal.alarm(600)
        compute = load_compute(f)
        with np.errstate(all='ignore'):
            X = compute(panel)
        X = X.reindex(index=idx, columns=cols).values.astype(float); X[~np.isfinite(X)] = np.nan
        signal.alarm(0)
        r = ev(k, X)
        rows.append(r if r else dict(skip=k, why='표본 부족'))
    except Exception as e:
        signal.alarm(0); rows.append(dict(skip=k, why=type(e).__name__ + ':' + str(e)[:80]))
    print(k, f'{time.time()-t0:.0f}s', rows[-1].get('뒤_20일_t', rows[-1].get('why')), flush=True)
    pickle.dump(rows, open(outp, 'wb'))
print('DONE', SH)
