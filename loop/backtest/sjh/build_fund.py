import pandas as pd, os
B=os.path.expanduser('~/mnt/loop/backtest')
f=pd.read_csv(B+'/_dart_fin_2019_2026.csv',dtype={'code':str})
f=f[f.account.isin(['매출액','영업이익'])].copy()
# CFS 우선, 없으면 OFS
f['pri']=(f.fs=='CFS').astype(int)
f=f.sort_values('pri',ascending=False).drop_duplicates(['code','year','reprt','account'])
w=f.pivot_table(index=['code','year','reprt'],columns='account',values='amt',aggfunc='first').reset_index()
w.columns.name=None
w=w.rename(columns={'매출액':'sa','영업이익':'op'})
# 공시 가용일 (보수적)
AV={11013:(0,5,16),11012:(0,8,15),11014:(0,11,15),11011:(1,4,1)}
def avd(r):
    dy,m,d=AV[r.reprt]; return (r.year+dy)*10000+m*100+d
w['avail']=w.apply(avd,axis=1)
# 전년 동기
prev=w[['code','year','reprt','sa','op']].copy(); prev['year']=prev.year+1
prev=prev.rename(columns={'sa':'sa_p','op':'op_p'})
w=w.merge(prev,on=['code','year','reprt'],how='left')
w['sa_g']=(w.sa-w.sa_p)/w.sa_p.abs()
w['op_g']=(w.op-w.op_p)/w.op_p.abs()
w['op_pos']=(w.op>0)&(w.op_p>0)
w=w.dropna(subset=['sa','op'])
w.to_csv(B+'/sjh/fund.csv',index=False)
print(len(w), w.code.nunique(), w.avail.min(), w.avail.max())
print(w[['sa_g','op_g']].describe())
