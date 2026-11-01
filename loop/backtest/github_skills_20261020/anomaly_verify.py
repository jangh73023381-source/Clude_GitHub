import numpy as np, pandas as pd, gc
src=open('anomaly.py').read()
exec(src.split("SPLIT = 20230630")[0])   # 데이터·재무 준비
from gh_stats import nw_se
HZ=20; F20=np.vstack([C[HZ:]/C[:-HZ]-1,np.full((HZ,N),np.nan)])*100
KX=np.r_[(bench[HZ:]/bench[:-HZ]-1)*100,np.full(HZ,np.nan)]
with np.errstate(invalid='ignore',divide='ignore'):
    shrs=ff(f.shrs.values); mcap=shrs*C
    sdr=lambda w: D(R).rolling(w,min_periods=w//2).std().values
    def cosk(w):
        rd=R-D(R).rolling(w,min_periods=w//2).mean().values; md=M-D(M).rolling(w,min_periods=w//2).mean().values
        return -(D(rd*md**2).rolling(w,min_periods=w//2).mean().values/(sdr(w)*D(M).rolling(w,min_periods=w//2).std().values**2))
    mvol=D(V).rolling(21,min_periods=15).sum().values
    def volsd(w): return -(D(mvol).rolling(w,min_periods=int(w*.66)).std().values/D(mvol).rolling(w,min_periods=int(w*.66)).mean().values)
    lev=ff(f.tl.values)/mcap; am=ff(f.ta.values)/mcap
    ey=ff(f.ni.values)/mcap; bm=ff(np.where(f['eq']>0,f['eq'],np.nan))/mcap
    lv=-sdr(20); nh=C/D(H).rolling(250,min_periods=200).max().values
    size=np.log(mcap)
dec=np.full((T,N),np.nan)
def ev(X, q=.9, within=None, ts=None):
    out=[]
    for t in (ts or range(260,T-HZ,20)):
        m=LIQ[t]&np.isfinite(X[t])&np.isfinite(F20[t])&np.isfinite(size[t])
        if m.sum()<150: continue
        idx=np.where(m)[0]; x=X[t,idx]; r=F20[t,idx]
        if within is None:
            sel=x>=np.quantile(x,q); out.append(r[sel].mean()-r.mean())
        else:  # 같은 통제변수 5분위 안에서 상위 10% vs 그 분위 평균 → 가중평균
            z=within[t,idx]; ok=np.isfinite(z); idx2=np.where(ok)[0]
            if len(idx2)<150: continue
            b=pd.qcut(pd.Series(z[idx2]).rank(method='first'),5,labels=False).values; d=[]
            for k in range(5):
                ii=idx2[b==k]; xx=x[ii]; rr=r[ii]; s=xx>=np.quantile(xx,q); d.append(rr[s].mean()-rr.mean())
            out.append(np.mean(d))
    x=np.array(out); k=len(x)//3
    return f"{x.mean():+.2f} (t {x.mean()/nw_se(x,0):.2f}, fold {x[:k].mean():.2f}/{x[k:2*k].mean():.2f}/{x[2*k:].mean():.2f})"
C_={'CoskewACX 252':cosk(252),'Leverage':lev,'AM':am,'VolSD 756':volsd(756)}
print('== 통제: 같은 분위 안에서 (시총·이익수익률·BM·저σ·신고가 5분위)')
for nm,X in C_.items():
    print(nm,'| 원본',ev(X),'| 시총내',ev(X,within=size),'| EY내',ev(X,within=ey),'| BM내',ev(X,within=bm),'| 저σ내',ev(X,within=lv),'| NH내',ev(X,within=nh))
print('\n== R1 창·분위')
for w in (126,504): print('Coskew',w,ev(cosk(w)))
for w in (504,1008): print('VolSD',w,ev(volsd(w)))
for q in (.8,.95): print('q',q,'Coskew',ev(C_['CoskewACX 252'],q=q),'| Leverage',ev(lev,q=q),'| AM',ev(am,q=q),'| VolSD',ev(C_['VolSD 756'],q=q))
print('\n== 신호 간 횡단면 순위상관(평균)')
names=list(C_)+['EY','BM','저σ','시총','NH']; arrs=list(C_.values())+[ey,bm,lv,size,nh]
cm=np.zeros((len(names),len(names))); cnt=0
for t in range(800,T-HZ,60):
    m=LIQ[t]&np.all([np.isfinite(a[t]) for a in arrs],0)
    if m.sum()<200: continue
    df=pd.DataFrame({n:a[t,m] for n,a in zip(names,arrs)}); cm+=df.corr('spearman').values; cnt+=1
print(pd.DataFrame(cm/cnt,index=names,columns=names).round(2).to_string())
