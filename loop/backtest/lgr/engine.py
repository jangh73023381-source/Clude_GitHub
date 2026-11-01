# -*- coding: utf-8 -*-
"""이가람식 수급 종목선정 백테스트 공용 엔진.
풀: D일 거래대금 top150 ∩ 상승(ret_D>0) ∩ 수급데이터 존재. 신호는 전부 D 종가 시점 정보.
수익: A1 종가→익일종가 / B1 익일시가→익일종가(당일치기) / B2 익일시가→D+2종가(1박2일) / B5 / B20.
초과 = 풀 동일가중(같은 날 같은 풀) 대비. 보조: vs 유니버스EW, vs KODEX200.
"""
import numpy as np, pandas as pd, os, json, warnings
warnings.filterwarnings('ignore')
H=os.path.dirname(os.path.abspath(__file__)); S=os.path.join(H,'..','sjh')
dates=np.load(S+'/dates.npy'); codes=np.load(S+'/codes.npy',allow_pickle=True)
C=np.load(S+'/C.npy').astype('float64'); O=np.load(S+'/O.npy').astype('float64'); V=np.load(S+'/V.npy').astype('float64')
SHR=np.load(S+'/SHR.npy').astype('float64'); MEM=np.load(S+'/MEM.npy'); bench=np.load(S+'/bench.npy')
T,N=C.shape
MC=C*SHR                       # 시가총액(원)
def F(c): return np.load(H+f'/F_{c}.npy').astype('float64')*1e6   # 백만원→원
ORG=F('orgn'); SAMO=F('samo_fund'); PEN=F('penfnd_etc'); INV=F('invtrt'); FIN=F('fnnc_invt'); FRG=F('frgnr_invsr'); IND=F('ind_invsr')
PRICA=F('acc_trde_prica')
TO=np.where(np.isfinite(PRICA),PRICA,C*V)
R1=np.full_like(C,np.nan); R1[1:]=C[1:]/C[:-1]-1        # 당일 등락률
# 시총대비 비율(%)
def ratio(X): 
    r=X/MC*100; r[~np.isfinite(r)]=np.nan; return r
rORG=ratio(ORG); rSAMO=ratio(SAMO); rPEN=ratio(PEN); rINV=ratio(INV); rFIN=ratio(FIN); rFRG=ratio(FRG); rIND=ratio(IND)
rMAJ=ratio(np.nan_to_num(SAMO)+np.nan_to_num(PEN)+np.nan_to_num(INV)); rMAJ[np.isnan(rORG)]=np.nan
def rollsum(M,w,mp=None):
    return pd.DataFrame(M).rolling(w,min_periods=mp or max(5,w//2)).sum().values
CUM5=rollsum(rORG,5); CUM20=rollsum(rORG,20); CUM60=rollsum(rORG,60)
CUM20_MAJ=rollsum(rMAJ,20); CUM20_FRG=rollsum(rFRG,20)
# 수급 오실레이터(근사): 20일 누적 - 120일 누적/6 (누적 수급의 추세 대비 이탈)
CUM120=rollsum(rORG,120,60)
OSC=CUM20-CUM120/6
HI250=pd.DataFrame(C).rolling(250,min_periods=120).max().values
# 미래수익
def fwd(h):
    A=np.full_like(C,np.nan); B=np.full_like(C,np.nan); G=np.full_like(C,np.nan)
    A[:-h]=C[h:]/C[:-h]-1
    B[:-h]=C[h:]/O[1:T-h+1]-1          # D+1 시가 → D+h 종가
    G[:-1]=O[1:]/C[:-1]-1              # 갭(D종가→D+1시가)
    return A,B,G
A1,B1,GAP=fwd(1); A2,B2,_=fwd(2); A5,B5,_=fwd(5); A20,B20,_=fwd(20)
bc=bench[:,1]; bo=bench[:,0]
def bfwd(h):
    a=np.full(T,np.nan); b=np.full(T,np.nan); a[:-h]=bc[h:]/bc[:-h]-1; b[:-h]=bc[h:]/bo[1:T-h+1]-1; return a,b
bA1,bB1=bfwd(1); bA2,bB2=bfwd(2); bA5,bB5=bfwd(5); bA20,bB20=bfwd(20)
bMA20=pd.Series(bc).rolling(20).mean().values; GATE=bc>bMA20
# ── 풀 ──
K_TO=150
def build_pool(k_to=K_TO, rising=True, require_flow=True):
    P=np.zeros((T,N),bool)
    for t in range(T):
        row=np.nan_to_num(TO[t],nan=-1); idx=np.argpartition(-row,k_to)[:k_to]
        m=np.ones(k_to,bool)
        if rising: m&=np.nan_to_num(R1[t,idx],nan=-1)>0
        if require_flow: m&=np.isfinite(rORG[t,idx])
        P[t,idx[m]]=True
    return P
POOL=build_pool()
MEMU=MEM.copy()  # 유니버스(유동성 통과)
def ew(mask,R):
    """날짜별 mask 동일가중 수익"""
    X=np.where(mask&np.isfinite(R),R,np.nan); cnt=np.isfinite(X).sum(1)
    out=np.nanmean(np.where(cnt[:,None]>0,X,np.nan),axis=1); out[cnt==0]=np.nan; return out
RET={'A1':A1,'B1':B1,'A2':A2,'B2':B2,'B5':B5,'B20':B20}
BRET={'A1':bA1,'B1':bB1,'A2':bA2,'B2':bB2,'B5':bB5,'B20':bB20}
POOL_EW={k:ew(POOL,v) for k,v in RET.items()}
UNI_EW={k:ew(MEMU,v) for k,v in RET.items()}
def select_topk(score,pool,k,lowest=False):
    """날짜별 pool 내 score 상위 k (lowest=True면 하위 k). NaN score 제외."""
    sel=np.zeros((T,N),bool)
    sc=np.where(pool&np.isfinite(score),score,np.nan)
    if lowest: sc=-sc
    for t in range(T):
        v=sc[t]; ok=np.where(np.isfinite(v))[0]
        if len(ok)==0: continue
        if len(ok)<=k: sel[t,ok]=True; continue
        top=ok[np.argpartition(-v[ok],k-1)[:k]]; sel[t,top]=True
    return sel
def stats(sel,key='B2',ref='pool'):
    r=ew(sel,RET[key]); base={'pool':POOL_EW[key],'uni':UNI_EW[key],'bench':BRET[key]}[ref]
    ex=r-base; ok=np.isfinite(ex); e=ex[ok]*100
    if len(e)<10: return dict(n=int(len(e)))
    t=e.mean()/e.std()*np.sqrt(len(e)) if e.std()>0 else 0
    return dict(n=int(len(e)),mean=round(float(e.mean()),4),med=round(float(np.median(e)),4),t=round(float(t),2),
                win=round(float((e>0).mean()),3),raw=round(float(np.nanmean(r[ok])*100),4),
                tail25=round(float(np.sort(e)[-len(e)//4:].sum()/e.sum()) if e.sum()!=0 else 0,2))
def yearly(sel,key='B2'):
    r=ew(sel,RET[key]); ex=(r-POOL_EW[key])*100; yr=np.array([str(d)[:4] for d in dates])
    return {y:round(float(np.nanmean(ex[yr==y])),3) for y in sorted(set(yr))}
def folds(sel,key='B2'):
    r=ew(sel,RET[key]); ex=(r-POOL_EW[key])*100; out=[]
    for a,b in ((0,T//3),(T//3,2*T//3),(2*T//3,T)):
        e=ex[a:b]; e=e[np.isfinite(e)]; out.append((round(float(e.mean()),3),round(float(e.mean()/e.std()*np.sqrt(len(e))),2)))
    return out
def compound(sel,key='B2',cost=0.004,hold=2):
    """비중복 트랜치: hold일마다 진입. 게이트 없음. 복리·MDD"""
    r=ew(sel,RET[key]); eq=1.0; peak=1.0; mdd=0; t=0; n=0
    while t<T:
        if np.isfinite(r[t]): eq*=1+r[t]-cost; n+=1
        peak=max(peak,eq); mdd=min(mdd,eq/peak-1); t+=hold
    return round((eq-1)*100,1),round(mdd*100,1),n
