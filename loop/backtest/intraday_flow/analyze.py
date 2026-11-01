import requests,re,pandas as pd,numpy as np
H={'User-Agent':'Mozilla/5.0','Referer':'https://finance.naver.com/'}
# ---- A. 10/22 하루 분 단위
f=pd.read_csv('flow_time_20261022.csv',dtype={'time':str})
j=requests.get('https://api.stock.naver.com/chart/domestic/index/KOSPI/minute?startDateTime=202610220900&endDateTime=202610221530',headers=H,timeout=15).json()
k=pd.DataFrame([(x['localDateTime'][8:12],x['currentPrice']) for x in j],columns=['hm','kospi'])
f['hm']=f.time.str[:4]; m=k.merge(f.drop_duplicates('hm'),on='hm',how='inner').sort_values('hm')
m['fc']=m.foreign/1e8; m['dk']=m.kospi.pct_change()*100; m['df']=m.fc.diff()
print('A. 10/22 분봉 매칭',len(m),'개 (',m.hm.iloc[0],'~',m.hm.iloc[-1],')')
print('   분당 외국인 순매수 변화 vs 코스피 분당 등락 상관(동시):',round(m.df.corr(m.dk),3),
      ' 외국인이 1분 먼저:',round(m.df.shift(1).corr(m.dk),3),' 주가가 1분 먼저:',round(m.df.corr(m.dk.shift(1)),3))
m5=m.iloc[::5].copy(); m5['dk']=m5.kospi.pct_change()*100; m5['df']=m5.fc.diff()
print('   5분 단위: 동시',round(m5.df.corr(m5.dk),3),' 외국인 먼저',round(m5.df.shift(1).corr(m5.dk),3),' 주가 먼저',round(m5.df.corr(m5.dk.shift(1)),3))
for hm in ['0901','1000','1100','1200','1300','1400','1500','1520','1530']:
    r=m[m.hm<=hm].iloc[-1]; print(f'   {hm[:2]}:{hm[2:]} 코스피 {r.kospi:,.2f}  외국인 누적 {r.fc:+,.0f}억')
fin=f[f.time>='160000'].iloc[0]; print(f"   16:01 집계 외국인 {fin.foreign/1e8:+,.0f}억 (15:20 단일가·장후 정정 포함)")
# ---- B. 7년 일별: 외국인 순매수 vs 갭/장중
t=requests.get('https://api.finance.naver.com/siseJson.naver?symbol=KOSPI&requestType=1&startTime=20190101&endTime=20261231&timeframe=day',headers=H,timeout=30).text
rows=[]
for rr in re.findall(r"\[([^\[\]]*)\]",t)[1:]:
    p=[x.strip().strip("'\"") for x in rr.split(',')]
    if p[0].isdigit(): rows.append((p[0],float(p[1]),float(p[4])))
ix=pd.DataFrame(rows,columns=['date','open','close'])
fl=pd.read_csv('../foreign_mkt/kospi_investor.csv',dtype={'date':str}); fl=fl[(fl[['indiv','foreign','inst']]!=0).any(axis=1)]
d=ix.merge(fl,on='date').sort_values('date').reset_index(drop=True)
d['gap']=(d.open/d.close.shift(1)-1)*100; d['intra']=(d.close/d.open-1)*100; d['ret']=d.close.pct_change()*100
d['fn']=d.foreign/d.close*2500
d['ngap']=d.gap.shift(-1); d['nintra']=d.intra.shift(-1); d['nret']=d.ret.shift(-1)
print('\nB. 2019~ 일별',len(d),'일 — 외국인 순매수(지수 수준 정규화)와의 상관')
for c in ['gap','intra','ret','ngap','nintra','nret']: print(f'   {c:6s} {d.fn.corr(d[c]):+.3f}')
q=pd.qcut(d.fn,5,labels=['강매도','매도','중립','매수','강매수'])
print(d.groupby(q)[['gap','intra','ngap','nintra']].mean().round(3).to_string())
# 갭과 장중 방향이 엇갈린 날: 외국인은 어느 쪽 편인가
up_gap_down_day=d[(d.gap>0.5)&(d.intra<-0.5)]; dn_gap_up_day=d[(d.gap<-0.5)&(d.intra>0.5)]
print(f"\n   갭상승 후 장중 하락한 날 n={len(up_gap_down_day)}: 외국인 순매수인 날 {(up_gap_down_day.foreign>0).mean()*100:.0f}%")
print(f"   갭하락 후 장중 상승한 날 n={len(dn_gap_up_day)}: 외국인 순매수인 날 {(dn_gap_up_day.foreign>0).mean()*100:.0f}%")
print(f"   전체 외국인 순매수 일 비율 {(d.foreign>0).mean()*100:.0f}%")
# 2026
y=d[d.date>='20260101']; print('\n   2026만: 외국인 vs 장중',round(y.fn.corr(y.intra),3),' vs 갭',round(y.fn.corr(y.gap),3),' vs 다음날 갭',round(y.fn.corr(y.ngap),3))
d.to_csv('daily.csv',index=False)
