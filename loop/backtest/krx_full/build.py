"""KRX 일별 스냅샷 → 넓은 형식 numpy 패널(연도별 순차 처리, 메모리 절약). 수익률은 KRX 등락률(FLUC_RT, 기준가 대비)을 쓴다 — 종가는 비수정."""
import pandas as pd,numpy as np,glob,gc
fs=sorted(glob.glob('20*.csv'))
D=set();C=set();meta={}
for f in fs:
    x=pd.read_csv(f,dtype=str,usecols=['date','code','name','market'])
    x=x[x.market.isin(['KOSPI','KOSDAQ'])]
    D|=set(x.date); C|=set(x.code)
    for r in x.drop_duplicates('code',keep='last').itertuples(): meta[r.code]=(r.name,r.market,r.date, meta.get(r.code,(0,0,0,r.date))[3] if r.code in meta else r.date)
    del x; gc.collect()
dates=np.array(sorted(D)); codes=np.array(sorted(C)); ix=pd.Index(dates); cx=pd.Index(codes)
np.save('dates.npy',dates); np.save('codes.npy',codes)
print('거래일',len(dates),dates[0],dates[-1],'종목',len(codes),flush=True)
import os
for col in [c for c in ['chg_pct','close','value','mktcap','shares','open','high','low'] if not os.path.exists(f'P_{c}.npy')]:
    M=np.full((len(dates),len(codes)),np.nan,dtype='float32')
    for f in fs:
        x=pd.read_csv(f,dtype={'date':str,'code':str},usecols=['date','code','market',col]); x=x[x.market.isin(['KOSPI','KOSDAQ'])].drop_duplicates(['date','code'])
        v=pd.to_numeric(x[col].astype(str).str.replace(',',''),errors='coerce').values
        M[ix.get_indexer(x.date),cx.get_indexer(x.code)]=v; del x; gc.collect()
    np.save(f'P_{col}.npy',M); del M; gc.collect(); print('저장',col,flush=True)
first={};last={}
cnt=None
pres=~np.isnan(np.load('P_close.npy'))
fi=pres.argmax(0); la=len(dates)-1-pres[::-1].argmax(0)
m=pd.DataFrame({'code':codes,'name':[meta[c][0] for c in codes],'market':[meta[c][1] for c in codes],'first':dates[fi],'last':dates[la]})
m.to_csv('codes_meta.csv',index=False)
print('중도 소멸 종목',(m['last']<dates[-1]).sum(),'/',len(codes),' 일별 종목 수 최소/중앙/최대',pres.sum(1).min(),int(np.median(pres.sum(1))),pres.sum(1).max())
