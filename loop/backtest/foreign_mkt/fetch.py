"""코스피 시장 투자자별 순매수(억원) 일별 — 네이버 모바일 index trend API. 조회 전용, 멱등."""
import requests,pandas as pd,os,sys
from concurrent.futures import ThreadPoolExecutor
H={'User-Agent':'Mozilla/5.0'}
B=os.path.dirname(os.path.abspath(__file__))
px=pd.read_csv(os.path.join(B,'..','panel_ohlc_long.csv'),usecols=['code','date'],dtype={'code':str,'date':str})
dates=sorted(set(px[px.code=='069500'].date.unique())|set(pd.read_csv(os.path.join(B,'kospi.csv'),dtype={'date':str}).date))
dates+= [d for d in ['20260923','20260924','20260925','20260926','20260929','20260930','20261001','20261002','20261005','20261006'] if d not in dates]
out=os.path.join(B,'kospi_investor.csv')
done=set(pd.read_csv(out,dtype=str).date) if os.path.exists(out) else set()
todo=[d for d in dates if d not in done]
def one(d):
    try:
        j=requests.get('https://m.stock.naver.com/api/index/KOSPI/trend?bizdate='+d,headers=H,timeout=10).json()
        if j.get('bizdate')!=d: return None
        f=lambda s:int(s.replace(',','').replace('+',''))
        return (d,f(j['personalValue']),f(j['foreignValue']),f(j['institutionalValue']))
    except Exception: return None
with ThreadPoolExecutor(12) as ex: res=[r for r in ex.map(one,todo) if r]
df=pd.DataFrame(res,columns=['date','indiv','foreign','inst'])
if os.path.exists(out): df=pd.concat([pd.read_csv(out,dtype={'date':str}),df])
df.drop_duplicates('date').sort_values('date').to_csv(out,index=False)
print(len(todo),'fetched',len(res),'total',len(df))
