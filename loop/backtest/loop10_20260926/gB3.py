from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb')); nh=pickle.load(open('nhm.pkl','rb'))
j=nh.merge(base[['date','port']],on='date',suffixes=('','_b')); d=(j.port-j.port_b).values
for k in (3,5,10,20):
    x=j.port.values.copy(); idx=np.argsort(-d)[:k]; x[idx]=j.port_b.values[idx]
    print(f'R5 상위{k}일 기준 대체 → MDD {prof(x)["mdd"]:.1f} Sh {prof(x)["sharpe"]:.2f} CAGR {prof(x)["cagr"]:.1f} (기준 {prof(j.port_b)["mdd"]:.1f}/{prof(j.port_b)["sharpe"]:.2f}/{prof(j.port_b)["cagr"]:.1f})')
from gB import selB
f=selB(0.95,'partial'); inv=np.mean([0 if f(i) is None else len(f(i))/5 for i in range(START,T-1)])
print('평균 투자비중 %.2f'%inv)
i=T-1; p=f(i); print('최신일',dates[i],'NHM 픽:',[] if p is None else [names[codes[c]] for c in p])
