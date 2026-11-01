import pandas as pd, requests, re, sys, time
from concurrent.futures import ThreadPoolExecutor

BASE='/home/'+__import__('os').environ.get('USER','')+'/mnt/loop/backtest'
import os
BASE=os.path.expanduser('~/mnt/loop/backtest')
pit=pd.read_csv(BASE+'/_krx_pit.csv',dtype={'code':str})
codes=sorted(pit.code.unique())
# + 벤치마크 ETF
codes=codes+['069500']
print('codes',len(codes),flush=True)

H={'User-Agent':'Mozilla/5.0','Referer':'https://finance.naver.com/'}
URL=('https://api.finance.naver.com/siseJson.naver?symbol={}&requestType=1'
     '&startTime=20181201&endTime=20260912&timeframe=day')

def one(c):
    for att in range(3):
        try:
            r=requests.get(URL.format(c),headers=H,timeout=15)
            t=r.text.strip()
            rows=re.findall(r"\[([^\[\]]*)\]",t)
            out=[]
            for rr in rows[1:]:
                p=[x.strip().strip("'\"") for x in rr.split(',')]
                if len(p)<6 or not p[0].isdigit(): continue
                try:
                    out.append((c,int(p[0]),float(p[1]),float(p[2]),float(p[3]),float(p[4]),float(p[5])))
                except: pass
            return out
        except Exception as e:
            time.sleep(1+att)
    return []

res=[]
with ThreadPoolExecutor(max_workers=16) as ex:
    for i,o in enumerate(ex.map(one,codes)):
        res.extend(o)
        if i%200==0: print(i,len(res),flush=True)

df=pd.DataFrame(res,columns=['code','date','open','high','low','close','volume'])
df=df[df.close>0].drop_duplicates(['code','date']).sort_values(['code','date'])
df.to_csv(BASE+'/sjh/px_daily.csv',index=False)
print('DONE',df.code.nunique(),len(df),df.date.min(),df.date.max(),flush=True)
