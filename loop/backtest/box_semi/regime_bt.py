import itertools
from regime import *
rng=np.random.default_rng(11)
SEMI={'091160':'KODEX반도체','396500':'TIGER반도체TOP10','395160':'KODEX AI반도체TOP2+'}
Kc=K.close
def regime(W=60,wp=0.3,sl=0.02):
    w=Kc.rolling(W).max()/Kc.rolling(W).min()-1;wpct=w.expanding(250).rank(pct=True)
    ma=Kc.rolling(W).mean();slope=(ma/ma.shift(20)-1).abs()
    return ((wpct<=wp)&(slope<sl))
def stats(r):
    r=r.fillna(0);eq=(1+r).cumprod();yrs=len(r)/250
    return (eq.iloc[-1]**(1/yrs)-1)*100, (r.mean()/r.std()*np.sqrt(250) if r.std()>0 else 0), (eq/eq.cummax()-1).min()*100
def run(S,reg,L=20,lo=.2,hi=.8,exit_off=True,stop=None,src='K'):
    idx=S.index.intersection(Kc.index);idx=idx[idx>=20200401]
    ref=(Kc if src=='K' else S.close).reindex(idx)
    H=ref.rolling(L,min_periods=L).max();Lo=ref.rolling(L,min_periods=L).min()
    # 채널은 워밍업 포함 전체에서 계산
    refall=(Kc if src=='K' else S.close);Hall=refall.rolling(L).max().reindex(idx);Lall=refall.rolling(L).min().reindex(idx)
    pos=((ref-Lall)/(Hall-Lall)).values;rg=reg.reindex(idx).fillna(False).values
    c=S.close.reindex(idx).values;o=S.open.reindex(idx).values;n=len(idx)
    r=np.zeros(n);tr=[];inp=False
    for t in range(n-1):
        if not inp:
            if rg[t] and pos[t]<=lo: inp=True;a=t+1;bl=Lall.values[t]
        else:
            ex=pos[t]>=hi or (exit_off and not rg[t]) or (stop is not None and ref.values[t]<bl*(1-stop))
            if ex: tr.append((a,t+1));inp=False
    if inp: tr.append((a,n-1))
    for a,b in tr:
        r[a]+=c[a]/o[a]-1
        for t in range(a+1,b): r[t]+=c[t]/c[t-1]-1
        if b>a: r[b]+=o[b]/c[b-1]-1
    rets=[ (o[b] if b<n-1 else c[b])/o[a]-1 for a,b in tr]
    return pd.Series(r,index=idx),tr,rets,idx,rg
def episodes(reg):
    x=reg.reindex(K.index[K.index>=20200401]).fillna(False).astype(int)
    return int(((x.diff()==1)).sum()+x.iloc[0])
def randctl(S,idx,rg,tr,reps=500):
    c=S.close.reindex(idx).values;o=S.open.reindex(idx).values;n=len(idx)
    ok=np.where(rg[:-1])[0];durs=[b-a for a,b in tr];out=[]
    for _ in range(reps):
        tot=[]
        for dlen in durs:
            a=rng.choice(ok)+1;b=min(a+dlen,n-1);tot.append((o[b] if b<n-1 else c[b])/o[a]-1)
        out.append(np.mean(tot))
    return np.array(out)
if __name__=='__main__':
    base=regime()
    print('기준 국면(60일폭 하위30% & MA60 20일 기울기<2%): 해당일',round(base.reindex(K.index[K.index>=20200401]).mean()*100,1),'% · 독립 에피소드',episodes(base))
    x=base.reindex(K.index[K.index>=20200401]).fillna(False)
    starts=x[(x.astype(int).diff()==1)].index.tolist();print('에피소드 시작일:',starts)
    for code,name in SEMI.items():
        S=get(code);bh=S.close.pct_change().reindex(S.index[S.index>=max(20200401,S.index[0])])
        for src in ['K','S']:
            r,tr,rets,idx,rg=run(S,base,src=src)
            ctl=randctl(S,idx,rg,tr)
            print(f'\n[{name}] 채널기준={"코스피" if src=="K" else "자기"} · 거래 {len(tr)} · 건당 평균 {np.mean(rets)*100:+.2f}% · 중앙 {np.median(rets)*100:+.2f}% · 승률 {np.mean(np.array(rets)>0)*100:.0f}% · 평균보유 {np.mean([b-a for a,b in tr]):.1f}일')
            print(f'   국면 안 무작위 진입(같은 보유일수) 500회: 건당 평균 중앙 {np.median(ctl)*100:+.2f}% · p(무작위≥실제)={np.mean(ctl>=np.mean(rets)):.3f}')
            s=stats(r);b=stats(bh.reindex(idx));print(f'   전체기간 CAGR {s[0]:.1f}/Sh {s[1]:.2f}/MDD {s[2]:.1f} vs B&H {b[0]:.1f}/{b[1]:.2f}/{b[2]:.1f} · 노출 {np.mean([1 if any(a<=t<b for a,b in tr) else 0 for t in range(len(idx))])*100:.1f}%')
            print('   거래:',[(int(idx[a]),b-a,round(x_*100,1)) for (a,b),x_ in zip(tr,rets)])
