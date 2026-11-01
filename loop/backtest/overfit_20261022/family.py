"""[6-1] 선정 방법 변형 가족(루프에서 실제로 시도한 축 위주)의 일별 OO 수익 행렬 생성 → fam_OO.csv. 7년 ETF 패널."""
import os,sys,numpy as np,pandas as pd,time
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
import engine as _E; P7=os.path.join(BT,'panel_ohlc_long.csv'); _E.load.__defaults__=(P7,)
from engine import load,Engine
P,dates,codes,names=load(P7); E=Engine(P,dates,codes,names); C=E.C
lag=lambda X,k:np.vstack([np.full((k,X.shape[1]),np.nan),X[:-k]])
MOM={k:(C/lag(C,k)-1)*100 for k in (5,10,20,60,120)}
V={k:E.vol(k) for k in (10,20,40,60)}
def lvsel(pool,k,n,score):
    def f(i,pl):
        p=E.pool(i,n=pool,score=MOM[score]); v=V[k][i,p]; m=~np.isnan(v)
        if m.sum()<n: return p[:n]
        return p[m][np.argsort(v[m],kind='stable')[:n]]
    return f
def momsel(score,n):
    return lambda i,pl:E.pool(i,n=n,score=MOM[score])
fam={}
t=time.time()
for pool in (10,20,30,50):
    for k in (10,20,40,60):
        fam[f'LV p{pool} σ{k} n5']=lvsel(pool,k,5,20)
for n in (3,7,10): fam[f'LV p30 σ20 n{n}']=lvsel(30,20,n,20)
for s in (5,10,60,120): fam[f'LV mom{s}pool σ20']=lvsel(30,20,5,s)
for s in (5,10,20,60,120): fam[f'MOM{s} top5']=momsel(s,5)
fam['MOM20 top10']=momsel(20,10)
out={}
for nm,sel in fam.items():
    df=E.run(sel,start=130)
    if len(df)==0: print('빈 결과',nm); continue
    out[nm]=pd.Series(df.OO.values,index=df.date.values)
M=pd.DataFrame(out).dropna(); M.to_csv(os.path.join(HERE,'fam_OO.csv')); print(M.shape,round(time.time()-t),'s')
