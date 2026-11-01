from gB import selB, wB, prox, Hh
from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb')); mlv=pickle.load(open('mlv.pkl','rb'))
o,nh=report('NHM ≥0.95 부족분 현금',selB(0.95,'partial'),weight=wB(0.95),ref=base)
j=nh.merge(base[['date','port']],on='date',suffixes=('','_b'))
for K in (3,6):
    print(f'[{K}분할]',' | '.join(f"MDD {prof(s.port)['mdd']:.1f}/{prof(s.port_b)['mdd']:.1f} Sh {prof(s.port)['sharpe']:.2f}/{prof(s.port_b)['sharpe']:.2f}" for s in (j.iloc[q*len(j)//K:(q+1)*len(j)//K] for q in range(K))))
j['y']=j.date.str[:4]
print('연도별 누적 NHM/mom150/KODEX200 | MDD'); 
for y,s in j.groupby('y'): print(y,f"{prof(s.port)['cum']:+.1f}/{prof(s.port_b)['cum']:+.1f}/{prof(s.bench)['cum']:+.1f} | {prof(s.port)['mdd']:.1f}/{prof(s.port_b)['mdd']:.1f}/{prof(s.bench)['mdd']:.1f}")
# 선정 효과만: 필터 통과 우선, 부족분은 mom150 차순위로 채움(항상 100% 투자)
def fillnext(i):
    s=MOM[150][i]; m=okH[i]&~np.isnan(s); idx=np.where(m)[0]; idx=idx[np.argsort(-s[idx],kind='stable')]
    a=[c for c in idx if prox[i,c]>=0.95][:5]; b=[c for c in idx if c not in a][:5-len(a)]
    return np.array(a+b)
report('NHM 선정효과만(부족분 mom150 차순위, 100% 투자)',fillnext,ref=base)
# R3: 종가 기준 250일 고가, 120일 고가
for L,src in ((250,'close'),(120,'high')):
    X=P['close'] if src=='close' else P['high']
    pr=C/pd.DataFrame(X).rolling(L,min_periods=int(L*.8)).max().values
    def f(i,pr=pr):
        s=MOM[150][i]; m=okH[i]&~np.isnan(s)&(pr[i]>=0.95); idx=np.where(m)[0]; idx=idx[np.argsort(-s[idx],kind='stable')][:5]
        return idx if len(idx) else None
    def w(i,pr=pr):
        s=MOM[150][i]; return min((okH[i]&~np.isnan(s)&(pr[i]>=0.95)).sum(),5)/5
    report(f'R3 {L}일 {src} 고가 기준',f,weight=w,ref=base)
# 결합: MLV 위에 52주 필터
Vs20=E.vol(20)
def comb(i):
    s=MOM[150][i]; m=okH[i]&~np.isnan(s); idx=np.where(m)[0]; idx=idx[np.argsort(-s[idx],kind='stable')][:30]
    idx=idx[prox[i,idx]>=0.95]
    if len(idx)==0: return None
    v=Vs20[i,idx]; return idx[np.argsort(v)[:5]]
def wc(i):
    p=comb(i); return 0 if p is None else len(p)/5
o,_=report('MLV + 52주고가≥0.95 (부족분 현금)',comb,weight=wc,ref=base)
pickle.dump(nh,open('nhm.pkl','wb'))
