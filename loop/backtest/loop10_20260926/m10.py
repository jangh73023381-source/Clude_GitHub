from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
def ext_run(K, H=20, score=MOM[150], maxext=99):
    S=np.zeros(T); Nn=np.zeros(T); holds=[]
    rank_cache={}
    def inK(i,c):
        if i not in rank_cache:
            p=top(score,i,K) if K>0 else None
            rank_cache[i]=set() if p is None else set(p.tolist())
        return c in rank_cache[i]
    for s in range(START,T-1):
        p=top(score,s)
        if p is None: continue
        for c in p:
            end=s+H; n=0
            while end<T-1 and n<maxext and K>0 and inK(end,c):
                end+=H; n+=1
            end=min(end,T-1)
            r=Rd[s+1:end+1,c]; ok=~np.isnan(r)
            S[s+1:end+1][ok]+=r[ok]; Nn[s+1:end+1][ok]+=1
            holds.append(end-s)
    port=np.where(Nn>0,S/np.maximum(Nn,1),np.nan)
    df=pd.DataFrame({'date':dates,'port':port,'bench':Rd[:,bi]})
    df=df.iloc[START+H:].dropna().reset_index(drop=True); df['ex']=df.port-df.bench
    return df, np.array(holds)
def show(nm,df,holds,ref):
    p=prof(df.port); j=df.merge(ref[['date','port']],on='date',suffixes=('','_r')); d=j.port-j.port_r; pr=prof(j.port_r); rr=r5(d.values)
    print(f"[{nm}] CAGR{p['cagr']:+6.1f} MDD{p['mdd']:6.1f} Sh{p['sharpe']:5.2f} 평균보유{holds.mean():.1f}일 중앙{np.median(holds):.0f} 최장{holds.max()} | ΔCAGR{p['cagr']-pr['cagr']:+5.1f} ΔMDD{p['mdd']-pr['mdd']:+5.1f} ΔSh{p['sharpe']-pr['sharpe']:+.2f} Δ일{d.mean():+.4f} t{tstat(d):+.2f} fold{['%+.3f'%x for x in folds(d.values)]} 중앙{rr['median']:+.4f} 상위3제거{rr['drop3']:+.4f}")
    return dict(name=nm,cagr=p['cagr'],mdd=p['mdd'],sh=p['sharpe'],dcagr=p['cagr']-pr['cagr'],dmdd=p['mdd']-pr['mdd'],dsh=p['sharpe']-pr['sharpe'],dm=d.mean(),dt=tstat(d),df3=folds(d.values),hold=holds.mean())
b0,h0=ext_run(0); show('기준 재현(연장 없음, 20일 고정)',b0,h0,base)
res=[]
for K in (5,10,20,30):
    df,h=ext_run(K); res.append(show(f'20일 후 mom150 상위{K} 안이면 20일 연장',df,h,b0))
pickle.dump(res,open('m10.pkl','wb'))
