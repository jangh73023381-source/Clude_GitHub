from vcommon import *
cl=pd.read_csv('/home/claude/w/debate/prereg_mom_classes.csv',dtype=str)
cmap=dict(zip(cl.code,cl.cls)); inc=dict(zip(cl.code,cl.income))
eligc=[c for c,e in zip(codes,E.elig) if e]
miss=[c for c in eligc if c not in cmap]; print('eligible codes',len(eligc),'missing from CSV',miss)
isEq=np.array([cmap.get(c)=='주식' for c in codes]); isInc=np.array([inc.get(c)=='1' for c in codes])
V=E.vol(20)
def mk_eq(mask,pooln=30):
    def sel(i,pl):
        pl=E.pool(i,pooln)
        lv=E.sel_lv(i,E.pool(i,30))
        v=V[i,pl]; m=mask[pl]&~np.isnan(v)
        c=pl[m]; c=c[np.argsort(v[m],kind='stable')][:5]
        fb=0
        if len(c)<5:
            fb=1
            for x in lv:
                if len(c)>=5: break
                if x not in c: c=np.append(c,x)
        FB.append(fb)
        return c
    return sel
LVp={}; EQp={}
FB=[]
lv=E.run(lambda i,pl:(LVp.__setitem__(i,E.sel_lv(i,pl)) or LVp[i]))
seq=mk_eq(isEq)
eq=E.run(lambda i,pl:(EQp.__setitem__(i,seq(i,pl)) or EQp[i]))
mom=E.run(E.sel_mom)
print('fallback rate',np.mean(FB))
ii=lv.i.values
q1=np.mean([~isEq[LVp[i]] for i in ii]); print('Q1 LV non-equity slot share',q1)
q2=np.mean([len(set(LVp[i])&set(EQp[i])) for i in ii]); print('Q2 overlap EQLV-LV',q2)
q3=(np.mean([isInc[EQp[i]].mean() for i in ii]),np.mean([isInc[LVp[i]].mean() for i in ii])); print('Q3 income EQLV,LV',q3)
j=lv[['i','OO','L1','OOx']].merge(eq[['i','OO','L1','OOx']],on='i',suffixes=('_lv','_eq')).merge(mom[['i','OO']].rename(columns={'OO':'OO_m'}),on='i')
print('n',len(j),len(lv),len(eq),len(mom))
a=j.OO_eq.values; l=j.OO_lv.values; m=j.OO_m.values
# C1 weight: vol match to EQLV
ws=np.linspace(0,1,1001); sd=[np.std(w*l+(1-w)*m,ddof=1) for w in ws]
w=ws[np.argmin(np.abs(np.array(sd)-a.std(ddof=1)))]; c1=w*l+(1-w)*m
print('C1 w_LV',w)
for nm,x in (('EQLV',a),('LV',l),('C1',c1),('MOM',m)): print(nm,fmt(prof(x)))
print('EQLV-C1 Sh diff, CI',ci_shdiff(a,c1)); print('EQLV-LV',ci_shdiff(a,l))
for k in ('L1','OOx'): print(k,'EQLV',prof(j[k+'_eq'])['sharpe'],'LV',prof(j[k+'_lv'])['sharpe'])
# C3 random labels
rng=np.random.default_rng(SEED); cc=[c for c in cl.code]; labs=list(cl.cls)
nulls=[]
for r in range(200):
    perm=rng.permutation(labs); mp=dict(zip(cc,perm)); msk=np.array([mp.get(c)=='주식' for c in codes])
    s=mk_eq(msk); d=E.run(s,metrics=('OO',))
    x=d.merge(j[['i']],on='i').OO.values
    nulls.append(prof(x)['sharpe'])
nulls=np.array(nulls); print('C3 null Sh mean',nulls.mean(),'p(null>=EQLV)',(nulls>=prof(a)['sharpe']).mean())
