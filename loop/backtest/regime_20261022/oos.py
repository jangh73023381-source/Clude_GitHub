"""표본 밖(7년 패널 이후 2026-09-23~) — 2년 패널로 별도 계산(이어붙이지 않음). 판정 미사용·보고 전용."""
import os,sys,json,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
import engine as _E; PANEL=os.path.join(BT,'panel_ohlc_2y.csv'); _E.load.__defaults__=(PANEL,)
import mid as M
from engine import prof
E=M.E; C=M.C; bi=M.bi; dates=M.dates
lag=lambda X,k:np.vstack([np.full((k,X.shape[1]),np.nan),X[:-k]])
B=pd.Series(C[:,bi]).ffill(); BEAR=(B<B.rolling(60).mean()).values
mom60=(C/lag(C,60)-1)*100; VOL=E.vol(20)
lv=lambda i,pl:E.sel_lv(i,pl); mom=lambda i,pl:pl[:5]
minvol=lambda i,pl:(lambda idx:idx[np.argsort(VOL[i,idx])[:5]])(np.where(E.ok[i]&~np.isnan(VOL[i]))[0])
lv60=lambda i,pl:E.sel_lv(i,E.pool(i,n=30,score=mom60))
sw=lambda bu,be:(lambda i,pl:(be if BEAR[i] else bu)(i,pl))
i0=dates.index('20260922')
print('OOS 선정일',dates[i0],'~',dates[-2],' 약세 판정 일수',int(BEAR[i0:-1].sum()),'/',len(dates)-1-i0, ' 첫 약세일', next((dates[k] for k in range(i0,len(dates)) if BEAR[k]),None))
out={}
for nm,sel,w in [('LV(현행)',lv,1),('MOM 상시',mom,1),('S1 강세MOM/약세LV',sw(mom,lv),1),('S2 약세=최소변동',sw(lv,minvol),1),('S3 약세=mom60 LV',sw(lv,lv60),1),('E1 약세 비중50%',lv,.5),('E2 약세 현금',lv,0)]:
    df=E.run(sel,start=i0-1); df=df[df.i>=i0]
    for k in ('A','OO'):
        df[k]=np.where([BEAR[i] for i in df.i],df[k]*w,df[k])
    oo=df.OO.dropna(); a=df.A.dropna()
    out[nm]=dict(A=float((np.prod(1+a/100)-1)*100),OO=float((np.prod(1+oo/100)-1)*100),n=len(df))
    print(f"{nm:18s} 누적 A {out[nm]['A']:+6.2f}%  OO {out[nm]['OO']:+6.2f}%  (n={len(df)})")
b=E.run(lv,start=i0-1); b=b[b.i>=i0]; print(f"KODEX200 A {((np.prod(1+b.bA/100)-1)*100):+.2f}%")
# 중기 트랜치
VOLm=VOL
def mlv(i):
    pl=M.top(M.MOM[150],i,n=30)
    if pl is None: return None
    q=pl[~np.isnan(VOLm[i,pl])]; return q[np.argsort(VOLm[i,q],kind='stable')[:5]]
for nm,sel,wt in [('mom150',M.base_sel,None),('MLV',mlv,None),('S4 약세=MLV',lambda i:mlv(i) if BEAR[i] else M.base_sel(i),None),('E3 mom150 약세50%',M.base_sel,lambda i:0.5 if BEAR[i] else 1.0)]:
    df=M.tranche(sel,weight=wt); df=df[df.date>'20260922']
    out['mid_'+nm]=float((np.prod(1+df.port/100)-1)*100)
    print(f"중기 {nm:18s} 누적 {out['mid_'+nm]:+6.2f}% (n={len(df)})  KODEX {((np.prod(1+df.bench/100)-1)*100):+.2f}%")
json.dump(out,open(os.path.join(HERE,'res_oos.json'),'w'),indent=1,ensure_ascii=False)
