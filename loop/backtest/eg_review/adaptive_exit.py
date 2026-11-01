"""적응형 청산 탐색 — 20일 일률 vs 변동성·목표가·조건소멸·분배·점수별 보유 등. 신호 단위 + 5슬롯 재현."""
import os,pickle,sys,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
O,H,L,C,V,MA20,MA60,VA,dates,B,eg=[d[k] for k in ['O','H','L','C','V','MA20','MA60','VA','dates','bench','eg']]; N=len(dates)
Cf=pd.DataFrame(C.T).ffill().values.T; Bf=pd.Series(B).ffill().values
def sh(x,k):
    y=np.full_like(x,np.nan); y[:,k:]=x[:,:-k]; return y
TR=np.maximum(H-L,np.maximum(abs(H-sh(C,1)),abs(L-sh(C,1)))); ATR=pd.DataFrame(TR.T).rolling(14).mean().values.T
MA10=pd.DataFrame(Cf.T).rolling(10).mean().values.T
sig=pd.read_pickle(os.path.join(HERE,'_sig20.pkl')); score={(r.m,r.t):r.score for r in sig.itertuples()}
import portfolio as P
def exit_idx(m,t,rule,p=None):
    c=Cf[m]; e=c[t]; a=ATR[m,t] if not np.isnan(ATR[m,t]) else e*0.02; hi=e; last=min(t+120,N-1); below=0
    sc=score.get((m,t),0)
    for j in range(t+1,last+1):
        h=j-t; hi=max(hi,c[j]); r=c[j]/e-1
        if rule=='fix20' and h>=20: return j
        if rule=='fix_score':   # 점수 상위(>0.5) 30일, 중간 20일, 하위(<-1) 10일
            hd=30 if sc>0.5 else (10 if sc<-1 else 20)
            if h>=hd: return j
        if rule=='tp_atr' and (c[j]>=e+p*a or h>=20): return j            # 목표가 p×ATR 또는 20일
        if rule=='tp_pct' and (r>=p or h>=20): return j                    # 목표 수익률 p 또는 20일
        if rule=='tp_pct_cap40' and (r>=p or h>=40): return j
        if rule=='chand' and (c[j]<=hi-p*a): return j                      # 샹들리에 p×ATR 트레일링(120일 상한)
        if rule=='chand_cap20' and (c[j]<=hi-p*a or h>=20): return j
        if rule=='chand_cap40' and (c[j]<=hi-p*a or h>=40): return j
        if rule=='chand_after20':                                         # 20일까지 고정, 이후 샹들리에
            if h>=20 and c[j]<=hi-p*a: return j
        if rule=='ma20_down' and (MA20[m,j]<MA20[m,j-1] or h>=40): return j  # MA20 하락 전환(신호 전제 소멸) 또는 40일
        if rule=='ma20_down_min10' and h>=10 and (MA20[m,j]<MA20[m,j-1] or h>=40): return j
        if rule=='ma20_down_after20' and h>=20 and (MA20[m,j]<MA20[m,j-1] or h>=60): return j
        if rule=='dist' and ((c[j]<O[m,j] and V[m,j]>=VA[m,j]*2.0) or h>=20): return j   # 거래량 2배 음봉(분배) 또는 20일
        if rule=='dist_after10' and h>=10 and ((c[j]<O[m,j] and V[m,j]>=VA[m,j]*2.0) or h>=40): return j
        if rule=='tp_or_sl_atr' and (c[j]>=e+p*a or c[j]<=e-p*a or h>=20): return j   # 대칭 ATR 목표/손절
        if rule=='tp3_trail':   # +p 도달 후 MA10 이탈 시 청산, 미도달 시 20일
            if r>=p:
                if c[j]<MA10[m,j]: return j
            elif h>=20: return j
            if h>=60: return j
        if rule=='half_tp':     # 반익절 근사: +p 도달 시 절반 청산(수익 = 0.5*p + 0.5*20일수익)
            pass
    return last
ent=[(m,t) for m,t in zip(*np.where(eg)) if t>=60 and t+121<N]
E={}
for m,t in zip(*np.where(eg)):
    if t>=60: E.setdefault(t,[]).append(m)
def sim(ex):
    cash=1.0;pos={};eq=np.ones(N)
    for t in range(60,N):
        for m in list(pos):
            if t>=pos[m][1]: cash+=pos[m][0]*Cf[m,t]; del pos[m]
        eqv=cash+sum(u*Cf[m,t] for m,(u,_) in pos.items())
        for m in sorted(E.get(t,[]),key=lambda m:-score.get((m,t),-9)):
            if m in pos or len(pos)>=5 or (m,t) not in ex: continue
            amt=min(cash,eqv/5); pos[m]=(amt/Cf[m,t],ex[(m,t)]); cash-=amt
        eq[t]=cash+sum(u*Cf[m,t] for m,(u,_) in pos.items())
    return eq
cfgs=[('fix20',None),('fix_score',None),
      ('tp_atr',2),('tp_atr',3),('tp_atr',4),('tp_pct',0.05),('tp_pct',0.08),('tp_pct',0.10),('tp_pct_cap40',0.08),
      ('chand',2),('chand',3),('chand',4),('chand_cap20',2),('chand_cap20',3),('chand_cap40',3),('chand_after20',3),
      ('ma20_down',None),('ma20_down_min10',None),('ma20_down_after20',None),('dist',None),('dist_after10',None),
      ('tp_or_sl_atr',2),('tp_or_sl_atr',3),('tp3_trail',0.05),('tp3_trail',0.08)]
print(f'{"규칙":22s} {"평균":>6s} {"중앙":>6s} {"승률":>5s} {"보유일":>5s} {"일당bp":>6s} {"vs지수":>6s} {"fold":>5s} {"5슬롯CAGR":>8s} {"MDD":>6s} {"Sharpe":>6s}')
res={}
for r,p in cfgs:
    ex={(m,t):exit_idx(m,t,r,p) for m,t in ent}
    a=pd.DataFrame([(t,ex[(m,t)]-t,Cf[m,ex[(m,t)]]/Cf[m,t]-1,Bf[ex[(m,t)]]/Bf[t]-1) for m,t in ent],columns=['t','h','r','b'])
    th=np.array_split(np.sort(a.t.unique()),3); base=res.get('fix20')
    f=''.join('+' if (a[a.t.isin(x)].r.mean()>(base[base.t.isin(x)].r.mean() if base is not None else 0)) else '-' for x in th)
    st=P.stats(sim(ex),60,N-1); nm=f'{r}{"" if p is None else " "+str(p)}'
    if r=='fix20': res['fix20']=a
    print(f'{nm:22s} {a.r.mean()*100:6.2f} {a.r.median()*100:6.2f} {(a.r>0).mean()*100:5.1f} {a.h.mean():5.1f} {(a.r/a.h).mean()*1e4:6.1f} {(a.r-a.b).mean()*100:+6.2f} {f:>5s} {st[1]*100:7.1f}% {st[2]*100:6.1f} {st[3]:6.2f}')

print('\n=== v1.2 눌림10 신호(1.46건/일)로 재현 — 신호가 많아지면 조기 청산의 자본 재배치 이점이 살아나는가 ===')
L10=pd.DataFrame(L.T).rolling(10).min().values.T
tr2=(C>=MA20)&(MA20>sh(MA20,1))&(C>MA60)&(MA60>=sh(MA60,5))&(L10<=MA20*1.02)
c2=(C>=sh(O,1))&(C>O)&(sh(C,1)<sh(O,1))&(C>=L+(H-L)*0.6)&(V>=VA*1.3)
eg10=np.nan_to_num(tr2&c2,nan=False)
E={}
for m,t in zip(*np.where(eg10)):
    if t>=60: E.setdefault(t,[]).append(m)
ent=[(m,t) for m,t in zip(*np.where(eg10)) if t>=60 and t+121<N]
for m,t in ent:
    if (m,t) not in score:
        chg=(C[m,t]/Cf[m,t-1]-1)*100; over=(C[m,t]/MA20[m,t]-1)*100; score[(m,t)]=(chg-2.6991)/2.5062+(over-5.0991)/4.0508
for r,p in [('fix20',None),('fix_score',None),('tp_pct',0.10),('tp_pct',0.08),('tp_atr',3),('tp_atr',4),('ma20_down_after20',None),('tp3_trail',0.08)]:
    ex={(m,t):exit_idx(m,t,r,p) for m,t in ent}
    a=pd.DataFrame([(t,ex[(m,t)]-t,Cf[m,ex[(m,t)]]/Cf[m,t]-1) for m,t in ent],columns=['t','h','r'])
    st=P.stats(sim(ex),60,N-1); nm=f'{r}{"" if p is None else " "+str(p)}'
    print(f'{nm:22s} 평균 {a.r.mean()*100:5.2f} 승률 {(a.r>0).mean()*100:4.1f} 보유 {a.h.mean():4.1f} 일당 {(a.r/a.h).mean()*1e4:5.1f}bp  5슬롯 CAGR {st[1]*100:5.1f}% MDD {st[2]*100:6.1f} Sharpe {st[3]:.2f}')
