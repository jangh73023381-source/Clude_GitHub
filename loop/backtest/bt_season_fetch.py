import yfinance as yf, pandas as pd, time, os
UNI=[('반도체','000660','SK하이닉스'),('자동차','005380','현대차'),('증권','006800','미래에셋증권'),
('은행금융','105560','KB금융'),('방산','012450','한화에어로스페이스'),('조선','329180','HD현대중공업'),
('2차전지','373220','LG에너지솔루션'),('바이오','207940','삼성바이오로직스'),('원자력','034020','두산에너빌리티'),
('AI전력','010120','LS ELECTRIC'),('화장품','090430','아모레퍼시픽'),('로봇','277810','레인보우로보틱스'),
('태양광','009830','한화솔루션'),('건설','047040','대우건설'),('금속귀금속','010130','고려아연')]
rows=[]
for sec,code,name in UNI:
    for suf in ('.KS','.KQ'):
        try:
            d=yf.download(code+suf,start='2000-01-01',progress=False,auto_adjust=False,threads=False)
        except Exception as e:
            print('ERR',code,suf,e); continue
        if d is None or len(d)==0: continue
        c=d['Close']
        if hasattr(c,'columns'): c=c.iloc[:,0]
        c=c.dropna()
        if len(c)<200: continue
        for dt,v in c.items():
            rows.append((sec,code,name,dt.strftime('%Y-%m-%d'),float(v)))
        print(code,name,suf,len(c),c.index[0].date(),c.index[-1].date())
        break
    time.sleep(0.3)
# benchmark
for bcode in ('^KS11','^KQ11'):
    for attempt in range(4):
        d=yf.download(bcode,start='2000-01-01',progress=False,auto_adjust=False,threads=False)
        if d is not None and len(d)>0: break
        time.sleep(3)
    c=d['Close']
    if hasattr(c,'columns'): c=c.iloc[:,0]
    c=c.dropna()
    for dt,v in c.items(): rows.append(('BENCH',bcode,bcode,dt.strftime('%Y-%m-%d'),float(v)))
    print(bcode,len(c),c.index[0].date(),c.index[-1].date())
pd.DataFrame(rows,columns=['sector','code','name','date','close']).to_csv('px.csv',index=False)
print('rows',len(rows))
