import engine as E, numpy as np, pandas as pd
from engine import *
def tstat(x): x=np.asarray(x,float); x=x[np.isfinite(x)]; return x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))
ev=events(0.08,0.02); k=3
# 1) 경로: t0-5 ~ I+60 풀 누적 초과 (A,B)
paths={}
for mode in ['A','B','CB']:
    P=[]
    for t0 in ev:
        idx=leaders(t0,mode,5 if mode=='B' else k) if mode!='CB' else ctrl(t0,'beta')
        row=[]
        for off in range(-5,65):
            t=t0+off
            row.append(np.nanmean(R[t,idx])-uni_ew[t] if t<T else np.nan)
        P.append(row)
    P=np.array(P); paths[mode]=np.nancumsum(np.nanmean(P,0))*100
for m,p in paths.items():
    print(m,'cum excess @ t0-1 %.2f  t0+2(식별) %.2f  +10 %.2f  +20 %.2f  +40 %.2f  +60 %.2f'%(p[4],p[7],p[17],p[27],p[47],p[67]))
# 2) 섹터 분산
for mode in ['A','B']:
    ns=[len(set(sec[leaders(t0,mode,5 if mode=='B' else k)])) for t0 in ev]
    print(mode,'pool 20종 섹터 수 평균',np.mean(ns))
# 3) 순환 — 5일 상대수익 자기상관 (풀 내부, 비겹침)
for mode in ['A','B','CB']:
    cs=[]
    for t0 in ev:
        idx=leaders(t0,mode,5 if mode=='B' else k) if mode!='CB' else ctrl(t0,'beta')
        s=t0+5
        for w in range(0,35,5):
            if s+w+10>=T: break
            a=C[s+w+5,idx]/C[s+w,idx]-1; b=C[s+w+10,idx]/C[s+w+5,idx]-1
            ok=np.isfinite(a)&np.isfinite(b)
            if ok.sum()>=8: cs.append(np.corrcoef(a[ok],b[ok])[0,1])
    print(mode,'5일 상대수익 자기상관 %.3f (t=%.2f, n=%d)'%(np.mean(cs),tstat(cs),len(cs)))
# 4) 플라시보 — 반도체 반등과 무관한 무작위 날짜에 같은 정의(3일 초과 상위20)
rng=np.random.default_rng(11); cand=[t for t in range(E.np.argmax(UNI.sum(1)>300)+21,T-50) if all(abs(t-e)>45 for e in ev)]
res=[]
for d in range(3):
    dts=sorted(rng.choice(cand,20,replace=False))
    a_all=[];a_dn=[]
    for t0 in dts:
        idx=leaders(t0,'A',k)
        for t in range(t0+k,t0+k+40):
            m=day_metrics(idx,t,'all'); n=day_metrics(idx,t,'down')
            if m: a_all.append((t0,m[0]))
            if n: a_dn.append((t0,n[0]))
    A=pd.DataFrame(a_all,columns=['e','x']); D=pd.DataFrame(a_dn,columns=['e','x'])
    print('placebo',d,'all %.3f (t_ev %.2f) down %.3f (t_ev %.2f)'%(A.x.mean()*100,tstat(A.groupby('e').x.mean()),D.x.mean()*100,tstat(D.groupby('e').x.mean())))
# 5) fold 3분할 (이벤트 순서)
df=pd.read_pickle('r1_main.pkl')
for pool in ['A','B']:
    g=df[(df.pool==pool)&(df.rule=='down')]; e=g.groupby('ev').ex1.mean()*100
    evs=sorted(e.index); f=np.array_split(evs,3)
    print(pool,'down fold',[round(e.loc[x].mean(),3) for x in f])
    d=g.groupby('t').ex1.mean().sort_values(ascending=False)*100
    print(pool,'R5 상위1/3/5/10일 제거 평균',[round(d.iloc[j:].mean(),3) for j in [1,3,5,10]],'중앙',round(d.median(),3))
print('events',[int(dates[i]) for i in ev])
