import os,numpy as np,pandas as pd
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
CO={'반도체':'091160','은행':'091170','2차전지':'305720','코스피200':'069500',
    '채권':'332610','금':'411060'}
def run(cols, window=None, label=''):
    X=cl[[CO[c] for c in cols]].dropna(); X.columns=cols
    R=X.pct_change().dropna()
    if window: R=R.tail(window)
    return R
def stats(r,nm,base=None):
    eq=(1+r).cumprod(); yrs=len(r)/252
    cagr=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    sh=r.mean()/r.std()*np.sqrt(252); vol=r.std()*np.sqrt(252)
    print(f"{nm:36s} CAGR {100*cagr:+6.2f}%  MDD {100*mdd:7.1f}%  Sharpe {sh:5.2f}  변동성 {100*vol:5.1f}%")
    return sh

print("=== A. 7년(2019-04~) · 반도체·은행·2차전지·코스피200·채권")
R=run(['반도체','은행','2차전지','코스피200','채권'])
print(f"   {R.index[0]}~{R.index[-1]} {len(R)}일")
mix={
 '현행 50/20/20/10 (+현금0)': {'반도체':.5,'은행':.2,'2차전지':.2,'코스피200':.1},
 '★ 반도체 72% + 현금 28% (등가)': {'반도체':.72},
 '반도체 50 / 은행 50': {'반도체':.5,'은행':.5},
 '반도체 50 / 은행 30 / 채권 20': {'반도체':.5,'은행':.3,'채권':.2},
 '반도체 40 / 은행 40 / 채권 20': {'반도체':.4,'은행':.4,'채권':.2},
 '현행에서 2차전지→은행 (50/40/0/10)': {'반도체':.5,'은행':.4,'코스피200':.1},
 '현행에서 코스피200→채권 (50/20/20/0+채10)': {'반도체':.5,'은행':.2,'2차전지':.2,'채권':.1},
}
base=None
for nm,w in mix.items():
    r=sum(R[k]*v for k,v in w.items())
    s=stats(r,nm)
print()
print("=== B. 금 포함 구간(2021-12~) 재확인")
R2=run(['반도체','은행','2차전지','코스피200','채권','금'])
print(f"   {R2.index[0]}~{R2.index[-1]} {len(R2)}일")
print("   [상관] 반도체 대비:", {k:round(R2['반도체'].corr(R2[k]),2) for k in R2.columns if k!='반도체'})
for nm,w in {'현행 50/20/20/10':{'반도체':.5,'은행':.2,'2차전지':.2,'코스피200':.1},
             '반도체 50 / 은행 30 / 금 20':{'반도체':.5,'은행':.3,'금':.2},
             '반도체 40 / 은행 30 / 금 20 / 채권 10':{'반도체':.4,'은행':.3,'금':.2,'채권':.1},
             '반도체 72% + 현금 28%':{'반도체':.72}}.items():
    stats(sum(R2[k]*v for k,v in w.items()),nm)
print()
print("=== C. 반도체 하위 5% 급락일 방어 (7년)")
bad=R[R['반도체']<=R['반도체'].quantile(0.05)]
for nm,w in mix.items():
    r=sum(bad[k]*v for k,v in w.items())
    print(f"{nm:36s} 급락일 평균 {100*r.mean():+6.2f}%")
