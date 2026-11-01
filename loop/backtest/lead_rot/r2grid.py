import engine as E, numpy as np, pandas as pd, json, sys
def tstat(x): x=np.asarray(x,float); x=x[np.isfinite(x)]; return x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))
base=dict(X=0.08,Y=0.02,k=3,H=40,npool=20)
vars_=[('base',{})]+[('X%g'%x,{'X':x}) for x in [0.06,0.10,0.12]]+[('Y3',{'Y':0.03}),('X6Y3',{'X':0.06,'Y':0.03})]+\
 [('k%d'%k,{'k':k}) for k in [1,2,5]]+[('H%d'%h,{'H':h}) for h in [10,20,60]]+[('n%d'%n,{'npool':n}) for n in [10,40]]+[('liq300',{'liq':300}),('liq150',{'liq':150})]
res=[]
for name,v in vars_:
    p=dict(base); p.update(v); E.LIQ=p.pop('liq',None)
    ev,df=E.run(nrand=0,modes=('A','B'),rules=('down','all'),**p)
    for pool in ['A','B','CB']:
        r={'var':name,'pool':pool,'nev':df.ev.nunique()}
        for rule in ['all','down']:
            g=df[(df.pool==pool)&(df.rule==rule)]
            d=g.groupby('t')[['ex1','ex2o']].mean(); e=g.groupby('ev').ex1.mean()
            r[rule+'_ex1']=round(d.ex1.mean()*100,3); r[rule+'_tev']=round(tstat(e),2); r[rule+'_ex2o']=round(d.ex2o.mean()*100,3)
        g1=df[(df.pool==pool)&(df.rule=='down')].groupby('t').ex1.mean(); g0=df[(df.pool==pool)&(df.rule=='all')].groupby('t').ex1.mean()
        dd=(g1-g0).dropna(); r['down-all']=round(dd.mean()*100,3); r['t_da']=round(tstat(dd),2)
        res.append(r); print(r,flush=True)
pd.DataFrame(res).to_csv('r2_grid.csv',index=False)
