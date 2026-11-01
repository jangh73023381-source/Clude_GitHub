# 유튜브 '종가베팅 3조건'(2026-09-28 영상 aLkBsImZ4fQ) 백테스트 — 개별종목 7.7년 PIT 패널
# 조건: ①거래량 전일 대비 k배(기본 15배=+1400%) ②종가 > 직전 L일 최고가(기본 60일, 전고점 돌파)
#       ③윗꼬리 없음 (H-C)/C <= w (기본 1%)  →  D 종가 매수, D+1 상승 VI(+10%) 부근 매도, 미도달 시 D+1 종가.
import numpy as np, json, sys
S='/sessions/'  # placeholder
import os
B=os.path.expanduser('~/mnt/loop/backtest/sjh'); Y=os.path.expanduser('~/mnt/loop/backtest/_yt_stage')
L=lambda n,d=Y: np.load(f'{d}/{n}.npy',allow_pickle=True)
O,H,Lo,C,V=L('O'),L('H'),L('L'),L('C'),L('V'); MEM=L('MEM'); dates=L('dates'); codes=L('codes'); bench=L('bench')
T,N=C.shape
COST=0.0020   # 왕복 비용 가정(매도 거래세 약 0.20% · 수수료 0). 개별종목은 ETF와 달리 거래세가 붙는다.
VI=0.10
def sh(A,k=1):
    R=np.full_like(A,np.nan); R[k:]=A[:-k]; return R
C1,V1=sh(C),sh(V)
r1=C/C1-1
vr=np.where(V1>0,V/V1,np.nan)
wick=(H-C)/C
def rollmax_prev(A,n):
    R=np.full_like(A,np.nan)
    for t in range(n,T): R[t]=np.nanmax(A[t-n:t],axis=0)
    return R
_hh={}
def hh(n):
    if n not in _hh: _hh[n]=rollmax_prev(H,n)
    return _hh[n]
On,Hn,Cn=np.roll(O,-1,0),np.roll(H,-1,0),np.roll(C,-1,0); On[-1]=Hn[-1]=Cn[-1]=np.nan
def exit_ret(entry):
    up=entry*(1+VI)
    px=np.where(On>=up,On,np.where(Hn>=up,up,Cn))
    return px/entry-1
RX=exit_ret(C)              # 영상 집행(VI 매도·미도달 종가)
RC=Cn/C-1                   # 단순 익일 종가
valid=MEM & np.isfinite(RX) & np.isfinite(C1) & (C>0)
UNIV_RX=np.nanmean(np.where(valid,RX,np.nan),axis=1)  # 같은 날 유니버스에 같은 집행규칙
UNIV_RC=np.nanmean(np.where(valid,RC,np.nan),axis=1)
LIMIT=r1>=0.29   # 상한가(+30%, 호가단위 절사로 +29.x% 마감 포함)
def sig(k=15,n=60,w=0.01,excl_limit=True,useH=False):
    br=(H if useH else C)>hh(n)
    s=valid & (vr>=k) & br & (wick<=w)
    if excl_limit: s&=~LIMIT
    return s
def stats(s,R=RX,U=UNIV_RX):
    t,i=np.nonzero(s)
    r=R[t,i]-COST; ex=r-(U[t])
    out=dict(n=int(len(r)),days=int(len(set(t))),mean=float(np.mean(r)*100) if len(r) else None,
             med=float(np.median(r)*100) if len(r) else None,win=float((r>0).mean()*100) if len(r) else None,
             ex=float(np.mean(ex)*100) if len(r) else None)
    return out,t,i,r,ex
if __name__=='__main__':
    out={}
    s0=sig(); o,t,i,r,ex=stats(s0); out['main']=o
    sL=sig(excl_limit=False)&LIMIT; out['limit_close']=stats(sL)[0]
    print(json.dumps(out,ensure_ascii=False))
