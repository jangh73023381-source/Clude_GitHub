from vcommon import *
from scipy.stats import rankdata
C=E.C; T,N=C.shape
def lag(X,k): return np.vstack([np.full((k,N),np.nan),X[:-k]])
MOM={k:(C/lag(C,k)-1)*100 for k in (120,150,200,250)}
okH=E.elig[None,:]&~(((C/lag(C,1)-1)>.10)|((C/lag(C,3)-1)>.20))
START=250
def pct(x,m):
    out=np.full(N,np.nan); idx=np.where(m)[0]
    if len(idx)==0: return out
    rk=rankdata(x[idx]); out[idx]=(rk-1)/(len(idx)-1) if len(idx)>1 else 0.5   # 0..1
    return out
def hbg(i,K=(120,150,200,250)):
    base=okH[i]&~np.isnan(MOM[150][i])&~np.isnan(C[i])
    ps=[]
    for k in K:
        m=okH[i]&~np.isnan(MOM[k][i])&~np.isnan(C[i])
        ps.append(pct(MOM[k][i],m))
    S=np.nanmean(np.vstack(ps),axis=0)
    idx=np.where(base)[0]
    o=np.lexsort((-MOM[150][i][idx],-S[idx]))
    return idx[o[:5]]
def m150(i):
    s=MOM[150][i]; m=okH[i]&~np.isnan(s)&~np.isnan(C[i]); idx=np.where(m)[0]
    return idx[np.argsort(-s[idx],kind='stable')[:5]]
import warnings; warnings.filterwarnings('ignore')
H={};B={}
for i in range(START,T-1):
    H[i]=set(hbg(i)); B[i]=set(m150(i))
ii=sorted(H)
ov=np.mean([len(H[i]&B[i]) for i in ii])
tH=np.mean([len(H[i]-H[i-1]) for i in ii[1:]]); tB=np.mean([len(B[i]-B[i-1]) for i in ii[1:]])
print('P1 overlap',ov,' P2 turnover HBG',tH,'mom150',tB,'reduction',1-tH/tB)
# alt pct def (rank/n)
