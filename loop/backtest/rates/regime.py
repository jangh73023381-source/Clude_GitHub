# 미국 금리 국면 → 한국 ETF 섹터·스타일 선행 20거래일 (2026-10-03)
# 상태변수는 한국 D일 아침에 알 수 있는 '직전 미국 종가'만 쓴다(룩어헤드 없음). 수익은 D 종가→D+20 종가.
import pandas as pd, numpy as np, json, sys
P=pd.read_pickle('/tmp/rates_panel.pkl'); C,F20,S20,M20,sec=P['C'],P['F20'],P['S20'],P['M20'],P['sec']
def us(f):
    s=pd.read_csv(f,dtype={'date':str}).set_index('date')['close']; return s[~s.index.duplicated()]
tnx,irx,cl=us('TNX.csv'),us('IRX.csv'),us('CLF.csv')
D=C.index
def lag(s):  # 각 한국일 D에 대해 미국일 < D 인 마지막 값
    idx=np.searchsorted(s.index.values,D.values,side='left')-1
    return pd.Series(np.where(idx>=0,s.values[np.clip(idx,0,None)],np.nan),index=D)
t60=(tnx-tnx.shift(60)); slope=tnx-irx; s60=slope-slope.shift(60); o60=(cl/cl.shift(60)-1)*100
st=pd.DataFrame({'lvl':lag(tnx),'d60':lag(t60),'s60':lag(s60),'o60':lag(o60)})
st['trend']=np.select([st.d60>=0.25,st.d60<=-0.25],['RISE','FALL'],'FLAT')
st['sticky']=np.where(st.d60>-0.25,'NOTFALL','FALL')          # '쉽게 안 떨어진다' = 하락 국면이 아님
st['bear_steep']=(st.d60>=0.25)&(st.s60>=0.10)
K=F20['069500']
ok=K.notna()&st.d60.notna(); st=st[ok]; Dk=st.index
secs=[s for s,n in sec.value_counts().items() if n>=2 and s!='기타']
SF=pd.DataFrame({s:F20[sec[sec==s].index].loc[Dk].mean(axis=1) for s in secs})
EX=SF.sub(K.loc[Dk],axis=0)
# 스타일: 유니버스 내 σ20 하위 20% − 상위 20%, mom20 상위 20% − 하위 20% (선행 20일)
def spread(sig,f,lowfirst):
    out={}
    for d in Dk:
        a=pd.DataFrame({'s':sig.loc[d],'f':f.loc[d]}).dropna()
        if len(a)<30: continue
        q=a['s'].rank(pct=True)
        lo,hi=a.f[q<=0.2].mean(),a.f[q>0.8].mean()
        out[d]=lo-hi if lowfirst else hi-lo
    return pd.Series(out)
LV=spread(S20,F20,True); MOM=spread(M20,F20,False)
rng=np.random.default_rng(7)
def test(x, lab, a, b, nperm=500):
    x=x.dropna(); l=lab.loc[x.index]
    obs=x[l==a].mean()-x[l==b].mean()
    n=len(x); ks=rng.integers(250,n-250,nperm); null=[]
    for k in ks:
        ls=pd.Series(np.roll(l.values,k),index=l.index)
        null.append(x[ls==a].mean()-x[ls==b].mean())
    null=np.array(null); p=(np.abs(null)>=abs(obs)).mean()
    # 3분할 fold
    folds=[]
    for part in np.array_split(np.arange(n),3):
        xx,ll=x.iloc[part],l.iloc[part]
        folds.append(xx[ll==a].mean()-xx[ll==b].mean() if (ll==a).any() and (ll==b).any() else np.nan)
    return obs,p,folds
res={'dates':[Dk[0],Dk[-1],len(Dk)],'regime_days':st.trend.value_counts().to_dict(),
     'notfall_days':int((st.sticky=='NOTFALL').sum()),'bear_steep_days':int(st.bear_steep.sum())}
# 1) 시장(KODEX200) 절대수익
mk={}
for g,lab in [('trend',st.trend),('sticky',st.sticky)]:
    for v in lab.unique():
        k=K.loc[Dk][lab==v]; mk[f'{g}:{v}']=[round(k.mean(),2),round((k>0).mean()*100,1),int(len(k))]
bs=K.loc[Dk][st.bear_steep]; mk['bear_steep']=[round(bs.mean(),2),round((bs>0).mean()*100,1),int(len(bs))]
res['kodex200_fwd20']=mk
o,p,f=test(K.loc[Dk],st.sticky,'NOTFALL','FALL'); res['kodex200_notfall_minus_fall']=[round(o,2),round(p,3),[round(v,2) for v in f]]
# 2) 섹터 초과(vs KODEX200) — 하락하지 않는 국면 vs 하락 국면, 상승 국면 vs 하락 국면
rows=[]
for s in secs:
    x=EX[s]
    o1,p1,f1=test(x,st.sticky,'NOTFALL','FALL')
    o2,p2,f2=test(x,st.trend,'RISE','FALL')
    rows.append(dict(sector=s,n_etf=int((sec==s).sum()),
        ex_notfall=round(x[st.sticky=='NOTFALL'].mean(),2),ex_fall=round(x[st.sticky=='FALL'].mean(),2),
        ex_rise=round(x[st.trend=='RISE'].mean(),2),ex_bearsteep=round(x[st.bear_steep].mean(),2),
        diff_nf=round(o1,2),p_nf=round(p1,3),folds_nf=''.join('+' if v>0 else '-' for v in f1),
        diff_rf=round(o2,2),p_rf=round(p2,3),folds_rf=''.join('+' if v>0 else '-' for v in f2)))
T=pd.DataFrame(rows).sort_values('diff_nf',ascending=False); T.to_csv('sector_regime.csv',index=False)
# 3) 스타일
for nm_,x in [('lowvol_minus_highvol',LV),('mom_top_minus_bottom',MOM)]:
    o1,p1,f1=test(x,st.sticky,'NOTFALL','FALL'); o2,p2,f2=test(x,st.trend,'RISE','FALL')
    res[nm_]={'notfall':round(x[st.sticky.reindex(x.index)=='NOTFALL'].mean(),2),'fall':round(x[st.sticky.reindex(x.index)=='FALL'].mean(),2),
              'rise':round(x[st.trend.reindex(x.index)=='RISE'].mean(),2),'bear_steep':round(x[st.bear_steep.reindex(x.index)].mean(),2),
              'nf_minus_fall':[round(o1,2),round(p1,3),[round(v,2) for v in f1]],'rise_minus_fall':[round(o2,2),round(p2,3),[round(v,2) for v in f2]]}
# 4) 현재 상태(오늘까지 미국 데이터)
res['now']={'tnx':round(tnx.iloc[-1],3),'d60':round(t60.iloc[-1],3),'slope_d60':round(s60.iloc[-1],3),'oil_60d%':round(o60.iloc[-1],1),'asof':tnx.index[-1]}
json.dump(res,open('regime_summary.json','w'),ensure_ascii=False,indent=1,default=str)
print(json.dumps(res,ensure_ascii=False,indent=1,default=str)); print(T.to_string(index=False))
