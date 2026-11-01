import sys,numpy as np,pandas as pd
sys.path.insert(0,'/home/claude/w/loop/backtest/loop10_20260926')
from universe_filters import eligible
df0=pd.read_csv('/home/claude/w/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
print(df0[(df0.code=='441640')&(df0.date.between(20240401,20240410))])
df0=df0[df0['name'].map(eligible)]
CL=df0.pivot_table(index='date',columns='code',values='close').sort_index()
cl=CL.loc[:20260917]
C=cl.to_numpy(float); n,m=C.shape; codes=list(cl.columns); ben=C[:,codes.index('069500')]; dates=list(cl.index)
M150=C/np.roll(C,150,axis=0)-1
r=[];dd=[]
for i in range(200,n-1):
    row=M150[i]; ok=np.isfinite(row)&np.isfinite(C[i]); idx=np.where(ok)[0]
    t=idx[np.argsort(-row[idx])][:5]
    cur=[c for c in t if np.isfinite(C[i+1][c])]
    x=C[i+1][cur]/C[i][cur]-1
    r.append(float(np.mean(x))); dd.append(dates[i+1])
    if dates[i+1]==20240405: print('0405 picks',[codes[c] for c in t], x)
r=np.array(r); b=ben[201:n]/ben[200:n-1]-1; d=r-b
print(d.mean()*100,[100*x.mean() for x in np.array_split(d,3)])
