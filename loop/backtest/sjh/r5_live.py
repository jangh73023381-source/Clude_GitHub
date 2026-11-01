exec(open(__import__('os').path.expanduser('~/mnt/loop/backtest/sjh/engine.py')).read())
import numpy as np, json
BASE_A=np.load(S+'/BASE_A.npy'); s0=np.searchsorted(dates,20200403)
def corem(opg=0.0,sag=True,gate=20):
    m=MEM.copy()&np.isfinite(C)&np.isfinite(TO20)
    bm=np.array([np.nanmean(bc[max(0,t-gate+1):t+1]) for t in range(T)])
    m&=(bc>bm)[:,None]; m&=(OPG>opg)&OPP
    if sag: m&=(SAG>0)
    return m
m=corem()
def m2(x):
    v=x[s0:]; v=v[np.isfinite(v)]
    ii=np.arange(s0,T,20); nv=x[ii]; nv=nv[np.isfinite(nv)]
    t=nv.mean()/(nv.std(ddof=1)/np.sqrt(len(nv))) if len(nv)>2 else np.nan
    return dict(mean=round(v.mean()*100,3),med=round(np.median(v)*100,3),t=round(t,2),win=round((v>0).mean()*100,1))

print('=== 무관 신호 대조군 (지속형: 종목코드 순) ===',flush=True)
fake=np.tile(np.arange(N,dtype=float),(T,1))
r,_=run(m,fake,10); print('코드순 상위10',m2(r-BASE_A),flush=True)
r,_=run(m,-fake,10); print('코드순 하위10',m2(r-BASE_A),flush=True)
# 지속형 무작위 점수(종목별 고정) 100회
ph=[]
for sd in range(100):
    rs=np.random.RandomState(5000+sd); sc=np.tile(rs.rand(N),(T,1))
    r2,_=run(m,sc,10); ph.append(np.nanmean((r2-BASE_A)[s0:]))
ph=np.array(ph)*100
print('지속형 무작위(100회) 평균%.3f [%.3f~%.3f]'%(ph.mean(),ph.min(),ph.max()),flush=True)

print('=== 실전 복리: 20거래일 비중복 리밸런싱, 비용 반영 ===',flush=True)
ii=np.arange(s0,T-21,20)
def sim(mask,score,topn=10,cost_bp=40):
    eq=1.0; eqb=1.0; curve=[]; prev=set(); turns=[]
    for t in ii:
        idx=np.where(mask[t]&np.isfinite(FB[t])&np.isfinite(score[t]))[0]
        if len(idx)==0:
            curve.append((dates[t],eq,eqb)); continue
        sel=set(idx[np.argsort(-score[t][idx])[:min(topn,len(idx))]].tolist())
        tn=len(sel-prev)/max(len(sel),1); turns.append(tn); prev=sel
        g=np.nanmean(FB[t][list(sel)])
        eq*= (1+g)*(1-cost_bp/10000*tn)
        eqb*= (1+ (bc[t+21]/bo[t+1]-1) )
        curve.append((dates[t],eq,eqb))
    c=np.array([x[1] for x in curve]); b=np.array([x[2] for x in curve])
    mdd=float(np.min(c/np.maximum.accumulate(c))-1); mddb=float(np.min(b/np.maximum.accumulate(b))-1)
    return dict(cum=round(c[-1]-1,3),mdd=round(mdd,3),bench_cum=round(b[-1]-1,3),bench_mdd=round(mddb,3),
                turnover=round(float(np.mean(turns)),3),n=len(c))
print('송재호식 핵심(실적+주도주) top10 :',sim(m,TO20),flush=True)
print('  비용0 :',sim(m,TO20,cost_bp=0),flush=True)
print('  top5  :',sim(m,TO20,topn=5),flush=True)
print('  S4풀 전체EW:',sim(m,np.zeros((T,N)),topn=9999),flush=True)
mU=MEM.copy()&np.isfinite(C)
print('유니버스 전체EW:',sim(mU,np.zeros((T,N)),topn=9999),flush=True)
print('유니버스 거래대금top10:',sim(mU,TO20,topn=10),flush=True)

print('=== 연도별 분해 (초과 vs 유니버스) ===',flush=True)
r,_=run(m,TO20,10); x=r-BASE_A
for y in range(2020,2027):
    lo=np.searchsorted(dates,y*10000); hi=np.searchsorted(dates,(y+1)*10000)
    v=x[max(lo,s0):hi]; v=v[np.isfinite(v)]
    if len(v)<20: continue
    print(y,'n=%d mean=%.3f med=%.3f win=%.1f'%(len(v),v.mean()*100,np.median(v)*100,(v>0).mean()*100),flush=True)
print('=== 다중검정 ===',flush=True)
print('시도한 설정 수 약 32개 → Bonferroni 임계 t≈ %.2f (양측 5%%)'%(abs(__import__("scipy.stats",fromlist=["t"]).t.ppf(0.025/32,77))),flush=True)
print('DONE')
