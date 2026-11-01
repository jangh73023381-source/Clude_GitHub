"""남은 10~12월 주별 '외국인 20거래일 누적 순매수 플러스 전환' 확률 — 블록 부트스트랩 시뮬레이션(참고용)."""
import pandas as pd,numpy as np
d=pd.read_csv('merged.csv',dtype={'date':str})
K=d.kospi.iloc[-1]; d['f']=d.foreign*(K/d.kospi)   # 현재 지수 수준으로 규모 환산(억원)
hist=d.f.values; last20=list(d.foreign.values[-20:])
# 남은 거래일(휴장: 12/25, 12/31)
days=pd.bdate_range('2026-10-22','2026-12-30'); days=[x for x in days if x.strftime('%m%d') not in ('1225',)]
wk=[]
for x in days:
    m=x - pd.Timedelta(days=x.weekday()); wk.append(m.strftime('%m/%d'))
H=len(days)
# 산술: 앞으로 매일 같은 금액 x 를 순매수할 때 t일째 20일 누적이 0을 넘으려면 필요한 x
need=[]
for t in range(1,21):
    old=sum(last20[t:]); need.append(-old/t)
pools={'7년 전체':hist,'순매도 국면 날만':d.f.values[(d.s20<0).values],'2026년만':d.f.values[(d.date>='20260101').values]}
rng=np.random.default_rng(42); N=20000; B=10
res={}
for nm,pool in pools.items():
    pool=pool[~np.isnan(pool)]; n=len(pool); first=np.full(N,-1)
    for s in range(N):
        path=[]
        while len(path)<H:
            st=rng.integers(0,n-B); path+=list(pool[st:st+B])
        w=last20+path[:H]
        for t in range(H):
            if sum(w[t+1:t+21])>0: first[s]=t; break
    res[nm]=first
out=pd.DataFrame({'week':wk})
for nm,f in res.items():
    p=[((f>=0)&(np.array(wk)[np.clip(f,0,None)]==w)).mean() for w in dict.fromkeys(wk)]
    res[nm]=p
W=list(dict.fromkeys(wk)); nd=[wk.count(w) for w in W]
tab=pd.DataFrame({'주(월요일)':W,'거래일':nd,**{k:np.round(np.array(v)*100,1) for k,v in res.items()}})
for k in pools: tab[k+'_누적']=tab[k].cumsum().round(1)
print(tab.to_string(index=False))
print('연내 미전환', {k:round(100-sum(v)*100,1) for k,v in res.items()})
print('필요 일평균 순매수(억원) t=5,10,15,20일째 전환:',[round(need[i]) for i in (4,9,14,19)])
print('최근 20일 합',sum(last20),' 최근 일별',last20[-6:])
