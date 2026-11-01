import engine as E, numpy as np, json
P=E.POOL; res={}
def line(name,sel):
    s2=E.stats(sel,'B2'); su=E.stats(sel,'B2','uni'); sb=E.stats(sel,'B2','bench'); s1=E.stats(sel,'B1'); a1=E.stats(sel,'A1')
    cp=E.compound(sel,'B2',0.004,2); cp1=E.compound(sel,'B1',0.004,1)
    gap=(a1['mean']-s1['mean'])/a1['mean'] if a1['mean'] else float('nan')
    res[name]=dict(B2=s2,vs_uni=su,vs_bench=sb,B1=s1,A1=a1,folds=E.folds(sel),yearly=E.yearly(sel),comp2=cp,comp1=cp1,gap=gap)
    print(f"{name:26s} B2 ex {s2['mean']:+.3f}(t{s2['t']:+.1f}) raw {s2['raw']:+.3f} | vs유니 {su['mean']:+.3f} vs벤치 {sb['mean']:+.3f} | 꼬리25% {s2['tail25']} | fold {E.folds(sel)} | 복리2일 {cp} 복리1일 {cp1} | 갭비중 {gap:.2f}")
    print('    yearly',E.yearly(sel))
for nm,sc in (('FLOW_기관',E.rORG),('FLOW_사모',E.rSAMO),('FLOW_연기금',E.rPEN),('FLOW_금융투자',E.rFIN)):
    for k in (5,10,20):
        line(f'{nm}_top{k}',E.select_topk(sc,P,k))
line('POOL_EW',P); line('UNI_EW',E.MEMU)
# 게이트: 지수>MA20
G=E.GATE[:,None]
line('FLOW_사모_top10_gateON',E.select_topk(E.rSAMO,P&G,10)); line('FLOW_사모_top10_gateOFF',E.select_topk(E.rSAMO,P&~G,10))
# 거래대금 풀 크기 고원 (50/100/150)
for kto in (50,100):
    Pk=E.build_pool(k_to=kto); line(f'FLOW_사모_top10_pool{kto}',E.select_topk(E.rSAMO,Pk,10)); line(f'POOL{kto}_EW',Pk)
# 무관신호 대조군: 종목별 고정 무작위(지속형) 500회 & 일별 무작위 500회 — 사모 top10 B2 기준
rng=np.random.default_rng(1); pers=[]; daily=[]
for i in range(300):
    sc=np.broadcast_to(rng.random(E.N),(E.T,E.N)); pers.append(E.stats(E.select_topk(sc,P,10),'B2')['mean'])
    sc=rng.random((E.T,E.N)); daily.append(E.stats(E.select_topk(sc,P,10),'B2')['mean'])
res['CTRL']={'persist':dict(mean=float(np.mean(pers)),p95=float(np.percentile(pers,95)),p99=float(np.percentile(pers,99))),'daily':dict(mean=float(np.mean(daily)),p95=float(np.percentile(daily,95)),p99=float(np.percentile(daily,99)))}
print('CTRL',res['CTRL'])
# 플라시보: 사모 신호를 날짜 내에서 셔플(라벨 순열) 300회
pl=[]
for i in range(300):
    sc=E.rSAMO.copy()
    for t in range(E.T):
        idx=np.where(P[t])[0]
        if len(idx)>1: sc[t,idx]=sc[t,rng.permutation(idx)]
    pl.append(E.stats(E.select_topk(sc,P,10),'B2')['mean'])
res['PLACEBO_samo']=dict(mean=float(np.mean(pl)),p99=float(np.percentile(pl,99)),p=float(np.mean(np.array(pl)>=res['FLOW_사모_top10']['B2']['mean'])))
print('PLACEBO',res['PLACEBO_samo'])
json.dump(res,open('res_gates.json','w'),ensure_ascii=False,indent=1)
