"""증시자금동향(고객예탁금·신용융자잔고, 억원) 일별 — 네이버 stock.naver.com/api/domestic/market/trendDeposit. 조회 전용."""
import requests,pandas as pd,os
H={'User-Agent':'Mozilla/5.0','Referer':'https://finance.naver.com/sise/sise_deposit.naver'}
rows=[];i=0
while True:
    j=requests.get(f'https://stock.naver.com/api/domestic/market/trendDeposit?startIdx={i}&pageSize=200',headers=H,timeout=15).json()
    c=j.get('content') or []
    if not c: break
    rows+=[(x['bizdate'],int(x['customerDeposit']),int(x['creditLoan'])) for x in c]
    if c[-1]['bizdate']<'20100101': break
    i+=1
df=pd.DataFrame(rows,columns=['date','deposit','credit']).drop_duplicates('date').sort_values('date')
df.to_csv('credit.csv',index=False); print(len(df),df.date.iloc[0],df.date.iloc[-1]); print(df.tail(3).to_string(index=False))
