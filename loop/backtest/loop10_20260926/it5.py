from ev import *
C=E.C; T,N=C.shape
def clenow(w):
    L=np.log(C); x=np.arange(w,dtype=float); xm=x.mean(); sxx=((x-xm)**2).sum()
    out=np.full((T,N),np.nan)
    from numpy.lib.stride_tricks import sliding_window_view as sw
    Wv=sw(L,w,axis=0)  # (T-w+1, N, w)
    ym=np.nanmean(Wv,axis=2)
    cov=np.nansum((Wv-ym[...,None])*(x-xm),axis=2)
    b=cov/sxx
    ssr=np.nansum((Wv-ym[...,None])**2,axis=2)
    r2=np.where(ssr>0,(b**2*sxx)/ssr,np.nan)
    nn=(~np.isnan(Wv)).sum(2)
    sc=(np.exp(b*252)-1)*r2
    sc[nn<w]=np.nan
    out[w-1:]=sc
    return out
CL={w:clenow(w) for w in (60,90)}
def lv_from(idx,i):
    v=E.vol(20)[i,idx]; m=~np.isnan(v)
    if m.sum()<5: return None
    return idx[m][np.argsort(v[m],kind='stable')[:5]]
def sel_cl(w, mode):
    S=CL[w]
    def f(i,pl):
        s=S[i]; idx=np.where(E.ok[i]&~np.isnan(s))[0]
        if len(idx)<5: return E.sel_lv(i,pl)
        o=idx[np.argsort(-s[idx],kind='stable')]
        if mode=='top5': return o[:5]
        if mode=='pool30lv':
            r=lv_from(o[:30],i); return r if r is not None else E.sel_lv(i,pl)
    return f
def sel_inpool(w):
    S=CL[w]
    def f(i,pl):
        v=E.vol(20)[i,pl]; s=S[i,pl]; m=~np.isnan(v)&~np.isnan(s)
        if m.sum()<5: return E.sel_lv(i,pl)
        c=pl[m]; sc=pd.Series(v[m]).rank().values+pd.Series(-s[m]).rank().values
        return c[np.argsort(sc,kind='stable')[:5]]
    return f
res=[]
for w in (60,90):
    o,_=evaluate(f'Clenow{w} top5 (vs LV)',sel_cl(w,'top5')); res.append(o)
    o,_=evaluate(f'Clenow{w} top5 (vs MOM)',sel_cl(w,'top5'),ref='MOM')
    o,_=evaluate(f'Clenow{w} pool30→σ',sel_cl(w,'pool30lv')); res.append(o)
    o,_=evaluate(f'mom20 pool 내 σ+Clenow{w} 랭크합',sel_inpool(w)); res.append(o)
import pickle; pickle.dump(res,open('it5.pkl','wb'))
