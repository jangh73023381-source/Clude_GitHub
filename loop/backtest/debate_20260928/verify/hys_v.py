from vcommon import *
V=E.vol(20)
def run_hys(K=8,PK=40):
    held=None; S={}; turn={}
    for i in range(20,E.T-3):
        p30=E.pool(i,30)
        if len(p30)<5: continue
        pk=E.pool(i,PK); lv=E.sel_lv(i,p30)
        v30=V[i,p30]
        if (~np.isnan(v30)).sum()<5:
            new=list(lv)
        elif held is None:
            new=list(lv)
        else:
            keep=[]
            setpk=set(pk)
            for h in held:
                if h not in setpk or np.isnan(V[i,h]): continue
                cand=set(p30)|{h}
                vs=np.array([V[i,c] for c in cand]); vs=vs[~np.isnan(vs)]
                rank=1+(vs<V[i,h]).sum()   # ties favourable; stable by value
                if rank<=K: keep.append(h)
            new=list(keep)
            o=p30[np.argsort(np.where(np.isnan(v30),np.inf,v30),kind='stable')]
            for c in o:
                if len(new)>=5: break
                if c not in new and not np.isnan(V[i,c]): new.append(c)
        turn[i]=5 if held is None else len(set(new)-set(held))
        held=new; S[i]=np.array(new)
    return S,turn
def evalS(S,turn,lvdf,tag):
    ii=lvdf.i.values
    oo=np.array([np.nanmean(E.fOO[i,S[i]]) for i in ii]); oox=np.array([np.nanmean(E.fOOx[i,S[i]]) if (~np.isnan(E.fOOx[i,S[i]])).any() else np.nan for i in ii])
    return oo,oox
lvS={}
lv=E.run(lambda i,pl:(lvS.__setitem__(i,E.sel_lv(i,pl)) or lvS[i]))
ii=lv.i.values
tl=np.mean([len(set(lvS[i])-set(lvS[j])) for j,i in zip(ii[:-1],ii[1:])])
# validation
S5,t5=run_hys(5,30); mism=sum(set(S5[i])!=set(lvS[i]) for i in ii); print('validation K5/pool30 mismatch days',mism)
for K in (8,6,10):
    S,t=run_hys(K,40)
    oo,oox=evalS(S,t,lv,K)
    d=oo-lv.OO.values; dx=oox-lv.OOx.values
    th=np.mean([len(set(S[i])-set(S[j])) for j,i in zip(ii[:-1],ii[1:])])
    m,ci=ci_mean(d); sd,sci=ci_shdiff(oo,lv.OO.values)
    mx,cix=ci_mean(dx)
    print(f'K{K}: OO diff mean {m:+.4f} CI {ci} | ShDiff {sd:+.3f} CI {sci} | MDD HYS {prof(oo)["mdd"]:.1f} LV {prof(lv.OO)["mdd"]:.1f} | turnover HYS {th:.3f} LV {tl:.3f} red {1-th/tl:.3f} | OOx diff {mx:+.4f} CI {cix} | folds {folds(d)}')
