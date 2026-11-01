import json,urllib.request,datetime,csv,os,sys
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
P1=1546300800   # 2019-01-01
P2=1788912000   # 2026-09-09
SYMS={'GSPC':'%5EGSPC','IXIC':'%5EIXIC','SOX':'%5ESOX','TNX':'%5ETNX','VIX':'%5EVIX','DXY':'DX-Y.NYB','KS11':'%5EKS11','KQ11':'%5EKQ11','USDKRW':'KRW=X','NVDA':'NVDA','SMH':'SMH'}
out={}
for name,q in SYMS.items():
    fp=f'{name}.csv'
    if os.path.exists(fp) and os.path.getsize(fp)>1000:
        print(name,'skip'); continue
    u=f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?period1={P1}&period2={P2}&interval=1d"
    try:
        d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30))
        r=d['chart']['result'][0]
        ts=r['timestamp']; c=r['indicators']['quote'][0]
        with open(fp,'w',newline='') as f:
            w=csv.writer(f); w.writerow(['date','open','high','low','close','volume'])
            for i,t in enumerate(ts):
                dt=datetime.datetime.utcfromtimestamp(t).strftime('%Y%m%d')
                w.writerow([dt,c['open'][i],c['high'][i],c['low'][i],c['close'][i],c['volume'][i]])
        print(name,len(ts),dt)
    except Exception as e:
        print(name,'ERR',e)
