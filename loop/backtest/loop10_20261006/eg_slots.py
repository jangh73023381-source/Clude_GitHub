"""축1~5 생존 후보를 '하드 필터'가 아니라 '슬롯 우선순위'(통과 신호 먼저)로 쓴 5슬롯 포트폴리오 검정."""
import os,sys,numpy as np,pandas as pd,json
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(os.path.dirname(HERE),'eg_review'))
import portfolio as P
exec(open(os.path.join(HERE,'eg_filters.py')).read().split("rows=[dict")[0])  # 신호·필터 정의 재사용
chg_=C/sh(C,1)-1; over=C/MA20-1
z=lambda x:(x-np.nanmean(x[base]))/np.nanstd(x[base])
SC=z(chg_)+z(over)
def entries(prio=None,only=None,rand=None):
    E={}
    for m,t in zip(*np.where(base)):
        if only is not None and not only[m,t]: continue
        E.setdefault(t,[]).append(m)
    for t in E:
        if rand is not None: rand.shuffle(E[t])
        elif prio is None: E[t].sort(key=lambda m:-SC[m,t])
        else: E[t].sort(key=lambda m:(-int(prio[m,t]),-SC[m,t]))
    return E
# portfolio.sim 은 score dict 로 재정렬하므로 score 를 무력화(동점) → 입력 순서 유지(sort 안정)
P.score={}
T0=250
def run(E):
    eq,ntr,rets,occ=P.sim(K=5,entries=E,t0=T0); tot,cagr,mdd,shp=P.stats(eq,t0=T0)
    f=[];idx=[T0,T0+(N-T0)//3,T0+2*(N-T0)//3,N-1]
    for a,b in zip(idx[:-1],idx[1:]):
        e2,_,_,_=P.sim(K=5,entries=E,t0=a,t1=b); f.append((e2[b]/e2[a]-1-(P.Bf[b]/P.Bf[a]-1))*100)
    return dict(cagr=cagr*100,mdd=mdd*100,sh=shp,ntr=ntr,avg=rets.mean()*100,f=f)
res={}
res['v1.2 (우선점수)']=run(entries())
for nm,ex in [('거래량>=2.0VA 우선',V>=VA*2.0),('몸통>=1.0ATR 우선',(C-O)>=1.0*ATR),('250일고점x0.92 우선',C>=H250*0.92)]:
    ex=np.nan_to_num(ex,nan=0).astype(bool)
    res[nm]=run(entries(prio=ex)); res[nm.replace('우선','만(하드)')]=run(entries(only=ex))
rng=np.random.default_rng(1); rr=[run(entries(rand=rng)) for _ in range(5)]
res['무작위 순서(5회 평균)']={k:np.mean([r[k] for r in rr],axis=0).tolist() if k=='f' else float(np.mean([r[k] for r in rr])) for k in rr[0]}
tot,cagr,mdd,shp=P.stats(P.Bf/P.Bf[T0],t0=T0); res['KODEX200 B&H']=dict(cagr=cagr*100,mdd=mdd*100,sh=shp,ntr=0,avg=0,f=[0,0,0])
for k,v in res.items(): print(f"{k:22s} CAGR {v['cagr']:5.1f}% MDD {v['mdd']:6.1f}% Sh {v['sh']:.2f} 거래 {v['ntr']:5.0f} 건당 {v['avg']:+.2f}% fold(vsKODEX200) {'/'.join('%+.0f'%x for x in v['f'])}")
json.dump(res,open(os.path.join(HERE,'res_eg_slots.json'),'w'),ensure_ascii=False,default=float,indent=1)
