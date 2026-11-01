# -*- coding: utf-8 -*-
"""inv_parts/*.csv → 날짜×종목 grid (백만원). sjh dates/codes 정렬. 커버 안 된 셀은 NaN."""
import os, glob, numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); S=os.path.join(HERE,'..','sjh')
dates=np.load(S+'/dates.npy'); codes=np.load(S+'/codes.npy',allow_pickle=True)
di={str(d):i for i,d in enumerate(dates)}; ci={str(c):i for i,c in enumerate(codes)}
COLS=['orgn','samo_fund','penfnd_etc','invtrt','fnnc_invt','frgnr_invsr','ind_invsr','etc_corp','acc_trde_prica']
files=[HERE+'/inv_merged.csv']
df=pd.concat((pd.read_csv(f,dtype={'code':str,'dt':str}) for f in files),ignore_index=True)
df=df.drop_duplicates(['dt','code'])
df=df[df.dt.isin(di)&df.code.isin(ci)]
print('rows',len(df))
ti=df.dt.map(di).values; ni=df.code.map(ci).values
T,N=len(dates),len(codes)
for c in COLS:
    M=np.full((T,N),np.nan,dtype='float32'); M[ti,ni]=df[c].values.astype('float32')
    np.save(HERE+f'/F_{c}.npy',M)
    print(c,'coverage',np.isfinite(M).mean().round(3))
