import pandas as pd,numpy as np,sys
df=pd.read_pickle(sys.argv[1] if len(sys.argv)>1 else 'r1_main.pkl')
print('events',df.ev.nunique())
def tstat(x): x=np.asarray(x,float); x=x[np.isfinite(x)]; return x.mean()/(x.std(ddof=1)/np.sqrt(len(x))) if len(x)>2 else np.nan
nr=df[~df.pool.str.startswith('RND')]
out=[]
for (p,r),g in nr.groupby(['pool','rule']):
    d=g.groupby('t')[['ex1','gap','intra','ex2o']].mean()   # 날짜 단위
    e=g.groupby('ev')['ex1'].mean()
    out.append(dict(pool=p,rule=r,days=len(d),n_sig=g.n.mean().round(1),ex1=d.ex1.mean()*100,t_day=tstat(d.ex1),t_ev=tstat(e),
        ev_pos=f"{(e>0).sum()}/{len(e)}",gap=d.gap.mean()*100,intra=d.intra.mean()*100,ex2o=d.ex2o.mean()*100,t2o=tstat(d.ex2o),rot=g.groupby('t').rot.first().mean()))
o=pd.DataFrame(out); pd.set_option('display.width',250); print(o.round(3).to_string(index=False))
rn=df[df.pool.str.startswith('RND')]
if len(rn):
    pm=rn.groupby('pool').apply(lambda g:g.groupby('t').ex1.mean().mean()*100)
    pm2=rn.groupby('pool').apply(lambda g:g.groupby('t').ex2o.mean().mean()*100)
    print('RANDOM down ex1: mean %.3f p5 %.3f p95 %.3f p99 %.3f | ex2o mean %.3f p95 %.3f'%(pm.mean(),pm.quantile(.05),pm.quantile(.95),pm.quantile(.99),pm2.mean(),pm2.quantile(.95)))
    for p in ['A','B','B1','CB','CV']:
        v=o[(o.pool==p)&(o.rule=='down')].ex1.values
        v2=o[(o.pool==p)&(o.rule=='down')].ex2o.values
        if len(v): print(p,'down ex1 p(rand>=)',(pm>=v[0]).mean(),' ex2o p',(pm2>=v2[0]).mean())
