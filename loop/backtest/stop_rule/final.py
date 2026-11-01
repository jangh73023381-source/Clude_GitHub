import os,sys,numpy as np,pandas as pd
sys.path.insert(0,os.environ['HOME']+'/mnt/loop/references/scripts')
from universe_filters import eligible
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
df=df[df['name'].map(eligible)]
piv=lambda v: df.pivot_table(index='date',columns='code',values=v).sort_index().to_numpy(float)
cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
C=cl.to_numpy(float); O=piv('open'); Hh=piv('high'); L=piv('low')
ben=C[:,list(cl.columns).index('069500')]; ma60=pd.Series(ben).rolling(60).mean().to_numpy()
M150=C/np.roll(C,150,axis=0)-1
SIG=pd.DataFrame(C).pct_change().rolling(20).std().to_numpy()
HOLD=20; BAND=0.005
rows=[]
for i in range(200,len(C)-HOLD):
    row=M150[i]; ok=np.isfinite(row)&np.isfinite(C[i])&np.isfinite(C[i+HOLD])
    idx=np.where(ok)[0]
    if len(idx)<20: continue
    o=idx[np.argsort(-row[idx])][:30]; o=o[np.isfinite(SIG[i][o])]; p=o[np.argsort(SIG[i][o])][:5]
    C0=C[i][p]; CH=C[i+HOLD][p]
    peak=C0.copy(); done=np.zeros(len(p),bool); fill=np.zeros(len(p)); ct1=CH.copy()
    for t in range(1,HOLD+1):
        j=i+t; peak=np.maximum(peak,Hh[j][p]); stop=peak*(1-BAND)
        hit=(~done)&(L[j][p]<=stop)&np.isfinite(L[j][p])
        if hit.any():
            f=np.where(O[j][p]<stop,O[j][p],stop)
            fill[hit]=f[hit]; done[hit]=True
            nx=C[min(j+1,i+HOLD)][p]; ct1[hit]=nx[hit]
    bh=CH/C0
    st=np.where(done,0.5*(fill/C0)+0.5*bh,bh)                       # 재매수 안 함
    reb=np.where(done,0.5*(fill/C0)*(CH/ct1)+0.5*bh,bh)             # 익일 종가 재매수
    bounce=np.where(done&(ct1>fill),0.5*(fill/C0)*(CH/ct1)+0.5*bh,np.where(done,0.5*(fill/C0)+0.5*bh,bh))
    rows.append((np.mean(bh)-1,np.mean(st)-1,np.mean(reb)-1,np.mean(bounce)-1,
                 0.5*(np.mean(bh)-1), (0.5 if ben[i]<ma60[i] else 1.0)*(np.mean(bh)-1)))
A=np.array(rows)
names=['① 스톱 없이 20일 보유','② 0.5%스톱 절반매도·재매수 안함','③ 0.5%스톱 절반매도·익일종가 재매수',
       '④ 0.5%스톱 절반매도·반등확인 후 재매수','⑤ 스톱없이 처음부터 절반만 매수','⑥ 스톱없이 100%, 약세국면만 절반']
print(f"{'방식':38s} {'평균':>8s} {'중앙':>8s} {'하위5%':>8s} {'하위1%':>8s} {'변동성':>7s} {'①대비':>9s}")
for k,nm in enumerate(names):
    x=A[:,k]; d=x-A[:,0]
    print(f"{nm:38s} {100*x.mean():+7.3f}% {100*np.median(x):+7.3f}% {100*np.percentile(x,5):+7.2f}% {100*np.percentile(x,1):+7.2f}% {100*x.std():6.2f}% {100*d.mean():+8.3f}%p")
print(f"n={len(A)} 구간(시작일 매일·겹침)")
