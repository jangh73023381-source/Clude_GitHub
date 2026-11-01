import os,pickle,sys,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,B,eg,tr,MA20,dates,secs=d['C'],d['bench'],d['eg'],d['trend'],d['MA20'],d['dates'],d['secs']; N=C.shape[1]
Cf=pd.DataFrame(C.T).ffill().values.T
sig=pd.read_pickle(os.path.join(HERE,'_sig20.pkl'))
score={(r.m,r.t):r.score for r in sig.itertuples()}
START=60
def sim(K=5, hold=20, extend=False, min_score=None, sector_rep=False, entries=None, seed=0, after20_ma20=False, t0=START, t1=N-1):
    """K 슬롯, 동일가중(equity/K), 진입=신호일 종가, 청산=hold일 후 종가.
    extend: 보유 중 재신호 시 청산일을 재신호+hold 로 연장. after20_ma20: 만기 후 MA20 위면 계속 보유(2일 연속 이탈 시 청산)."""
    if entries is None:
        E={}
        for m,t in zip(*np.where(eg)):
            if t<START: continue
            E.setdefault(t,[]).append(m)
    else: E=entries
    cash=1.0; pos={}  # m -> dict(units, exit, below)
    eq=np.zeros(N); eq[:t0]=1.0
    ntr=0; rets=[]; occ=0
    for t in range(t0,t1+1):
        # 청산
        for m in list(pos):
            p=pos[m]; sell=False
            if after20_ma20:
                if t>=p['exit']:
                    p['below']=p['below']+1 if Cf[m,t]<MA20[m,t] else 0
                    if p['below']>=2 or t-p['t0']>=120: sell=True
            elif t>=p['exit']: sell=True
            if sell:
                cash+=p['units']*Cf[m,t]; rets.append(Cf[m,t]/p['entry']-1); del pos[m]
        # 재신호 연장
        cands=[m for m in E.get(t,[]) if not np.isnan(Cf[m,t])]
        if extend:
            for m in cands:
                if m in pos: pos[m]['exit']=t+hold
        cands=[m for m in cands if m not in pos]
        if min_score is not None: cands=[m for m in cands if score.get((m,t),-9)>=min_score]
        cands.sort(key=lambda m:-score.get((m,t),-9))
        if sector_rep and len(cands)>K-len(pos):
            seen=set(); c2=[]
            for m in cands:
                if secs[m] in seen: continue
                seen.add(secs[m]); c2.append(m)
            cands=c2+[m for m in cands if m not in c2]
        equity=cash+sum(p['units']*Cf[m,t] for m,p in pos.items())
        for m in cands:
            if len(pos)>=K or cash<=1e-9: break
            amt=min(cash,equity/K); pos[m]=dict(units=amt/Cf[m,t],exit=t+hold,entry=Cf[m,t],below=0,t0=t); cash-=amt; ntr+=1
        eq[t]=cash+sum(p['units']*Cf[m,t] for m,p in pos.items()); occ+=len(pos)
    return eq,ntr,np.array(rets),occ/(t1-t0+1)
def stats(eq,t0=START,t1=N-1):
    e=eq[t0:t1+1]; r=np.diff(e)/e[:-1]; yrs=(t1-t0)/245
    cagr=(e[-1]/e[0])**(1/yrs)-1; mdd=(e/np.maximum.accumulate(e)-1).min(); sh=r.mean()/r.std()*np.sqrt(245) if r.std()>0 else 0
    return e[-1]/e[0]-1,cagr,mdd,sh
Bf=pd.Series(B).ffill().values
if __name__=='__main__':
    tot,cagr,mdd,sh=stats(Bf/Bf[START])
    print(f'{"KODEX200 B&H":34s} tot {tot*100:7.1f}% cagr {cagr*100:5.1f}% mdd {mdd*100:6.1f}% sharpe {sh:4.2f}')
    cfgs=[('K5 fix20',dict(K=5)),('K5 fix20 +재신호연장',dict(K=5,extend=True)),('K5 fix20 +연장 +score>-1.33',dict(K=5,extend=True,min_score=-1.33)),
          ('K5 fix20 +연장 +score>-0.79',dict(K=5,extend=True,min_score=-0.79)),('K5 fix20 +연장 +섹터대표',dict(K=5,extend=True,sector_rep=True)),
          ('K5 만기후 MA20추종',dict(K=5,after20_ma20=True)),('K5 fix40',dict(K=5,hold=40)),('K5 fix60',dict(K=5,hold=60)),
          ('K10 fix20',dict(K=10)),('K10 fix20 +연장',dict(K=10,extend=True)),('K20 fix20 +연장',dict(K=20,extend=True)),('K3 fix20 +연장',dict(K=3,extend=True))]
    out={}
    for nm,kw in cfgs:
        eq,ntr,rets,occ=sim(**kw); tot,cagr,mdd,sh=stats(eq); out[nm]=eq
        # fold 3
        f=[]
        for a,b in zip([START,START+(N-START)//3,START+2*(N-START)//3],[START+(N-START)//3,START+2*(N-START)//3,N-1]):
            e2,_,_,_=sim(t0=a,t1=b,**kw); bt=Bf[b]/Bf[a]-1; f.append(e2[b]/e2[a]-1-bt)
        print(f'{nm:34s} tot {tot*100:7.1f}% cagr {cagr*100:5.1f}% mdd {mdd*100:6.1f}% sharpe {sh:4.2f} trades {ntr:4d} avg {rets.mean()*100:5.2f}% win {(rets>0).mean()*100:4.1f} occ {occ:4.1f} fold(vsB) {"/".join(f"{x*100:+.0f}" for x in f)}')
    # B1 랜덤 5슬롯 (추세일 무작위 진입) 5회 평균
    rng=np.random.default_rng(0); res=[]
    for s in range(5):
        E={}
        for m,t in zip(*np.where(tr&~eg)):
            if t>=START and rng.random()<0.04: E.setdefault(t,[]).append(m)
        eq,ntr,rets,occ=sim(K=5,entries=E); res.append(stats(eq))
    r=np.array(res).mean(0); print(f'{"B1 무작위 K5 fix20 (5회평균)":34s} tot {r[0]*100:7.1f}% cagr {r[1]*100:5.1f}% mdd {r[2]*100:6.1f}% sharpe {r[3]:4.2f}')
    pickle.dump(out,open(os.path.join(HERE,'_eq.pkl'),'wb'))
