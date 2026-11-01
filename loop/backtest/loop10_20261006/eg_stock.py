"""축9 — Rule EG(v1.2 수식) 개별주 패널 적용. 2026-08-31 HTS-BUY 기각 절이 '개별주는 미시도'로 남긴 축.
패널 sjh(3,101종, 2019-01~2026-09-11, 네이버 수정주가) · 유니버스 = PIT 유동종목 MEM(거래대금 5억·1,000원·시총 300억).
비교 기준 B1 = 같은 날 추세전제(C>=MA20 & MA20↑ & C>MA60 & MA60↑5일)만 충족한 MEM 종목. 20거래일 보유."""
import os,json,numpy as np,pandas as pd,warnings; warnings.filterwarnings('ignore')
HERE=os.path.dirname(os.path.abspath(__file__)); S=os.path.join(os.path.dirname(HERE),'sjh')
dates=np.load(S+'/dates.npy'); C=np.load(S+'/C.npy').astype(float); O=np.load(S+'/O.npy').astype(float); V=np.load(S+'/V.npy').astype(float)
H=np.load(HERE+'/_stk_high.npy').astype(float); L=np.load(HERE+'/_stk_low.npy').astype(float); MEM=np.load(S+'/MEM.npy')
bench=np.load(S+'/bench.npy'); T,N=C.shape
for X in (C,O,H,L): X[X<=0]=np.nan
rm=lambda X,w:pd.DataFrame(X).rolling(w,min_periods=w).mean().values
rmin=lambda X,w:pd.DataFrame(X).rolling(w,min_periods=w).min().values
lag=lambda X,k:np.vstack([np.full((k,X.shape[1]),np.nan),X[:-k]])
MA20=rm(C,20); MA60=rm(C,60); VA=rm(V,20); TO20=rm(C*V,20)
trend=(C>=MA20)&(MA20>lag(MA20,1))&(C>MA60)&(MA60>=lag(MA60,5))
pull=rmin(L,10)<=MA20*1.02
cand=(C>=lag(O,1))&(C>O)&(lag(C,1)<lag(O,1))&(C>=L+(H-L)*0.6)
vol=V>=VA*1.3
hz=20
F=np.full_like(C,np.nan); F[:-hz]=C[hz:]/C[:-hz]-1                     # 신호일 종가 진입
FD1=np.full_like(C,np.nan); FD1[:-hz-1]=C[hz+1:]/C[1:-hz]-1            # D+1 종가 진입
FO=np.full_like(C,np.nan); FO[:-hz-1]=C[hz+1:]/O[1:-hz]-1               # D+1 시가 진입
bc=bench[:,1]; bF=np.full(T,np.nan); bF[:-hz]=bc[hz:]/bc[:-hz]-1
valid=np.zeros((T,N),bool); valid[70:T-hz-1]=True
U=MEM&valid&~np.isnan(F)
# 일시 정지·상한가류 이상치 방지: 20일 수익 ±300% 밖 제외
U&=np.abs(F)<3
B1=np.nan_to_num(trend,nan=0).astype(bool)&U
sig=lambda *xs:np.logical_and.reduce([np.nan_to_num(x,nan=0).astype(bool) for x in xs])&B1
EG=sig(pull,cand,vol)
rank=pd.DataFrame(np.where(MEM,TO20,np.nan)).rank(axis=1,ascending=False).values
folds=np.array_split(np.arange(70,T-hz-1),3); rng=np.random.default_rng(11)
def dm(s,R):
    t,i=np.where(s); return pd.DataFrame(dict(t=t,r=R[t,i])).dropna().groupby('t').r.mean()
def ev(name,s,ref=B1,R=F,placebo=True):
    r=R[s]; r=r[~np.isnan(r)]; b=R[ref]; b=b[~np.isnan(b)]
    cd=dm(s,R); bd=dm(ref,R).reindex(cd.index); d=(cd-bd)*100; srt=np.sort(d.values)[::-1]
    f=[]
    for fd in folds:
        sl=slice(fd[0],fd[-1]+1); f.append((np.nanmean(R[sl][s[sl]])-np.nanmean(R[sl][ref[sl]]))*100)
    yrs={}
    for y in range(2019,2027):
        m=(dates//10000==y); 
        if (s[m]).sum()>20: yrs[y]=round((np.nanmean(R[m][s[m]])-np.nanmean(R[m][ref[m]]))*100,2)
    out=dict(name=name,n=len(r),perday=len(r)/len(range(70,T-hz-1)),mean=r.mean()*100,vs=(r.mean()-b.mean())*100,med=np.median(r)*100,
             win=(r>0).mean()*100,f=f,dmean=d.mean(),dmed=np.median(d),drop3=(srt.sum()-srt[:3].sum())/(len(srt)-3),
             drop10=(srt.sum()-srt[:10].sum())/(len(srt)-10),t=d.mean()/(d.std(ddof=1)/len(d)**.5),days=len(d),yrs=yrs)
    if placebo:
        t,i=np.where(s); cnt=pd.Series(t).value_counts()
        tb,ib=np.where(ref); g=pd.DataFrame(dict(t=tb,r=R[tb,ib])).dropna(); G={k:v.r.values for k,v in g.groupby('t')}
        sims=[]
        for _ in range(200):
            tot=k=0
            for tt,c in cnt.items():
                x=G.get(tt); 
                if x is None: continue
                c=min(c,len(x)); tot+=rng.choice(x,c,replace=False).sum(); k+=c
            sims.append(tot/k*100)
        sims=np.array(sims); out['p']=float((sims>=out['mean']).mean()); out['null']=float(sims.mean())
    return out
res=[]
print(f"B1 추세전제: n={B1.sum()} 평균 {np.nanmean(F[B1])*100:+.2f}% 승률 {(F[B1]>0).mean()*100:.1f}%  (MEM 전체 {np.nanmean(F[U])*100:+.2f}%)")
for nm,s in [('EG v1.2 (개별주)',EG),('EG − 거래량 조건',sig(pull,cand)),('EG − 눌림 조건',sig(cand,vol)),('장악형+거래량만(눌림 없음,추세전제)',sig(cand,vol)),
             ('EG ∩ 거래대금 상위300',EG&(rank<=300)),('EG ∩ 거래대금 300위 밖',EG&(rank>300)),
             ('EG 눌림5일(v1.1)',sig(rmin(L,5)<=MA20*1.02,cand,vol)),('EG 거래량 1.5배',sig(pull,cand,V>=VA*1.5)),('EG 거래량 2.0배',sig(pull,cand,V>=VA*2.0)),
             ('EG 종가위치 0.5',sig(pull,(C>=lag(O,1))&(C>O)&(lag(C,1)<lag(O,1))&(C>=L+(H-L)*0.5),vol)),('EG 종가위치 0.7',sig(pull,(C>=lag(O,1))&(C>O)&(lag(C,1)<lag(O,1))&(C>=L+(H-L)*0.7),vol))]:
    o=ev(nm,s); res.append(o)
    print(f"{nm:28s} n{o['n']:6d} {o['perday']:.1f}/일 평균{o['mean']:+.2f} vsB1{o['vs']:+.2f} 중앙{o['med']:+.2f} 승{o['win']:.1f} fold[{', '.join('%+.2f'%x for x in o['f'])}] 일차 평균{o['dmean']:+.2f} t{o['t']:+.2f} 중앙{o['dmed']:+.2f} -3일{o['drop3']:+.2f} -10일{o['drop10']:+.2f} R4 p={o['p']:.3f}(귀무{o['null']:+.2f})",flush=True)
print('연도별 EG−B1(%p):',res[0]['yrs'])
for nm,R in [('D+1 종가 진입',FD1),('D+1 시가 진입',FO)]:
    o=ev('EG '+nm,EG,R=R,placebo=False); res.append(o)
    print(f"EG {nm}: 평균{o['mean']:+.2f} vsB1{o['vs']:+.2f} fold[{', '.join('%+.2f'%x for x in o['f'])}] -3일{o['drop3']:+.2f}")
json.dump(res,open(HERE+'/res_eg_stock.json','w'),default=float,indent=1,ensure_ascii=False)
