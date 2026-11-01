from ev import *
R=E.R
def ID(k):
    pos=pd.DataFrame((R>0).astype(float)).where(~np.isnan(R)).rolling(k,min_periods=k//2).mean().values
    neg=pd.DataFrame((R<0).astype(float)).where(~np.isnan(R)).rolling(k,min_periods=k//2).mean().values
    C=E.C; N=E.N; lagC=np.vstack([np.full((k,N),np.nan),C[:-k]]); mk=C/lagC-1
    return np.sign(mk)*(neg-pos)
IDs={k:ID(k) for k in (20,60)}
def rk(x): return pd.Series(x).rank(method='average').values
def sel_id(k, mode):
    I=IDs[k]
    def f(i,pl):
        v=E.vol(20)[i,pl]; d=I[i,pl]; m=~np.isnan(v)&~np.isnan(d)
        if m.sum()<5: return E.sel_lv(i,pl)
        c,v,d=pl[m],v[m],d[m]
        if mode=='id': o=np.lexsort((v,d))[:5]
        elif mode=='filt':
            keep=d<=np.median(d); c2,v2=c[keep],v[keep]
            if len(c2)<5: return E.sel_lv(i,pl)
            return c2[np.argsort(v2,kind='stable')[:5]]
        else: o=np.argsort(rk(v)+rk(d),kind='stable')[:5]
        return c[o]
    return f
res=[]
for k in (20,60):
    for mode in ('id','filt','blend'):
        o,_=evaluate(f'FIP ID{k} {mode}',sel_id(k,mode)); res.append(o)
import pickle; pickle.dump(res,open('it4.pkl','wb'))
