import pickle, glob, numpy as np, pandas as pd
Z = np.load('dense.npz'); dates, codes = Z['dates'], Z['codes']; C, V, H = Z['C'], Z['V'], Z['H']
T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
liq = (C >= 1000) & (val20 >= 1e9)
di = {int(d): i for i, d in enumerate(dates)}; ci = {c: j for j, c in enumerate(codes)}
FW = {h: np.vstack([C[h:] / C[:-h] - 1, np.full((h, N), np.nan)]) * 100 for h in (3, 5, 20)}
hi250 = pd.DataFrame(H).rolling(250, min_periods=250).max().values
NH = C >= 0.95 * hi250
Cp = np.vstack([np.full((1, N), np.nan), C[:-1]]); Vp = np.vstack([np.full((1, N), np.nan), V[:-1]])
RAW4 = liq & (C / Cp >= 1.04) & (V > Vp)


def nw_se(x, lag):
    x = np.asarray(x) - np.mean(x); n = len(x); s = (x * x).mean()
    for k in range(1, lag + 1): s += 2 * (1 - k / (lag + 1)) * (x[k:] * x[:-k]).mean()
    return np.sqrt(s / n)


def stats(name, sig, h, ref=None, sample_dates=None):
    """sig: list of (t, j). 기준=같은날 유동 유니버스 동일가중."""
    F = FW[h]; df = pd.DataFrame(sig, columns=['t', 'j']).drop_duplicates()
    df['r'] = F[df.t, df.j]; df = df.dropna()
    ts = np.array(sorted(df.t.unique()))
    um = np.array([np.nanmean(np.where(liq[t], F[t], np.nan)) for t in ts])
    gm = df.groupby('t').r.mean().reindex(ts).values
    ex = gm - um
    srt = np.sort(ex)[::-1]; n = len(ex); k3 = n // 3
    se = nw_se(ex, h - 1 if h > 1 else 0)
    out = dict(군=name, h=h, 신호일=n, 일평균종목=round(len(df) / n, 1), 초과=ex.mean(), t=ex.mean() / se,
               일별중앙=np.median(ex), 종목승률=(df.r > 0).mean() * 100,
               fold1=ex[:k3].mean(), fold2=ex[k3:2 * k3].mean(), fold3=ex[2 * k3:].mean(),
               상위3일제거=srt[3:].mean(), 상위5pct제거=srt[int(n * .05):].mean())
    if ref is not None:  # 같은 날 대조군 대비 증분
        rm = []
        for t in ts:
            js = np.where(ref[t] & ~np.isnan(F[t]))[0]
            rm.append(F[t, js].mean() if len(js) else np.nan)
        d = gm - np.array(rm); d = d[~np.isnan(d)]
        out['대조대비'] = d.mean(); out['대조t'] = d.mean() / nw_se(d, h - 1)
    return out


R = []
for w, lab in (('mb', 'Momentum Burst'), ('eh', 'Exhaustion Hammer')):
    rows = sum((pickle.load(open(p, 'rb')) for p in sorted(glob.glob(f'sb_{w}_*.pkl'))), [])
    s = pd.DataFrame(rows, columns=['d', 'code', 'state', 'score', 'trig', 'risk'])
    s['t'] = s.d.map(di); s['j'] = s.code.map(ci)
    for cut, nm in ((55, 'Watch+'), (70, 'B+ (수동검토)'), (80, 'A- (Day1 실행)')):
        g = s[s.score >= cut]
        for h in ((3, 5, 20) if w == 'mb' else (5, 20)):
            R.append(stats(f'{lab} {nm}', g[['t', 'j']].values, h, ref=RAW4 if w == 'mb' else None))
# raw 4% control
rt, rj = np.where(RAW4); m = rt >= 260
for h in (3, 5, 20):
    R.append(stats('대조: 단순 +4%·거래량증가', np.c_[rt[m], rj[m]], h))
# CANSLIM
rows = sum((pickle.load(open(p, 'rb')) for p in sorted(glob.glob('cs_5_*.pkl'))), [])
c = pd.DataFrame(rows, columns='d code comp ok C A N S L M'.split()); c['t'] = c.d.map(di); c['j'] = c.code.map(ci)
for nm, g in (('CANSLIM 60+', c[c.comp >= 60]), ('CANSLIM 70+', c[c.comp >= 70]),
              ('CANSLIM 최소기준 전부통과', c[c.ok == 1]),
              ('CANSLIM 일별 상위10', c.sort_values('comp', ascending=False).groupby('d').head(10))):
    R.append(stats(nm, g[['t', 'j']].values, 20, ref=NH))
cd = sorted(c.t.unique()); nt, nj = np.where(NH & liq); mm = np.isin(nt, cd)
R.append(stats('대조: 신고가근접(같은 주간 표본일)', np.c_[nt[mm], nj[mm]], 20))
r = pd.DataFrame(R); pd.set_option('display.width', 300); pd.set_option('display.max_columns', 40)
print(r.round(2).to_string(index=False))
r.to_csv('summary_all.csv', index=False)
