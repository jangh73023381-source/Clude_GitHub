exec(open('bt2.py').read().split('rows=[]')[0])
A,B=20260801,20260922
def cum(r): return ((1+r.fillna(0)).prod()-1)*100
def mdd(r): e=(1+r.fillna(0)).cumprod(); return ((e/e.cummax())-1).min()*100
for code in ['091160','396500','395160','069500']:
    d=P[code]; m=(d.index>=A)&(d.index<=B); bh=d.close.pct_change()[m]
    print(f'\n{codes[code]}  B&H 8~9월 {cum(bh):+.1f}% MDD {mdd(bh):.1f}%  ({m.sum()}거래일)')
    res=[]
    for N,lo,hi,stop in itertools.product([10,20,40,60],[0.1,0.2,0.3],[0.7,0.8,0.9],[None,0.05]):
        # 창 시작 시점에 포지션 없이 시작: 창 이전 데이터는 박스 계산에만 사용
        dd=d.copy(); r,tr,exp=run(dd,N,lo,hi,stop)
        # 창 안에서 시작한 거래만
        tr2=[t for t in tr if d.index[t[0]]>=A]
        rr=pd.Series(0.0,index=d.index)
        c=d.close.values;o=d.open.values
        for a,b,_ in tr2:
            rr.iloc[a]+=c[a]/o[a]-1
            for t in range(a+1,min(b,len(d))): rr.iloc[t]+=c[t]/c[t-1]-1
            if b<len(d): rr.iloc[b]+=o[b]/c[b-1]-1
        res.append((N,lo,hi,stop,cum(rr[m]),mdd(rr[m]),len(tr2),(rr[m]!=0).mean()*100))
    X=pd.DataFrame(res,columns='N lo hi stop cum mdd ntr exp'.split())
    print(f'  72변형: 누적 중앙 {X["cum"].median():+.1f}% · 최고 {X["cum"].max():+.1f}% · 최저 {X["cum"].min():+.1f}% · B&H 이긴 비율 {(X["cum"]>cum(bh)).mean()*100:.0f}% · 거래 0건 변형 {(X.ntr==0).mean()*100:.0f}% · MDD 중앙 {X.mdd.median():.1f}%')
    for N in [10,20,60]:
        r=X[(X.N==N)&(X.lo==.2)&(X.hi==.8)&(X.stop.isna())].iloc[0]
        print(f'  N{N} 0.2/0.8: 누적 {r["cum"]:+.1f}% 거래 {int(r.ntr)} 노출 {r.exp:.0f}%')
# 참고: 8~9월 거래 내역 (TOP10, N20)
d=P['396500'];r,tr,_=run(d,20,.2,.8,None)
print('\nTOP10 N20 0.2/0.8 8~9월 거래:',[(d.index[a],d.index[min(b,len(d)-1)],f'{x*100:+.1f}%') for a,b,x in tr if d.index[a]>=A])
d=P['396500'];r,tr,_=run(d,10,.2,.8,None)
print('TOP10 N10 0.2/0.8 8~9월 거래:',[(d.index[a],d.index[min(b,len(d)-1)],f'{x*100:+.1f}%') for a,b,x in tr if d.index[a]>=A])
