import os,pickle,numpy as np,pandas as pd,sys
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0,os.path.join(LOOP,'references','scripts'))
from etf_sector_map import sector
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
r=pd.read_csv(os.path.join(HERE,'_ohlc_recent.csv'),dtype={'code':str})
new=r[r.date==20260903]
codes=d['codes']; ci={c:i for i,c in enumerate(codes)}
def ext(k,col):
    x=np.full((len(codes),1),np.nan)
    for row in new.itertuples(): x[ci[row.code],0]=getattr(row,col)
    return np.concatenate([d[k],x],axis=1)
O,H,L,C,V=[ext(k,c) for k,c in zip('OHLCV',['open','high','low','close','volume'])]
dates=np.append(d['dates'],20260903); N=len(dates)
rm=lambda x,w: pd.DataFrame(x.T).rolling(w,min_periods=w).mean().values.T
MA20=rm(C,20); MA60=rm(C,60); VA=rm(V,20); L5=pd.DataFrame(L.T).rolling(5).min().values.T; AMT=rm(C*V,20)
def sh(x,k):
    y=np.full_like(x,np.nan); y[:,k:]=x[:,:-k]; return y
trend=(C>=MA20)&(MA20>sh(MA20,1))&(C>MA60)&(MA60>=sh(MA60,5))&(L5<=MA20*1.02)
eg=trend&(C>=sh(O,1))&(C>O)&(sh(C,1)<sh(O,1))&(C>=L+(H-L)*0.6)&(V>=VA*1.3)
eg=np.nan_to_num(eg,nan=False).astype(bool); trend=np.nan_to_num(trend,nan=False).astype(bool)
t=N-1
rk=pd.Series(AMT[:,t]).rank(ascending=False)
def prio(chg,over): return (chg-2.6991)/2.5062+(over-5.0991)/4.0508
out=[]
for asof in [N-2,N-1]:
    print(f'\n=== D={dates[asof]} ===')
    sig=[]
    for m in range(len(codes)):
        if eg[m,asof]:
            chg=(C[m,asof]/C[m,asof-1]-1)*100; over=(C[m,asof]/MA20[m,asof]-1)*100
            sig.append(dict(code=codes[m],name=d['names'][codes[m]],sec=sector(d['names'][codes[m]]),close=C[m,asof],chg=chg,over=over,vr=V[m,asof]/VA[m,asof],pos=(C[m,asof]-L[m,asof])/(H[m,asof]-L[m,asof]) if H[m,asof]>L[m,asof] else 1,score=prio(chg,over),rank=int(rk[m]),ma20=MA20[m,asof],ma60=MA60[m,asof]))
    sig.sort(key=lambda x:-x['score'])
    print('■ 매수 신호',len(sig))
    for x in sig: print(f"  {x['sec']:8s} {x['name'][:28]:30s} {x['code']} 종가 {x['close']:,.0f} 등락 {x['chg']:+.2f}% 이격 {x['over']:+.1f}% 거래량 {x['vr']:.2f}배 위치 {x['pos']:.2f} 점수 {x['score']:+.2f} 거래대금순위 {x['rank']}")
    # 보유
    for m in range(len(codes)):
        for j in np.where(eg[m,:asof])[0]:
            age=asof-j
            if 0<age<=20: print(f"  보유 {d['names'][codes[m]]} {codes[m]} 매수 {dates[j]} {C[m,j]:,.0f} → {C[m,asof]:,.0f} {(C[m,asof]/C[m,j]-1)*100:+.1f}% 보유 {age}일 잔여 {20-age}")
    # 대기
    w=[]
    for m in range(len(codes)):
        if trend[m,asof] and not eg[m,asof]:
            w.append(dict(code=codes[m],name=d['names'][codes[m]],sec=sector(d['names'][codes[m]]),close=C[m,asof],over=(C[m,asof]/MA20[m,asof]-1)*100,vr=V[m,asof]/VA[m,asof],ready=bool(C[m,asof]<O[m,asof]),chg=(C[m,asof]/C[m,asof-1]-1)*100,rank=int(pd.Series(AMT[:,asof]).rank(ascending=False)[m])))
    print('■ 대기(추세 5조건 충족)',len(w))
    for x in sorted(w,key=lambda z:-int(z['ready'])): print(f"  {x['sec']:8s} {x['name'][:28]:30s} {x['code']} 종가 {x['close']:,.0f} 등락 {x['chg']:+.2f}% 이격 {x['over']:+.1f}% 거래량 {x['vr']:.2f}배 {'★음봉→내일트리거가능' if x['ready'] else '양봉'} 순위 {x['rank']}")
    if asof==N-1: out=dict(sig=sig,watch=w)
# 시장 상태
b=ci['069500']; print(f"\nKODEX200 9/3 {C[b,t]:,.0f} ({(C[b,t]/C[b,t-1]-1)*100:+.2f}%) MA20 {MA20[b,t]:,.0f} MA60 {MA60[b,t]:,.0f}")
# 추세 조건 충족 종목 수 추이
print('추세 충족 종목 수 최근 10일:', [(int(dates[k]),int(trend[:,k].sum()),int(eg[:,k].sum())) for k in range(N-10,N)])
pickle.dump(out,open(os.path.join(HERE,'_scan_0903.pkl'),'wb'))
