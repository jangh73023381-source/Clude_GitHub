import json,urllib.request,urllib.parse,time,csv
UA={'User-Agent':'Mozilla/5.0'}
SY=['^KS11','^KQ11','^IXIC','^NDX','^GSPC','QQQ','RSP','SPY','IWM','^SOX','SPCX','RKLB','ASTS','LUNR','ARKX','UFO',
    '012450.KS','047810.KS','099320.KQ','451760.KQ','189300.KQ','211270.KQ','462350.KQ','272210.KS','KRW=X']
out=[]
for s in SY:
    try:
        u=f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?period1=1262304000&period2=1791100000&interval=1d'
        j=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30))['chart']['result'][0]
        q=j['indicators']['quote'][0]; ts=j['timestamp']; off=j['meta'].get('gmtoffset',0)
        n=0
        for t,c,v in zip(ts,q['close'],q['volume']):
            if c is None: continue
            d=time.strftime('%Y%m%d',time.gmtime(t+off)); out.append((s,d,c,v or 0)); n+=1
        print(s,n,out[-1][1])
    except Exception as e: print(s,'ERR',e)
    time.sleep(0.3)
csv.writer(open('px.csv','w')).writerows([('sym','date','close','volume')]+out)
