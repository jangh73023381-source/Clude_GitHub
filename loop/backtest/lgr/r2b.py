import engine as E, numpy as np, json
P=E.POOL; res={}
def line(name,sel):
    s2=E.stats(sel,'B2'); su=E.stats(sel,'B2','uni'); s1=E.stats(sel,'B1')
    res[name]=dict(B2=s2,vs_uni=su,B1=s1,folds=E.folds(sel))
    print(f"{name:26s} B2 ex {s2['mean']:+.3f}(t{s2['t']:+.1f}) raw {s2['raw']:+.3f} | vs유니 {su['mean']:+.3f} | B1 raw {s1['raw']:+.3f} | fold {E.folds(sel)}")
for kto in (50,100):
    Pk=E.build_pool(k_to=kto); line(f'FLOW_사모_top10_pool{kto}',E.select_topk(E.rSAMO,Pk,10)); line(f'FLOW_연기금_top10_pool{kto}',E.select_topk(E.rPEN,Pk,10)); line(f'POOL{kto}_EW',Pk)
rng=np.random.default_rng(1); pers=[]; daily=[]
for i in range(100):
    sc=np.broadcast_to(rng.random(E.N),(E.T,E.N)); pers.append(E.stats(E.select_topk(sc,P,10),'B2')['mean'])
    sc=rng.random((E.T,E.N)); daily.append(E.stats(E.select_topk(sc,P,10),'B2')['mean'])
res['CTRL']={'persist':dict(mean=float(np.mean(pers)),p95=float(np.percentile(pers,95)),p99=float(np.percentile(pers,99))),'daily':dict(mean=float(np.mean(daily)),p95=float(np.percentile(daily,95)),p99=float(np.percentile(daily,99)))}
print('CTRL',res['CTRL'])
json.dump(res,open('res_gates_b.json','w'),ensure_ascii=False,indent=1)
