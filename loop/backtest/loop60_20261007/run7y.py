from rules import *
import json
r60=json.load(open(os.path.join(HERE,'res60.json')))['res']
P,dates,codes,names=load(os.path.join(BT,'panel_ohlc_long.csv')); E=Engine(P,dates,codes,names)
idx=[i for i in range(260,E.T-1) if not np.isnan(E.fA[i,E.bi])]
RL=build(E); out={}; base=run(E,RL['LV(기준)'],idx)
print('7년',dates[idx[0]],'~',dates[idx[-1]],len(idx),flush=True)
for nm,f in RL.items():
    if nm.startswith('LV'): 
        out[nm]=dict(cagr=prof(base.A)['cagr'],mdd=prof(base.A)['mdd'],sh=prof(base.A)['sharpe'],hit=float(base.hit.mean())); continue
    df=run(E,f,idx); m=base.merge(df,on='date',suffixes=('_b','')); d=(m.A-m.A_b).values
    roll=pd.Series(d).rolling(60).mean().dropna().values
    edge60=r60[nm]['dA']
    pa=prof(df.A); rr=r5(d)
    o=dict(cagr=pa['cagr'],mdd=pa['mdd'],sh=pa['sharpe'],hit=float(df.hit.mean()),dA=float(d.mean()),tA=float(tstat(d)),f=[float(x) for x in folds(d)],drop3=float(rr['drop3']),
           win60=float(np.mean(roll>0)),pct_recent=float(np.mean(roll<edge60)),edge60=edge60,q=[float(x) for x in np.quantile(roll,[.1,.5,.9])])
    out[nm]=o
    print(f"{nm:34s} 7년 CAGR{o['cagr']:+6.1f} MDD{o['mdd']:6.1f} Sh{o['sh']:5.2f} 적중{o['hit']:.2f} | LV대비 {o['dA']:+.4f} t{o['tA']:+.2f} f[{', '.join('%+.3f'%x for x in o['f'])}] -3일{o['drop3']:+.4f} | 60일창 승률 {o['win60']*100:.0f}% · 이번60일 {edge60:+.3f} = 역사 {o['pct_recent']*100:.0f}%ile (10/50/90: {o['q'][0]:+.3f}/{o['q'][1]:+.3f}/{o['q'][2]:+.3f})",flush=True)
b=out['LV(기준)']; print(f"LV 7년 CAGR{b['cagr']:+.1f} MDD{b['mdd']:.1f} Sh{b['sh']:.2f} 적중{b['hit']:.2f}")
json.dump(out,open(os.path.join(HERE,'res7y.json'),'w'),default=float,ensure_ascii=False,indent=1); print('DONE')
