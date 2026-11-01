import os,pickle,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,B,eg,tr,MA20,VA,V,rank,dates=d['C'],d['bench'],d['eg'],d['trend'],d['MA20'],d['VA'],d['V'],d['rank'],d['dates']; N=C.shape[1]
Cf=pd.DataFrame(C.T).ffill().values.T
H=20
rows=[]
for m,t in zip(*np.where(eg)):
    if t<60 or t+H>=N: continue
    r=Cf[m,t+H]/Cf[m,t]-1
    chg=(C[m,t]/Cf[m,t-1]-1)*100; over=(C[m,t]/MA20[m,t]-1)*100
    score=(chg-2.6991)/2.5062+(over-5.0991)/4.0508
    # 최저 종가 낙폭(20일 내)
    mdd=(Cf[m,t+1:t+H+1].min()/Cf[m,t]-1)
    rows.append(dict(m=m,t=t,ret=r,rank=rank[m,t],chg=chg,over=over,vr=V[m,t]/VA[m,t],score=score,mdd=mdd,year=int(str(dates[t])[:4]),sec=d['secs'][m]))
a=pd.DataFrame(rows)
# B1
rng=np.random.default_rng(1)
trd=[(m,t) for m,t in zip(*np.where(tr&~eg)) if t>=60 and t+H<N]
b=[]
for m,t in [trd[i] for i in rng.choice(len(trd),15000,replace=False)]:
    b.append(dict(t=t,ret=Cf[m,t+H]/Cf[m,t]-1,rank=rank[m,t],year=int(str(dates[t])[:4])))
b=pd.DataFrame(b)
print('== 연도별 (EG 20일 vs B1) ==')
for y,g in a.groupby('year'):
    bb=b[b.year==y]; print(f'{y} n={len(g):4d} EG {g.ret.mean()*100:6.2f}% win {(g.ret>0).mean()*100:4.1f} B1 {bb.ret.mean()*100:6.2f}% diff {(g.ret.mean()-bb.ret.mean())*100:+.2f}')
print('== 거래대금 순위 버킷 ==')
for lo,hi in [(1,30),(31,60),(61,100),(101,140),(141,200)]:
    g=a[(a['rank']>=lo)&(a['rank']<=hi)]; bb=b[(b['rank']>=lo)&(b['rank']<=hi)]
    print(f'rank {lo:3d}-{hi:3d} n={len(g):4d} EG {g.ret.mean()*100:6.2f}% med {g.ret.median()*100:5.2f} win {(g.ret>0).mean()*100:4.1f} B1 {bb.ret.mean()*100:6.2f} diff {(g.ret.mean()-bb.ret.mean())*100:+.2f}  mdd_mean {g.mdd.mean()*100:5.2f}')
print('== 우선점수 분위 ==')
a['q']=pd.qcut(a.score,5,labels=False)
for q,g in a.groupby('q'): print(f'q{q} n={len(g)} score>{g.score.min():+.2f} EG {g.ret.mean()*100:6.2f}% win {(g.ret>0).mean()*100:4.1f} med {g.ret.median()*100:5.2f}')
print('== 당일등락 / 이격 / 거래량배수 버킷 ==')
for col,bins in [('chg',[-5,0,1,2,3,5,8,50]),('over',[-5,0,2,4,6,8,12,60]),('vr',[1.3,1.5,2,3,5,50])]:
    a['b']=pd.cut(a[col],bins)
    for bnm,g in a.groupby('b',observed=True): print(f'{col} {str(bnm):14s} n={len(g):4d} EG {g.ret.mean()*100:6.2f}% win {(g.ret>0).mean()*100:4.1f}')
print('== 신호일 KOSPI(=KODEX200) 국면 ==')
Bs=pd.Series(B).ffill(); bm20=Bs.rolling(20).mean(); bm60=Bs.rolling(60).mean()
a['reg']=[('B>MA20' if Bs[t]>bm20[t] else 'B<MA20')+('&>MA60' if Bs[t]>bm60[t] else '&<MA60') for t in a.t]
b['reg']=[('B>MA20' if Bs[t]>bm20[t] else 'B<MA20')+('&>MA60' if Bs[t]>bm60[t] else '&<MA60') for t in b.t]
for rg,g in a.groupby('reg'):
    bb=b[b.reg==rg]; print(f'{rg} n={len(g):4d} EG {g.ret.mean()*100:6.2f}% win {(g.ret>0).mean()*100:4.1f} B1 {bb.ret.mean()*100:6.2f} diff {(g.ret.mean()-bb.ret.mean())*100:+.2f}')
print('== 섹터별 (n>=30) ==')
for s,g in a.groupby('sec'):
    if len(g)>=30: print(f'{s:12s} n={len(g):4d} EG {g.ret.mean()*100:6.2f}% win {(g.ret>0).mean()*100:4.1f}')
print('== 신호 수/일 분포 ==')
cnt=a.groupby('t').size(); print(cnt.describe()); print('days with signal',len(cnt),'of',N-80)
print('== 손절 검토: 20일 내 최저 종가 낙폭 분위 ==', a.mdd.quantile([.1,.25,.5,.75,.9]).round(4).to_dict())
for sl in [-0.03,-0.05,-0.07,-0.10]:
    hit=a[a.mdd<=sl]; print(f'sl {sl}: hit {len(hit)} ({len(hit)/len(a)*100:.1f}%), 20일 최종 mean {hit.ret.mean()*100:+.2f}% win {(hit.ret>0).mean()*100:.1f}')
a.to_pickle(os.path.join(HERE,'_sig20.pkl'))
