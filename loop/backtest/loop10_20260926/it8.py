from ev import *
dates=E.dates; R=E.R; bi=E.bi
ym=np.array([int(d[:6]) for d in dates]); yy=ym//100; mm=ym%100
ex=R-R[:,[bi]]
# 월별 누적 초과(종목×연월)
months=sorted(set(ym))
M=np.full((len(months),E.N),np.nan)
for a,v in enumerate(months):
    rows=ym==v; X=ex[rows]; cnt=(~np.isnan(X)).sum(0)
    M[a]=np.where(cnt>=10,np.nansum(X,0),np.nan)
mi={v:a for a,v in enumerate(months)}
def seas(i, minyrs=2):
    # D+1 이 속한 달의 과거 같은 달(작년 이전) 평균
    t=ym[i+1]; y,m=t//100,t%100
    past=[mi[p] for p in months if p%100==m and p//100<y]
    if len(past)<minyrs: return np.full(E.N,np.nan)
    X=M[past]; c=(~np.isnan(X)).sum(0)
    return np.where(c>=minyrs,np.nanmean(X,0),np.nan)
cache={}
def S(i):
    if i not in cache: cache[i]=seas(i)
    return cache[i]
def sel(mode):
    def f(i,pl):
        v=E.vol(20)[i,pl]; s=S(i)[pl]; m=~np.isnan(v)
        if m.sum()<5: return pl[:5]
        c,v,s=pl[m],v[m],s[m]
        sr=pd.Series(s).rank(pct=True).fillna(0.5).values
        if mode=='blend': o=np.argsort(pd.Series(v).rank(pct=True).values-sr,kind='stable')[:5]; return c[o]
        if mode=='filt':
            keep=sr>1/3
            if keep.sum()<5: return c[np.argsort(v,kind='stable')[:5]]
            c2,v2=c[keep],v[keep]; return c2[np.argsort(v2,kind='stable')[:5]]
    return f
res=[]
for mode in ('blend','filt'):
    o,_=evaluate(f'계절성 {mode}',sel(mode)); res.append(o)
# 계절성 신호 자체의 횡단면 IC (전체 적격 유니버스, 월 단위)
ics=[]
for a,v in enumerate(months):
    if a==0: continue
    i=int(np.where(ym==v)[0][0])-1
    s=seas(i); r=M[a]; ok=~np.isnan(s)&~np.isnan(r)&E.elig
    if ok.sum()>=15: ics.append(pd.Series(s[ok]).corr(pd.Series(r[ok]),method='spearman'))
ics=np.array(ics); print('월간 계절성 랭크IC 평균 %.4f t %.2f n %d'%(ics.mean(),tstat(ics),len(ics)))
import pickle; pickle.dump(res,open('it8.pkl','wb'))
