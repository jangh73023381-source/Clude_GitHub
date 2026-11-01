exec(open(__import__('os').path.expanduser('~/mnt/loop/backtest/sjh/engine.py')).read())
import numpy as np, json
BASE_A=np.load(S+'/BASE_A.npy'); s0=np.searchsorted(dates,20200403)
m=MEM.copy()&np.isfinite(C)&np.isfinite(TO20)
bm=np.array([np.nanmean(bc[max(0,t-19):t+1]) for t in range(T)])
m&=(bc>bm)[:,None]; m&=(OPG>0)&OPP&(SAG>0)
r,_=run(m,TO20,10); ACT=np.nanmean((r-BASE_A)[s0:])*100
print('실제(실적필터+거래대금top10) = %.3f%%p/20일'%ACT,flush=True)

print('=== 관문: 지속형 무작위 신호 대조군 500회 ===',flush=True)
ph=[]
for sd in range(500):
    rs=np.random.RandomState(9000+sd); sc=np.tile(rs.rand(N),(T,1))
    r2,_=run(m,sc,10); ph.append(np.nanmean((r2-BASE_A)[s0:])*100)
ph=np.array(ph)
print('지속형무작위 평균%.3f 표준편차%.3f p50 %.3f p95 %.3f p99 %.3f | 실제 %.3f | p=%.4f'%(
    ph.mean(),ph.std(),np.percentile(ph,50),np.percentile(ph,95),np.percentile(ph,99),ACT,(ph>=ACT).mean()),flush=True)

print('=== 관문: 거래대금 랭킹을 유니버스에서 돌린 대조군(상호작용 검증) ===',flush=True)
mU=MEM.copy()&np.isfinite(C)&np.isfinite(TO20)
rU,_=run(mU,TO20,10); print('유니버스 거래대금top10 %.3f'%(np.nanmean((rU-BASE_A)[s0:])*100),flush=True)
mG=mU&(bc>bm)[:,None]
rG,_=run(mG,TO20,10); print('게이트만+거래대금top10 %.3f'%(np.nanmean((rG-BASE_A)[s0:])*100),flush=True)
mS=mU&((OPG>0)&OPP&(SAG>0))
rS,_=run(mS,TO20,10); print('실적필터만+거래대금top10 %.3f'%(np.nanmean((rS-BASE_A)[s0:])*100),flush=True)
poolEW=np.array([np.nanmean(EA[t][m[t]]) if m[t].sum()>=10 else np.nan for t in range(T)])
print('실적+게이트 풀 EW %.3f'%(np.nanmean((poolEW-BASE_A)[s0:])*100),flush=True)

print('=== 실전 복리: KODEX200 상시보유 대비 ===',flush=True)
ii=np.arange(s0,T-21,20)
def sim(mask,score,topn=10,cost_bp=40):
    eq=1.0; prev=set(); curve=[]; turns=[]
    for t in ii:
        idx=np.where(mask[t]&np.isfinite(FB[t])&np.isfinite(score[t]))[0]
        if len(idx)==0:
            if prev: turns.append(1.0); eq*=(1-cost_bp/10000)
            prev=set(); curve.append(eq); continue
        sel=set(idx[np.argsort(-score[t][idx])[:min(topn,len(idx))]].tolist())
        tn=len(sel-prev)/max(len(sel),1); turns.append(tn); prev=sel
        eq*=(1+np.nanmean(FB[t][list(sel)]))*(1-cost_bp/10000*tn); curve.append(eq)
    c=np.array(curve); mdd=float(np.min(c/np.maximum.accumulate(c))-1)
    return c[-1]-1, mdd, float(np.mean(turns))
bq=np.array([np.nancumprod([1+(bc[t+21]/bo[t+1]-1) for t in ii])][0])
print('KODEX200 상시보유  누적 %.3f  MDD %.3f'%(bq[-1]-1, np.min(bq/np.maximum.accumulate(bq))-1),flush=True)
for nm,mk,sc,tn in [('송재호식 핵심 top10',m,TO20,10),('송재호식 핵심 top5',m,TO20,5),
                    ('실적필터 풀 EW',m,np.zeros((T,N)),9999),
                    ('유니버스 EW',mU,np.zeros((T,N)),9999)]:
    cum,mdd,to=sim(mk,sc,tn); print('%-22s 누적 %.3f  MDD %.3f  교체율 %.2f'%(nm,cum,mdd,to),flush=True)
print('=== 다중검정 ===',flush=True)
# t 분포 임계 (df=77) 근사 via numpy 없음 → 정규근사
from math import erf,sqrt
def z_for(p):
    lo,hi=0,6
    for _ in range(60):
        mid=(lo+hi)/2
        if 0.5*(1-erf(mid/sqrt(2)))>p/2: lo=mid
        else: hi=mid
    return (lo+hi)/2
print('설정 약 32개 → Bonferroni 임계 |t| ≈ %.2f (정규근사, df=77이면 약간 더 큼)'%z_for(0.05/32),flush=True)
print('DONE')
