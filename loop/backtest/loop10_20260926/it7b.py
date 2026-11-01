from ev import *
dates=E.dates; ym=[d[:6] for d in dates]
last=[j for j in range(len(dates)-1) if ym[j+1]!=ym[j]]
off={}
for j in last:
    for k in range(-4,4):
        if 0<=j+k<len(dates): off[dates[j+k]]=k
for nm in ('MOM','LV'):
    df=BASE[nm].copy(); df['nxt']=[dates[i+1] for i in df.i]; df['k']=df.nxt.map(off)
    e=df.A-df.bA
    g=pd.DataFrame({'k':df.k,'e':e,'p':df.A,'b':df.bA}).groupby('k').agg(n=('e','size'),ex=('e','mean'),p=('p','mean'),b=('b','mean'))
    print(nm); print(g.round(3))
# 연도별 T-1 효과
df=BASE['MOM'].copy(); df['nxt']=[dates[i+1] for i in df.i]; df['k']=df.nxt.map(off); df['y']=df.nxt.str[:4]; df['e']=df.A-df.bA
print(df[df.k==-1].groupby('y').e.agg(['size','mean']).round(3))
print(df[df.k==-1].groupby(df.nxt.str[4:6]).e.agg(['size','mean']).round(3))
