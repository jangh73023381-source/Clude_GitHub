import numpy as np, pandas as pd
def nw_se(x, lag):
    x = np.asarray(x, float) - np.mean(x); n = len(x); s = (x * x).mean()
    for k in range(1, min(lag, n - 1) + 1): s += 2 * (1 - k / (lag + 1)) * (x[k:] * x[:-k]).mean()
    return np.sqrt(s / n)
def summarize(name, t, ex, lag, extra=None):
    """t: 신호일 인덱스, ex: 건별 초과. 날짜별 평균 → 통계."""
    d = pd.DataFrame({'t': t, 'ex': ex}).groupby('t').ex.mean().sort_index()
    x = d.values; n = len(x); k = n // 3; srt = np.sort(x)[::-1]
    o = dict(전략=name, 신호일=n, 건수=len(ex), 초과=x.mean(), t=x.mean() / nw_se(x, lag), 일별중앙=np.median(x),
             건별중앙=np.median(ex), fold1=x[:k].mean(), fold2=x[k:2*k].mean(), fold3=x[2*k:].mean(),
             상위5pct제거=srt[max(1, int(n * .05)):].mean())
    if extra: o.update(extra)
    return o
