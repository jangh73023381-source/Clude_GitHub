import os,pickle,sys,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,MA20,MA60,dates,B,eg=d['C'],d['MA20'],d['MA60'],d['dates'],d['bench'],d['eg']; N=len(dates)
Cf=pd.DataFrame(C.T).ffill().values.T; Bf=pd.Series(B).ffill().values
rm=lambda w: pd.DataFrame(Cf.T).rolling(w).mean().values.T
MA5,MA10=rm(5),rm(10)
def exit_idx(m,t,rule):
    c=Cf[m]; last=min(t+120,N-1); below=0
    for j in range(t+1,last+1):
        h=j-t
        if rule=='fix20' and h>=20: return j
        if rule=='ma5' and c[j]<MA5[m,j]: return j
        if rule=='ma10' and c[j]<MA10[m,j]: return j
        if rule=='ma20' and c[j]<MA20[m,j]: return j
        if rule=='ma20_cap20' and (c[j]<MA20[m,j] or h>=20): return j
        if rule=='ma10_cap20' and (c[j]<MA10[m,j] or h>=20): return j
        if rule=='ma20_2d_cap20':
            below=below+1 if c[j]<MA20[m,j] else 0
            if below>=2 or h>=20: return j
        if rule=='ma20_cap40' and (c[j]<MA20[m,j] or h>=40): return j
        if rule=='hold20_then_ma20' and h>=20 and c[j]<MA20[m,j]: return j
        if rule=='hold10_then_ma10' and h>=10 and c[j]<MA10[m,j]: return j
        if rule=='ma20_or_profit_ma10':  # 손실 중엔 MA20 이탈, 수익 중엔 MA10 이탈
            if (c[j]<c[t] and c[j]<MA20[m,j]) or (c[j]>=c[t] and c[j]<MA10[m,j]): return j
        if rule=='ma60' and c[j]<MA60[m,j]: return j
    return last
ent=[(m,t) for m,t in zip(*np.where(eg)) if t>=60 and t+121<N]
rules=['fix20','ma5','ma10','ma20','ma20_2d_cap20','ma10_cap20','ma20_cap20','ma20_cap40','hold10_then_ma10','hold20_then_ma20','ma20_or_profit_ma10','ma60']
print(f'{"규칙":22s} {"평균":>6s} {"중앙":>6s} {"승률":>5s} {"보유일":>5s} {"일당bp":>6s} {"vs지수":>6s} {"fold":>5s} {"5슬롯CAGR":>8s} {"MDD":>6s}')
import portfolio as P
E={}
for m,t in zip(*np.where(eg)):
    if t>=60: E.setdefault(t,[]).append(m)
for r in rules:
    rows=[]
    for m,t in ent:
        j=exit_idx(m,t,r); rows.append((t,j-t,Cf[m,j]/Cf[m,t]-1,Bf[j]/Bf[t]-1))
    a=pd.DataFrame(rows,columns=['t','h','r','b'])
    th=np.array_split(np.sort(a.t.unique()),3); f=''.join('+' if a[a.t.isin(x)].r.mean()>0 else '-' for x in th)
    # 5슬롯 시뮬: 규칙별 청산 인덱스 사전
    ex={(m,t):exit_idx(m,t,r) for m,t in ent}
    def sim_rule():
        cash=1.0;pos={};eq=np.ones(N)
        for t in range(60,N):
            for m in list(pos):
                if t>=pos[m][1]: cash+=pos[m][0]*Cf[m,t]; del pos[m]
            eqv=cash+sum(u*Cf[m,t] for m,(u,_) in pos.items())
            for m in sorted(E.get(t,[]),key=lambda m:-P.score.get((m,t),-9)):
                if m in pos or len(pos)>=5 or (m,t) not in ex: continue
                amt=min(cash,eqv/5); pos[m]=(amt/Cf[m,t],ex[(m,t)]); cash-=amt
            eq[t]=cash+sum(u*Cf[m,t] for m,(u,_) in pos.items())
        return eq
    eq=sim_rule(); st=P.stats(eq,60,N-1)
    print(f'{r:22s} {a.r.mean()*100:6.2f} {a.r.median()*100:6.2f} {(a.r>0).mean()*100:5.1f} {a.h.mean():5.1f} {(a.r/a.h).mean()*1e4:6.1f} {(a.r-a.b).mean()*100:+6.2f} {f:>5s} {st[1]*100:7.1f}% {st[2]*100:6.1f}')
