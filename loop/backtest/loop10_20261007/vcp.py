"""축6 변동성 수축 심화: R1(n1 6~12) · R3(σ5/σ20, σ10/σ60, ATR5/ATR60) · R2 fold · R5."""
from common import *
E,base=setup(); res={}; C=E.C
H,L=E.P['high'],E.P['low']; pc=lag(pd.DataFrame(C).ffill().values,1)
tr=np.nanmax(np.stack([H-L,np.abs(H-pc),np.abs(L-pc)]),axis=0)/C*100
atr=lambda k:pd.DataFrame(tr).rolling(k,min_periods=max(3,k//2)).mean().values
def two_stage(sec,n1):
    def f(i,pl):
        c=E.sel_lv(i,pl,n=n1); v=sec[i,c]; ok=~np.isnan(v)
        if ok.sum()<5: return c[:5]
        c,v=c[ok],v[ok]; return c[np.argsort(v,kind='stable')[:5]]
    return f
defs={'σ5/σ60':E.vol(5)/E.vol(60),'σ5/σ20':E.vol(5)/E.vol(20),'σ10/σ60':E.vol(10)/E.vol(60),'ATR5/ATR60':atr(5)/atr(60)}
for dn,M in defs.items():
    for n1 in ((6,7,8,9,10,12) if dn=='σ5/σ60' else (7,8,10)):
        comp(base,f'수축 {dn} σ하위{n1}',E.run(two_stage(M,n1),start=S),res)
json.dump(res,open(os.path.join(HERE,'res_vcp.json'),'w'),default=float,indent=1); print('DONE')
