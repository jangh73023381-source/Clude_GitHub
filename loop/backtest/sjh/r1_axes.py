exec(open(__import__('os').path.expanduser('~/mnt/loop/backtest/sjh/engine.py')).read())
import time,json
t0=time.time()
# 섹터 선점 캐시 (20일 수익률 중앙값 상위 5섹터 / 자금유입 상위 5섹터)
S1_MOM=np.load(S+'/S1_MOM.npy')
S1_FLOW=np.load(S+'/S1_FLOW.npy')
print('sector cache',round(time.time()-t0,1),'s  pass-rate',S1_MOM.mean().round(3),S1_FLOW.mean().round(3),flush=True)

res=[]
def go(label,cfg,topn=10):
    cfg=dict(cfg)
    if cfg.get('s1')=='mom': cfg['_s1cache']=S1_MOM
    elif cfg.get('s1')=='flow': cfg['_s1cache']=S1_FLOW
    m,sc=build(cfg)
    r,_=run(m,sc,topn)
    st=stats(r,label); st['pool']=int(np.nanmean(m[MEM.any(1)].sum(1)))
    res.append(st); print(st,flush=True); return r,m,sc

# --- 기준선들
mb=MEM.copy()&np.isfinite(EA)
rb=np.array([np.nanmean(EA[t][mb[t]]) if mb[t].sum()>0 else np.nan for t in range(T)])
res.append(dict(**stats(rb,'[기준] 유니버스 동일가중'),pool=int(np.nanmean(MEM.sum(1)))))
print(res[-1],flush=True)

# --- 단일 축 (각각 단독, 랭킹=거래대금, top10)
go('G 시장게이트만(지수>MA20)',dict(gate=1))
go('S1 섹터선점(20일모멘텀 상위5섹터)',dict(s1='mom'))
go('S1f 섹터선점(자금유입 상위5섹터)',dict(s1='flow'))
go('S2 선취매(미급등: 고점대비<0.9 & 60일수익 하위절반)',dict(s2=1))
go('S3 성장모멘텀(매출 YoY>0)',dict(s3=1))
go('S4 실적확인(영업이익 YoY>0 & 흑자)',dict(s4=1))
go('S5a 바닥탈출',dict(s5='bottom'))
go('S5b 눌림목',dict(s5='pull'))
go('S5 바닥OR눌림',dict(s5='either'))
go('S6 주도주집중만(거래대금 상위10)',dict())
json.dump(res,open(S+'/res_axes.json','w'),ensure_ascii=False,indent=1)
print('elapsed',round(time.time()-t0,1))
