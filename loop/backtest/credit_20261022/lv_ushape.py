"""신용 U자 노출 규칙을 Rule LV(단기 [6-1]) 포트폴리오에 얹기. 7년 ETF 패널, 지표 A·OO. 신용 판정은 선정일 D 기준 T-2 신용(확장창 분위)."""
import os,sys,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
import engine as _E; P7=os.path.join(BT,'panel_ohlc_long.csv'); _E.load.__defaults__=(P7,)
from engine import load,Engine,prof,tstat,r5,folds
P,dates,codes,names=load(P7); E=Engine(P,dates,codes,names)
lv=E.run(lambda i,pl:E.sel_lv(i,pl),start=60)
c=pd.read_csv('merged.csv',dtype={'date':str})
def expo_series(sig,w=0.5,lo=.2,hi=.8):
    s=sig.shift(2); ql=s.expanding(500).quantile(lo).shift(1); qh=s.expanding(500).quantile(hi).shift(1)
    e=np.where((s>ql)&(s<qh),w,1.0); e=pd.Series(e,index=c.date); e[ql.isna().values]=np.nan; return e
z=lambda x,w:(x-x.rolling(w).mean())/x.rolling(w).std()
def apply(e,df=lv):
    x=df.copy(); ee=e.reindex(x.date).values
    for k in ('A','OO'): x[k]=x[k]*ee
    x['e']=ee; return x.dropna(subset=['e'])
def show(nm,x,base=None):
    base=lv[lv.date.isin(x.date)] if base is None else base
    out=[]
    for k in ('A','OO'):
        p,pb=prof(x[k]),prof(base[k]); d=(x[k].values-base[k].values)
        n=len(x); fs=[prof(x[k].values[j*n//3:(j+1)*n//3])['sharpe']-prof(base[k].values[j*n//3:(j+1)*n//3])['sharpe'] for j in range(3)]
        out.append(f"{k}: CAGR {p['cagr']:5.1f}({pb['cagr']:.1f}) MDD {p['mdd']:6.1f}({pb['mdd']:.1f}) Sh {p['sharpe']:.2f}({pb['sharpe']:.2f}) ΔSh fold[{', '.join('%+.2f'%v for v in fs)}]")
    print(f"{nm:30s} 노출 {x.e.mean():.2f} | "+' | '.join(out)); return prof(x.OO)['sharpe'],prof(x.A)['sharpe']
print('(괄호 = Rule LV 상시)  기간',lv.date.iloc[0],'~',lv.date.iloc[-1])
e0=expo_series(z(c.credit,250)); x0=apply(e0); sh,sha=show('신용 U자 중간50% (z250)',x0)
# 대조 1: 같은 평균노출 상수
k=x0.e.mean(); xc=lv[lv.date.isin(x0.date)].copy(); xc['A']*=k; xc['OO']*=k; xc['e']=k; show('같은 평균노출 상수',xc)
# 대조 2: 시차이동 300회
rng=np.random.default_rng(9); arr=e0.values; sims=[]
for _ in range(300):
    ee=pd.Series(np.roll(arr,rng.integers(250,len(arr)-250)),index=e0.index); xx=apply(ee); sims.append((prof(xx.OO)['sharpe'],prof(xx.A)['sharpe']))
sims=np.array(sims); print(f"   시차이동 대조 OO Sh 평균 {sims[:,0].mean():.2f} p={np.mean(sims[:,0]>=sh):.3f} | A Sh 평균 {sims[:,1].mean():.2f} p={np.mean(sims[:,1]>=sha):.3f}")
# 대조 3: 신용 없이 코스피로 만든 U자
show('U자 코스피 120일 수익(대조)',apply(expo_series(c.kospi.pct_change(120))))
show('U자 코스피 수준 z250(대조)',apply(expo_series(z(c.kospi,250))))
print('\n[R1]')
for w in (120,500): show(f'신용 U자 z{w}',apply(expo_series(z(c.credit,w))))
show('신용 U자 중간 0%',apply(expo_series(z(c.credit,250),w=0)))
show('신용 U자 중간 75%',apply(expo_series(z(c.credit,250),w=.75)))
show('신용 U자 경계 30/70',apply(expo_series(z(c.credit,250),lo=.3,hi=.7)))
print('\n[R5 · OO 일별 차] 상위 1·3·5·10일 제거')
b=lv[lv.date.isin(x0.date)]; dd=x0.OO.values-b.OO.values; rr=r5(dd); print({k:round(v,4) for k,v in rr.items()})
print('\n[연도별 OO 누적, 규칙 − LV(%p)]')
x0['y']=x0.date.str[:4]; b=b.assign(y=b.date.str[:4])
for y in sorted(x0.y.unique()):
    a=x0[x0.y==y].OO; bb=b[b.y==y].OO; print(y, f"{((np.prod(1+a/100)-1)-(np.prod(1+bb/100)-1))*100:+.1f}", end=' | ')
print()
