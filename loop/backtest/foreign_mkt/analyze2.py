"""외국인 순매도 국면이 끝나는 조건 — 어떤 상태에서 이후 20일 외국인 누적이 플러스로 돌았나(사후 조건부 빈도, 예측 규칙 아님)."""
import pandas as pd,numpy as np
d=pd.read_csv('merged.csv',dtype={'date':str})
t=pd.read_csv('../rates/TNX.csv',dtype={'date':str}).rename(columns={'close':'us10'})
# 한국 D일에는 D 이전 마지막 미국 종가
d['di']=d.date.astype(int); t['di']=t.date.astype(int); d=pd.merge_asof(d.sort_values('di'),t[['di','us10']].sort_values('di'),on='di',allow_exact_matches=False)
d['us10_20']=(d.us10-d.us10.shift(20))*100
d['k_dd']=(d.kospi/d.kospi.rolling(120,min_periods=20).max()-1)*100
d['fwd_pos']=(d.fwd20>0).astype(float); d.loc[d.fwd20.isna(),'fwd_pos']=np.nan
base=d[d.s20<0]   # 순매도 국면 안의 날만
print('순매도 국면 날 수',len(base),' 이후 20일 외국인 순매수 전환 기저확률',round(base.fwd_pos.mean(),3))
def cond(name,m):
    s=base[m].fwd_pos.dropna(); print(f'{name:38s} n{len(s):4d} 전환확률 {s.mean():.3f}')
cond('미국10년물 20일 −15bp 이하',base.us10_20<=-15)
cond('미국10년물 20일 +15bp 이상',base.us10_20>=15)
cond('환율 20일 −20원 이하(원화강세)',base.fx20<=-20)
cond('환율 20일 +20원 이상(원화약세)',base.fx20>=20)
cond('KOSPI 120일 고점 대비 −15% 이하',base.k_dd<=-15)
cond('KOSPI 120일 고점 대비 −5% 이내',base.k_dd>-5)
cond('KOSPI 20일 −5% 이하',base.k20<=-5)
cond('20일 누적 매도 강도 하위 25%(가장 셈)',base.s20<=base.s20.quantile(.25))
cond('20일 누적 매도 약함(상위 25%)',base.s20>=base.s20.quantile(.75))
cond('2026년만',base.date>='20260101')
last=d.iloc[-1]; print('\n오늘 상태: us10',round(last.us10,3),'us10 20일',round(last.us10_20,1),'bp · fx20',last.fx20,'· KOSPI 120일고점대비',round(last.k_dd,1),'% · k20',round(last.k20,2),'· s20(정규화)',round(last.s20))
print('s20 분위(국면 내)',round((base.s20<=last.s20).mean(),3))
# 2026 누적
y=d[d.date>='20260101']; print('2026 외국인 누적(억원 원값)',y.foreign.sum(),' 2월 이후',d[d.date>='20260201'].foreign.sum())
