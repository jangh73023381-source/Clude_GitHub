import numpy as np,pandas as pd
d=np.load('dates.npy',allow_pickle=True); c=np.load('codes.npy',allow_pickle=True); R=np.load('P_chg_pct.npy'); C=np.load('P_close.npy')
print('|등락률|>30% 셀',int(np.nansum(np.abs(R)>30.5)),' (2015-06 이전 상하한 15%)')
# 비수정 종가로 만든 수익률과 등락률 차이 → 기업행위 일
Cf=pd.DataFrame(C).ffill().values; raw=(C/np.vstack([np.full((1,C.shape[1]),np.nan),Cf[:-1]])-1)*100
diff=np.abs(raw-R); print('종가 수익률과 등락률이 5%p 넘게 다른 셀(분할·증자 등 기준가 조정)',int(np.nansum(diff>5)))
# 네이버 수정주가 패널(sjh, 현 상장사)과 대조
S='../sjh/'; sd=np.load(S+'dates.npy'); sc=np.load(S+'codes.npy',allow_pickle=True); SC=np.load(S+'C.npy').astype(float)
sret=(SC[1:]/SC[:-1]-1)*100; sd2=sd[1:]
di=pd.Index(d.astype(str)); ci=pd.Index(c.astype(str))
rows=di.get_indexer(sd2.astype(str)); cols=ci.get_indexer(sc.astype(str)); ok=cols>=0
K=R[np.ix_(rows[rows>=0],cols[ok])]; N=sret[np.ix_(np.where(rows>=0)[0],np.where(ok)[0])]
m=~np.isnan(K)&~np.isnan(N); e=np.abs(K[m]-N[m])
print('네이버 수정주가 대조: 셀',m.sum(),' |차|<0.05%p 비율',round((e<0.05).mean()*100,2),'% · 중앙',round(np.median(e),4),' >1%p',int((e>1).sum()))
meta=pd.read_csv('codes_meta.csv',dtype=str); g=meta[meta['last']<d[-1]]
print('중도 소멸 예시',g.sample(8,random_state=1)[['code','name','first','last']].to_string(index=False))
print('연도별 소멸 수',g['last'].str[:4].value_counts().sort_index().to_dict())
