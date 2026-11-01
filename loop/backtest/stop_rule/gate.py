import os,sys,numpy as np,pandas as pd
sys.path.insert(0,os.environ['HOME']+'/mnt/loop/references/scripts')
from universe_filters import eligible
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
df=df[df['name'].map(eligible)]
cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
C=cl.to_numpy(float); ben=C[:,list(cl.columns).index('069500')]
ma60=pd.Series(ben).rolling(60).mean().to_numpy()
M150=C/np.roll(C,150,axis=0)-1
SIG=pd.DataFrame(C).pct_change().rolling(20).std().to_numpy()
H=20; rs=[];bear=[]
for i in range(200,len(C)-H):
    row=M150[i]; ok=np.isfinite(row)&np.isfinite(C[i])&np.isfinite(C[i+H])
    idx=np.where(ok)[0]
    if len(idx)<20: continue
    o=idx[np.argsort(-row[idx])][:30]; o=o[np.isfinite(SIG[i][o])]; p=o[np.argsort(SIG[i][o])][:5]
    rs.append(float(np.mean(C[i+H][p]/C[i][p]-1))); bear.append(ben[i]<ma60[i])
r=np.array(rs); bear=np.array(bear)
g=np.where(bear,0.5*r,r)
for nm,x in [('항상 100%',r),('약세국면(KODEX200<MA60) 비중 1/2',g)]:
    print(f"{nm:34s} 평균 {100*x.mean():+.3f}%  하위5% {100*np.percentile(x,5):+.2f}%  하위1% {100*np.percentile(x,1):+.2f}%  변동성 {100*x.std():.2f}%")
print(f"약세국면 비중 {100*bear.mean():.1f}%의 날  평균 {100*r[bear].mean():+.3f}%  vs 정상 {100*r[~bear].mean():+.3f}%")
