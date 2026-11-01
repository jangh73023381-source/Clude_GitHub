import os,pickle,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,B,eg,tr=d['C'],d['bench'],d['eg'],d['trend']; N=C.shape[1]
Cf=pd.DataFrame(C.T).ffill().values.T
ent=[(m,t) for m,t in zip(*np.where(eg)) if t>=60 and t+80<N]
rng=np.random.default_rng(0)
trd=[(m,t) for m,t in zip(*np.where(tr&~eg)) if t>=60 and t+80<N]
b1=[trd[i] for i in rng.choice(len(trd),15000,replace=False)]
def path(E):
    R=np.array([[Cf[m,t+h]/Cf[m,t]-1 for h in range(0,81)] for m,t in E])
    Bh=np.array([[B[t+h]/B[t]-1 for h in range(0,81)] for m,t in E])
    return R,Bh
Re,Be=path(ent); Rb,Bb=path(b1)
print('h  EG%  vsBench  B1%  EG-B1  win%  medEG%')
for h in [1,2,3,5,8,10,12,15,18,20,22,25,30,35,40,50,60,80]:
    print(f'{h:2d} {Re[:,h].mean()*100:5.2f} {(Re[:,h]-Be[:,h]).mean()*100:6.2f} {Rb[:,h].mean()*100:5.2f} {(Re[:,h].mean()-Rb[:,h].mean())*100:5.2f} {(Re[:,h]>0).mean()*100:5.1f} {np.median(Re[:,h])*100:5.2f}')
# 일별 한계 초과수익 (EG-B1) 구간
inc=np.diff(Re.mean(0)-Rb.mean(0))*100
for a,b in [(0,5),(5,10),(10,15),(15,20),(20,30),(30,40),(40,60),(60,80)]:
    print(f'day {a+1}-{b}: marginal EG-B1 {inc[a:b].sum():+.2f}%p, EG-bench {np.diff(Re.mean(0)-Be.mean(0))[a:b].sum()*100:+.2f}%p')
