import engine as E, numpy as np, json
res={}
def run(name,sel,keys=('A1','B1','B2','B5','B20')):
    res[name]={k:E.stats(sel,k) for k in keys}
    res[name]['vs_uni_B2']=E.stats(sel,'B2','uni'); res[name]['vs_bench_B2']=E.stats(sel,'B2','bench')
    res[name]['size']=float(sel.sum(1).mean())
    s=res[name]; print(f"{name:28s} n={s['B2'].get('n',0):4d} | A1 {s['A1'].get('mean',0):+.3f} | B1 {s['B1'].get('mean',0):+.3f}(t{s['B1'].get('t',0):+.1f}) | B2 {s['B2'].get('mean',0):+.3f}(t{s['B2'].get('t',0):+.1f}, med {s['B2'].get('med',0):+.3f}, win {s['B2'].get('win',0):.2f}) | B5 {s['B5'].get('mean',0):+.3f} | B20 {s['B20'].get('mean',0):+.3f} | raw B2 {s['B2'].get('raw',0):+.3f}")
P=E.POOL; k=10
print('== 풀 자체 (vs 유니버스EW / 벤치) B1/B2/B5/B20 raw %:',[round(float(np.nanmean(E.POOL_EW[x]))*100,3) for x in ('B1','B2','B5','B20')],'uni',[round(float(np.nanmean(E.UNI_EW[x]))*100,3) for x in ('B1','B2','B5','B20')])
# 축 1: 시총대비 순매수 강도 (주체별) top10
for nm,sc in (('FLOW_기관',E.rORG),('FLOW_사모',E.rSAMO),('FLOW_연기금',E.rPEN),('FLOW_투신',E.rINV),('FLOW_금융투자',E.rFIN),('FLOW_메이저3',E.rMAJ),('FLOW_외국인',E.rFRG),('FLOW_개인',E.rIND)):
    run(nm+'_top10',E.select_topk(sc,P,k))
# 반대편: 기관 순매도 강한 것
run('FLOW_기관_bottom10',E.select_topk(E.rORG,P,k,lowest=True))
# 축 2: 빈집 (누적 낮음) / 반대(차있음)
for nm,sc in (('EMPTY_cum5',E.CUM5),('EMPTY_cum20',E.CUM20),('EMPTY_cum60',E.CUM60),('EMPTY_osc',E.OSC),('EMPTY_cum20메이저',E.CUM20_MAJ),('EMPTY_cum20외인',E.CUM20_FRG)):
    run(nm+'_low10',E.select_topk(sc,P,k,lowest=True))
    run(nm+'_high10',E.select_topk(sc,P,k))
# 축 3: 결합 — 기관 순매수>0 & 누적 풀 중앙값 이하 → 기관 강도순
def combo(cum,flow=E.rORG):
    med=np.nanmedian(np.where(P,cum,np.nan),axis=1)
    m=P&(flow>0)&(cum<=med[:,None]); return m
for nm,cum in (('COMBO_cum20',E.CUM20),('COMBO_cum60',E.CUM60),('COMBO_osc',E.OSC)):
    m=combo(cum); run(nm+'_top10',E.select_topk(E.rORG,m,k)); run(nm+'_EW',m)
# 반대 결합: 기관 매수 & 이미 차있음
med=np.nanmedian(np.where(P,E.CUM20,np.nan),axis=1); m=P&(E.rORG>0)&(E.CUM20>med[:,None]); run('COMBO_rev_full_top10',E.select_topk(E.rORG,m,k))
# 축 4: 급등 제외(등락률 상위 10 제외 / 10%↑ 제외)
R=E.R1; rk=E.select_topk(R,P,10); P2=P&~rk; run('POOL_no급등10',P2); run('FLOW_기관_top10_no급등',E.select_topk(E.rORG,P2,k))
P3=P&(R<0.10); run('FLOW_기관_top10_ret<10%',E.select_topk(E.rORG,P3,k))
# 상승 필터 제거(거래대금 top150 전체)
PA=E.build_pool(rising=False); run('POOLall150_EW',PA); run('FLOW_기관_top10_all150',E.select_topk(E.rORG,PA,k))
# 하락 종목만
PD=PA&~P; run('POOL_down_EW',PD); run('FLOW_기관_top10_down',E.select_topk(E.rORG,PD,k))
# 대조군: 풀 내 무작위 10 (200회) — B2
rng=np.random.default_rng(0); vals=[]
for i in range(200):
    sc=rng.random((E.T,E.N)); vals.append(E.stats(E.select_topk(sc,P,k),'B2')['mean'])
res['RANDOM10']={'mean':float(np.mean(vals)),'p95':float(np.percentile(vals,95)),'p99':float(np.percentile(vals,99)),'sd':float(np.std(vals))}
print('RANDOM10 B2', res['RANDOM10'])
json.dump(res,open('res_axes.json','w'),ensure_ascii=False,indent=1)
