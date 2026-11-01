"""국면별 전환 — 중기(20거래일 겹침 트랜치). PREREG.md 설계."""
import os,sys,json,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
import engine as _E; _E.load.__defaults__=(os.path.join(BT,'panel_ohlc_long.csv'),)
import mid as M
from engine import prof,tstat,r5,folds
C=M.C; bi=M.bi; T=M.T
B=pd.Series(C[:,bi]).ffill(); BEAR=(B<B.rolling(60).mean()).values
VOL=M.E.vol(20)
def mlv(i):
    pl=M.top(M.MOM[150],i,n=30)
    if pl is None: return None
    v=VOL[i,pl]; q=pl[~np.isnan(v)]; return q[np.argsort(VOL[i,q],kind='stable')[:5]]
base,bdf=M.report('mom150 상시(기준)',M.base_sel,quiet=True)
def go(nm,sel,weight=None,R=BEAR):
    o,df=M.report(nm,sel,weight=weight,ref=bdf,quiet=True)
    j=df.merge(bdf[['date','port']],on='date',suffixes=('','_b')); d=(j.port-j.port_b).values
    di={x:k for k,x in enumerate(M.dates)}; reg=np.array([R[di[x]] for x in j.date])   # 수익일 기준 국면(보고용)
    o['bull']=d[~reg].mean(); o['bear']=d[reg].mean(); o['bull_t']=tstat(d[~reg]); o['bear_t']=tstat(d[reg])
    print(f"{nm:26s} CAGR {o['cagr']:6.1f} MDD {o['mdd']:6.1f} Sh {o['sh']:.2f} | Δ강세 {o['bull']:+.4f}(t{o['bull_t']:+.1f}) Δ약세 {o['bear']:+.4f}(t{o['bear_t']:+.1f}) fold[{', '.join('%+.3f'%x for x in o['df3'])}] -3일 {o['ddrop3']:+.4f}",flush=True)
    return o
print(f"기준 mom150: CAGR {base['cagr']:.1f} MDD {base['mdd']:.1f} Sh {base['sh']:.2f}")
res={'base':base}
res['MLV 상시(참고)']=go('MLV 상시(참고)',mlv)
res['S4 강세=mom150/약세=MLV']=go('S4 강세=mom150/약세=MLV',lambda i:mlv(i) if BEAR[i] else M.base_sel(i))
res['E3 mom150 + 약세 트랜치50%']=go('E3 mom150 + 약세 트랜치50%',M.base_sel,weight=lambda i:0.5 if BEAR[i] else 1.0)
res['E4 MLV + 약세 트랜치50%']=go('E4 MLV + 약세 트랜치50%',mlv,weight=lambda i:0.5 if BEAR[i] else 1.0)
rng=np.random.default_rng(7); sims={'S4':[],'E3':[]}
for _ in range(40):
    R=np.roll(BEAR,rng.integers(250,T-250))
    o,_d=M.report('x',lambda i,R=R:mlv(i) if R[i] else M.base_sel(i),quiet=True); sims['S4'].append(o['sh'])
    o,_d=M.report('x',M.base_sel,weight=lambda i,R=R:0.5 if R[i] else 1.0,quiet=True); sims['E3'].append(o['sh'])
for k,nm in [('S4','S4 강세=mom150/약세=MLV'),('E3','E3 mom150 + 약세 트랜치50%')]:
    res[nm]['placebo_p']=float(np.mean(np.array(sims[k])>=res[nm]['sh'])); res[nm]['placebo_mean']=float(np.mean(sims[k]))
    print(f"대조({k}) Sh 귀무 {np.mean(sims[k]):.2f} p={res[nm]['placebo_p']:.3f}")
json.dump(res,open(os.path.join(HERE,'res_mid.json'),'w'),default=float,indent=1,ensure_ascii=False)
