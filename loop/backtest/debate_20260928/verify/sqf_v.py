from vcommon import *
import statsmodels.api as sm
R=E.R; T,N=R.shape
V=E.vol(20)
Rdf=pd.DataFrame(R)
fut=Rdf.rolling(20,min_periods=20).std().shift(-20).values   # row i -> std of R[i+1..i+20]
vol=P['volume']; C=E.C
zero=((np.abs(R)<1e-9)&~np.isnan(R))|(vol==0)
Z=pd.DataFrame(zero.astype(float)).rolling(20,min_periods=20).mean().values
TV=pd.DataFrame(C*vol).rolling(20,min_periods=20).mean().values
rows=[]
for i in range(20,T-21):
    pl=E.pool(i,30)
    if len(pl)<5: continue
    for j in pl:
        rows.append((i,dates[i][:6],j,fut[i,j],V[i,j],Z[i,j],TV[i,j]))
d=pd.DataFrame(rows,columns=['i','ym','j','fut','s20','z','tv']).dropna()
d=d[(d.fut>0)&(d.s20>0)]
d['y']=np.log(d.fut/d.s20)
print('n obs',len(d),'months',d.ym.nunique(), 'Z mean',d.z.mean(),'share Z>0',(d.z>0).mean())
def run(d,mode):
    if mode=='xs':
        d=d.copy(); d['sq']=d.groupby('i').s20.transform(lambda x: pd.qcut(x.rank(method='first'),5,labels=False))
        d['tq']=d.groupby('i').tv.transform(lambda x: pd.qcut(x.rank(method='first'),5,labels=False))
    else:
        d=d.copy(); d['sq']=pd.qcut(d.s20,5,labels=False); d['tq']=pd.qcut(d.tv,5,labels=False)
    X=pd.concat([d[['z']],pd.get_dummies(d.sq,prefix='s',drop_first=True,dtype=float),pd.get_dummies(d.tq,prefix='t',drop_first=True,dtype=float)],axis=1)
    X=sm.add_constant(X)
    g=pd.factorize(d.ym)[0]
    r=sm.OLS(d.y,X).fit(cov_type='cluster',cov_kwds={'groups':g})
    r0=sm.OLS(d.y,sm.add_constant(pd.concat([d[['z']],pd.get_dummies(d.sq,prefix='s',drop_first=True,dtype=float)],axis=1))).fit(cov_type='cluster',cov_kwds={'groups':g})
    print(mode,'Z coef(σ+TV ctrl)',r.params['z'],'t',r.tvalues['z'],' | σ ctrl only coef',r0.params['z'],'t',r0.tvalues['z'])
run(d,'xs'); run(d,'pooled')
# tercile ratio
d['zt']=d.groupby('i').z.transform(lambda x: pd.qcut(x.rank(method='first'),3,labels=False))
print('median ratio by Z tercile', d.groupby('zt').y.apply(lambda x: np.exp(x.median())).to_dict())
print('--- robustness (hypothesis-favorable variants) ---')
g=pd.factorize(d.ym)[0]
d['zpos']=(d.z>0).astype(float); d['ls']=np.log(d.s20); d['ltv']=np.log(d.tv.clip(lower=1))
for zc in ('z','zpos'):
    for ctr in (['ls'],['ls','ltv']):
        r=sm.OLS(d.y,sm.add_constant(d[[zc]+ctr])).fit(cov_type='cluster',cov_kwds={'groups':g})
        print(zc,ctr,'coef',round(r.params[zc],4),'t',round(r.tvalues[zc],2))
