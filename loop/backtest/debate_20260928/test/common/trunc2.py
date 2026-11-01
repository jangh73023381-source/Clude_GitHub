import sys,numpy as np,pandas as pd
sys.path.insert(0,'/home/claude/w/loop/backtest/loop10_20260926')
from universe_filters import eligible
df0=pd.read_csv('/home/claude/w/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
df0=df0[df0['name'].map(eligible)]
CL=df0.pivot_table(index='date',columns='code',values='close').sort_index()
dates=list(CL.index)
for end in dates[-25:]:
    cl=CL.loc[:end].dropna(axis=1,how='all')
    C=cl.to_numpy(float); n,m=C.shape; codes=list(cl.columns); ben=C[:,codes.index('069500')]
    M150=C/np.roll(C,150,axis=0)-1
    r=[]
    for i in range(200,n-1):
        row=M150[i]; ok=np.isfinite(row)&np.isfinite(C[i]); idx=np.where(ok)[0]
        t=idx[np.argsort(-row[idx])][:5] if len(idx)>=20 else []
        cur=[c for c in t if np.isfinite(C[i+1][c])]
        r.append(float(np.mean(C[i+1][cur]/C[i][cur]-1)) if cur else 0.)
    r=np.array(r); eq=np.cumprod(1+r); b=ben[201:n]/ben[200:n-1]-1
    print(end, m, f"{100*(eq[-1]-1):+.1f}", f"{r.mean()/r.std()*252**.5:.2f}", f"B {100*(np.prod(1+b)-1):+.1f} {b.mean()/b.std()*252**.5:.2f}")
