# -*- coding: utf-8 -*-
import pandas as pd, numpy as np
E=pd.read_csv('monthly_excess.csv')

# 장기표본 섹터만 발견 대상 (월별 셀 n>=18)
cnt=E.groupby(['sector','month']).size().groupby('sector').min()
LONG=sorted(cnt[cnt>=18].index)
SHORT=sorted(cnt[cnt<18].index)
print('발견 대상 섹터(%d): %s'%(len(LONG),', '.join(LONG)))
print('표본부족 제외(%d): %s'%(len(SHORT),', '.join(f'{s}(n={cnt[s]})' for s in SHORT)))
print()

L=E[E['sector'].isin(LONG)].copy()
TRAIN_END=2015   # 2000~2015 발견
def tstat(x):
    x=np.asarray(x,float); n=len(x)
    if n<3: return np.nan,np.nan,n
    sd=x.std(ddof=1)
    return x.mean(),(x.mean()/(sd/np.sqrt(n)) if sd>0 else np.nan),n

rows=[]
for (sec,mo),g in L.groupby(['sector','month']):
    tr=g[g.year<=TRAIN_END]['excess']; te=g[g.year>TRAIN_END]['excess']; al=g['excess']
    mtr,ttr,ntr=tstat(tr); mte,tte,nte=tstat(te); ma,ta,na=tstat(al)
    rows.append(dict(sector=sec,month=mo,n_all=na,mean_all=ma,t_all=ta,
                     n_tr=ntr,mean_tr=mtr,t_tr=ttr,n_te=nte,mean_te=mte,t_te=tte,
                     win_all=(al>0).mean()*100,win_te=(te>0).mean()*100))
R=pd.DataFrame(rows)

# p값 (양측, 정규근사 대신 t분포)
from scipy import stats as st
R['p_all']=2*(1-st.t.cdf(R['t_all'].abs(),R['n_all']-1))
R['p_tr']=2*(1-st.t.cdf(R['t_tr'].abs(),R['n_tr']-1))

def bh(p,q=0.10):
    p=np.asarray(p); n=len(p); o=np.argsort(p); rank=np.arange(1,n+1)
    thr=q*rank/n; passed=p[o]<=thr
    k=np.max(np.where(passed)[0])+1 if passed.any() else 0
    cut=p[o][k-1] if k>0 else -1
    return p<=cut

R['fdr_all']=bh(R['p_all'].values,0.10)
R['fdr_tr']=bh(R['p_tr'].values,0.10)
R.to_csv('walkforward.csv',index=False)

print('=== 검정 규모 ===')
print(f'조합 수 {len(R)}개 (섹터 {len(LONG)} x 12개월). 우연히 p<0.05가 나올 기대 개수 = {0.05*len(R):.1f}개')
print(f'실제 p<0.05 개수 = {(R.p_all<0.05).sum()}개 / p<0.01 = {(R.p_all<0.01).sum()}개')
print(f'BH FDR q=0.10 통과 (전체기간) = {R.fdr_all.sum()}개')
print(f'BH FDR q=0.10 통과 (train 2000~{TRAIN_END}만) = {R.fdr_tr.sum()}개')
print()
print('=== 전체기간 t값 상위 10 (FDR 표시) ===')
c=['sector','month','n_all','mean_all','t_all','p_all','fdr_all','win_all','mean_tr','mean_te','win_te']
print(R.sort_values('t_all',ascending=False).head(10)[c].to_string(index=False,float_format=lambda v:f'{v:8.3f}'))
print()
print('=== 전체기간 t값 하위 10 ===')
print(R.sort_values('t_all').head(10)[c].to_string(index=False,float_format=lambda v:f'{v:8.3f}'))
print()
print(f'=== train(2000~{TRAIN_END}) 상위 8 → test(2016~2026) 성적 ===')
tr=R.sort_values('t_tr',ascending=False).head(8)
print(tr[['sector','month','n_tr','mean_tr','t_tr','p_tr','n_te','mean_te','t_te','win_te']].to_string(index=False,float_format=lambda v:f'{v:8.3f}'))
print()
print(f'=== train 하위 8 → test 성적 ===')
tl=R.sort_values('t_tr').head(8)
print(tl[['sector','month','n_tr','mean_tr','t_tr','p_tr','n_te','mean_te','t_te','win_te']].to_string(index=False,float_format=lambda v:f'{v:8.3f}'))
