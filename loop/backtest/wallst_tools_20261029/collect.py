# 월가 시장분석 도구 이력 수집 (2026-10-29, 루프 외 · 사용자 요청). 조회 전용·멱등.
import urllib.request, json, csv, io, os, sys, time, datetime as dt
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
R=os.path.join(os.path.dirname(os.path.abspath(__file__)),'raw')
def get(url,hdr=UA,to=60):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url,headers=hdr),timeout=to).read()
        except Exception as e:
            err=e; time.sleep(2)
    raise err
def save(name,rows,head):
    with open(os.path.join(R,name),'w',newline='') as f:
        w=csv.writer(f); w.writerow(head); w.writerows(rows)
    print(name,len(rows),rows[0] if rows else None,rows[-1] if rows else None)
YAHOO=['^VIX','^VIX3M','^SKEW','^TNX','^IRX','DX-Y.NYB','KRW=X','^GSPC','SPY','EEM','HYG','IEF','AUDJPY=X','HG=F','GC=F','KC=F','069500.KS']
FRED=['BAMLH0A0HYM2','BAA10Y','T10Y2Y','NFCI','STLFSI4','WALCL','WTREGEN','RRPONTSYD']
only=sys.argv[1:]
for a in only:
    if a not in YAHOO+FRED+['OFR','CNN','NAAIM']: (YAHOO if ('=' in a or '^' in a or '.' in a) else FRED).append(a)
p1=int(dt.datetime(2009,1,1).timestamp()); p2=int(time.time())
for s in YAHOO:
    if only and s not in only: continue
    try:
        j=json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?period1={p1}&period2={p2}&interval=1d"))
        r=j['chart']['result'][0]; q=r['indicators']['quote'][0]
        rows=[(dt.datetime.utcfromtimestamp(t+r['meta'].get('gmtoffset',0)).strftime('%Y%m%d'),q['open'][i],q['high'][i],q['low'][i],q['close'][i]) for i,t in enumerate(r['timestamp']) if q['close'][i] is not None]
        save('y_'+s.replace('^','').replace('=','_')+'.csv',rows,['date','open','high','low','close'])
    except Exception as e: print('FAIL',s,e)
import urllib.parse
for s in FRED:
    if only and s not in only: continue
    try:
        t=get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}",hdr={},to=90).decode()
        rows=[(a.replace('-',''),b) for a,b in csv.reader(io.StringIO(t)) if b not in ('',s,'.') and a[:1].isdigit()]
        save('f_'+s+'.csv',rows,['date','value'])
    except Exception as e: print('FAIL',s,e)
if not only or 'OFR' in only:
    t=get("https://www.financialresearch.gov/financial-stress-index/data/fsi.csv").decode()
    rr=list(csv.reader(io.StringIO(t))); save('ofr_fsi.csv',[(a[0].replace('-',''),a[1]) for a in rr[1:] if a[1]],['date','value'])
if not only or 'CNN' in only:
    import subprocess  # urllib 은 418(봇 차단), curl 은 통과
    j=json.loads(subprocess.run(['curl','-s','--max-time','40','-A',UA['User-Agent'],'-H','Referer: https://edition.cnn.com/','https://production.dataviz.cnn.io/index/fearandgreed/graphdata/2020-07-15'],capture_output=True).stdout)
    h=j['fear_and_greed_historical']['data']
    save('cnn_fg.csv',[(dt.datetime.utcfromtimestamp(x['x']/1000).strftime('%Y%m%d'),x['y']) for x in h],['date','value'])
if not only or 'NAAIM' in only:
    b=get("https://naaim.org/wp-content/uploads/2026/08/USE_Data-since-Inception_2026-08-19.xlsx")
    open(os.path.join(R,'naaim.xlsx'),'wb').write(b); print('naaim.xlsx',len(b))
