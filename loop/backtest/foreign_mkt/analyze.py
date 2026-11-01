import pandas as pd,numpy as np
f=pd.read_csv('kospi_investor.csv',dtype={'date':str}); f=f[(f[['indiv','foreign','inst']]!=0).any(axis=1)]
k=pd.read_csv('kospi.csv',dtype={'date':str}); x=pd.read_csv('usdkrw.csv',dtype={'date':str})
d=f.merge(k,on='date').merge(x,on='date',how='left'); d['usdkrw']=d.usdkrw.ffill()
d['fn']=d.foreign/d.kospi*2500   # KOSPI 2500 기준으로 규모 정규화(억원)
d['s20']=d.fn.rolling(20).sum(); d['s60']=d.fn.rolling(60).sum()
d['ym']=d.date.str[:6]
print('== 최근 월별 외국인 순매수(억원, 원값) / KOSPI 월말 / 환율 월말')
m=d.groupby('ym').agg(foreign=('foreign','sum'),kospi=('kospi','last'),fx=('usdkrw','last'),days=('date','count'))
print(m.tail(16).to_string())
print('\n== 최근 30거래일')
print(d[['date','foreign','inst','indiv','kospi','usdkrw']].tail(30).to_string(index=False))
# 연속 순매도 일수
s=(d.foreign<0).astype(int).values; streak=0
for v in s[::-1]:
    if v: streak+=1
    else: break
print('\n현재 연속 순매도 일수',streak)
# 순매도 국면: s20 이 음수인 연속 구간
neg=(d.s20<0).values; eps=[]; i=0
while i<len(d):
    if neg[i]:
        j=i
        while j<len(d) and neg[j]: j+=1
        seg=d.iloc[i:j]
        eps.append(dict(start=d.date.iloc[i],end=d.date.iloc[j-1],days=j-i,ongoing=j==len(d),cum=seg.fn.sum(),
            kospi_ret=(d.kospi.iloc[j-1]/d.kospi.iloc[max(i-20,0)]-1)*100,fx_chg=d.usdkrw.iloc[j-1]-d.usdkrw.iloc[max(i-20,0)],
            fx_after20=(d.usdkrw.iloc[min(j+19,len(d)-1)]-d.usdkrw.iloc[j-1]) if j<len(d) else np.nan,
            k_after20=(d.kospi.iloc[min(j+19,len(d)-1)]/d.kospi.iloc[j-1]-1)*100 if j<len(d) else np.nan))
        i=j
    else: i+=1
E=pd.DataFrame(eps); E=E[E.days>=5]
print('\n== 20일 누적 순매도 국면(5일 이상) — 총',len(E))
print(E.round(1).to_string(index=False))
done=E[~E.ongoing]
print('\n완료 국면 지속일 분포: 중앙',done.days.median(),'평균',round(done.days.mean(),1),'75%',done.days.quantile(.75),'최대',done.days.max())
cur=E[E.ongoing]
if len(cur):
    L=int(cur.days.iloc[0]); longer=done[done.days>=L]
    print(f'현재 국면 {L}일째. 과거 {L}일 이상 간 국면 {len(longer)}개 → 추가 지속 중앙 {np.median(longer.days-L) if len(longer) else np.nan}일, 목록 {list(longer.days)}')
# 환율 선행성: 환율 20일 변화 vs 향후 20일 외국인 순매수(정규화) 상관
d['fx20']=d.usdkrw.diff(20); d['fwd20']=d.fn[::-1].rolling(20).sum()[::-1].shift(-1); d['k20']=d.kospi.pct_change(20)*100
for col in ['fx20','k20','s20']:
    c=d[[col,'fwd20']].dropna().corr().iloc[0,1]; print(f'상관 {col} → 향후20일 외국인순매수: {c:+.3f}')
# 동시 상관
d['fxd']=d.usdkrw.diff(); print('일별 동시 상관 외국인순매수 vs 환율변화',round(d[['fn','fxd']].dropna().corr().iloc[0,1],3),' vs KOSPI 등락',round(d.fn.corr(d.kospi.pct_change()),3))
# 외국인 순매수 지속성: 오늘 부호 → 내일 부호
p=((d.foreign>0)==(d.foreign.shift(-1)>0)).mean(); print('외국인 순매수 부호 다음날 유지 확률',round(p,3))
# s20 부호 전환 후 KOSPI 성과
d.to_csv('merged.csv',index=False)
