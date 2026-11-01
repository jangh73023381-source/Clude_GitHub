from ev import *
C=E.C; N=E.N
def lag(X,k): return np.vstack([np.full((k,N),np.nan),X[:-k]])
MOMS={k:(C/lag(C,k)-1)*100 for k in (5,10,60,120)}
MA60=pd.DataFrame(C).rolling(60,min_periods=60).mean().values
MA120=pd.DataFrame(C).rolling(120,min_periods=120).mean().values
def lv_from(idx,i,n=5):
    v=E.vol(20)[i,idx]; m=~np.isnan(v)
    if m.sum()<n: return None
    return idx[m][np.argsort(v[m],kind='stable')[:n]]
def sel_pool(score, n=30):
    def f(i,pl):
        s=score[i]; idx=np.where(E.ok[i]&~np.isnan(s))[0]
        if len(idx)<5: return E.sel_lv(i,pl)
        o=idx[np.argsort(-s[idx],kind='stable')][:n]
        r=lv_from(o,i); return r if r is not None else E.sel_lv(i,pl)
    return f
def sel_all():
    def f(i,pl):
        idx=np.where(E.ok[i])[0]; r=lv_from(idx,i); return r if r is not None else E.sel_lv(i,pl)
    return f
def sel_trend(MA):
    def f(i,pl):
        idx=np.where(E.ok[i]&(C[i]>MA[i]))[0]
        if len(idx)<5: return E.sel_lv(i,pl)
        r=lv_from(idx,i); return r if r is not None else E.sel_lv(i,pl)
    return f
def sel_mompos():
    def f(i,pl):
        idx=np.where(E.ok[i]&(E.mom[i]>0))[0]
        if len(idx)<5: return None
        return lv_from(idx,i)
    return f
res=[]
for k in (5,10,60,120):
    o,_=evaluate(f'pool=mom{k} top30 → σ',sel_pool(MOMS[k])); res.append(o)
o,_=evaluate('pool=전체(모멘텀 없음) → σ',sel_all()); res.append(o)
o,_=evaluate('pool=C>MA60 → σ',sel_trend(MA60)); res.append(o)
o,_=evaluate('pool=C>MA120 → σ',sel_trend(MA120)); res.append(o)
o,_=evaluate('pool=mom20>0 전체 → σ (부족시 현금X)',sel_mompos()); res.append(o)
import pickle; pickle.dump(res,open('it3.pkl','wb'))
