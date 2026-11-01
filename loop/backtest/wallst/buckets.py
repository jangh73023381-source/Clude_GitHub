import pandas as pd, numpy as np, json
sec=pd.read_csv('joined.csv',dtype={'date':str,'usdate':str})
def bucket(v):
    if v<=-2: return '1.SOX≤-2%'
    if v<=-1: return '2.-2~-1%'
    if v< 1:  return '3.-1~+1%'
    if v< 2:  return '4.+1~+2%'
    return '5.SOX≥+2%'
sec['B']=sec['SOX_r'].map(bucket)
order=['1.SOX≤-2%','2.-2~-1%','3.-1~+1%','4.+1~+2%','5.SOX≥+2%']
nday=sec.groupby('B')['date'].nunique().reindex(order)
print("구간별 한국 거래일 수:"); print(nday.to_string()); print()
focus=['반도체','AI','AI전력인프라','IT테크','로봇','2차전지','원자력','방산우주','국내지수','증권','은행금융','자동차','바이오','건설','배당','귀금속','채권']
tab=sec[sec['sector'].isin(focus)].pivot_table(index='sector',columns='B',values='mean',aggfunc='mean').reindex(focus)[order]
print("■ 익일 한국 섹터 평균 수익률(%) — 전일 SOX 구간별")
print(tab.to_string(float_format=lambda v:f"{v:6.2f}"))
print()
win=sec[sec['sector'].isin(focus)].assign(w=lambda d:(d['mean']>0).astype(float)).pivot_table(index='sector',columns='B',values='w',aggfunc='mean').reindex(focus)[order]*100
print("■ 익일 상승 확률(%)")
print(win.to_string(float_format=lambda v:f"{v:5.1f}"))
tab.to_csv('bucket_mean.csv'); win.to_csv('bucket_win.csv')
