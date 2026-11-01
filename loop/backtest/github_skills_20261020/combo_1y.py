import numpy as np, pandas as pd, pickle, itertools
src=open('combo_run.py').read().split("rows = []; raw = {}")[0]
exec(src)
from gh_stats import nw_se
last=T-HZ-1; first=last-244   # 최근 245거래일 신호일(매일 시작)
print('1년 구간', dates[first], '~', dates[last])
allt=list(range(first,last+1))
def st(o):
    ts=[t for t in allt if t in o]; x=np.array([o[t][0] for t in ts]); k=np.array([o[t][1] for t in ts])
    if len(x)<60: return {}
    n=len(x); k3=n//3; sr=np.sort(x)[::-1]
    return dict(n=n, 초과=x.mean(), t=x.mean()/nw_se(x,19), 중앙=np.median(x), f1=x[:k3].mean(), f2=x[k3:2*k3].mean(), f3=x[2*k3:].mean(),
                상위5pct제거=sr[int(n*.05):].mean(), KODEX대비=k.mean(), KODEX_t=k.mean()/nw_se(k,19), 종목수=np.mean([o[t][2] for t in ts]))
rows=[]
combos=[(k,) for k in names]+list(itertools.combinations(names,2))+list(itertools.combinations(names,3))
for cb in combos:
    for m in (('RA',) if len(cb)==1 else ('RA','AND')):
        rows.append(dict(조합=' + '.join(cb),k=len(cb),방법=m,**st(evaluate(cb,m))))
r=pd.DataFrame(rows); r.to_csv('combo_1y.csv',index=False)
print('done',len(r))
