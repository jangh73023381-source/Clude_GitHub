from common import *
E,base=setup(); res=json.load(open(os.path.join(HERE,'res_vcp.json'))); out={}
bO=base.set_index('date').OO; bA=base.set_index('date').A
for n1 in (7,8):
    rng=np.random.default_rng(100+n1); sims=[]
    for s in range(200):
        df=E.run(lambda i,pl:rng.permutation(E.sel_lv(i,pl,n=n1))[:5],start=S).set_index('date'); j=df.index.intersection(bO.index)
        sims.append(((df.OO[j]-bO[j]).mean(),prof(df.OO)['sharpe'],(df.A[j]-bA[j]).mean(),prof(df.A)['sharpe'],np.mean(folds((df.OO[j]-bO[j]).values)[2])))
    sims=np.array(sims)
    print(f'귀무 σ하위{n1}: dOO {sims[:,0].mean():+.4f} ShOO {sims[:,1].mean():.2f} dA {sims[:,2].mean():+.4f} fold3 dOO {sims[:,4].mean():+.4f}')
    for k,v in res.items():
        if not k.endswith(f'σ하위{n1}'): continue
        o,a=v['OO'],v['A']
        p=dict(dO=float(np.mean(sims[:,0]>=o['diff'])),shO=float(np.mean(sims[:,1]>=o['sh'])),dA=float(np.mean(sims[:,2]>=a['diff'])),shA=float(np.mean(sims[:,3]>=a['sh'])))
        out[k]=p; print(f"  {k}: dOO p={p['dO']:.3f} ShOO p={p['shO']:.3f} dA p={p['dA']:.3f} ShA p={p['shA']:.3f}",flush=True)
json.dump(out,open(os.path.join(HERE,'res_vcp_null.json'),'w'),indent=1); print('DONE')
