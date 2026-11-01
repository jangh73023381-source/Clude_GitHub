# -*- coding: utf-8 -*-
import os,numpy as np,pandas as pd
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
C={'반도체':'091160','은행':'091170','2차전지':'305720','코스피200':'069500'}
X=cl[[v for v in C.values()]].dropna(); X.columns=list(C)
R=X.pct_change().dropna()
print(f"기간 {R.index[0]} ~ {R.index[-1]}  {len(R)}거래일\n")
def corr(sub,lab):
    c=sub.corr()
    print(f"[{lab}] 상관계수")
    print(c.round(2).to_string()); print()
pass
def stats(r,nm):
    eq=(1+r).cumprod(); yrs=len(r)/252
    cagr=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    sh=r.mean()/r.std()*np.sqrt(252)
    m=(1+r).groupby([str(i)[:6] for i in r.index]).prod()-1
    b=np.polyfit(R['반도체'],r,1)[0]
    print(f"{nm:34s} CAGR {100*cagr:+6.2f}%  MDD {100*mdd:7.1f}%  Sharpe {sh:5.2f}  "
          f"변동성 {100*r.std()*np.sqrt(252):5.1f}%  최악월 {100*m.min():6.1f}%  반도체베타 {b:5.2f}")
    return r
W={'현행 50/20/20/10':[.5,.2,.2,.1],
   '반도체 30 (30/20/20/30)':[.3,.2,.2,.3],
   '균등 25/25/25/25':[.25,.25,.25,.25],
   '반도체 70':[.7,.1,.1,.1]}
print("[포트폴리오] 일별 리밸런싱(목표비중 유지) 기준")
for nm,w in W.items():
    stats((R*np.array(w)).sum(1),nm)
for k in C: stats(R[k],f'  단일: {k}')
# 분산효과
w=np.array([.5,.2,.2,.1]); pv=(R*w).sum(1).std()
dr=(R.std()*w).sum()/pv
print(f"\n분산효과비율(가중평균변동성/포트변동성) = {dr:.3f} → 유효 베팅 수 ≈ {dr**2:.2f}개 (명목 4개)")
print(f"코스피200을 반도체에 회귀한 베타 = {np.polyfit(R['반도체'],R['코스피200'],1)[0]:.2f}")
print(f"은행을 반도체에 회귀한 베타   = {np.polyfit(R['반도체'],R['은행'],1)[0]:.2f}")
print(f"2차전지를 반도체에 회귀한 베타 = {np.polyfit(R['반도체'],R['2차전지'],1)[0]:.2f}")
# 반도체 급락일에 각 버킷이 어떻게 움직였나
bad=R[R['반도체']<=R['반도체'].quantile(0.05)]
print(f"\n[반도체 하위 5% 급락일 {len(bad)}일] 평균")
print((100*bad.mean()).round(2).to_string())
print(f"  현행 포트 평균 {100*(bad*w).sum(1).mean():.2f}%")
