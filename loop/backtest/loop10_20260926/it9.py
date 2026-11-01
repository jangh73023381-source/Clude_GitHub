from ev import *
C=E.C; N=E.N; bi=E.bi
def lag(X,k): return np.vstack([np.full((k,N),np.nan),X[:-k]])
r=lambda k:(C/lag(C,k)-1)
W=0.4*r(63)+0.2*r(126)+0.2*r(189)+0.2*r(252)
RSR=np.full_like(W,np.nan)
for i in range(E.T):
    idx=np.where(E.elig&~np.isnan(W[i]))[0]
    if len(idx)>=10: RSR[i,idx]=pd.Series(W[i,idx]).rank(pct=True).values*99
RL=C/C[:,[bi]]
RLmax=pd.DataFrame(RL).rolling(250,min_periods=120).max().values
nearhi=RL>=RLmax*0.98
MA20=pd.DataFrame(C[:,bi]).rolling(20).mean().values[:,0]
gate=C[:,bi]>MA20
def lvsel(idx,i):
    v=E.vol(20)[i,idx]; m=~np.isnan(v)
    if m.sum()<5: return None
    return idx[m][np.argsort(v[m],kind='stable')[:5]]
def sel(mode,th=80):
    def f(i,pl):
        base=E.ok[i]&(RSR[i]>=th)
        if mode=='nh': base=base&nearhi[i]
        idx=np.where(base)[0]
        if len(idx)<5: return E.sel_lv(i,pl)
        if mode=='top': return idx[np.argsort(-RSR[i,idx],kind='stable')[:5]]
        rr=lvsel(idx,i); return rr if rr is not None else E.sel_lv(i,pl)
    return f
res=[]
o,df=evaluate('RS≥80 상위5(순수, vs MOM)',sel('top'),ref='MOM')
o,df=evaluate('RS≥80 상위5(순수, vs LV)',sel('top')); res.append(o)
o,df=evaluate('RS≥80 → σ하위5',sel('lv')); res.append(o)
o,df=evaluate('RS≥80 ∩ RS라인신고가 → σ하위5',sel('nh')); res.append(o)
# 게이트(지수>MA20 아니면 현금)
g=df.copy(); off=~gate[g.i.values]
for k in ('A','OO','L1'): g.loc[off,k]=0.0
print('게이트OFF 비율',off.mean())
o,_=evaluate('RS≥80 ∩ RS라인신고가 → σ + 지수MA20 게이트',None,df=g); res.append(o)
import pickle; pickle.dump(res,open('it9.pkl','wb'))
