"""축8 — Rule NHM(신고가 근접)을 MLV(중기 저변동 정렬) 위에서 재판정. 20거래일 겹침 트랜치(mid.py 틀 그대로)."""
import os,sys,json,numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
os.chdir(os.path.join(BT,'loop10_20260926'))
import engine as _E; _E.load.__defaults__=(os.path.join(BT,'panel_ohlc_long.csv'),)
import mid as M
from engine import prof,tstat,r5,folds
C=M.C; Hh=M.P['high']; import pandas as pd
H250=pd.DataFrame(Hh).rolling(250,min_periods=200).max().values
VOL=M.E.vol(20)
def mlv(i,mask=None,fill=True):
    pl=M.top(M.MOM[150],i,n=30)
    if pl is None: return None
    q=pl if mask is None else pl[mask[i,pl]]
    v=VOL[i,q]; q=q[~np.isnan(v)]; v=v[~np.isnan(v)]
    pk=list(q[np.argsort(v,kind='stable')][:5])
    if len(pk)<5 and fill and mask is not None:
        rest=[x for x in pl[np.argsort(VOL[i,pl],kind='stable')] if x not in pk and not np.isnan(VOL[i,x])]
        pk+=rest[:5-len(pk)]
    return np.array(pk) if pk else None
mom,_=M.report('mom150 상위5(Rule MM)',M.base_sel)
base,bdf=M.report('MLV(기준)',lambda i:mlv(i),ref=_ )
res={'mom150':mom,'MLV':base}
for k in (0.90,0.95,0.97):
    mk=C>=H250*k
    for fill in (False,True):
        nm=f'MLV ∩ C>=H250x{k} {"부족분 MLV로 채움" if fill else "부족분 현금"}'
        o,_d=M.report(nm,lambda i,mk=mk,fill=fill:mlv(i,mk,fill),ref=bdf); res[nm]=o
# 플라시보: 0.95 현금형과 같은 통과율의 무작위 마스크 30회
mk=C>=H250*0.95; rate=np.nanmean(mk[M.START:]); rng=np.random.default_rng(5); sims=[]
for s in range(30):
    rm=rng.random(C.shape)<rate
    o,_d=M.report('rnd',lambda i:mlv(i,rm,False),ref=bdf,quiet=True); sims.append((o['sh'],o['mdd'],o['cagr']))
sims=np.array(sims); t=res['MLV ∩ C>=H250x0.95 부족분 현금']
print(f"플라시보(통과율 {rate:.2f}) Sh 귀무 {sims[:,0].mean():.2f} p={np.mean(sims[:,0]>=t['sh']):.3f} | MDD 귀무 {sims[:,1].mean():.1f} p={np.mean(sims[:,1]>=t['mdd']):.3f} | CAGR 귀무 {sims[:,2].mean():.1f} p={np.mean(sims[:,2]>=t['cagr']):.3f}")
res['placebo']=sims.tolist()
json.dump(res,open(os.path.join(HERE,'res_mid.json'),'w'),default=float,indent=1)
