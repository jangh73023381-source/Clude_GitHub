import yfinance as yf, pandas as pd, numpy as np, time, sys, os, json
import os as _os; SP=_os.path.dirname(_os.path.abspath(__file__))
uni=[l.split(':') for l in open(SP+'/u420.txt',encoding='utf-8').read().strip().split('\n')]
start,end=int(sys.argv[1]),int(sys.argv[2])
out=SP+f'/raw_{start}_{end}.csv'
rows=[]
t0=time.time()
for code,mkt,name in uni[start:end]:
    sym=code+'.'+mkt
    try:
        tk=yf.Ticker(sym)
        et=tk.eps_trend
        if et is None or et.empty or '0y' not in et.index: continue
        r=et.loc['0y']; r1=et.loc['+1y'] if '+1y' in et.index else None
        ee=tk.earnings_estimate
        nan_=float(ee.loc['0y','numberOfAnalysts']) if ee is not None and not ee.empty else np.nan
        pt=tk.analyst_price_targets or {}
        rc=tk.recommendations
        sb=bu=ho=se=ss=np.nan
        if rc is not None and not rc.empty:
            z=rc[rc.period=='0m']
            if len(z): sb,bu,ho,se,ss=[float(z.iloc[0][k]) for k in ['strongBuy','buy','hold','sell','strongSell']]
        px=tk.history(period='7mo',auto_adjust=True)['Close']
        if len(px)<90: continue
        p=px.values
        d=dict(code=code,name=name,mkt=mkt,n=nan_,
               e_cur=float(r['current']),e7=float(r['7daysAgo']),e30=float(r['30daysAgo']),
               e60=float(r['60daysAgo']),e90=float(r['90daysAgo']),
               f_cur=float(r1['current']) if r1 is not None else np.nan,
               f30=float(r1['30daysAgo']) if r1 is not None else np.nan,
               f60=float(r1['60daysAgo']) if r1 is not None else np.nan,
               f90=float(r1['90daysAgo']) if r1 is not None else np.nan,
               tp_mean=pt.get('mean',np.nan),tp_cur=pt.get('current',np.nan),
               sb=sb,bu=bu,ho=ho,se=se,ss=ss,
               p0=p[-1],p21=p[-22],p42=p[-43],p63=p[-64],p84=p[-85])
        rows.append(d)
    except Exception:
        pass
pd.DataFrame(rows).to_csv(out,index=False)
print(f'{start}-{end}: {len(rows)}종 {time.time()-t0:.0f}s -> {out}')
