from engine import *
P,dates,codes,names=load(); E=Engine(P,dates,codes,names)
C,O=E.C,E.O
prevC=np.vstack([np.full((1,E.N),np.nan),C[:-1]])
valid=~np.isnan(O)&~np.isnan(prevC)
eq=(np.abs(O/prevC-1)<1e-9)&valid
print('open결측비율',np.isnan(O[~np.isnan(C)]).mean(),' open==전일종가 비율',eq.sum()/valid.sum())
H,L=P['high'],P['low']
bad=((O>H*1.0001)|(O<L*0.9999))&valid
print('open이 고저 범위 밖',bad.sum()/valid.sum())
# 연도별 open 결측
yrs=np.array([d[:4] for d in dates])
for y in sorted(set(yrs)):
    m=yrs==y; cc=~np.isnan(C[m]); print(y, 'open결측', round(np.isnan(O[m][cc]).mean(),4), 'eq', round(eq[m].sum()/max(valid[m].sum(),1),4))
