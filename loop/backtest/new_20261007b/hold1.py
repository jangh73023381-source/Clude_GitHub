from common import *
E,base=setup(); C,R=E.C,E.R; H,L=E.P['high'],E.P['low']
s5,s10,s20,s60=E.vol(5),E.vol(10),E.vol(20),E.vol(60)
tr=np.maximum(H-L,np.maximum(np.abs(H-np.vstack([np.full((1,C.shape[1]),np.nan),C[:-1]])),np.abs(L-np.vstack([np.full((1,C.shape[1]),np.nan),C[:-1]]))))
atr5=pd.DataFrame(tr).rolling(5,min_periods=4).mean().values; atr60=pd.DataFrame(tr).rolling(60,min_periods=40).mean().values
defs={'σ5/σ60':s5/s60,'σ5/σ20':s5/s20,'σ10/σ60':s10/s60,'ATR5/ATR60':atr5/atr60}
B=base.set_index('date')
def two(sec,n1):
    def f(i,pl):
        c=E.sel_lv(i,pl,n=n1); v=sec[i,c]; ok=~np.isnan(v)
        if ok.sum()<5: return c[:5]
        c,v=c[ok],v[ok]; return c[np.argsort(v,kind='stable')[:5]]
    return f
out={}
for n1 in (7,8):
    rng=np.random.default_rng(1000+n1); sims=[]
    for s in range(1000):
        df=E.run(lambda i,pl:rng.permutation(E.sel_lv(i,pl,n=n1))[:5],start=S,metrics=('OO',)).set_index('date')
        d=(df.OO-B.OO.reindex(df.index)).values
        sims.append((np.nanmean(d),prof(df.OO)['sharpe'],folds(d)[1]))
    sims=np.array(sims)
    for nm,sec in defs.items():
        df=E.run(two(sec,n1),start=S).set_index('date'); d=(df.OO-B.OO.reindex(df.index)).values
        f=folds(d); sh=prof(df.OO)['sharpe']; rr=r5(d)
        # 귀무 대비 '초과분'(후보 − 무작위 평균)
        p1=np.mean(sims[:,0]>=np.nanmean(d)); p2=np.mean(sims[:,1]>=sh); pf2=np.mean(sims[:,2]>=f[1])
        out[f'{nm} σ{n1}']=dict(dOO=float(np.nanmean(d)),sh=sh,f=[float(x) for x in f],p_mean=float(p1),p_sh=float(p2),p_fold2=float(pf2),drop3=float(rr['drop3']),null_mean=float(sims[:,0].mean()))
        print(f'{nm} σ하위{n1}: dOO {np.nanmean(d):+.4f}(귀무 {sims[:,0].mean():+.4f}) p={p1:.3f} | Sh {sh:.2f} p={p2:.3f} | fold {f[0]:+.3f}/{f[1]:+.3f}/{f[2]:+.3f} (fold2 p={pf2:.3f}) | R5-3일 {rr["drop3"]:+.4f}',flush=True)
json.dump(out,open('res_hold1.json','w'),indent=1,default=float)
