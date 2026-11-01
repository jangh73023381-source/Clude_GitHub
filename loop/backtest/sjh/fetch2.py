import pandas as pd, requests, re, sys, time, os, glob
from concurrent.futures import ThreadPoolExecutor
B=os.path.expanduser('~/mnt/loop/backtest'); S=B+'/sjh'
pit=pd.read_csv(B+'/_krx_pit.csv',dtype={'code':str})
codes=sorted(set(pit.code.unique())|{'069500'})
done=set()
for f in glob.glob(S+'/_p_*.csv')+glob.glob(S+'/px_daily.csv'):
    try: done|=set(pd.read_csv(f,dtype={'code':str}).code.unique())
    except: pass
todo=[c for c in codes if c not in done]
print('todo',len(todo),flush=True)
H={'User-Agent':'Mozilla/5.0','Referer':'https://finance.naver.com/'}
URL=('https://api.finance.naver.com/siseJson.naver?symbol={}&requestType=1'
     '&startTime=20181201&endTime=20260912&timeframe=day')
def one(c):
    for att in range(2):
        try:
            t=requests.get(URL.format(c),headers=H,timeout=10).text
            out=[]
            for rr in re.findall(r"\[([^\[\]]*)\]",t)[1:]:
                p=[x.strip().strip("'\"") for x in rr.split(',')]
                if len(p)<6 or not p[0].isdigit(): continue
                try: out.append((c,int(p[0]),float(p[1]),float(p[2]),float(p[3]),float(p[4]),float(p[5])))
                except: pass
            return out
        except Exception: time.sleep(0.5)
    return []
CH=700
for i in range(0,len(todo),CH):
    chunk=todo[i:i+CH]; res=[]
    with ThreadPoolExecutor(max_workers=16) as ex:
        for o in ex.map(one,chunk): res.extend(o)
    pd.DataFrame(res,columns=['code','date','open','high','low','close','volume']).to_csv(
        S+'/_p_'+chunk[0]+'.csv',index=False)
    print('chunk',i,len(res),flush=True)
print('OK',flush=True)
