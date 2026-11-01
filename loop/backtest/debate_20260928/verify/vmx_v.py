from vcommon import *
C=E.C; T,N=C.shape; bi=E.bi; Rd=E.R
def lag(X,k): return np.vstack([np.full((k,N),np.nan),X[:-k]])
M150=(C/lag(C,150)-1)*100
okH=E.elig[None,:]&~(((C/lag(C,1)-1)>.10)|((C/lag(C,3)-1)>.20))
START=250
def top(i):
    s=M150[i]; m=okH[i]&~np.isnan(s)&~np.isnan(C[i]); idx=np.where(m)[0]
    if len(idx)<5: return None
    return idx[np.argsort(-s[idx],kind='stable')[:5]]
# sleeve daily ret r[t] = ret on day t of picks chosen at t-1
r=np.full(T,np.nan)
for i in range(START,T-1):
    p=top(i)
    if p is None: r[i+1]=0; continue
    x=Rd[i+1,p]; x=x[~np.isnan(x)]; r[i+1]=x.mean() if len(x) else 0
t0=START+1
rs=pd.Series(r); bm=pd.Series(Rd[:,bi])
def weights(L=126,step=5,src=rs,band=0.10):
    sg=src.rolling(L,min_periods=L).std()
    med=sg.expanding().median()
    raw=np.minimum(1,med/sg).values
    w=np.full(T,np.nan); cur=np.nan; last=-99
    for i in range(T):
        if np.isnan(raw[i]): continue
        if np.isnan(cur): cur=raw[i]; last=i
        elif i-last>=step:
            last=i
            if abs(raw[i]-cur)>=band: cur=raw[i]
        w[i]=cur
    return w, sg.values
w,sgS=weights()
sgM=bm.rolling(126,min_periods=126).std().values
# evaluation: returns on day t+1 use w[t]; warmup 250 sleeve days
ev=np.arange(t0+250,T)
sl=r[ev]; wv=w[ev-1]; vm=wv*sl
ok=~np.isnan(vm); print('eval days',ok.sum(),dates[ev[ok][0]],dates[ev[ok][-1]])
# P1
m=~np.isnan(sgS)&~np.isnan(sgM)&(np.arange(T)>=t0+126)
a,b=np.log(sgS[m]),np.log(sgM[m]); rat=sgS[m]/sgM[m]
print('P1 corr',np.corrcoef(a,b)[0,1],'CV',rat.std()/rat.mean())
ma60=pd.Series(C[:,bi]).rolling(60).mean().values; below=C[:,bi]<ma60
wd=w[ev-1]; bd=below[ev-1]
print('P2 share(below|w<0.9)',bd[wd<0.9].mean(),'P3 share w<1',(wd<1).mean(),'mean w',np.nanmean(wd))
# performance
ex=np.nanmean(wd)
print('sleeve',fmt(prof(sl[ok])),'\nVMX',fmt(prof(vm[ok])))
print('VMX vs const(=sleeve Sh) diff,CI',ci_shdiff(vm[ok],(ex*sl)[ok]))
# gate controls
gbin=(~bd).astype(float); print('binary gate mean exposure',gbin.mean())
g_scaled=gbin*min(1,ex/gbin.mean())*sl
print('gate binary(scaled) Sh',prof(g_scaled[ok])['sharpe'],'diff CI',ci_shdiff(vm[ok],g_scaled[ok]))
# partial gate: 1 above, g below to match mean exposure
fb=bd.mean(); g=(ex-(1-fb))/fb
gp=np.where(bd,g,1.0)*sl if g>=0 else g_scaled
print('partial gate g',g,'Sh',prof(gp[ok])['sharpe'],'diff CI',ci_shdiff(vm[ok],gp[ok]))
# KODEX sigma version (control 2)
w2,_=weights(src=bm); v2=w2[ev-1]*sl
print('ctrl2 Kodex-sigma Sh',prof(v2[ok])['sharpe'],'mean w',np.nanmean(w2[ev-1]))
for L in (63,252):
    wl,_=weights(L=L); x=wl[ev-1]*sl; print('L',L,'Sh',prof(x[ok])['sharpe'],ci_shdiff(x[ok],sl[ok]))
w1,_=weights(step=1); x=w1[ev-1]*sl; print('step1 Sh',prof(x[ok])['sharpe'],ci_shdiff(x[ok],sl[ok]))
