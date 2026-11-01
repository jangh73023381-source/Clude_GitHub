import json, pickle, statistics, math
from bt_attn import *
px,names=load_px()
cc=pickle.load(open('_cache.pkl','rb')); dates=cc['dates']
ser,cols=load_search('sector_search.csv')

# 섹터 일별 등가중 수익률 (전체 유니버스 기준, pool 무관)
sec_ret={}
for i,d in enumerate(dates[1:],1):
    p=dates[i-1]; agg={}
    for c in px:
        nm=names.get(c,'')
        if not eligible(nm): continue
        a,b=px[c].get(p),px[c].get(d)
        if not (a and b): continue
        s=sm.sector(nm)
        agg.setdefault(s,[]).append((b/a-1)*100)
    sec_ret[d]={s:sum(v)/len(v) for s,v in agg.items() if len(v)>=2}

sc=attn_scores(ser,5,60)
def corr(x,y):
    n=len(x); mx,my=sum(x)/n,sum(y)/n
    sx=math.sqrt(sum((a-mx)**2 for a in x)); sy=math.sqrt(sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/(sx*sy) if sx and sy else 0.0

print("■ 관심도-수익률 리드래그 (풀링, k>0 = 관심도가 수익률보다 k거래일 뒤)")
print(f"{'k':>4}{'상관':>10}{'n':>8}")
di={d:i for i,d in enumerate(dates)}
for k in range(-5,6):
    X,Y=[],[]
    for d,rets in sec_ret.items():
        i=di[d]; j=i+k
        if j<0 or j>=len(dates): continue
        dk=dates[j]
        for s,r in rets.items():
            if s not in sc: continue
            a=a_of(sc,s,dk)
            X.append(a); Y.append(r)
    print(f"{k:>4}{corr(X,Y):>10.4f}{len(X):>8}")

print("\n■ 관심도 5분위별 익일 섹터 수익률 (%)  ← 선정에 쓸 수 있는 형태")
rows=[]
for d,rets in sec_ret.items():
    for s,r in rets.items():
        if s in sc: rows.append((a_of(sc,s,d), r))   # a_of 는 D-1 값 → 익일(D) 수익률
rows.sort()
n=len(rows); q=n//5
for i in range(5):
    seg=rows[i*q:(i+1)*q if i<4 else n]
    print(f"  Q{i+1} (관심 {seg[0][0]:+.3f}~{seg[-1][0]:+.3f})  익일 평균 {statistics.mean([x[1] for x in seg]):+.4f}%  n={len(seg)}")
