import os,pickle,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,B,eg,tr,MA20,MA60=d['C'],d['bench'],d['eg'],d['trend'],d['MA20'],d['MA60']; N=C.shape[1]
Cf=pd.DataFrame(C.T).ffill().values.T; Bf=pd.Series(B).ffill().values
rows=[]
for m,t in zip(*np.where(eg)):
    if t<60 or t+40>=N: continue
    r20=Cf[m,t+20]/Cf[m,t]-1; r2040=Cf[m,t+40]/Cf[m,t+20]-1; b2040=Bf[t+40]/Bf[t+20]-1
    resig=eg[m,t+1:t+21].any(); above=Cf[m,t+20]>MA20[m,t+20]; above60=Cf[m,t+20]>MA60[m,t+20]
    trend20=tr[m,t+20]
    rows.append(dict(r20=r20,r2040=r2040,b2040=b2040,resig=resig,above=above,above60=above60,trend20=trend20,up=r20>0))
a=pd.DataFrame(rows)
# B1: 임의 추세일의 이후 20일
rng=np.random.default_rng(0); trd=[(m,t) for m,t in zip(*np.where(tr)) if t>=60 and t+20<N]
b=np.array([Cf[m,t+20]/Cf[m,t]-1 for m,t in [trd[i] for i in rng.choice(len(trd),15000,replace=False)]])
print(f'전체: day20→40 수익 {a.r2040.mean()*100:+.2f}% (bench {a.b2040.mean()*100:+.2f}, B1추세일 {b.mean()*100:+.2f}) n={len(a)}')
for col in ['up','above','above60','trend20','resig']:
    for v,g in a.groupby(col):
        print(f'{col}={v!s:5s} n={len(g):4d} day20→40 {g.r2040.mean()*100:+.2f}% win {(g.r2040>0).mean()*100:4.1f} vs bench {(g.r2040-g.b2040).mean()*100:+.2f} vs B1 {(g.r2040.mean()-b.mean())*100:+.2f}')
g=a[a.up&a.above&a.trend20]; print(f'up&aboveMA20&trend n={len(g)} day20→40 {g.r2040.mean()*100:+.2f}% vs bench {(g.r2040-g.b2040).mean()*100:+.2f} vs B1 {(g.r2040.mean()-b.mean())*100:+.2f}')
g=a[a.resig&a.above]; print(f'resig&above n={len(g)} day20→40 {g.r2040.mean()*100:+.2f}% vs bench {(g.r2040-g.b2040).mean()*100:+.2f}')
