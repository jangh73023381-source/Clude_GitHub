"""매수 수식 보완 후보 검정 — 현행 EG 9조건에 한 축씩 추가/변경. 신호 단위 20일 수익(진입=신호일 종가)."""
import os,pickle,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
O,H,L,C,V,MA20,MA60,VA,AMT,trend,eg0,B,dates=[d[k] for k in ['O','H','L','C','V','MA20','MA60','VA','AMT','trend','eg','bench','dates']]
M,N=C.shape; Cf=pd.DataFrame(C.T).ffill().values.T
def sh(x,k):
    y=np.full_like(x,np.nan); y[:,k:]=x[:,:-k]; return y
def rm(x,w): return pd.DataFrame(x.T).rolling(w,min_periods=w).mean().values.T
def rmax(x,w): return pd.DataFrame(x.T).rolling(w,min_periods=w).max().values.T
def rmin(x,w): return pd.DataFrame(x.T).rolling(w,min_periods=w).min().values.T
TR=np.maximum(H-L,np.maximum(abs(H-sh(C,1)),abs(L-sh(C,1)))); ATR=rm(TR,14)
MA120=rm(C,120); H250=rmax(H,250); H60=rmax(H,60)
Bf=pd.Series(B).ffill().values; Bm60=pd.Series(Bf).rolling(60).mean().values; Bm20=pd.Series(Bf).rolling(20).mean().values
R20=C/sh(C,20)-1; BR20=(Bf/np.roll(Bf,20)-1)[None,:]
base_trend=(C>=MA20)&(MA20>sh(MA20,1))&(C>MA60)&(MA60>=sh(MA60,5))
pull=(rmin(L,5)<=MA20*1.02)
cand=(C>=sh(O,1))&(C>O)&(sh(C,1)<sh(O,1))&(C>=L+(H-L)*0.6)
vol=(V>=VA*1.3)
def sig(t=base_trend,p=pull,c=cand,v=vol,extra=None):
    s=t&p&c&v
    if extra is not None: s=s&extra
    return np.nan_to_num(s,nan=False).astype(bool)
ret20=np.full((M,N),np.nan); ret20[:,:-20]=Cf[:,20:]/Cf[:,:-20]-1
valid=np.zeros((M,N),bool); valid[:,60:N-21]=True
rng=np.random.default_rng(0)
b1=np.nan_to_num(trend&~eg0&valid,nan=False); b1i=np.where(b1); pick=rng.choice(len(b1i[0]),15000,replace=False)
B1=ret20[b1i[0][pick],b1i[1][pick]]; b1mean=np.nanmean(B1)
folds=np.array_split(np.arange(60,N-21),3)
def ev(name,s):
    s=s&valid; r=ret20[s]; ts=np.where(s)[1]
    n=len(r); m=r.mean(); med=np.median(r); win=(r>0).mean()
    f=[ret20[:,fd[0]:fd[-1]+1][s[:,fd[0]:fd[-1]+1]].mean() for fd in folds]
    # 각 fold 평균 vs 현행 EG 같은 fold 평균
    # R5: 신호일별 평균 초과(현행 대비)의 상위 3일 제거
    df=pd.DataFrame(dict(t=ts,r=r)); day=df.groupby('t').r.mean()
    # 일별 (후보-B1)의 합에서 상위3일 제거 후 평균
    ex=day-b1mean; srt=ex.sort_values(); r5=(ex.sum()-srt.tail(3).sum())/len(ex)
    return dict(name=name,n=n,perday=n/(N-81),mean=m*100,med=med*100,win=win*100,vsB1=(m-b1mean)*100,f=[x*100 for x in f],r5=r5*100)
rows=[]
rows.append(ev('현행 EG(9조건)',sig()))
# 축1 추세 정렬
rows.append(ev('+MA20>MA60',sig(extra=MA20>MA60)))
rows.append(ev('+C>MA120',sig(extra=C>MA120)))
rows.append(ev('+MA60 20일 상승',sig(t=base_trend&(MA60>=sh(MA60,20)))))
# 축2 눌림 깊이/기간
for k,w in [(1.00,5),(1.03,5),(1.05,5),(1.02,3),(1.02,10)]:
    rows.append(ev(f'눌림 lowest(L,{w})<=MA20*{k:.2f}',sig(p=(rmin(L,w)<=MA20*k))))
rows.append(ev('+눌림 저점이 MA20 아래 터치(L5<MA20)',sig(extra=rmin(L,5)<MA20)))
# 축3 캔들 강도
rows.append(ev('종가위치 >=0.7',sig(c=(C>=sh(O,1))&(C>O)&(sh(C,1)<sh(O,1))&(C>=L+(H-L)*0.7))))
rows.append(ev('종가위치 >=0.8',sig(c=(C>=sh(O,1))&(C>O)&(sh(C,1)<sh(O,1))&(C>=L+(H-L)*0.8))))
rows.append(ev('+몸통(C-O) >= 0.5 ATR14',sig(extra=(C-O)>=0.5*ATR)))
rows.append(ev('+몸통 >= 1.0 ATR14',sig(extra=(C-O)>=1.0*ATR)))
rows.append(ev('+전일 음봉 2일 연속(C(2)<O(2))',sig(extra=sh(C,2)<sh(O,2))))
rows.append(ev('+저점 상승(L>L(1))',sig(extra=L>sh(L,1))))
rows.append(ev('+갭상승 시가(O>C(1))',sig(extra=O>sh(C,1))))
rows.append(ev('+종가>전일 고가(C>H(1))',sig(extra=C>sh(H,1))))
# 축4 거래량
for k in [1.5,2.0]:
    rows.append(ev(f'거래량 >= {k}배',sig(v=(V>=VA*k))))
rows.append(ev('거래대금 >= 1.3배(대금 기준)',sig(v=(C*V>=AMT*1.3))))
rows.append(ev('+눌림구간 거래량 감소(avg V(1..3) < VA)',sig(extra=(sh(V,1)+sh(V,2)+sh(V,3))/3<VA)))
# 축5 상대강도/고점
rows.append(ev('+RS: 20일수익 > KODEX200',sig(extra=R20>BR20)))
rows.append(ev('+250일 고점 5% 이내',sig(extra=C>=H250*0.95)))
rows.append(ev('+60일 고점 3% 이내',sig(extra=C>=H60*0.97)))
# 축6 과열 제한
rows.append(ev('당일등락 <= +8%',sig(extra=(C/sh(C,1)-1)<=0.08)))
rows.append(ev('MA20 이격 <= +12%',sig(extra=C<=MA20*1.12)))
rows.append(ev('원본 HTS 과열배제(C<=MA20*1.10)',sig(extra=C<=MA20*1.10)))
# 축7 국면
rows.append(ev('+KODEX200 > MA60',sig(extra=np.broadcast_to(Bf>Bm60,(M,N)))))
rows.append(ev('+KODEX200 > MA20',sig(extra=np.broadcast_to(Bf>Bm20,(M,N)))))
base=rows[0]
print(f'B1(추세일) 20일 평균 {b1mean*100:+.2f}%   현행 fold {["%.2f"%x for x in base["f"]]}')
print(f'{"후보":40s} {"n":>5s} {"/일":>5s} {"평균%":>6s} {"중앙%":>6s} {"승률":>5s} {"vsB1":>6s} {"vs현행":>6s} {"fold(vs현행)":>12s} {"R5":>6s}')
for r in rows:
    fv=''.join('+' if a>b else '-' for a,b in zip(r['f'],base['f']))
    print(f'{r["name"]:40s} {r["n"]:5d} {r["perday"]:5.2f} {r["mean"]:6.2f} {r["med"]:6.2f} {r["win"]:5.1f} {r["vsB1"]:+6.2f} {r["mean"]-base["mean"]:+6.2f} {fv:>12s} {r["r5"]:+6.2f}')
print('\n=== R1 고원: 눌림 기간 × 깊이 ===')
for w in [5,7,10,15,20]:
    for k in [1.00,1.02,1.05]:
        r=ev(f'w{w} k{k:.2f}',sig(p=(rmin(L,w)<=MA20*k)))
        fv=''.join('+' if a>b else '-' for a,b in zip(r['f'],base['f']))
        print(f'{r["name"]:12s} n={r["n"]:5d} /일 {r["perday"]:.2f} 평균 {r["mean"]:5.2f} 중앙 {r["med"]:5.2f} 승률 {r["win"]:.1f} vs현행 {r["mean"]-base["mean"]:+.2f} fold {fv} R5 {r["r5"]:+.2f}')
# 5슬롯 포트폴리오로 눌림10 재현
import sys; sys.path.insert(0,HERE); import portfolio as P
E={}
s10=sig(p=(rmin(L,10)<=MA20*1.02))
for m,t in zip(*np.where(s10)):
    if t>=60: E.setdefault(t,[]).append(m)
for nm,kw in [('현행 K5',dict(K=5)),('눌림10 K5',dict(K=5,entries=E))]:
    eq,ntr,rets,occ=P.sim(**kw); st=P.stats(eq); print(f'{nm}: cagr {st[1]*100:.1f}% mdd {st[2]*100:.1f} sharpe {st[3]:.2f} trades {ntr} occ {occ:.1f}')
