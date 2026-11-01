import sys,numpy as np,pandas as pd
sys.path.insert(0,'/home/claude/w/loop/backtest/loop10_20260926')
from universe_filters import eligible
df0=pd.read_csv('/home/claude/w/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
df0=df0[df0['name'].map(eligible)]
for end in [20260918,20260917,20260916,20260915,20260912,20260911,20260910,20260909]:
    df=df0[df0.date<=end]
    cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
    C=cl.to_numpy(float); n,m=C.shape
    M150=C/np.roll(C,150,axis=0)-1
    r=[]
    for i in range(200,n-1):
        row=M150[i]; ok=np.isfinite(row)&np.isfinite(C[i]); idx=np.where(ok)[0]
        t=idx[np.argsort(-row[idx])][:5] if len(idx)>=20 else []
        cur=[c for c in t if np.isfinite(C[i+1][c])]
        r.append(float(np.mean(C[i+1][cur]/C[i][cur]-1)) if cur else 0.)
    r=np.array(r); eq=np.cumprod(1+r)
    print(end, cl.shape, f"{100*(eq[-1]-1):+.1f}", f"{100*(eq/np.maximum.accumulate(eq)-1).min():.1f}", f"{r.mean()/r.std()*252**.5:.2f}")
