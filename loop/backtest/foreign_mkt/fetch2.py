import requests,re,pandas as pd,os
H={'User-Agent':'Mozilla/5.0','Referer':'https://finance.naver.com/'}
B=os.path.dirname(os.path.abspath(__file__))
t=requests.get('https://api.finance.naver.com/siseJson.naver?symbol=KOSPI&requestType=1&startTime=20190101&endTime=20261231&timeframe=day',headers=H,timeout=20).text
rows=[]
for rr in re.findall(r"\[([^\[\]]*)\]",t)[1:]:
    p=[x.strip().strip("'\"") for x in rr.split(',')]
    if p[0].isdigit(): rows.append((p[0],float(p[4])))
pd.DataFrame(rows,columns=['date','kospi']).to_csv(B+'/kospi.csv',index=False)
fx=[]
for pg in range(1,200):
    j=requests.get(f'https://api.stock.naver.com/marketindex/exchange/FX_USDKRW/prices?page={pg}&pageSize=60',headers=H,timeout=10).json()
    if not j: break
    fx+= [(x['localTradedAt'].replace('-',''),float(x['closePrice'].replace(',',''))) for x in j]
    if fx[-1][0]<'20190101': break
pd.DataFrame(fx,columns=['date','usdkrw']).drop_duplicates('date').sort_values('date').to_csv(B+'/usdkrw.csv',index=False)
print(len(rows),len(fx),fx[-1])
