# independent simplified IGN P1: merge twins (corr>=.97, components), herds on reps, natural ignition, lead vs first mom5 top5 entry
from vcommon import *
from scipy.sparse.csgraph import connected_components
C,R,T,N=E.C,E.R,E.T,E.N; V=E.vol(20)
def lag(X,k): return np.vstack([np.full((k,N),np.nan),X[:-k]])
R5=(C/lag(C,5)-1)*100
B=np.full((T,N),np.nan); HERD={}; TOP5={}
for i in range(60,T):
    full=~np.isnan(R[i-59:i+1]).any(0)
    U=np.where(E.ok[i]&full&~np.isnan(R5[i])&~np.isnan(V[i]))[0]
    if len(U)<10: continue
    Cm=np.corrcoef(R[i-59:i+1,U].T)
    nc,lab=connected_components(Cm>=0.97,directed=False)
    reps=[];tw={}
    for c in range(nc):
        m=np.where(lab==c)[0]; r=m[np.argmin(V[i,U[m]])]; reps.append(r); tw[r]=m
    reps=np.array(reps); q=np.quantile(R5[i,U],.8)
    Cr=Cm[np.ix_(reps,reps)]
    for k,r in enumerate(reps):
        pe=np.where(Cr[k]>=0.80)[0]; pe=pe[pe!=k]
        if len(pe)<2: continue
        g=np.r_[k,pe]; B[i,U[r]]=(R5[i,U[reps[g]]]>=q).mean()
        HERD[(i,U[r])]=set(U[np.concatenate([tw[reps[x]] for x in g])])
    TOP5[i]=set(U[np.argsort(-R5[i,U],kind='stable')[:5]])
ev=[(i,c) for (i,c) in HERD if B[i,c]>=0.6 and i>=80 and not (B[i-20:i,c]>=0.6).any()]
print('events',len(ev))
for back in (0,5,10):
    L=[]
    for i,c in ev:
        for t in range(i-back,min(T,i+11)):
            if t in TOP5 and TOP5[t]&HERD[(i,c)]: L.append(i-t); break
    L=np.array(L); print('back',back,'n',len(L),'median',np.median(L),'share<=-2',(L<=-2).mean())
