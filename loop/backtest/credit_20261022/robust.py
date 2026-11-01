"""생존 후보 강건성: 신용/예탁금 비율 z, 신용 급감 후 반등."""
import pandas as pd,numpy as np
d=pd.read_csv('merged.csv',dtype={'date':str}); LAG=2
def z(x,w): return (x-x.rolling(w).mean())/x.rolling(w).std()
d['k20']=d.kospi.pct_change(20)*100; d['k60']=d.kospi.pct_change(60)*100
out=[]
def qs(sig,h=20,name=''):
    s=d[sig].shift(LAG); y=d[f'fk{h}']; ok=s.notna()&y.notna(); q=pd.qcut(s[ok],5,labels=False); g=y[ok].groupby(q).mean()
    # 비중복 표본(h일 간격) t
    idx=np.where(ok)[0]; res=[]
    for o in range(h):
        sel=idx[o::h]; ss=s.iloc[sel]; yy=y.iloc[sel]; qq=pd.qcut(ss,5,labels=False,duplicates='drop'); res.append(yy[qq==4].mean()-yy[qq==0].mean())
    print(f"{name:40s} Q1..Q5 {[round(x,2) for x in g]}  Q5-Q1 {g.iloc[4]-g.iloc[0]:+.2f}  비중복 오프셋 {h}개 중 음수 {sum(np.array(res)<0)}")
print('[R1] z 창 길이 · h=20')
for w in (60,120,250,500):
    d[f'cdr{w}']=z(d.cdr,w); qs(f'cdr{w}',20,f'신용/예탁금 z({w}일)')
print('\n[R3] 정의 교체·구성요소 분해 · h=20')
d['dep_z']=z(d.deposit,250); d['cr_z']=z(d.credit,250); d['cdr_raw']=d.cdr
d['cdr_chg60']=d.cdr.pct_change(60)*100
for s,nm in [('cdr_raw','신용/예탁금 원값'),('cdr_chg60','신용/예탁금 60일 변화'),('cr_z','신용 단독 z'),('dep_z','예탁금 단독 z'),('k20','(대조) 코스피 20일 수익'),('k60','(대조) 코스피 60일 수익')]: qs(s,20,nm)
print('\n[통제] 회귀 fwd20 ~ cdrz + 코스피20·60일 수익 + 레버리지z (비중복 20일 표본, OLS t)')
import numpy.linalg as la
s=d[['cdrz','k20','k60','levz']].shift(LAG); y=d.fk20; X=pd.concat([s,y],axis=1).dropna()
X=X.iloc[::20]; A=np.column_stack([np.ones(len(X)),X[['cdrz','k20','k60','levz']].values]); b,res,_,_=la.lstsq(A,X.fk20.values,rcond=None)
e=X.fk20.values-A@b; cov=np.linalg.inv(A.T@A)*e.var(ddof=A.shape[1]); t=b/np.sqrt(np.diag(cov))
for nm,bb,tt in zip(['상수','cdrz','k20','k60','levz'],b,t): print(f'  {nm:6s} 계수 {bb:+.3f} t {tt:+.2f}')
print(f'  n={len(X)}')
print('\n[연도별] cdrz 상위20% 날의 20일 수익 − 그해 평균')
s=d.cdrz.shift(LAG); thr=s.quantile(.8); d['yr']=d.date.str[:4]
for y_,g in d.groupby('yr'):
    hi=g[s.loc[g.index]>=thr]
    if len(hi)>10: print(y_,f"n{len(hi):3d} {hi.fk20.mean()-g.fk20.mean():+.2f}%p",end=' | ')
print('\n\n[R5] Q5 의 20일 수익: 최악 꼬리 의존 확인 — Q5 날 중 하위 5% 제거 후 평균')
q5=d.loc[s>=thr,'fk20'].dropna(); q1=d.loc[s<=s.quantile(.2),'fk20'].dropna()
print(f"Q5 평균 {q5.mean():+.2f} 중앙 {q5.median():+.2f} 승률 {(q5>0).mean()*100:.0f}% · 하위5% 제거 {q5[q5>q5.quantile(.05)].mean():+.2f} | Q1 평균 {q1.mean():+.2f} 중앙 {q1.median():+.2f} 상위5% 제거 {q1[q1<q1.quantile(.95)].mean():+.2f}")
cur=d.cdrz.iloc[-1]; print(f"\n현재 cdrz {cur:+.2f} → 분위 {(s.dropna()<=cur).mean()*100:.0f}%ile (Q5 컷 {thr:+.2f})")
# 급감 반등 강건성
print('\n[급감] 신용 5일 변화 하위 x% 후 20일, fold')
d['c5']=d.credit.pct_change(5)*100; s5=d.c5.shift(LAG)
for qq in (.02,.05,.10):
    th=s5.quantile(qq); a=d.loc[s5<=th]; fo=[p.fk20.mean() for p in np.array_split(a,3)]
    # 독립 이벤트(20일 간격)
    ev=[];last=-99
    for i in a.index:
        if i-last>=20: ev.append(i); last=i
    print(f"하위{qq*100:.0f}% (≤{th:.1f}%) n={len(a)} 독립이벤트 {len(ev)} 평균 {a.fk20.mean():+.2f} 독립 {d.loc[ev,'fk20'].mean():+.2f} 승률 {(d.loc[ev,'fk20']>0).mean()*100:.0f}% fold {[round(x,2) for x in fo]} 기저 {d.fk20.mean():+.2f}")
print('독립 이벤트(5%):',[ (d.date[i],round(d.fk20[i],1)) for i in ev][:40])
