"""우선순위형 R1(인접 임계) + R4(같은 통과율의 무작위 우선 비트 200회) — 5슬롯 CAGR·Sharpe."""
import os,numpy as np,json
HERE=os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE,'eg_slots.py')).read().split("res={}")[0])
b=run(entries()); print(f"base CAGR {b['cagr']:.1f} Sh {b['sh']:.2f}")
out={}
for ax,vs in [('vol',[1.5,1.75,2.0,2.5,3.0]),('body',[0.5,0.75,1.0,1.25,1.5])]:
    for k in vs:
        ex=np.nan_to_num((V>=VA*k) if ax=='vol' else ((C-O)>=k*ATR),nan=0).astype(bool)
        r=run(entries(prio=ex)); rate=ex[base].mean()
        rng=np.random.default_rng(7); sims=[]
        for _ in range(200):
            rb=np.zeros_like(base); rb[base]=rng.random(base.sum())<rate
            sims.append(run(entries(prio=rb)))
        pc=np.mean([s['cagr']>=r['cagr'] for s in sims]); ps=np.mean([s['sh']>=r['sh'] for s in sims])
        out[f'{ax}{k}']=dict(r=r,rate=rate,pc=pc,ps=ps,null_c=np.mean([s['cagr'] for s in sims]),null_s=np.mean([s['sh'] for s in sims]))
        print(f"{ax} {k}: 통과율 {rate:.2f} CAGR {r['cagr']:.1f} Sh {r['sh']:.2f} MDD {r['mdd']:.1f} fold {'/'.join('%+.0f'%x for x in r['f'])} | 무작위우선 CAGR {out[f'{ax}{k}']['null_c']:.1f} Sh {out[f'{ax}{k}']['null_s']:.2f} p_CAGR {pc:.3f} p_Sh {ps:.3f}",flush=True)
json.dump(dict(base=b,grid=out),open(os.path.join(HERE,'res_eg_slots2.json'),'w'),default=float,indent=1)
