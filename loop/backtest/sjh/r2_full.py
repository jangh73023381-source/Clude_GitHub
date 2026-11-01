exec(open(__import__('os').path.expanduser('~/mnt/loop/backtest/sjh/engine.py')).read())
import numpy as np, json, time
S1_MOM=np.load(S+'/S1_MOM.npy'); S1_FLOW=np.load(S+'/S1_FLOW.npy')
s0=np.searchsorted(dates,20200403)

# 유니버스 동일가중 초과(기준선) : A/B 각각
def base_series(E):
    mb=MEM&np.isfinite(E)
    return np.array([np.nanmean(E[t][mb[t]]) if mb[t].sum()>=20 else np.nan for t in range(T)])
BASE_A=base_series(EA); BASE_B=base_series(EB)
np.save(S+'/BASE_A.npy',BASE_A); np.save(S+'/BASE_B.npy',BASE_B)

def stat2(r,label,extra=None):
    rel=r-BASE_A if len(r)==T else None
    out={'label':label}
    for nm,x in [('vsBM',r),('vsUNI',r-BASE_A)]:
        v=x[s0:]; v=v[np.isfinite(v)]
        ii=np.arange(s0,T,20); nv=x[ii]; nv=nv[np.isfinite(nv)]
        t=nv.mean()/(nv.std(ddof=1)/np.sqrt(len(nv))) if len(nv)>2 else np.nan
        out[nm+'_mean']=round(v.mean()*100,3); out[nm+'_med']=round(np.median(v)*100,3)
        out[nm+'_t']=round(t,2); out[nm+'_win']=round((v>0).mean()*100,1)
    out['n']=int(np.isfinite(r[s0:]).sum())
    if extra: out.update(extra)
    return out

res=[]
def go(label,cfg,topn=10,E=None,keep=False):
    cfg=dict(cfg)
    if cfg.get('s1')=='mom': cfg['_s1cache']=S1_MOM
    elif cfg.get('s1')=='flow': cfg['_s1cache']=S1_FLOW
    m,sc=build(cfg)
    r,pk=run(m,sc,topn,E=E)
    pool=float(np.nanmean(m[s0:].sum(1)))
    st=stat2(r,label,{'pool':round(pool,0),'topn':topn})
    res.append(st); print(json.dumps(st,ensure_ascii=False),flush=True)
    return (r,m,sc,pk) if keep else None

print(json.dumps(stat2(BASE_A,'[기준] 유니버스 동일가중',{'pool':round(float(MEM[s0:].sum(1).mean()),0)}),ensure_ascii=False),flush=True)
res.append(stat2(BASE_A,'[기준] 유니버스 동일가중',{'pool':round(float(MEM[s0:].sum(1).mean()),0)}))

print('--- 단일 축 ---',flush=True)
go('G 시장게이트(지수>MA20)',dict(gate=1))
go('S1 섹터선점(20일모멘텀 상위5)',dict(s1='mom'))
go('S1f 섹터선점(자금유입 상위5)',dict(s1='flow'))
go('S2 선취매(미급등)',dict(s2=1))
go('S3 성장모멘텀(매출YoY>0)',dict(s3=1))
go('S4 실적확인(영업이익YoY>0&흑자)',dict(s4=1))
go('S5a 바닥탈출',dict(s5='bottom'))
go('S5b 눌림목',dict(s5='pull'))
go('S5 바닥OR눌림',dict(s5='either'))
go('S6 주도주집중(거래대금랭킹)',dict())

print('--- 누적 결합 ---',flush=True)
acc=dict(gate=1); go('G',acc)
acc=dict(gate=1,s1='mom'); go('G+S1',acc)
acc=dict(gate=1,s1='mom',s2=1); go('G+S1+S2',acc)
acc=dict(gate=1,s1='mom',s2=1,s3=1); go('G+S1+S2+S3',acc)
acc=dict(gate=1,s1='mom',s2=1,s3=1,s4=1); go('G+S1+S2+S3+S4',acc)
FULL=dict(gate=1,s1='mom',s2=1,s3=1,s4=1,s5='either',rank='to')
rF,mF,scF,pkF=go('★원안 전체결합(G+S1~S5, 주도주랭킹)',FULL,keep=True)
np.save(S+'/mFULL.npy',mF); np.save(S+'/rFULL.npy',rF)

print('--- 대조군 ---',flush=True)
# 1) 풀 내 무작위 (필터 vs 랭킹 분리)
ph=[]
for sd in range(200):
    rs=np.random.RandomState(sd); sc=rs.rand(T,N)
    r,_=run(mF,sc,10)
    ph.append(np.nanmean((r-BASE_A)[s0:]))
ph=np.array(ph)*100
print('풀내 무작위10 (200회) vsUNI 평균 %.3f  [p5 %.3f p50 %.3f p95 %.3f]  원안 %.3f  p=%.3f'%(
    ph.mean(),np.percentile(ph,5),np.percentile(ph,50),np.percentile(ph,95),
    np.nanmean((rF-BASE_A)[s0:])*100, (ph>=np.nanmean((rF-BASE_A)[s0:])*100).mean()),flush=True)
res.append({'label':'대조군: 풀내 무작위10(200회)','vsUNI_mean':round(ph.mean(),3),
            'p5':round(np.percentile(ph,5),3),'p95':round(np.percentile(ph,95),3),
            'p_value':round(float((ph>=np.nanmean((rF-BASE_A)[s0:])*100).mean()),3)})
# 2) 유니버스 무작위 (필터 없음)
ph2=[]
mU=MEM.copy()
for sd in range(100):
    rs=np.random.RandomState(1000+sd); sc=rs.rand(T,N)
    r,_=run(mU,sc,10); ph2.append(np.nanmean((r-BASE_A)[s0:]))
ph2=np.array(ph2)*100
print('유니버스 무작위10(100회) vsUNI 평균 %.3f [%.3f~%.3f]'%(ph2.mean(),ph2.min(),ph2.max()),flush=True)
res.append({'label':'대조군: 유니버스 무작위10(100회)','vsUNI_mean':round(ph2.mean(),3)})
# 3) 무관 신호 대조군: 종목코드 숫자 기반(주가와 무관)
fake=np.tile(np.array([int(c) for c in codes],dtype=float),(T,1))
r,_=run(MEM.copy(),fake,10); res.append(stat2(r,'대조군: 무관신호(종목코드 순)'))
print(json.dumps(res[-1],ensure_ascii=False),flush=True)
json.dump(res,open(S+'/res_full.json','w'),ensure_ascii=False,indent=1)
print('DONE')
