import os,sys,numpy as np,pandas as pd
sys.path.insert(0,os.environ['HOME']+'/mnt/loop/references/scripts')
from universe_filters import eligible
R=pd.read_pickle(os.environ['HOME']+'/work/ep.pkl'); g=R[R.H==20]
bh=(g.CH/g.C0).to_numpy(); trig=(g.t>0).to_numpy()
stop=np.where(trig,0.5*(g.fill/g.C0)+0.5*(g.CH/g.C0),bh)
half=1+0.5*(bh-1)
for nm,x in [('방치 100%',bh),('0.5% 스톱(절반매도)',stop),('그냥 절반만 매수',half)]:
    print(f"{nm:20s} 평균 {100*(x.mean()-1):+.4f}%  중앙 {100*(np.median(x)-1):+.3f}%  하위5% {100*(np.percentile(x,5)-1):+.2f}%  하위1% {100*(np.percentile(x,1)-1):+.2f}%  변동성 {100*x.std():.2f}%")
d=stop-half
print(f"스톱 - 절반매수 차: {100*d.mean():+.4f}%p  t={d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):.2f}")
