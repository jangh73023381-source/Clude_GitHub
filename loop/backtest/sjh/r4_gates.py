exec(open(__import__('os').path.expanduser('~/mnt/loop/backtest/sjh/engine.py')).read())
import numpy as np, json
BASE_A=np.load(S+'/BASE_A.npy'); BASE_B=np.load(S+'/BASE_B.npy')
S1_8=np.load(S+'/S1_8.npy')
s0=np.searchsorted(dates,20200403)
def m2(r,B=None,E='A'):
    B=(BASE_A if E=='A' else BASE_B) if B is None else B
    x=r-B; v=x[s0:]; v=v[np.isfinite(v)]
    ii=np.arange(s0,T,20); nv=x[ii]; nv=nv[np.isfinite(nv)]
    t=nv.mean()/(nv.std(ddof=1)/np.sqrt(len(nv))) if len(nv)>2 else np.nan
    return dict(mean=round(v.mean()*100,3),med=round(np.median(v)*100,3),t=round(t,2),win=round((v>0).mean()*100,1),n=len(v))
def core(opg_thr=0.0,sag=True,topn=10,gate=20,rank='to',E=None,mask_extra=None):
    m=MEM.copy()&np.isfinite(C)&np.isfinite(TO20)
    if gate:
        g=np.full(T,False)
        bm=np.array([np.nanmean(bc[max(0,t-gate+1):t+1]) for t in range(T)])
        g=bc>bm
        m&=g[:,None]
    m&=(OPG>opg_thr)&OPP
    if sag: m&=(SAG>0)
    if mask_extra is not None: m&=mask_extra
    sc={'to':TO20,'mc':C*SHR,'mom':R20}[rank]
    r,_=run(m,sc,topn,E=E)
    return r,m
print('=== R1 고원: 영업이익성장 임계 ===',flush=True)
for thr in [-0.3,-0.1,0.0,0.1,0.3,0.5]:
    r,m=core(opg_thr=thr); print(thr,m2(r),'pool',round(float(m[s0:].sum(1).mean()),0),flush=True)
print('=== R1 고원: 종목수 ===',flush=True)
for n in [5,10,20,30,50]:
    r,m=core(topn=n); print(n,m2(r),flush=True)
print('=== R1 고원: 지수 MA 기간 ===',flush=True)
for g in [0,10,20,40,60,120]:
    r,m=core(gate=g); print(g,m2(r),'pool',round(float(m[s0:].sum(1).mean()),0),flush=True)
print('=== R3 정의교체 ===',flush=True)
r,_=core(sag=False); print('매출성장 조건 제거',m2(r),flush=True)
r,_=core(rank='mc'); print('랭킹=시총',m2(r),flush=True)
r,_=core(rank='mom'); print('랭킹=20일모멘텀',m2(r),flush=True)
r,_=core(mask_extra=S1_8); print('+섹터선점8',m2(r),flush=True)
print('=== R2 fold 3분할 ===',flush=True)
r,m=core()
x=r-BASE_A; ii=np.arange(s0,T,20); nv=x[ii]; nv=nv[np.isfinite(nv)]
k=len(nv)//3
for f in range(3):
    seg=nv[f*k:(f+1)*k] if f<2 else nv[2*k:]
    print('fold%d n=%d mean=%.3f t=%.2f'%(f+1,len(seg),seg.mean()*100,seg.mean()/(seg.std(ddof=1)/np.sqrt(len(seg)))),flush=True)
print('=== R4 플라시보: 풀내 무작위 10종 (300회) ===',flush=True)
ph=[]
for sd in range(300):
    rs=np.random.RandomState(sd); r2,_=run(m,rs.rand(T,N),10)
    ph.append(np.nanmean((r2-BASE_A)[s0:]))
ph=np.array(ph)*100; act=m2(r)['mean']
print('풀내무작위 평균%.3f p5 %.3f p50 %.3f p95 %.3f | 실제 %.3f | p=%.3f'%(ph.mean(),np.percentile(ph,5),np.percentile(ph,50),np.percentile(ph,95),act,(ph>=act).mean()),flush=True)
print('=== R5 꼬리: 중앙값 기반 & 상위분기 기여 ===',flush=True)
x=(r-BASE_A)[s0:]; x=x[np.isfinite(x)]
srt=np.sort(x)[::-1]; top=srt[:len(srt)//4].sum()/srt.sum()
print('평균%.3f 중앙%.3f 상위25%% 기여비중 %.1f%%'%(x.mean()*100,np.median(x)*100,top*100),flush=True)
print('=== A(지표) vs B(집행, 익일시가 진입) ===',flush=True)
rA,_=core(E=EA); rB,_=core(E=EB)
print('A',m2(rA,E='A'),flush=True); print('B',m2(rB,B=BASE_B,E='B'),flush=True)
gap=(np.nanmean((rA-BASE_A)[s0:])-np.nanmean((rB-BASE_B)[s0:]))/np.nanmean((rA-BASE_A)[s0:])
print('갭 비중 %.1f%%'%(gap*100),flush=True)
print('=== 시총 중립 확인 (S4 풀 자체 EW vs 유니버스) ===',flush=True)
poolEW=np.array([np.nanmean(EA[t][m[t]]) if m[t].sum()>=10 else np.nan for t in range(T)])
print('S4풀 EW', m2(poolEW),flush=True)
mc=C*SHR; q=np.nanpercentile(np.where(MEM,mc,np.nan),80,axis=1)
big=MEM&(mc>=q[:,None])
bigEW=np.array([np.nanmean(EA[t][big[t]]) if big[t].sum()>=10 else np.nan for t in range(T)])
print('시총상위20% EW', m2(bigEW),flush=True)
np.save(S+'/rCORE.npy',r); np.save(S+'/mCORE.npy',m)
print('DONE')
