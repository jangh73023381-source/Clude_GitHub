import os,pickle,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,O,B,eg,tr,MA20,MA60=d['C'],d['O'],d['bench'],d['eg'],d['trend'],d['MA20'],d['MA60']; N=C.shape[1]
Cf=pd.DataFrame(C.T).ffill().values.T; Bf=pd.Series(B).ffill().values
Bs=pd.Series(Bf); bm60=Bs.rolling(60).mean().values; bm20=Bs.rolling(20).mean().values
rows=[]
for m,t in zip(*np.where(eg)):
    if t<60 or t+21>=N: continue
    chg=(C[m,t]/Cf[m,t-1]-1)*100; over=(C[m,t]/MA20[m,t]-1)*100; score=(chg-2.6991)/2.5062+(over-5.0991)/4.0508
    rows.append(dict(t=t,r0=Cf[m,t+20]/Cf[m,t]-1, r1c=Cf[m,t+21]/Cf[m,t+1]-1, r1o=Cf[m,t+21]/O[m,t+1]-1 if not np.isnan(O[m,t+1]) else np.nan,
        d1=(Cf[m,t+1]/Cf[m,t]-1)*100, gap=(O[m,t+1]/Cf[m,t]-1)*100, above1=Cf[m,t+1]>=MA20[m,t+1], score=score, bear=Bf[t]<bm60[t], bear20=Bf[t]<bm20[t]))
a=pd.DataFrame(rows)
rng=np.random.default_rng(0); trd=[(m,t) for m,t in zip(*np.where(tr&~eg)) if t>=60 and t+21<N]
b=np.array([Cf[m,t+21]/Cf[m,t+1]-1 for m,t in [trd[i] for i in rng.choice(len(trd),15000,replace=False)]])
print(f'D종가 진입 20일 {a.r0.mean()*100:+.2f}% | D+1종가 진입 {a.r1c.mean()*100:+.2f}% (win {(a.r1c>0).mean()*100:.1f}) | D+1시가 진입 {a.r1o.mean()*100:+.2f}% | B1(D+1) {b.mean()*100:+.2f} → D+1종가 vs B1 {(a.r1c.mean()-b.mean())*100:+.2f}')
a['d1b']=pd.cut(a.d1,[-20,-2,-1,0,1,2,3,5,50])
for k,g in a.groupby('d1b',observed=True): print(f'D+1 등락 {str(k):12s} n={len(g):4d} D+1종가 진입 20일 {g.r1c.mean()*100:+.2f}% win {(g.r1c>0).mean()*100:.1f}')
for v,g in a.groupby('above1'): print(f'D+1 종가>=MA20 {v}: n={len(g)} {g.r1c.mean()*100:+.2f}%')
for v,g in a.groupby('bear'): print(f'KODEX200<MA60 {v}: n={len(g)} D종가 {g.r0.mean()*100:+.2f}% D+1종가 {g.r1c.mean()*100:+.2f}% win {(g.r1c>0).mean()*100:.1f}')
g=a[a.bear&a.bear20]; print(f'KODEX200<MA20&<MA60: n={len(g)} D종가 {g.r0.mean()*100:+.2f}% D+1종가 {g.r1c.mean()*100:+.2f}% win {(g.r1c>0).mean()*100:.1f}')
a['q']=pd.qcut(a.score,3,labels=['하','중','상'])
for q,g in a.groupby('q',observed=True): print(f'점수 {q}: D+1종가 {g.r1c.mean()*100:+.2f}%')
# fold
for i,th in enumerate(np.array_split(np.sort(a.t.unique()),3)):
    g=a[a.t.isin(th)]; print(f'fold{i+1} D+1종가 {g.r1c.mean()*100:+.2f}%')
