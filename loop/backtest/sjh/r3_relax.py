exec(open(__import__('os').path.expanduser('~/mnt/loop/backtest/sjh/engine.py')).read())
import numpy as np, json
S1_MOM=np.load(S+'/S1_MOM.npy'); S1_FLOW=np.load(S+'/S1_FLOW.npy')
BASE_A=np.load(S+'/BASE_A.npy'); BASE_B=np.load(S+'/BASE_B.npy')
s0=np.searchsorted(dates,20200403)
S1_8=sector_rank(sec,G2,R20,8); S1_12=sector_rank(sec,G2,R20,12)
np.save(S+'/S1_8.npy',S1_8); np.save(S+'/S1_12.npy',S1_12)
CACHE={'mom':S1_MOM,'flow':S1_FLOW,'mom8':S1_8,'mom12':S1_12}

def stat2(r,label,extra=None,B=None):
    B=BASE_A if B is None else B
    out={'label':label}
    for nm,x in [('vsBM',r),('vsUNI',r-B)]:
        v=x[s0:]; v=v[np.isfinite(v)]
        ii=np.arange(s0,T,20); nv=x[ii]; nv=nv[np.isfinite(nv)]
        t=nv.mean()/(nv.std(ddof=1)/np.sqrt(len(nv))) if len(nv)>2 else np.nan
        out[nm+'_mean']=round(v.mean()*100,3); out[nm+'_med']=round(np.median(v)*100,3)
        out[nm+'_t']=round(t,2); out[nm+'_win']=round((v>0).mean()*100,1)
    out['n']=int(np.isfinite(r[s0:]).sum())
    if extra: out.update(extra)
    return out
res=[]
def go(label,cfg,topn=10,keep=False):
    cfg=dict(cfg)
    if cfg.get('s1') in CACHE: cfg['_s1cache']=CACHE[cfg['s1']]
    m,sc=build(cfg); r,pk=run(m,sc,topn)
    st=stat2(r,label,{'pool':round(float(m[s0:].sum(1).mean()),1),'topn':topn})
    res.append(st); print(json.dumps(st,ensure_ascii=False),flush=True); 
    return (r,m,sc) if keep else None

F=dict(gate=1,s1='mom8',s3=1,s4=1,rank='to')
print('--- 송재호식 완화판(풀 확보) ---',flush=True)
go('V1 G+섹터8+실적성장(S3&S4)',F)
go('V2 V1+선취매soft(고점<0.9)',dict(F,s2='soft'))
go('V3 V1+선취매hard(원안)',dict(F,s2='hard'))
go('V4 V1+바닥OR눌림',dict(F,s5='either'))
go('V5 V1+선취매soft+바닥OR눌림 = 송재호식 완화 전체',dict(F,s2='soft',s5='either'))
print('--- 방향 반전(선취매 ↔ 신고가) ---',flush=True)
go('V6 V1+신고가근접(선취매 반전)',dict(F,s2='inv'))
go('V7 V1+신고가근접+랭킹 모멘텀',dict(F,s2='inv',rank='mom'))
print('--- 랭킹축 교체 ---',flush=True)
for rk,nm in [('to','거래대금(주도주)'),('mc','시총'),('mom','20일모멘텀')]:
    go('V1 랭킹=%s'%nm,dict(F,rank=rk))
print('--- 실적축 단독 강도 ---',flush=True)
go('S4만 + 게이트',dict(gate=1,s4=1,rank='to'))
go('S3&S4만',dict(s3=1,s4=1,rank='to'))
go('S3&S4만 + 게이트',dict(gate=1,s3=1,s4=1,rank='to'))
json.dump(res,open(S+'/res_relax.json','w'),ensure_ascii=False,indent=1)
print('DONE')
