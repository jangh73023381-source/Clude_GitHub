from engine import *
P,dates,codes,names=load(); E=Engine(P,dates,codes,names)
C,O,V=E.C,E.O,P['volume']
for nm,sel in (('MOM',E.sel_mom),('LV',E.sel_lv)):
    tot=eqn=0; stale_gap=[]
    for i in range(20,E.T-2):
        pl=E.pool(i)
        if len(pl)<5: continue
        pk=sel(i,pl)
        o1=O[i+1,pk]; c0=C[i,pk]
        e=np.abs(o1/c0-1)<1e-9
        tot+=len(pk); eqn+=e.sum()
    print(nm,'익일시가==전일종가 비율',eqn/tot)
# 벤치
e=np.abs(O[1:,E.bi]/C[:-1,E.bi]-1)<1e-9; print('bench',e.mean())
