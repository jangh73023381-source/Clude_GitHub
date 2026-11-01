"""외국인 강매도 다음 날 장중 약세 — 활용 검정. 신호: 데이터일 D 외국인 순매수(지수 정규화)가 확장창 하위 20%(직전일까지 분포).
(a) KODEX200 ETF: D+1 시가→종가 (b) Rule LV 픽(선정 D): D+1 시가→종가 = 시가 매수 대신 종가 매수로 미루면 피하는 구간."""
import os,sys,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
import engine as _E; P7=os.path.join(BT,'panel_ohlc_long.csv'); _E.load.__defaults__=(P7,)
from engine import load,Engine,prof,tstat,r5,folds
P,dates,codes,names=load(P7); E=Engine(P,dates,codes,names)
fl=pd.read_csv(os.path.join(BT,'foreign_mkt','merged.csv'),dtype={'date':str})[['date','foreign','kospi']]
fl['fn']=fl.foreign/fl.kospi
fl['thr']=fl.fn.expanding(120).quantile(.2).shift(1); fl['sig']=fl.fn<=fl.thr
sig=dict(zip(fl.date,fl.sig)); thr_ok=dict(zip(fl.date,fl.thr.notna()))
lv=E.run(lambda i,pl:E.sel_lv(i,pl),start=60)
lv['S']=[sig.get(d,False) for d in lv.date]; lv=lv[[thr_ok.get(d,False) for d in lv.date]]
print('표본',lv.date.iloc[0],'~',lv.date.iloc[-1],len(lv),'일 · 신호일',int(lv.S.sum()))
def rep(nm,x,s):
    a,b=x[s],x[~s]; t=(a.mean()-b.mean())/np.sqrt(a.var()/len(a)+b.var()/len(b))
    fo=[round(p[p.S].B.mean() if 'B' in p else 0,3) for p in np.array_split(lv,3)]
    print(f"{nm:34s} 신호일 {a.mean():+.3f}% (n={len(a)}) vs 그 외 {b.mean():+.3f}%  차 {a.mean()-b.mean():+.3f} t={t:+.2f}")
# (a) KODEX200 장중
rep('(a) KODEX200 D+1 시가→종가',lv.bB,lv.S)
rep('(a) KODEX200 D+1 갭(종가→시가)',lv.bG,lv.S)
rep('(b) LV 픽 D+1 시가→종가',lv.B,lv.S)
rep('(b) LV 픽 D+1 갭',lv.G,lv.S)
print('   LV 픽 장중 3분할(신호일):',[round(p.B[p.S].mean(),3) for p in np.array_split(lv,3)],' 그 외:',[round(p.B[~p.S].mean(),3) for p in np.array_split(lv,3)])
# 전략 비교 (b): 현행=OO(시가매수 다음 시가 교체) vs 신호일엔 D+1 종가 매수(그날 장중 구간은 현금, 이후 동일)
# 근사: 신호일의 OO 수익에서 D+1 장중 수익을 빼고(놓친 구간) — 시가→다음시가 = 장중 + 다음 갭
lv['OO2']=np.where(lv.S,(1+lv.OO/100)/(1+lv.B/100)*100-100,lv.OO)
for k in ('OO','OO2'):
    p=prof(lv[k]); print(f"   {k}: CAGR {p['cagr']:.1f} MDD {p['mdd']:.1f} Sh {p['sharpe']:.2f}")
d=(lv.OO2-lv.OO).values; rr=r5(d); print('   일별 차 R5',{k:round(v,4) for k,v in rr.items()}, ' fold',[round(v,4) for v in folds(d)])
# 대조: 같은 수의 무작위 날에 종가로 미루기
rng=np.random.default_rng(2); obs=prof(lv.OO2)['sharpe']; n=int(lv.S.sum()); sims=[]
for _ in range(500):
    s=np.zeros(len(lv),bool); s[rng.choice(len(lv),n,replace=False)]=True
    sims.append(prof(np.where(s,(1+lv.OO/100)/(1+lv.B/100)*100-100,lv.OO))['sharpe'])
print(f"   무작위 같은 일수 대조 Sh 평균 {np.mean(sims):.2f} p={np.mean(np.array(sims)>=obs):.3f}")
# (a) 전략: KODEX200 보유, 신호 다음날 시가 매도·종가 재매수
k=lv[['date','bA','bB','bOO','S']].copy()
x=np.where(k.S,(1+k.bOO/100)/(1+k.bB/100)*100-100,k.bOO)
for nm,v in [('KODEX200 시가→시가 보유',k.bOO),('신호일 장중만 회피',x)]:
    p=prof(v); print(f"   {nm}: CAGR {p['cagr']:.1f} MDD {p['mdd']:.1f} Sh {p['sharpe']:.2f}")
sims=[]
for _ in range(500):
    s=np.zeros(len(k),bool); s[rng.choice(len(k),n,replace=False)]=True
    sims.append(prof(np.where(s,(1+k.bOO/100)/(1+k.bB/100)*100-100,k.bOO))['sharpe'])
print(f"   무작위 같은 일수 대조 Sh 평균 {np.mean(sims):.2f} p={np.mean(np.array(sims)>=prof(x)['sharpe']):.3f}")
k['y']=k.date.str[:4]; print('   연도별 신호일 KODEX200 장중 평균:',{y:round(g.bB[g.S].mean(),2) for y,g in k.groupby('y')})
print('   [R1] 임계 하위 10/30%:')
for q in (.1,.3):
    th=fl.fn.expanding(120).quantile(q).shift(1); ss=dict(zip(fl.date,fl.fn<=th)); s=np.array([ss.get(dd,False) for dd in lv.date])
    a=lv.B[s]; b=lv.B[~s]; print(f"     q{int(q*100)} LV 픽 장중 신호일 {a.mean():+.3f} vs {b.mean():+.3f} (n={s.sum()}) | KODEX200 {lv.bB[s].mean():+.3f} vs {lv.bB[~s].mean():+.3f}")
dk=(x-k.bOO.values); rr=r5(dk); print('\n   KODEX200 회피 일별 차 R5',{a:round(b,4) for a,b in rr.items()},' fold',[round(v,4) for v in folds(dk)])
for j,p in enumerate(np.array_split(k.assign(x=x),3)):
    print(f"   3분할{j+1} 보유 Sh {prof(p.bOO)['sharpe']:.2f} → 회피 Sh {prof(p.x)['sharpe']:.2f}")
