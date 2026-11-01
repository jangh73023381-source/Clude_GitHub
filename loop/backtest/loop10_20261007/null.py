"""무작위 대조: σ20 하위 n1 중 무작위 5 (200회) vs 후보 2단계 선정. 지표 OO·A 평균차·Sharpe."""
from common import *
E,base=setup(); C,R=E.C,E.R; V=E.P['volume']; RD=pd.DataFrame(R)
s5=E.vol(5); s60=E.vol(60); s20=E.vol(20)
def two_stage(sec,n1,asc):
    def f(i,pl):
        c=E.sel_lv(i,pl,n=n1); v=sec[i,c]; ok=~np.isnan(v)
        if ok.sum()<5: return c[:5]
        c,v=c[ok],v[ok]; o=np.argsort(v if asc else -v,kind='stable'); return c[o[:5]]
    return f
up=(R>0).astype(float); up[np.isnan(R)]=np.nan
uv=pd.DataFrame(np.where(up==1,V,0.0)).rolling(20,min_periods=10).sum().values/pd.DataFrame(V).rolling(20,min_periods=10).sum().values
ac=RD.rolling(60,min_periods=40).corr(RD.shift(1)).values
cands={'수축 σ8':(s5/s60,8,True),'저가 σ10':(C,10,True),'UVR하위 σ10':(uv,10,True),'AC하위 σ10':(ac,10,True)}
bA,bO=base.set_index('date').A,base.set_index('date').OO
res={}
for nm,(sec,n1,asc) in cands.items():
    df=E.run(two_stage(sec,n1,asc),start=S).set_index('date')
    j=df.index.intersection(bA.index)
    cand=dict(dA=float((df.A[j]-bA[j]).mean()),dO=float((df.OO[j]-bO[j]).mean()),shA=prof(df.A)['sharpe'],shO=prof(df.OO)['sharpe'],mddO=prof(df.OO)['mdd'])
    res[nm]=dict(cand=cand,n1=n1)
for n1 in sorted(set(v[1] for v in cands.values())):
    rng=np.random.default_rng(11+n1); sims=[]
    for s in range(200):
        df=E.run(lambda i,pl:rng.permutation(E.sel_lv(i,pl,n=n1))[:5],start=S).set_index('date')
        j=df.index.intersection(bA.index)
        sims.append(((df.A[j]-bA[j]).mean(),(df.OO[j]-bO[j]).mean(),prof(df.A)['sharpe'],prof(df.OO)['sharpe'],prof(df.OO)['mdd']))
    sims=np.array(sims)
    print(f'귀무 σ하위{n1}→무작위5: dA {sims[:,0].mean():+.4f} dOO {sims[:,1].mean():+.4f} ShA {sims[:,2].mean():.2f} ShOO {sims[:,3].mean():.2f} MDD_OO {sims[:,4].mean():.1f}',flush=True)
    for nm,v in res.items():
        if v['n1']!=n1: continue
        c=v['cand']
        v['null']=dict(dA=float(sims[:,0].mean()),dO=float(sims[:,1].mean()),shA=float(sims[:,2].mean()),shO=float(sims[:,3].mean()))
        v['p']=dict(dA=float(np.mean(sims[:,0]>=c['dA'])),dO=float(np.mean(sims[:,1]>=c['dO'])),shA=float(np.mean(sims[:,2]>=c['shA'])),shO=float(np.mean(sims[:,3]>=c['shO'])))
        print(f"  {nm}: dA {c['dA']:+.4f}(p={v['p']['dA']:.3f}) dOO {c['dO']:+.4f}(p={v['p']['dO']:.3f}) ShA {c['shA']:.2f}(p={v['p']['shA']:.3f}) ShOO {c['shO']:.2f}(p={v['p']['shO']:.3f})",flush=True)
json.dump(res,open(os.path.join(HERE,'res_null.json'),'w'),default=float,indent=1)
print('DONE')
