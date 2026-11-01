# -*- coding: utf-8 -*-
"""ETF 설정/환매(상장좌수 변화) → 익일 수익률 1차 스크리닝. 조회 전용·기록 없음."""
import sys, os
import pandas as pd, numpy as np

def _spear(x,y):
    import numpy as np
    rx=pd.Series(x).rank().values; ry=pd.Series(y).rank().values
    r=np.corrcoef(rx,ry)[0,1]; n=len(rx)
    t=r*np.sqrt((n-2)/max(1-r*r,1e-12))
    from math import erf,sqrt
    p=2*(1-0.5*(1+erf(abs(t)/sqrt(2))))
    return r,p
def _tt(a,b):
    import numpy as np
    a=np.asarray(a); b=np.asarray(b); na,nb=len(a),len(b)
    se=np.sqrt(a.var(ddof=1)/na+b.var(ddof=1)/nb)
    t=(a.mean()-b.mean())/max(se,1e-12)
    from math import erf,sqrt
    return t, 2*(1-0.5*(1+erf(abs(t)/sqrt(2))))
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(LOOP,'references','scripts'))
import universe_filters as uf
df=pd.read_csv(os.path.join(LOOP,'backtest','krx_etf_panel.csv'),dtype={'code':str,'date':str})
print(f'패널 {len(df):,}행 {df.date.min()}~{df.date.max()} {df.date.nunique()}거래일 {df.code.nunique()}종')
# 유니버스 필터
keep=df.name.map(lambda n: uf.is_allowed(n) if hasattr(uf,'is_allowed') else True)
if keep.dtype==bool and keep.sum()>0: df=df[keep]
print(f'유니버스 필터 후 {df.code.nunique()}종')
df=df.sort_values(['code','date'])
g=df.groupby('code')
df['shrs_chg']=g.list_shrs.pct_change()          # 설정(+)/환매(-)
df['shrs_chg5']=g.list_shrs.pct_change(5)
df['fwd1']=g.close.shift(-1)/df.close-1          # D 종가 → D+1 종가
df['prev_chg']=g.chg_pct.shift(0)/100
# 벤치: 당일 전체 ETF 동일가중
bench=df.groupby('date').fwd1.mean().rename('bench')
df=df.merge(bench,on='date',how='left'); df['exc']=df.fwd1-df.bench
d=df.dropna(subset=['shrs_chg','fwd1','exc']).copy()
d=d[d.list_shrs>0]
print(f'관측 {len(d):,}건  (설정/환매가 0이 아닌 날 {100*(d.shrs_chg.abs()>1e-9).mean():.1f}%)')

def report(sig,lbl,data=None):
    z=(data if data is not None else d)[[sig,'exc','fwd1']].dropna()
    z=z[z[sig].abs()>1e-9]
    if len(z)<200: print(f'{lbl}: 표본 {len(z)} 부족'); return
    r,p=_spear(z[sig].values,z.exc.values)
    z=z.copy(); z['q']=pd.qcut(z[sig].rank(method='first'),5,labels=False)
    m=z.groupby('q').exc.mean()*100
    tv,tp=_tt(z[z.q==4].exc.values,z[z.q==0].exc.values)
    print(f'\n{lbl}  n={len(z):,}')
    print(f'  rho={r:+.4f} p={p:.3f}   5분위 초과(%p): '+' / '.join(f'{v:+.3f}' for v in m))
    print(f'  Q5-Q1 {m.iloc[-1]-m.iloc[0]:+.3f}%p  t={tv:+.2f} p={tp:.3f}')
    return z

print('\n'+'='*74); print('[D] 당일 설정/환매 → 익일 초과수익  ※KRX는 D+1 공개라 실전 조달 불가(참고)'); print('='*74)
report('shrs_chg','당일 상장좌수 변화율')
report('shrs_chg5','5일 누적 상장좌수 변화율')

print('\n'+'='*74); print('[D-1] 전일 설정/환매 → 익일 초과수익  ★실전 조달 가능 (§4-6)'); print('='*74)
d['shrs_chg_lag']=d.groupby('code').shrs_chg.shift(1)
d['shrs_chg5_lag']=d.groupby('code').shrs_chg5.shift(1)
report('shrs_chg_lag','전일 상장좌수 변화율')
report('shrs_chg5_lag','전일까지 5일 누적 변화율')
d.to_csv(os.path.join(HERE,'_flow_panel.csv'),index=False)
