# -*- coding: utf-8 -*-
"""(7) 반도체 1월 독립 복제: 다른 반도체 종목 + 미국 SOX"""
import yfinance as yf, pandas as pd, numpy as np, time
T={'005930.KS':'삼성전자','000990.KS':'DB하이텍','042700.KS':'한미반도체','039030.KQ':'이오테크닉스','^SOX':'미국 필라델피아반도체'}
px={}
for t in T:
    for a in range(3):
        d=yf.download(t,start='2000-01-01',progress=False,auto_adjust=False,threads=False)
        if d is not None and len(d): break
        time.sleep(2)
    c=d['Close']
    if hasattr(c,'columns'): c=c.iloc[:,0]
    px[t]=c.dropna()
    time.sleep(0.3)
ks=yf.download('^KS11',start='2000-01-01',progress=False,auto_adjust=False,threads=False)['Close']
if hasattr(ks,'columns'): ks=ks.iloc[:,0]
spx=yf.download('^GSPC',start='2000-01-01',progress=False,auto_adjust=False,threads=False)['Close']
if hasattr(spx,'columns'): spx=spx.iloc[:,0]
mk=ks.resample('ME').last().pct_change()*100
ms=spx.resample('ME').last().pct_change()*100
print('  종목                       1월 n   1월 초과평균   t값   승률 | 전체월 평균')
for t,n in T.items():
    m=px[t].resample('ME').last().pct_change()*100
    b=ms if t=='^SOX' else mk
    ex=(m-b).dropna(); j=ex[ex.index.month==1].values
    tt=j.mean()/(j.std(ddof=1)/np.sqrt(len(j)))
    print(f'  {n:<22} {len(j):4d}   {j.mean():+8.2f}%p  {tt:+5.2f}  {(j>0).mean()*100:5.1f}% | {ex.mean():+6.2f}')
