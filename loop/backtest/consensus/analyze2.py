import pandas as pd, numpy as np
from scipy import stats
import os as _os; SP=_os.path.dirname(_os.path.abspath(__file__))
df=pd.read_csv(SP+'/panel.csv',dtype={'code':str})
def sp(a,b,lbl,d=None):
    d=df if d is None else d
    z=d[[a,b]].dropna()
    if len(z)<20: print(f'{lbl:<44} n={len(z)} 부족'); return
    r,p=stats.spearmanr(z[a],z[b]); print(f'{lbl:<44} n={len(z):3d}  rho={r:+.3f}  p={p:.3f}{"  ★" if p<0.05 else ""}')
def quint(sig,ret,lbl,k=5):
    z=df[[sig,ret,'name']].dropna().copy()
    if len(z)<50: print(lbl,'표본부족'); return
    z['q']=pd.qcut(z[sig].rank(method='first'),k,labels=False)
    g=z.groupby('q')[ret].agg(['size','mean','median'])
    g['mean']=(g['mean']*100).round(2); g['median']=(g['median']*100).round(2)
    print(f'\n{lbl}')
    print('  분위(낮음→높음) 이후1개월 평균: '+' / '.join(f'{v:+.2f}' for v in g['mean']))
    print('                        중앙: '+' / '.join(f'{v:+.2f}' for v in g['median']))
    t=stats.ttest_ind(z[z.q==k-1][ret],z[z.q==0][ret])
    print(f'  Q5-Q1 {100*(g["mean"].iloc[-1]-g["mean"].iloc[0]):+.2f}%p  t={t.statistic:+.2f} p={t.pvalue:.3f}   전체평균 {100*z[ret].mean():+.2f}%')

print('='*72); print('축 1 (계속) — 5분위 단조성'); print('='*72)
quint('rv_mid','r_late','[선행] 1~2개월전 EPS 수정 → 이후 1개월 수익률')
quint('rv_late','r_late','[동시] 최근 1개월 EPS 수정 ↔ 같은 기간 수익률 (참고)')
quint('fv_mid','r_late','[선행] 내년 EPS 추정치 수정 → 이후 1개월 수익률')

print('\n'+'='*72); print('축 2. 목표주가 괴리율 (컨센서스 목표가 / 현재가 - 1)'); print('='*72)
print(f"  괴리율 분포: 중앙 {100*df.upside.median():.1f}%  하위10% {100*df.upside.quantile(.1):.1f}%  상위10% {100*df.upside.quantile(.9):.1f}%")
sp('upside','r_late','  괴리율 ↔ 최근 1개월 주가(동시·역방향 자명)')
quint('upside','r_late','  목표주가 괴리율 → 이후 1개월 수익률')

print('\n'+'='*72); print('축 3. 투자의견 — 매수(strongBuy+buy) 비율'); print('='*72)
print(f"  매수비율 분포: 중앙 {100*df.buyratio.median():.0f}%  하위10% {100*df.buyratio.quantile(.1):.0f}%  '매도' 의견 있는 종목 {int((df.se+df.ss>0).sum())}/{len(df)}종")
quint('buyratio','r_late','  매수의견 비율 → 이후 1개월 수익률')

print('\n'+'='*72); print('축 4. 커버리지 층화 — 애널리스트 수가 많으면 다른가'); print('='*72)
for lo,hi,lbl in [(3,7,'3~7명'),(8,15,'8~15명'),(16,99,'16명+')]:
    d=df[(df.n>=lo)&(df.n<=hi)]
    sp('rv_mid','r_late',f'  [{lbl}] 1~2개월전 수정 → 이후 1개월',d)
