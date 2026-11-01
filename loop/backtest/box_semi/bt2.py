import pandas as pd, numpy as np, itertools, json, sys
rng=np.random.default_rng(7)
df=pd.read_csv('../panel_ohlc_long.csv',dtype={'code':str})
codes={'091160':'KODEX반도체','091230':'TIGER반도체','396500':'TIGER반도체TOP10','395160':'KODEX AI반도체TOP2+','069500':'KODEX200','091170':'KODEX은행'}
P={c:df[df.code==c].set_index('date').sort_index() for c in codes}
k2c=P['069500'].close
def stats(r):
    r=r.fillna(0); eq=(1+r).cumprod(); yrs=len(r)/250
    cagr=eq.iloc[-1]**(1/yrs)-1; sh=r.mean()/r.std()*np.sqrt(250) if r.std()>0 else 0
    mdd=(eq/eq.cummax()-1).min(); return cagr*100,sh,mdd*100
def run(d,N,lo,hi,stop,gate=None,cost=0.0):
    c=d.close.values;o=d.open.values;n=len(c)
    H=d.close.rolling(N).max().values;L=d.close.rolling(N).min().values
    pos=np.zeros(n);inpos=False;trades=[];ent=None;boxlow=None
    # signal at close t, execute open t+1. pos[t]=holding during (close t-1 -> close t)
    r=np.zeros(n)
    for t in range(N,n-1):
        p=(c[t]-L[t])/(H[t]-L[t]) if H[t]>L[t] else .5
        if not inpos:
            if p<=lo and (gate is None or gate[t]):
                inpos=True;ent=t+1;boxlow=L[t];px_in=o[t+1]
        else:
            exit_=p>=hi or (stop is not None and c[t]<boxlow*(1-stop))
            if exit_:
                trades.append((ent,t+1,o[t+1]/px_in-1-cost));inpos=False
    # daily returns: from entry open to exit open
    held=np.zeros(n,bool)
    tr=list(trades)+([(ent,n-1,c[-1]/px_in-1)] if inpos else [])
    for a,b,_ in tr:
        # day a: open->close ; days a+1..b-1 close->close ; day b: prev close -> open
        r[a]+=c[a]/o[a]-1
        for t in range(a+1,b): r[t]+=c[t]/c[t-1]-1
        if b<n and b>a: r[b]+=o[b]/c[b-1]-1
        held[a:b]=True
        if cost: r[a]-=cost
    return pd.Series(r,index=d.index),tr,held.mean()
def randctl(d,tr,reps=300):
    c=d.close.values;o=d.open.values;n=len(c);durs=[b-a for a,b,_ in tr];res=[]
    for _ in range(reps):
        r=np.zeros(n);ok=True;t0=60;used=np.zeros(n,bool)
        for L_ in rng.permutation(durs):
            for _try in range(50):
                a=rng.integers(60,n-L_-1)
                if not used[a-1:a+L_+1].any(): break
            used[a:a+L_]=True;b=a+L_
            r[a]+=c[a]/o[a]-1
            for t in range(a+1,b): r[t]+=c[t]/c[t-1]-1
            r[b]+=o[b]/c[b-1]-1
        res.append(stats(pd.Series(r)))
    return np.array(res)
rows=[]
grid=list(itertools.product([20,40,60,120],[0.1,0.2,0.3],[0.7,0.8,0.9],[None,0.05,0.10]))
for code in codes:
    d=P[code];bh=stats(d.close.pct_change())
    for N,lo,hi,stop in grid:
        r,tr,exp=run(d,N,lo,hi,stop)
        cg,sh,md=stats(r);w=[x[2] for x in tr]
        rows.append(dict(code=codes[code],N=N,lo=lo,hi=hi,stop=stop,cagr=cg,sharpe=sh,mdd=md,ntr=len(tr),win=np.mean(np.array(w)>0)*100 if w else np.nan,avgtr=np.mean(w)*100 if w else np.nan,exp=exp*100,bh_cagr=bh[0],bh_sh=bh[1],bh_mdd=bh[2]))
R=pd.DataFrame(rows);R.to_csv('grid.csv',index=False)
pd.set_option('display.width',250);pd.set_option('display.max_columns',30)
g=R.groupby('code').agg(bh_cagr=('bh_cagr','first'),bh_sh=('bh_sh','first'),bh_mdd=('bh_mdd','first'),
  med_cagr=('cagr','median'),best_cagr=('cagr','max'),med_sh=('sharpe','median'),best_sh=('sharpe','max'),
  share_beat_sh=('sharpe',lambda s:(s>R.loc[s.index,'bh_sh']).mean()*100),share_beat_cagr=('cagr',lambda s:(s>R.loc[s.index,'bh_cagr']).mean()*100),med_exp=('exp','median'),med_mdd=('mdd','median'))
print(g.round(2).to_string())
# 기준안: N=60, 0.2/0.8, no stop
print('\n기준안 N60 0.2/0.8 손절없음')
print(R[(R.N==60)&(R.lo==.2)&(R.hi==.8)&(R.stop.isna())].round(2).to_string())
# 무작위 대조군 (기준안, 주력 2종)
for code in ['091160','396500']:
    d=P[code];r,tr,exp=run(d,60,.2,.8,None);obs=stats(r);ctl=randctl(d,tr)
    print(f'\n{codes[code]} 무작위타이밍 대조군(같은 거래수·보유일수 300회): 실제 CAGR {obs[0]:.1f} Sh {obs[1]:.2f} MDD {obs[2]:.1f} | 무작위 중앙 CAGR {np.median(ctl[:,0]):.1f} Sh {np.median(ctl[:,1]):.2f} MDD {np.median(ctl[:,2]):.1f} | p(무작위Sh>=실제)={np.mean(ctl[:,1]>=obs[1]):.3f}')
    # 파라미터 그리드 전체에 대해 무작위 대조군 Sharpe 대비 (빠른 30회)
# folds
print('\nfold (KODEX반도체, 기준안 vs B&H, CAGR/Sharpe)')
d=P['091160'];r,tr,_=run(d,60,.2,.8,None);bhr=d.close.pct_change()
for a,b in [(20190401,20211231),(20220101,20240630),(20240701,20261231)]:
    m=(r.index>=a)&(r.index<=b);s1=stats(r[m]);s2=stats(bhr[m])
    print(a,b,'전략',np.round(s1,2),'B&H',np.round(s2,2))
d=P['396500'];r,tr,_=run(d,60,.2,.8,None);bhr=d.close.pct_change()
print('TIGER반도체TOP10')
for a,b in [(20210101,20231231),(20240101,20250630),(20250701,20261231)]:
    m=(r.index>=a)&(r.index<=b);s1=stats(r[m]);s2=stats(bhr[m])
    print(a,b,'전략',np.round(s1,2),'B&H',np.round(s2,2))
# 거래 목록(기준안 TOP10)
print('\nTOP10 기준안 거래'); 
for a,b,x in tr: print(d.index[a],d.index[min(b,len(d)-1)],b-a,'일',f'{x*100:+.1f}%')
