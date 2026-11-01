import sys; sys.path.insert(0,'/sessions/exciting-sharp-albattani/mnt/loop/backtest')
from bt_engine import load, score, is_spot
import statistics as st
px,name,dates=load()
def ret(c,d,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None
def sel(d,k,n=5):
    s=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<10000 or not is_spot(name[c]): continue
        m=ret(c,d,k)
        if m is not None: s.append((c,m))
    s.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in s[:n]]
def dist(k):
    H=[];E=[];P=[]
    pair_w=pair_l=0
    for i in range(20,len(dates)-1):
        d,dn=dates[i],dates[i+1]
        p=sel(d,k); 
        if len(p)<5: continue
        s=score(px,name,d,dn,p)
        if not s or s['avg_excess'] is None: continue
        H.append(s['hit']);E.append(s['avg_excess']*100);P.append(s['avg_pct'])
        # paired vs mom5
        p5=sel(d,5); s5=score(px,name,d,dn,p5)
        if s5 and s5['hit'] is not None:
            if s['hit']>s5['hit']: pair_w+=1
            elif s['hit']<s5['hit']: pair_l+=1
    n=len(H)
    print(f"mom{k}: {n}일 평균적중 {st.mean(H):.2f}/5  ≥1 {sum(h>=1 for h in H)/n*100:.0f}%  ≥3 {sum(h>=3 for h in H)/n*100:.0f}%  5/5 {sum(h==5 for h in H)/n*100:.1f}%  평균백분위 {st.mean(P):.1f}  초과 {st.mean(E):+.2f}%")
    if k!=5: print(f"     vs mom5 일대일: mom{k} 우세 {pair_w}일 / 열세 {pair_l}일")
dist(5); dist(20)
# 무작위 기준
print("무작위 기대: 평균적중 0.50/5(10%×5), 평균백분위 50, 초과 0")
