import sys, numpy as np, pandas as pd
src=open('live.py').read().split("out=[]; dropped=0")[0]
exec(src)  # D, k, B(bench stitched), names, asof
SK='/tmp/claude-0/ext/claude-trading-skills/skills/'
sys.path.insert(0,SK+'stockbee-momentum-burst-screener/scripts'); import screen_momentum_burst as MB
sys.path.insert(0,SK+'stockbee-exhaustion-hammer-screener/scripts'); import screen_exhaustion_hammer as EH
sys.argv=['x','--min-price','1000','--min-volume','0','--dollar-threshold','1e15','--nine-million-volume','1000000000000000']; amb=MB.parse_arguments()
sys.argv=['x','--min-price','1000','--min-volume','0','--min-avg-dollar-volume','1e9','--min-market-cap','0']; aeh=EH.parse_arguments()
[sys.modules.pop(m) for m in list(sys.modules) if m=='scorer' or m.startswith('calculators')]
sys.path[:]=[p for p in sys.path if 'vcp-screener' not in p]; sys.path.insert(0,SK+'canslim-screener/scripts')
from calculators.new_highs_calculator import calculate_newness
from calculators.supply_demand_calculator import calculate_supply_demand
from calculators.leadership_calculator import calculate_leadership
from calculators.market_calculator import calculate_market_direction
from scorer import calculate_composite_score_phase3, check_minimum_thresholds_phase3
import importlib.util
spec=importlib.util.spec_from_file_location('cb','canslim_bt.py')
fsrc=open('canslim_bt.py').read(); ns={}
exec(fsrc.split("def hist")[0].split("ST, SH, NS")[0],ns)  # imports
f=pd.read_csv('/mnt/user-data/uploads/loop/backtest/sjh/fund.csv',dtype={'code':str})
ns['q']={c:g.sort_values('avail') for c,g in f.groupby('code')}; ns['ann']={c:g[g.reprt==11011].sort_values('year') for c,g in f.groupby('code')}
exec("def c_score"+fsrc.split("def c_score")[1].split("def hist")[0],ns)
pit=pd.read_csv('/mnt/user-data/uploads/loop/backtest/_krx_pit.csv',dtype={'code':str}).drop_duplicates('code',keep='last').set_index('code').name
bh=[{"date":str(B[0][i]),"close":float(B[4][i])} for i in range(len(B[0])-1,len(B[0])-261,-1)]
mscore=calculate_market_direction({"price":float(B[4][-1])},bh)["score"]
ov=k[(k.date>=20260812)&(k.date<=20260911)]; ovm={c:g for c,g in ov.groupby('code')}; kk={c:g for c,g in k[k.date>20260911].groupby('code')}
R={'mb':[],'eh':[],'cs':[]}
for code,(d,o,h,l,c,v) in D.items():
    if code=='069500' or code not in kk or int(d[-1])!=20260911: continue
    m=dict(zip(d.astype(int),c)); g=ovm.get(code)
    if g is None or not all(abs(m.get(int(r.date),np.nan)/r.close-1)<0.001 for r in g.itertuples()): continue
    g2=kk[code].sort_values('date')
    if (g2.chg_pct.abs()>30).any(): continue
    A=[np.concatenate([x,g2[col].values]) for x,col in zip((d,o,h,l,c,v),('date','open','high','low','close','volume'))]
    d2,o2,h2,l2,c2,v2=A; e=len(d2)-1
    if int(d2[-1])!=asof or c2[e]<1000 or (c2[e-19:e+1]*v2[e-19:e+1]).mean()<1e9: continue
    nm=pit.get(code,code)
    bars=lambda M,n:[M.Bar(date=str(d2[i]),open=o2[i],high=h2[i],low=l2[i],close=c2[i],volume=int(v2[i])) for i in range(e,e-n,-1)]
    r=MB.analyze_symbol(code,bars(MB,80),amb)
    if r['state']!='REJECTED': R['mb'].append((code,nm,c2[e],r['setup_score'],r['state'],r['day_gain_pct'],r['stop_reference']))
    r=EH.analyze_symbol(code,bars(EH,120),aeh)
    if r['state']!='REJECTED': R['eh'].append((code,nm,c2[e],r['setup_score'],r['state']))
    cs_=ns['c_score'](code,asof)
    if cs_ is None: continue
    hs=[{"date":str(d2[i]),"close":c2[i],"volume":v2[i],"high":h2[i],"low":l2[i],"open":o2[i]} for i in range(e,e-260,-1)]
    quote={"price":c2[e],"yearHigh":h2[e-251:e+1].max(),"yearLow":l2[e-251:e+1].min(),"volume":v2[e],"avgVolume":v2[e-50:e].mean()}
    sc=[cs_,ns['a_score'](code,asof),calculate_newness(quote)["score"],calculate_supply_demand({"historical":hs[:90]})["score"],calculate_leadership(hs,bh,rs_benchmark="KOSPI")["score"],50,mscore]
    R['cs'].append((code,nm,c2[e],calculate_composite_score_phase3(*sc)["composite_score"],int(check_minimum_thresholds_phase3(*sc)["passes_all"]),*sc[:5]))
mb=pd.DataFrame(R['mb'],columns='code name close score state gain stop'.split()).sort_values('score',ascending=False)
eh=pd.DataFrame(R['eh'],columns='code name close score state'.split()).sort_values('score',ascending=False)
cs=pd.DataFrame(R['cs'],columns='code name close comp pass C A N S L'.split()).sort_values(['pass','comp'],ascending=False)
print('asof',asof,'M(시장)',mscore)
print('MB A-이상',(mb.score>=80).sum()); print(mb.head(10).round(1).to_string(index=False))
print('EH A-이상',(eh.score>=80).sum()); print(eh.head(5).to_string(index=False))
print('CANSLIM 통과',cs['pass'].sum()); print(cs.head(15).round(1).to_string(index=False))
with pd.ExcelWriter('/mnt/user-data/outputs/vcp_skill/GitHub스킬_후보_20261015.xlsx') as w:
    cs.to_excel(w,sheet_name='CANSLIM',index=False); mb.to_excel(w,sheet_name='MomentumBurst',index=False); eh.to_excel(w,sheet_name='ExhaustionHammer',index=False)
    pd.read_csv('live_vcp.csv',dtype={'code':str}).to_excel(w,sheet_name='VCP',index=False)
