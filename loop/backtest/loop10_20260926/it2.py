from ev import *
R=E.R
def sel_mv(look=60, minobs=None, start='lowvol'):
    minobs = minobs or int(look*0.66)
    def f(i, pl):
        W=R[max(0,i-look+1):i+1][:, pl]
        okc = (~np.isnan(W)).sum(0) >= minobs
        if okc.sum()<5: return E.sel_lv(i,pl)
        c=pl[okc]; W=W[:,okc]
        X=pd.DataFrame(W).cov(min_periods=minobs).values
        if np.isnan(X).any():
            X=np.nan_to_num(X, nan=0.0)
        v=np.diag(X)
        ch=[int(np.argmin(v))]
        while len(ch)<5:
            best=None
            for j in range(len(c)):
                if j in ch: continue
                s=ch+[j]; w=np.ones(len(s))/len(s)
                pv=w@X[np.ix_(s,s)]@w
                if best is None or pv<best[0]: best=(pv,j)
            ch.append(best[1])
        return c[ch]
    return f
def sel_dedup(rho=0.9, look=60):
    def f(i,pl):
        v=E.vol(20)[i,pl]; m=~np.isnan(v)
        if m.sum()<5: return pl[:5]
        c=pl[m][np.argsort(v[m],kind='stable')]
        W=pd.DataFrame(R[max(0,i-look+1):i+1][:,c]).corr(min_periods=20).values
        ch=[]
        for j in range(len(c)):
            if all(not (W[j,k]>rho) for k in ch): ch.append(j)
            if len(ch)==5: break
        if len(ch)<5:
            for j in range(len(c)):
                if j not in ch: ch.append(j)
                if len(ch)==5: break
        return c[ch]
    return f
res=[]
for look in (20,40,60,120):
    o,_=evaluate(f'MV look{look}', sel_mv(look)); res.append(o)
for rho in (0.7,0.8,0.9):
    o,_=evaluate(f'LV+dedup rho{rho}', sel_dedup(rho)); res.append(o)
import pickle; pickle.dump(res,open('it2.pkl','wb'))
