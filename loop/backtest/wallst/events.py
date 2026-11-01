import pandas as pd, numpy as np, json
sec=pd.read_csv('joined.csv',dtype={'date':str,'usdate':str})
fomc=set(json.load(open('fomc_dates.json'))+['20190501','20200315'])
sec['is_fomc']=sec['usdate'].isin(fomc)
kd=sec[['date','usdate','SOX_r','GSPC_r','TNX_d','is_fomc']].drop_duplicates('date').sort_values('date').reset_index(drop=True)
ev=kd[kd['is_fomc']]
print("FOMC 결정 익일 한국 거래일:",len(ev))
print("  그날 밤 미국: SOX 평균 %+.2f%% (|SOX|평균 %.2f%%) / SPX %+.2f%% / 10년물 %+.1fbp"%(
    ev['SOX_r'].mean(),ev['SOX_r'].abs().mean(),ev['GSPC_r'].mean(),ev['TNX_d'].mean()))
print("  전체 평균: |SOX| %.2f%% / |SPX| %.2f%% / |10Y| %.1fbp"%(
    kd['SOX_r'].abs().mean(),kd['GSPC_r'].abs().mean(),kd['TNX_d'].abs().mean()))
print()
focus=['반도체','AI','IT테크','2차전지','원자력','국내지수','은행금융','바이오','귀금속','채권']
f=sec[sec['sector'].isin(focus)]
a=f[f['is_fomc']].groupby('sector')['mean'].agg(['mean','median','count'])
b=f[~f['is_fomc']].groupby('sector')['mean'].agg(['mean','median'])
cmp=a.join(b,rsuffix='_평시').reindex(focus)
cmp.columns=['FOMC익일평균','FOMC익일중앙','n','평시평균','평시중앙']
print("■ FOMC 결정 익일 한국 섹터 (%)")
print(cmp.to_string(float_format=lambda v:f"{v:6.2f}"))
print()
# FOMC 방향별
ev2=f.merge(kd[['date','is_fomc']].rename(columns={'is_fomc':'x'}),on='date')
up=f[f['is_fomc']&(f['SOX_r']>0)]; dn=f[f['is_fomc']&(f['SOX_r']<=0)]
t=pd.DataFrame({'FOMC후SOX상승':up.groupby('sector')['mean'].mean(),
                'n_up':up.groupby('sector')['mean'].count(),
                'FOMC후SOX하락':dn.groupby('sector')['mean'].mean(),
                'n_dn':dn.groupby('sector')['mean'].count()}).reindex(focus)
print("■ FOMC 반응 방향별 익일 한국 (%)")
print(t.to_string(float_format=lambda v:f"{v:6.2f}"))
