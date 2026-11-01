from rules import *
import json
P,dates,codes,names=load(os.path.join(BT,'panel_ohlc_2y.csv')); E=Engine(P,dates,codes,names)
valid=[i for i in range(260,E.T-1) if not np.isnan(E.fA[i,E.bi])]
idx=valid[-60:]
print('60일 창',dates[idx[0]],'~',dates[idx[-1]],'(보유 종료',dates[idx[-1]+1],')',len(idx))
RL=build(E); out={}; base=run(E,RL['LV(기준)'],idx)
for nm,f in RL.items():
    df=run(E,f,idx); m=base.merge(df,on='date',suffixes=('_b',''))
    d=(m.A-m.A_b).values; dO=(m.OO-m.OO_b).values
    pa=prof(df.A); rr=r5(d)
    o=dict(n=len(df),cumA=pa['cum'],mddA=pa['mdd'],shA=pa['sharpe'],meanA=pa['mean'],
           cumOO=prof(df.OO.dropna())['cum'],hit=float(df.hit.mean()),full5=int((df.hit==5).sum()),
           dA=float(np.mean(d)),tA=float(tstat(d)) if np.std(d)>0 else 0.0,fA=[float(x) for x in folds(d)],drop3=float(rr['drop3']),med=float(rr['median']),
           dOO=float(np.nanmean(dO)),winA=float(np.mean(d>0)),bench_cum=prof(df.bA)['cum'],picks_last=[names[codes[c]] for c in ([] if isinstance(f(idx[-1],E.pool(idx[-1])),str) else f(idx[-1],E.pool(idx[-1])))])
    out[nm]=o
    print(f"{nm:34s} 누적A {o['cumA']:+6.1f}% MDD{o['mddA']:6.1f} Sh{o['shA']:5.2f} | 적중 {o['hit']:.2f}/5 (5/5 {o['full5']}일) | LV대비 A {o['dA']:+.3f}%p t{o['tA']:+.2f} f[{', '.join('%+.2f'%x for x in o['fA'])}] -3일{o['drop3']:+.3f} 승률{o['winA']*100:.0f}% | OO {o['dOO']:+.3f} 누적OO {o['cumOO']:+.1f}",flush=True)
print('KODEX200 누적',round(out['LV(기준)']['bench_cum'],1))
json.dump(dict(window=[dates[idx[0]],dates[idx[-1]]],res=out),open(os.path.join(HERE,'res60.json'),'w'),default=float,ensure_ascii=False,indent=1)
