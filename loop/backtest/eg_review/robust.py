import os,pickle,numpy as np,pandas as pd,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import portfolio as P
from portfolio import sim,stats,Bf,START,N,eg,dates
HERE=os.path.dirname(os.path.abspath(__file__))
# 1) 우선순위 무작위 vs 점수
rng=np.random.default_rng(0)
res=[]
for s in range(20):
    P.score={k:rng.random() for k in P.score}  # 무작위 점수
    eq,ntr,rets,occ=sim(K=5); res.append(stats(eq))
r=np.array(res); print(f'K5 fix20 무작위우선순위 20회: cagr mean {r[:,1].mean()*100:.1f}% [{r[:,1].min()*100:.1f},{r[:,1].max()*100:.1f}] mdd mean {r[:,2].mean()*100:.1f} sharpe mean {r[:,3].mean():.2f}')
P.score=pd.read_pickle(os.path.join(HERE,'_sig20.pkl')).set_index(['m','t']).score.to_dict()
sc=dict(P.score)
P.score={k:-v for k,v in sc.items()}
eq,ntr,rets,occ=sim(K=5); t=stats(eq); print(f'K5 fix20 점수 역순: cagr {t[1]*100:.1f}% mdd {t[2]*100:.1f} sharpe {t[3]:.2f}')
P.score=sc
for nm,kw in [('K5 fix20 점수순',dict(K=5)),('K5 fix20 score>-1.33',dict(K=5,min_score=-1.33)),('K5 fix20 score>-0.79',dict(K=5,min_score=-0.79)),('K5 fix20 섹터대표',dict(K=5,sector_rep=True)),('K5 fix15',dict(K=5,hold=15)),('K5 fix25',dict(K=5,hold=25)),('K5 fix30',dict(K=5,hold=30)),('K7 fix20',dict(K=7)),('K4 fix20',dict(K=4))]:
    eq,ntr,rets,occ=sim(**kw); t=stats(eq); print(f'{nm:24s} cagr {t[1]*100:5.1f}% mdd {t[2]*100:6.1f} sharpe {t[3]:.2f} trades {ntr} occ {occ:.1f}')
# 2) 연도별 K5 fix20 vs KODEX200
eq,_,_,_=sim(K=5)
yrs=np.array([int(str(x)[:4]) for x in dates])
print('연도별: 전략 / KODEX200 / 초과')
for y in sorted(set(yrs[START:])):
    idx=np.where(yrs==y)[0]; a=max(idx[0]-1,START); b=idx[-1]
    print(f'{y}: {(eq[b]/eq[a]-1)*100:+6.1f}% / {(Bf[b]/Bf[a]-1)*100:+6.1f}% / {((eq[b]/eq[a])-(Bf[b]/Bf[a]))*100:+6.1f}%p')
# 3) 플라시보: 신호일을 무작위로 이동(같은 종목, ±30~120일) 20회
res=[]
for s in range(20):
    rng=np.random.default_rng(100+s); E={}
    for m,t in zip(*np.where(eg)):
        tt=t+int(rng.integers(30,120))*int(rng.choice([-1,1]))
        if START<=tt<N: E.setdefault(tt,[]).append(m)
    P.score={k:rng.random() for k in P.score}
    eq2,_,_,_=sim(K=5,entries=E); res.append(stats(eq2))
r=np.array(res); print(f'플라시보(신호일 이동) K5: cagr mean {r[:,1].mean()*100:.1f}% max {r[:,1].max()*100:.1f}% sharpe mean {r[:,3].mean():.2f}')
# 4) R5 유사: 최고 기여 3거래일 제거 후 초과 (일별 초과수익 합)
P.score=sc
eq,_,_,_=sim(K=5); r_s=np.diff(eq[START:])/eq[START:-1]; r_b=np.diff(Bf[START:])/Bf[START:-1]
ex=r_s-r_b; srt=np.sort(ex)
print(f'일별 초과수익 합 {ex.sum()*100:+.1f}%p · 상위3일 제거 {(ex.sum()-srt[-3:].sum())*100:+.1f}%p · 상위10일 제거 {(ex.sum()-srt[-10:].sum())*100:+.1f}%p · 중앙값 {np.median(ex)*1e4:+.2f}bp')
