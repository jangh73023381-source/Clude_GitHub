"""신용잔고 상대수준 U자 활용 검정: 양 극단(Q1·Q5) 100% / 중간(Q2~Q4) 비중 w. 분위는 그 시점까지의 과거 분포로만(확장창) 정해 룩어헤드 차단."""
import pandas as pd,numpy as np
d=pd.read_csv('merged.csv',dtype={'date':str}); LAG=2
r=d.kospi.pct_change().shift(-1).values*100   # t 판단 → t+1 수익
def z(x,w): return (x-x.rolling(w).mean())/x.rolling(w).std()
def prof(x):
    x=x[~np.isnan(x)]; c=np.cumprod(1+x/100); y=len(x)/250
    return dict(cagr=(c[-1]**(1/y)-1)*100,mdd=((c/np.maximum.accumulate(c))-1).min()*100,sh=x.mean()/x.std()*250**.5)
def rule(sig,w=0.5,lo=.2,hi=.8):
    s=sig.shift(LAG)
    ql=s.expanding(500).quantile(lo).shift(1); qh=s.expanding(500).quantile(hi).shift(1)  # 과거 분포 기준 경계
    mid=(s>ql)&(s<qh); expo=np.where(mid,w,1.0); expo[ql.isna().values]=np.nan
    return expo
def run(expo,name,verbose=True):
    ok=~np.isnan(expo)&~np.isnan(r); x=r[ok]*expo[ok]; b=r[ok]
    p,pb=prof(x),prof(b); n=len(x); f=[]
    for k in range(3):
        sl=slice(k*n//3,(k+1)*n//3); f.append(prof(x[sl])['sh']-prof(b[sl])['sh'])
    if verbose: print(f"{name:34s} CAGR {p['cagr']:5.1f}({pb['cagr']:.1f}) MDD {p['mdd']:6.1f}({pb['mdd']:.1f}) Sh {p['sh']:.2f}({pb['sh']:.2f}) 평균노출 {expo[ok].mean():.2f} ΔSh fold {[round(v,2) for v in f]}")
    return p['sh'],expo[ok].mean(),ok
print('(괄호 = 코스피 상시보유)')
base=z(d.credit,250)
sh,ex,ok=run(rule(base),'U자: 중간 50% (신용 z250)')
# 대조1: 같은 평균노출을 무작위 시점에 배분(시차이동 300회)
rng=np.random.default_rng(3); e=rule(base); sims=[]
for _ in range(300):
    k=rng.integers(250,len(e)-250); sims.append(run(np.roll(e,k),'',False)[0])
print(f"   시차이동 대조 Sh 평균 {np.mean(sims):.2f} p={np.mean(np.array(sims)>=sh):.3f}")
# 대조2: 일정 비중 상수 노출
x=r[ok]*ex; print(f"   같은 평균노출 상수 보유 Sh {prof(x)['sh']:.2f}")
print('\n[R1] 창 길이·중간 비중·경계')
for w in (120,500): run(rule(z(d.credit,w)),f'U자 중간50% (z{w})')
for wt in (0,0.75): run(rule(base,w=wt),f'U자 중간{int(wt*100)}% (z250)')
run(rule(base,lo=.3,hi=.7),'U자 경계 30/70%')
print('\n[대안] 신용/예탁금 비율 z: 높으면 50%')
s=d.cdrz.shift(LAG); qh=s.expanding(500).quantile(.8).shift(1); ex2=np.where(s>=qh,0.5,1.0); ex2[qh.isna().values]=np.nan
sh2,_,_=run(ex2,'신용/예탁 상위20% → 50%')
sims=[run(np.roll(ex2,rng.integers(250,len(ex2)-250)),'',False)[0] for _ in range(300)]
print(f"   시차이동 대조 Sh 평균 {np.mean(sims):.2f} p={np.mean(np.array(sims)>=sh2):.3f}")
print('\n[U자의 정체] 신용 z 분위별 직전 60일 코스피 수익 / 이후 20일')
q=pd.qcut(base.shift(LAG),5,labels=False); print(pd.DataFrame({'직전60일':d.kospi.pct_change(60).mul(100).groupby(q).mean(),'이후20일':d.fk20.groupby(q).mean()}).round(2).T)
print('\n[연도별 U자 여부] (Q1·Q5 평균 − Q2~Q4 평균, 이후 20일 %p)')
s=base.shift(LAG); yr=d.date.str[:4]; out=[]
for y,g in d.groupby(yr):
    if y<'2011': continue
    qq=pd.qcut(s[g.index],5,labels=False,duplicates='drop'); a=g.fk20[(qq==0)|(qq==4)].mean(); b=g.fk20[(qq>=1)&(qq<=3)].mean(); out.append((y,round(a-b,2)))
print(out, ' 양수 연도', sum(v>0 for _,v in out),'/',len(out))

print('\n[대조: 신용 없이 코스피 자체로 같은 U자]')
for w,nm in [(60,'코스피 60일 수익'),(120,'코스피 120일 수익')]:
    run(rule(d.kospi.pct_change(w)),f'U자 중간50% ({nm})')
run(rule(z(d.kospi,250)),'U자 중간50% (코스피 수준 z250)')
print('\n[연도별 U자 규칙 − 상시보유 수익 차(%p)]')
e=rule(base); ok=~np.isnan(e)&~np.isnan(r); dd=d[ok].copy(); dd['x']=r[ok]*e[ok]; dd['b']=r[ok]
g=dd.groupby(dd.date.str[:4]).apply(lambda g:pd.Series({'규칙':(np.prod(1+g.x/100)-1)*100,'보유':(np.prod(1+g.b/100)-1)*100}))
g['차']=g['규칙']-g['보유']; print(g.round(1).T.to_string())
