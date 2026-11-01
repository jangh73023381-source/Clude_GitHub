import pandas as pd, numpy as np, pickle, json
from kr_adapter import to_hist, prefilter, run_one
D=pickle.load(open('px.pkl','rb'))
k=pd.read_csv('/mnt/user-data/uploads/loop/backtest/krx_stock_panel.csv',dtype={'code':str})
names=k.drop_duplicates('code',keep='last').set_index('code')
# benchmark: 069500(~9/11) + KOSPI 시총가중 일수익(9/12~)
kp=k[k.market=='KOSPI'].copy(); kp=kp.sort_values(['code','date'])
kp['mc_prev']=kp.groupby('code').mktcap.shift(1)
seg=kp[kp.date>20260911].dropna(subset=['mc_prev'])
br=seg.groupby('date').apply(lambda g:(g.mc_prev*g.chg_pct).sum()/g.mc_prev.sum()/100)
bd,bo,bh,bl,bc,bv=[list(x) for x in D['069500']]
for dt,r in br.items():
    p=bc[-1]*(1+r); bd.append(dt); bo.append(p); bh.append(p); bl.append(p); bc.append(p); bv.append(0)
B=[np.array(x) for x in (bd,bo,bh,bl,bc,bv)]
asof=int(B[0][-1]); bench=to_hist(*B,len(B[0])-1)
out=[]; dropped=0
kk={c:g for c,g in k[k.date>20260911].groupby('code')}
ov=k[(k.date>=20260812)&(k.date<=20260911)]
ovm={c:g for c,g in ov.groupby('code')}
for code,(d,o,h,l,c,v) in D.items():
    if code=='069500' or code not in kk or int(d[-1])!=20260911: continue
    m=dict(zip(d.astype(int),c)); g=ovm.get(code)
    if g is None or not all(abs(m.get(int(r.date),np.nan)/r.close-1)<0.001 for r in g.itertuples()): dropped+=1; continue
    g2=kk[code].sort_values('date')
    if (g2.chg_pct.abs()>30).any(): dropped+=1; continue
    d2=np.concatenate([d,g2.date.values]); o2=np.concatenate([o,g2.open.values]); h2=np.concatenate([h,g2.high.values])
    l2=np.concatenate([l,g2.low.values]); c2=np.concatenate([c,g2.close.values]); v2=np.concatenate([v,g2.volume.values])
    if int(d2[-1])!=asof: continue
    e=len(d2)-1
    if not prefilter(c2,h2,l2,v2,e): continue
    r=run_one(code,d2,o2,h2,l2,c2,v2,e,bench)
    if r:
        r['name']=names.name.get(code,''); r['nh']=bool(c2[e]>=0.95*h2[e-249:e+1].max()); r['val20']=float((c2[e-19:e+1]*v2[e-19:e+1]).mean()/1e8)
        out.append(r)
res=pd.DataFrame(out).sort_values('score',ascending=False)
print('asof',asof,'이음매 탈락',dropped,'TT통과',len(res))
print(res.state.value_counts().to_string())
res.to_csv('live_vcp.csv',index=False)
act=res[res.state.isin(['Pre-breakout','Breakout'])]
print(act[['code','name','price','score','rating','valid_vcp','state','pattern','pivot','dist_pivot','stop','ncon','rs','nh','val20']].head(25).round(1).to_string())
print('STRICT:',res[res.valid_vcp & res.state.isin(['Pre-breakout','Breakout'])][['code','name']].values.tolist())
