import pandas as pd, numpy as np, json
sec=pd.read_csv('joined.csv',dtype={'date':str,'usdate':str})
fomc=set(json.load(open('fomc_dates.json'))+['20190501','20200315'])
kd=sorted(sec['date'].unique())
kidx={d:i for i,d in enumerate(kd)}
# 이벤트 '전날' 한국장 = 그날 밤(KST 새벽) FOMC가 있는 미국날짜 D 의 한국 같은 날짜 D
pre=[d for d in kd if d in fomc]
print("FOMC 당일(=발표 전 한국장) 거래일:",len(pre))
foc=['반도체','AI','국내지수','2차전지','귀금속','채권']
f=sec[sec['sector'].isin(foc)]
a=f[f['date'].isin(pre)].groupby('sector')['mean'].agg(['mean','median','count'])
b=f[~f['date'].isin(pre)].groupby('sector')['mean'].mean().rename('평시')
print("\n■ FOMC 발표 전 한국장 당일 수익률(%)")
print(a.join(b).reindex(foc).to_string(float_format=lambda v:f"{v:6.3f}"))

# 버킷별 D+1,D+2,D+3 누적
piv=sec.pivot_table(index='date',columns='sector',values='mean')
piv=piv.reindex(kd)
us=sec[['date','SOX_r']].drop_duplicates('date').set_index('date').reindex(kd)['SOX_r']
def bk(v):
    if v<=-2: return '①SOX≤-2%'
    if v<=-1: return '②-2~-1%'
    if v<1: return '③-1~+1%'
    if v<2: return '④+1~+2%'
    return '⑤SOX≥+2%'
B=us.map(bk)
rows=[]
for s in ['반도체','AI','국내지수','2차전지','귀금속','채권']:
    r=piv[s]
    for lab in ['①SOX≤-2%','②-2~-1%','③-1~+1%','④+1~+2%','⑤SOX≥+2%']:
        m=(B==lab)
        d1=r[m].mean()
        d2=(r.shift(-1)[m]).mean()
        d3=(r.shift(-2)[m]).mean()
        rows.append({'sector':s,'bucket':lab,'D+1':d1,'D+2':d2,'D+3':d3,'누적3일':d1+d2+d3,'n':int(m.sum())})
t=pd.DataFrame(rows)
print("\n■ 전일 SOX 구간별 한국 섹터 D+1/D+2/D+3 (%) — 충격이 하루로 끝나는가")
for s,g in t.groupby('sector',sort=False):
    print(f"\n[{s}]")
    print(g[['bucket','D+1','D+2','D+3','누적3일','n']].to_string(index=False,float_format=lambda v:f"{v:6.2f}"))
