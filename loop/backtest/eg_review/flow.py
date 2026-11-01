"""수급(외국인·기관 순매수) 축 — EG 신호 게이팅 검정. 데이터 flow_2y.csv(2024-02~2026-07, 키움 ka10045)."""
import os,pickle,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.dirname(os.path.dirname(HERE))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,V,eg,trend,dates,codes=d['C'],d['V'],d['eg'],d['trend'],d['dates'],d['codes']; M,N=C.shape
Cf=pd.DataFrame(C.T).ffill().values.T
fl=pd.read_csv(os.path.join(LOOP,'backtest','flow_2y.csv'),dtype={'code':str})
di={int(x):i for i,x in enumerate(dates)}; ci={c:i for i,c in enumerate(codes)}
FOR=np.full((M,N),np.nan); ORG=np.full((M,N),np.nan)
for r in fl.itertuples():
    if r.code in ci and r.date in di: FOR[ci[r.code],di[r.date]]=r.for_net; ORG[ci[r.code],di[r.date]]=r.orgn_net
have=~np.isnan(FOR)
ret20=np.full((M,N),np.nan); ret20[:,:-20]=Cf[:,20:]/Cf[:,:-20]-1
valid=np.zeros((M,N),bool); valid[:,60:N-21]=True
base=eg&valid&have
def rs(x,w): return pd.DataFrame(x.T).rolling(w,min_periods=1).sum().values.T
V5=rs(V,5); F5=rs(np.nan_to_num(FOR),5); O5=rs(np.nan_to_num(ORG),5)
rate_f=FOR/V; rate_o=ORG/V; rate_b=(FOR+ORG)/V
r5f=F5/V5; r5o=O5/V5; r5b=(F5+O5)/V5
print('EG 신호 중 수급 데이터 보유:',base.sum(),'/',(eg&valid).sum(), ' 기간', dates[np.where(have.any(0))[0][[0,-1]]])
r0=ret20[base]; print(f'기준(현행, 수급기간) n={len(r0)} 평균 {r0.mean()*100:+.2f}% 중앙 {np.median(r0)*100:+.2f} 승률 {(r0>0).mean()*100:.1f}')
# 연도 fold within period
ts=np.where(base)[1]; tb=np.array_split(np.sort(np.unique(ts)),3)
def ev(name,cond):
    s=base&np.nan_to_num(cond,nan=False)
    r=ret20[s]; t=np.where(s)[1]
    f=[]
    for fd in tb:
        a=r[np.isin(t,fd)]; b=r0[np.isin(ts,fd)]
        f.append('+' if len(a) and a.mean()>b.mean() else '-')
    rr=ret20[base&~np.nan_to_num(cond,nan=False)]
    print(f'{name:38s} n={len(r):4d} ({len(r)/len(r0)*100:4.0f}%) 평균 {r.mean()*100:+.2f}% 중앙 {np.median(r)*100:+.2f} 승률 {(r>0).mean()*100:.1f} | 배제분 평균 {rr.mean()*100:+.2f}% | fold {"".join(f)}')
ev('외국인 당일 순매수(>0)',FOR>0)
ev('기관 당일 순매수(>0)',ORG>0)
ev('외국인+기관 합산 당일 순매수',FOR+ORG>0)
ev('외국인 또는 기관 순매수',(FOR>0)|(ORG>0))
ev('외국인 5일 누적 순매수',F5>0)
ev('기관 5일 누적 순매수',O5>0)
ev('합산 5일 누적 순매수',F5+O5>0)
ev('합산 당일 강도 > 거래량 5%',rate_b>0.05)
ev('합산 당일 강도 > 거래량 10%',rate_b>0.10)
ev('외국인 당일 강도 > 5%',rate_f>0.05)
ev('기관 당일 강도 > 5%',rate_o>0.05)
ev('합산 5일 강도 > 5%',r5b>0.05)
ev('합산 당일 순매도 강도 < -10% (역)',rate_b<-0.10)
ev('외국인 당일 순매도(<0) (역)',FOR<0)
# 분위
x=rate_b[base]; q=pd.qcut(x,5,labels=False,duplicates='drop')
for k in sorted(set(q)):
    print(f'  합산 당일 강도 5분위 q{k}: n={(q==k).sum()} 평균 {r0[q==k].mean()*100:+.2f}% 승률 {(r0[q==k]>0).mean()*100:.1f}')
x=r5b[base]; q=pd.qcut(x,5,labels=False,duplicates='drop')
for k in sorted(set(q)):
    print(f'  합산 5일 강도 5분위 q{k}: n={(q==k).sum()} 평균 {r0[q==k].mean()*100:+.2f}% 승률 {(r0[q==k]>0).mean()*100:.1f}')

print('\n=== 통계 검정: 합산 5일 누적 순매수 > 0 ===')
cond=np.nan_to_num(F5+O5>0,nan=False)
def clus_t(mask_a,mask_b):
    ta=np.where(mask_a)[1]; tb_=np.where(mask_b)[1]; ra=ret20[mask_a]; rb=ret20[mask_b]
    da=pd.Series(ra).groupby(ta).mean(); db=pd.Series(rb).groupby(tb_).mean()
    diff=da.mean()-db.mean(); se=np.sqrt(da.var()/len(da)+db.var()/len(db)); return diff,diff/se,len(da),len(db)
diff,t,na,nb=clus_t(base&cond,base&~cond); print(f'일자 클러스터 평균차 {diff*100:+.2f}%p t={t:.2f} (일수 {na}/{nb})')
rng=np.random.default_rng(0); idx=np.where(base); lab=cond[idx]; obs=ret20[idx][lab].mean()-ret20[idx][~lab].mean(); cnt=0
# 플라시보: 날짜 블록 단위로 라벨 셔플(같은 날 신호끼리 묶어 셔플)
tsig=idx[1]; ud=np.unique(tsig); rr=ret20[idx]
for _ in range(300):
    perm=lab.copy()
    for u in ud:
        m=tsig==u; perm[m]=rng.permutation(lab[m])
    if perm.sum()==0 or (~perm).sum()==0: continue
    if rr[perm].mean()-rr[~perm].mean()>=obs: cnt+=1
print(f'플라시보(일내 라벨 셔플 300회) p={cnt/300:.3f}  관측차 {obs*100:+.2f}%p')
# 종목 간 셔플(전체)
cnt=0
for _ in range(300):
    perm=rng.permutation(lab)
    if rr[perm].mean()-rr[~perm].mean()>=obs: cnt+=1
print(f'플라시보(전체 셔플 300회) p={cnt/300:.3f}')
# R5
da=pd.Series(rr[lab]).groupby(tsig[lab]).mean(); db=pd.Series(rr[~lab]).groupby(tsig[~lab]).mean()
al=da.index.union(db.index); ex=(da.reindex(al).fillna(db.reindex(al))- db.mean())  # 통과일 평균 - 배제 전체평균
s=ex.sort_values(); print(f'R5: 통과일 초과(배제평균 대비) 평균 {ex.mean()*100:+.2f} · 상위3일 제거 {(ex.sum()-s.tail(3).sum())/len(ex)*100:+.2f} · 상위10일 제거 {(ex.sum()-s.tail(10).sum())/len(ex)*100:+.2f} · 중앙값 {ex.median()*100:+.2f}')
# 반기별
yrs=np.array([str(x)[:6] for x in dates]); 
for h in ['202402','202407','202501','202507','202601','202607']:
    pass
per=pd.Series(rr).groupby([tsig//1]).size()
for a,b in [(20240201,20240801),(20240801,20250201),(20250201,20250801),(20250801,20260201),(20260201,20260801)]:
    m=(dates[tsig]>=a)&(dates[tsig]<b)
    if m.sum(): print(f'  {a}~{b}: 통과 n={int((m&lab).sum()):3d} {rr[m&lab].mean()*100 if (m&lab).sum() else 0:+.2f}% / 배제 n={int((m&~lab).sum()):3d} {rr[m&~lab].mean()*100 if (m&~lab).sum() else 0:+.2f}%')
# 눌림 10일 변형과 결합
MA20=d['MA20']; L=d['L']
pull10=pd.DataFrame(L.T).rolling(10,min_periods=10).min().values.T<=MA20*1.02
tr2=(C>=MA20)&(MA20>np.roll(MA20,1,axis=1))&(C>d['MA60'])&(d['MA60']>=np.roll(d['MA60'],5,axis=1))&pull10
O=d['O'];H=d['H']
c2=(C>=np.roll(O,1,axis=1))&(C>O)&(np.roll(C,1,axis=1)<np.roll(O,1,axis=1))&(C>=L+(H-L)*0.6)&(V>=d['VA']*1.3)
eg10=np.nan_to_num(tr2&c2,nan=False)&valid&have
for nm,s in [('눌림10 전체',eg10),('눌림10 + 수급',eg10&cond),('눌림10 수급미달',eg10&~cond),('현행 + 수급',base&cond)]:
    r=ret20[s]; print(f'{nm:14s} n={len(r)} 평균 {r.mean()*100:+.2f}% 중앙 {np.median(r)*100:+.2f} 승률 {(r>0).mean()*100:.1f} /일 {len(r)/have.any(0).sum():.2f}')
