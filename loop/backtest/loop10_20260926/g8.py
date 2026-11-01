from ev import *
import warnings; warnings.filterwarnings('ignore')
dates=E.dates; R=E.R; bi=E.bi
ym=np.array([int(d[:6]) for d in dates]); months=sorted(set(ym)); mi={v:a for a,v in enumerate(months)}
def monthly(X):
    M=np.full((len(months),E.N),np.nan)
    for a,v in enumerate(months):
        rows=ym==v; Y=X[rows]; cnt=(~np.isnan(Y)).sum(0); M[a]=np.where(cnt>=10,np.nansum(Y,0),np.nan)
    return M
Mex=monthly(R-R[:,[bi]]); Mraw=monthly(R)
def seas(i,M,minyrs=2,shift=0):
    t=ym[i+1]; y,m=t//100,t%100; m2=(m-1+shift)%12+1
    past=[mi[p] for p in months if p%100==m2 and (p//100<y if m2>=1 else True) and p<t - (0 if shift==0 else 0)]
    past=[mi[p] for p in months if p%100==m2 and p < (y*100+m) and not (p//100==y)]  # 올해 제외 = 작년 이전만
    if len(past)<minyrs: return np.full(E.N,np.nan)
    X=M[past]; c=(~np.isnan(X)).sum(0)
    return np.where(c>=minyrs,np.nanmean(X,0),np.nan)
def mk(M=Mex,q=1/3,minyrs=2,shift=0,fixed=None):
    cache={}
    def f(i,pl):
        v=E.vol(20)[i,pl]; m=~np.isnan(v)
        if m.sum()<5: return pl[:5]
        c,v=pl[m],v[m]
        if fixed is not None: s=fixed[c]
        else:
            if i not in cache: cache[i]=seas(i,M,minyrs,shift)
            s=cache[i][c]
        sr=pd.Series(s).rank(pct=True).fillna(0.5).values
        keep=sr>q
        if keep.sum()<5: return c[np.argsort(v,kind='stable')[:5]]
        return c[keep][np.argsort(v[keep],kind='stable')[:5]]
    return f
import sys
part=sys.argv[1]
if part=='r1':
    for q in (0.2,0.25,1/3,0.4,0.5):
        for my in (2,3):
            evaluate(f'R1 q{q:.2f} minyrs{my}',mk(q=q,minyrs=my))
if part=='r3':
    evaluate('R3 원수익률(초과 아님) 계절성',mk(M=Mraw))
if part=='r4shift':
    for sh in range(1,12):
        o,_=evaluate(f'R4 엉뚱한 달(+{sh}개월) 계절성',mk(shift=sh),quiet=True)
        print(sh, *[f"{k}:Δ{o[k]['dmean']:+.4f} t{o[k]['t']:+.2f} ΔCAGR{o[k]['dcagr']:+.1f}" for k in MET])
if part=='r4fix':
    rng=np.random.default_rng(20260926); out=[]
    for r in range(200):
        fx=rng.random(E.N)
        o,_=evaluate('fix',mk(fixed=fx),quiet=True); out.append([o[k]['dmean'] for k in MET])
    out=np.array(out); np.save('r4fix.npy',out)
    real=[0.0098,0.0093,0.0185]
    for j,k in enumerate(MET): print(k,'귀무평균 %+.4f p95 %+.4f p99 %+.4f 실제 %+.4f p=%.3f'%(out[:,j].mean(),np.quantile(out[:,j],.95),np.quantile(out[:,j],.99),real[j],(out[:,j]>=real[j]).mean()))
