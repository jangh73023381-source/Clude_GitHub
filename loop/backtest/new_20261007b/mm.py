from common import *
E,base=setup(); C,R=E.C,E.R; T,N=C.shape
def lagm(X,k): return np.vstack([np.full((k,N),np.nan),X[:-k]])
m150=(C/lagm(C,150)-1)*100; m60=(C/lagm(C,60)-1); r3=(C/lagm(C,3)-1); rr5=(C/lagm(C,5)-1)
r1=(C/lagm(C,1)-1)*100; hot=((r1>10)|(r3*100>20))
s20=E.vol(20)
def run(sel,start=252):
    rows=[]
    for i in range(start,T-3):
        pk=sel(i)
        if pk is None: continue
        a=E.fA[i,pk] if len(pk) else np.array([])
        a=a[~np.isnan(a)]
        rows.append(dict(date=E.dates[i],ret=a.mean() if len(a) else 0.0,n=len(a),b=E.fA[i,E.bi]))
    return pd.DataFrame(rows)
def mom150(i,n=5):
    ok=E.elig&~np.isnan(m150[i])&~hot[i]; idx=np.where(ok)[0]; return idx[np.argsort(-m150[i,idx])[:n]]
def legacy(i):
    ok=E.elig&(m60[i]<-0.10)&(r3[i]>0.03)&(r3[i]<0.14)&~np.isnan(rr5[i]); idx=np.where(ok)[0]
    return idx[np.argsort(-(r3[i,idx]+rr5[i,idx]))[:5]]
def mlv(i):
    p=mom150(i,30); v=s20[i,p]; ok=~np.isnan(v); return p[ok][np.argsort(v[ok])[:5]]
res={}
for nm,f in (('mom150',mom150),('낙폭과대룰(현행 대조)',legacy),('MLV',mlv)):
    df=run(f); x=df.ret.values; b=df.b.values; p=prof(x); pb=prof(b); d=x-b
    res[nm]=df
    yr=df.assign(y=df.date.str[:4]).groupby('y').apply(lambda g:(np.prod(1+g.ret/100)-1)*100).round(1).to_dict()
    print(f"{nm:14s} CAGR{p['cagr']:+.1f} MDD{p['mdd']:.1f} Sh{p['sharpe']:.2f} | 지수대비 {d.mean():+.4f}%p/일 t{tstat(d):+.2f} fold {' '.join('%+.3f'%v for v in folds(d))} R5-3일 {r5(d)['drop3']:+.4f} | 현금일 {np.mean(df.n==0)*100:.0f}% | 연도 {yr}",flush=True)
print(f"KODEX200      CAGR{pb['cagr']:+.1f} MDD{pb['mdd']:.1f} Sh{pb['sharpe']:.2f}")
a=res['mom150'].set_index('date').ret; l=res['낙폭과대룰(현행 대조)'].set_index('date'); j=a.index.intersection(l.index)
dd=(a[j]-l.ret[j]).values; print('mom150 − 낙폭과대룰 (현금일 포함)',f'{dd.mean():+.4f} t{tstat(dd):+.2f} fold',[round(v,3) for v in folds(dd)],'R5-3일',round(r5(dd)['drop3'],4))
m=l.n[j].values>0; print('  현행 후보 있는 날만',f'{dd[m].mean():+.4f} t{tstat(dd[m]):+.2f} (n={m.sum()})')
# 최근 OOS 구간과 같은 길이(44일) 롤링 창에서 mom150 이 현행에 지는 비율
roll=pd.Series(dd).rolling(44).mean().dropna(); print('44일 창에서 mom150 열위 비율',f'{(roll<0).mean()*100:.0f}%', '최근 44일',round(roll.iloc[-1],3))
# 20일 트랜치(고정 보유) 버전
def tranche(sel,H=20):
    out=[]
    for i in range(252,T-H-1,1):
        pk=sel(i)
        if len(pk)==0: out.append(0.0); continue
        v=(C[i+H,pk]/C[i,pk]-1)*100; v=v[~np.isnan(v)]; out.append(v.mean() if len(v) else 0.0)
    return np.array(out)
for nm,f in (('mom150',mom150),('낙폭과대룰',legacy),('MLV',mlv)):
    t=tranche(f); bb=np.array([(C[i+20,E.bi]/C[i,E.bi]-1)*100 for i in range(252,T-21)])
    print(f'20일 트랜치 {nm}: 평균 {t.mean():+.2f}% (지수 {bb.mean():+.2f}%) 초과 {np.mean(t-bb):+.2f}%p 승률 {np.mean(t>bb)*100:.0f}% fold',[round(v,2) for v in folds(t-bb)])
