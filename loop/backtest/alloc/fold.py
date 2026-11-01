import os,numpy as np,pandas as pd
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
CO={'반도체':'091160','은행':'091170','2차전지':'305720','코스피200':'069500','채권':'332610','금':'411060'}
def prep(cols,tail=None):
    X=cl[[CO[c] for c in cols]].dropna(); X.columns=cols
    R=X.pct_change().dropna()
    return R.tail(tail) if tail else R
def foldstat(R,w,nm,ref):
    r=sum(R[k]*v for k,v in w.items()); rr=sum(R[k]*v for k,v in ref.items())
    out=[]
    for i,(a,b) in enumerate(zip(np.array_split(r,3),np.array_split(rr,3))):
        ea=(1+a).cumprod().iloc[-1]**(252/len(a))-1; eb=(1+b).cumprod().iloc[-1]**(252/len(b))-1
        sa=a.mean()/a.std()*np.sqrt(252); sb=b.mean()/b.std()*np.sqrt(252)
        ma=(1+a).cumprod(); mda=(ma/ma.cummax()-1).min()
        mb=(1+b).cumprod(); mdb=(mb/mb.cummax()-1).min()
        out.append(f"f{i+1}: CAGR {100*ea:+6.1f}%({100*(ea-eb):+5.1f}) Sharpe {sa:4.2f}({sa-sb:+5.2f}) MDD {100*mda:6.1f}%({100*(mda-mdb):+5.1f})")
    print(f"{nm}\n   "+"\n   ".join(out))
REF={'반도체':.5,'은행':.2,'2차전지':.2,'코스피200':.1}
print("=== 7년 · 기준=현행 50/20/20/10 (괄호는 현행 대비 차)")
R=prep(['반도체','은행','2차전지','코스피200','채권'])
foldstat(R,REF,'현행 50/20/20/10',REF)
foldstat(R,{'반도체':.5,'은행':.4,'코스피200':.1},'2차전지→은행 (50/40/0/10)',REF)
foldstat(R,{'반도체':.5,'은행':.3,'채권':.2},'반도체50/은행30/채권20',REF)
foldstat(R,{'반도체':.72},'반도체72%+현금28%',REF)
print("\n=== 금 구간(2021-12~) · 기준=현행")
R2=prep(['반도체','은행','2차전지','코스피200','채권','금'])
foldstat(R2,REF,'현행 50/20/20/10',REF)
foldstat(R2,{'반도체':.5,'은행':.3,'금':.2},'반도체50/은행30/금20',REF)
