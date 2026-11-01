from ev import *
inv=pd.read_pickle('inv.pkl')
def grid(col):
    g=inv.pivot(index='dt',columns='code',values=col).reindex(index=E.dates,columns=E.codes)
    return g.values.astype(float)
TV=grid('acc_trde_prica')
SIG={}
for nm,cols in (('사모+연기금',['samo_fund','penfnd_etc']),('외국인',['frgnr_invsr']),('기관계',['orgn']),('개인',['ind_invsr'])):
    X=sum(np.nan_to_num(grid(c)) for c in cols); X[np.isnan(TV)]=np.nan
    for k in (5,20):
        num=pd.DataFrame(X).rolling(k,min_periods=k).sum().values
        den=pd.DataFrame(TV).rolling(k,min_periods=k).sum().values
        SIG[(nm,k)]=np.where(den>0,num/den,np.nan)
def sel(S,mode):
    def f(i,pl):
        v=E.vol(20)[i,pl]; s=S[i,pl]; m=~np.isnan(v)
        if m.sum()<5: return pl[:5]
        c,v,s=pl[m],v[m],s[m]
        if mode=='filt':
            keep=~(s<0)   # 순매도 제외(결측은 유지)
            if keep.sum()<5: return c[np.argsort(v,kind='stable')[:5]]
            return c[keep][np.argsort(v[keep],kind='stable')[:5]]
        if mode=='blend':
            sr=pd.Series(s).rank(pct=True).fillna(0.5).values
            return c[np.argsort(pd.Series(v).rank(pct=True).values-sr,kind='stable')[:5]]
        if mode=='top':
            ss=np.where(np.isnan(s),-9,s); return c[np.argsort(-ss,kind='stable')[:5]]
    return f
# 신호 가용 커버리지
cov=np.mean([(~np.isnan(SIG[("사모+연기금",5)][i,E.pool(i)])).mean() for i in range(100,E.T-3,20)])
print('pool 내 신호 커버리지 %.3f'%cov)
res=[]
for k in (5,20):
    S=SIG[('사모+연기금',k)]
    for mode in ('filt','blend'):
        o,_=evaluate(f'사모+연기금{k}일 {mode}',sel(S,mode)); res.append(o)
    o,_=evaluate(f'사모+연기금{k}일 pool상위5 (vs MOM)',sel(S,'top'),ref='MOM'); res.append(o)
# 진단: 다른 주체 (blend, 5일)
for nm in ('외국인','기관계','개인'):
    evaluate(f'[진단] {nm}5일 blend',sel(SIG[(nm,5)],'blend'))
import pickle; pickle.dump(res,open('it10.pkl','wb'))
