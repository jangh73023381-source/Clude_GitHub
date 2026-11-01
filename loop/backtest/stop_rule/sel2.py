import os,sys,numpy as np,pandas as pd
sys.path.insert(0,os.environ['HOME']+'/mnt/loop/references/scripts')
from universe_filters import eligible
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
df=df[df['name'].map(eligible)]
cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
dates=cl.index.to_numpy(); C=cl.to_numpy(float)
bi=list(cl.columns).index('069500'); ben=C[:,bi]
def mom(k): return C/np.roll(C,k,axis=0)-1
M={20:mom(20),60:mom(60),150:mom(150)}
SIG=pd.DataFrame(C).pct_change().rolling(20).std().to_numpy()
def run(H,rank,lowvol=False,k=5,pool=30):
    out=[];bs=[];ds=[]
    for i in range(200,len(dates)-H):
        row=rank[i]; ok=np.isfinite(row)&np.isfinite(C[i])&np.isfinite(C[i+H])
        idx=np.where(ok)[0]
        if len(idx)<20: continue
        order=idx[np.argsort(-row[idx])]
        if lowvol:
            p=order[:pool]; p=p[np.isfinite(SIG[i][p])]; p=p[np.argsort(SIG[i][p])][:k]
        else: p=order[:k]
        r=float(np.mean(C[i+H][p]/C[i][p]-1)); b=ben[i+H]/ben[i]-1
        out.append(r); bs.append(b); ds.append(r-b)
    return np.array(out),np.array(bs),np.array(ds)
print("겹치는 구간 전부(시작일 매일) — 평균은 불편, t값은 겹침 때문에 쓰지 않음")
for H in [5,10,20,40]:
    print(f"--- 보유 {H}거래일")
    for nm,kw in [('mom20 상위5',dict(rank=M[20])),('mom150 상위5',dict(rank=M[150])),
                  ('mom20→저변동5 (현행 LV)',dict(rank=M[20],lowvol=True)),
                  ('mom150→저변동5',dict(rank=M[150],lowvol=True))]:
        r,b,d=run(H,**kw)
        f=np.array_split(d,3); folds='/'.join(f"{100*x.mean():+.2f}" for x in f)
        print(f"  {nm:22s} n={len(r):5d} 평균 {100*r.mean():+6.3f}%  벤치 {100*b.mean():+6.3f}%  초과 {100*d.mean():+6.3f}%p  이김 {100*(d>0).mean():4.1f}%  3분할 {folds}")
