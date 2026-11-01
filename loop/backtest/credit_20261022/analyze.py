"""신용융자잔고 · 수급 · 주가 상관/선행성 검정 (2026-10-22, 루프 외).
신용잔고는 공개 지연이 있다(10/22 밤 기준 최신 10/20) → 예측 검정은 T일 판단에 T-2 거래일까지의 신용만 사용(LAG=2)."""
import pandas as pd,numpy as np,json
LAG=2
c=pd.read_csv('credit.csv',dtype={'date':str}); ix=pd.read_csv('index.csv',dtype={'date':str})
f=pd.read_csv('flows.csv',dtype={'date':str}); f=f[(f[['indiv','foreign','inst']]!=0).any(axis=1)]
d=ix.merge(c,on='date',how='left').sort_values('date').reset_index(drop=True)
d[['credit','deposit']]=d[['credit','deposit']].ffill()
d=d[d.date>='20100101'].reset_index(drop=True)
d['mkt']=(d.kospi/d.kospi.iloc[0]+d.kosdaq/d.kosdaq.iloc[0])/2      # 두 시장 동일가중 지수(신용은 양 시장 합계)
d['rk']=d.kospi.pct_change()*100; d['rq']=d.kosdaq.pct_change()*100
d['dc']=d.credit.pct_change()*100                                   # 신용 일변화율
d['c20']=d.credit.pct_change(20)*100; d['c60']=d.credit.pct_change(60)*100
d['lev']=d.credit/d.mkt; d['levz']=(d.lev-d.lev.rolling(250).mean())/d.lev.rolling(250).std()   # 지수 대비 신용(레버리지) 250일 z
d['cdr']=d.credit/d.deposit                                          # 신용/예탁금
d['cdrz']=(d.cdr-d.cdr.rolling(250).mean())/d.cdr.rolling(250).std()
for h in (5,20,60): d[f'fk{h}']=(d.kospi.shift(-h)/d.kospi-1)*100
res={}
print('기간',d.date.iloc[0],'~',d.date.iloc[-1],len(d),'일')
# 1) 동시·선후 상관: 신용 일변화 vs 코스피 등락 (k>0: 주가가 k일 먼저)
print('\n[1] corr(신용 일변화(t), 코스피 등락(t-k))  k>0 = 주가가 먼저')
lag=[]
for k in range(-5,6):
    r=d.dc.corr(d.rk.shift(k)); lag.append((k,round(r,3)))
print(lag); res['lag_price']=lag
# 2) 수급: 2019+ 투자자별 vs 신용 변화
m=d.merge(f,on='date')
print('\n[2] 2019+ 동시 상관(일별): 신용변화(억원) vs 개인/외국인/기관 순매수')
m['dca']=m.credit.diff()
for col in ['indiv','foreign','inst']:
    print(col,[ (k,round(m.dca.corr(m[col].shift(k)),3)) for k in (-2,-1,0,1,2)])
res['flow_corr']={col:float(m.dca.corr(m[col])) for col in ['indiv','foreign','inst']}
# 20일 누적끼리
m['dca20']=m.credit.diff(20); 
for col in ['indiv','foreign','inst']: m[col+'20']=m[col].rolling(20).sum()
print('20일 누적 상관:',{col:round(m.dca20.corr(m[col+'20']),3) for col in ['indiv','foreign','inst']}, ' 코스피20일:',round(m.dca20.corr(m.kospi.pct_change(20)),3))
# 3) 예측: 신호(T-LAG 기준) → 향후 코스피 수익, 5분위
def quint(sig,h,name):
    s=d[sig].shift(LAG); y=d[f'fk{h}']; ok=s.notna()&y.notna(); q=pd.qcut(s[ok],5,labels=False)
    g=y[ok].groupby(q).agg(['mean','count']); spread=g['mean'].iloc[4]-g['mean'].iloc[0]
    # 시차이동 대조: 신호를 원형으로 250일 이상 밀어 300회
    rng=np.random.default_rng(5); vals=s[ok].values; yy=y[ok].values; n=len(vals); sims=[]
    for _ in range(300):
        v=np.roll(vals,rng.integers(250,n-250)); qq=pd.qcut(v,5,labels=False); sims.append(yy[qq==4].mean()-yy[qq==0].mean())
    sims=np.array(sims); p=float(np.mean(np.abs(sims)>=abs(spread)))
    # 3분할 fold 의 Q5-Q1
    fo=[]
    idx=np.where(ok)[0]
    for part in np.array_split(idx,3):
        ss=s.iloc[part]; yy2=y.iloc[part]; qq=pd.qcut(ss,5,labels=False); fo.append(yy2[qq==4].mean()-yy2[qq==0].mean())
    out=dict(q=[round(x,2) for x in g['mean']],spread=round(spread,2),p=round(p,3),folds=[round(x,2) for x in fo])
    print(f"{name:34s} h={h:2d}  분위 평균 {out['q']}  Q5-Q1 {spread:+.2f}%p  대조 p={p:.3f}  fold {out['folds']}")
    return out
print(f'\n[3] 신호(T-{LAG}일 신용) → 향후 코스피 수익(%), 5분위(Q1 낮음 → Q5 높음)')
for sig,nm in [('c20','신용 20일 증가율'),('c60','신용 60일 증가율'),('levz','지수 대비 신용 레버리지 z(250일)'),('cdrz','신용/예탁금 비율 z(250일)')]:
    for h in (5,20,60): res[f'{sig}_{h}']=quint(sig,h,nm)
# 4) 반대매매 급감일: 신용 5일 감소율 하위 5% → 이후 수익
d['c5']=d.credit.pct_change(5)*100
s=d.c5.shift(LAG); thr=s.quantile(.05)
for h in (5,20):
    a=d.loc[s<=thr,f'fk{h}'].dropna(); b=d[f'fk{h}'].dropna()
    print(f"\n[4] 신용 5일 급감(하위5%, ≤{thr:.1f}%) 후 {h}일: {a.mean():+.2f}% (n={len(a)}, 승률 {(a>0).mean()*100:.0f}%) vs 전체 {b.mean():+.2f}% (승률 {(b>0).mean()*100:.0f}%)")
    res[f'capit_{h}']=dict(mean=a.mean(),n=len(a),win=(a>0).mean(),base=b.mean())
# 5) 현재 위치
last=d.iloc[-1]; 
print(f"\n[5] 현재({c.date.iloc[-1]} 신용) 신용 {last.credit/1e4:.1f}조 · 20일 {last.c20:+.1f}% · 60일 {last.c60:+.1f}% · 레버리지 z {last.levz:+.2f} · 신용/예탁 {last.cdr:.3f}(z {last.cdrz:+.2f})")
pk=d.loc[d.credit.idxmax()]; print(f"   사상 최대 신용 {pk.credit/1e4:.1f}조 ({pk.date}) · 2026 경로:",[(r.date,round(r.credit/1e4,1),round(r.kospi)) for r in d[d.date>='20260101'].iloc[::20].itertuples()])
d.to_csv('merged.csv',index=False); json.dump(res,open('res.json','w'),default=float,indent=1,ensure_ascii=False)
