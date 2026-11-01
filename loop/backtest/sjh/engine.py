import numpy as np, os, json
S=os.path.expanduser('~/mnt/loop/backtest/sjh')
dates=np.load(S+'/dates.npy'); codes=np.load(S+'/codes.npy',allow_pickle=True)
C=np.load(S+'/C.npy'); O=np.load(S+'/O.npy'); V=np.load(S+'/V.npy')
MEM=np.load(S+'/MEM.npy'); SHR=np.load(S+'/SHR.npy')
SAG=np.load(S+'/SAG.npy'); OPG=np.load(S+'/OPG.npy'); OPP=np.load(S+'/OPP.npy')
sec=np.load(S+'/sec.npy',allow_pickle=True); secy=np.load(S+'/secy.npy',allow_pickle=True)
bench=np.load(S+'/bench.npy')
T,N=C.shape
C=C.astype('float64'); O=O.astype('float64'); V=V.astype('float64')

import pandas as pd
def _df(M): return pd.DataFrame(M)
def roll(M,w,f):
    r=_df(M).rolling(w,min_periods=max(3,w//2))
    return {'max':r.max(),'min':r.min(),'mean':r.mean()}[f].values
nanmax='max'; nanmin='min'; nanmean='mean'

import warnings; warnings.filterwarnings('ignore')
MA5=roll(C,5,nanmean); MA20=roll(C,20,nanmean); MA60=roll(C,60,nanmean)
HI250=roll(C,250,nanmax); LO250=roll(C,250,nanmin)
TO=C*V
TO20=roll(TO,20,nanmean); TO60=roll(TO,60,nanmean)
def lagret(w):
    r=np.full_like(C,np.nan); r[w:]=C[w:]/C[:-w]-1; return r
R5=lagret(5); R20=lagret(20); R60=lagret(60); R120=lagret(120)
MA20_up=np.full_like(C,np.nan); MA20_up[5:]=MA20[5:]-MA20[:-5]

H=20
# 미래수익: A=지표(종가→종가), B=집행(익일시가→D+H 종가)
FA=np.full_like(C,np.nan); FB=np.full_like(C,np.nan)
FA[:-H]=C[H:]/C[:-H]-1
FB[:-H-1]=C[H+1:]/O[1:-H]-1
bA=np.full(T,np.nan); bB=np.full(T,np.nan)
bc=bench[:,1]; bo=bench[:,0]
bA[:-H]=bc[H:]/bc[:-H]-1
bB[:-H-1]=bc[H+1:]/bo[1:-H]-1
EA=FA-bA[:,None]; EB=FB-bB[:,None]

# 시장 게이트: KODEX200 > MA20
bMA20=np.full(T,np.nan)
for t in range(19,T): bMA20[t]=np.nanmean(bc[t-19:t+1])
GATE=bc>bMA20

# 섹터 그룹 인덱스
def secgroups(sv):
    g={}
    for s in set(sv.tolist()):
        if s in ('NA','nan','None'): continue
        idx=np.where(sv==s)[0]
        if len(idx)>=5: g[s]=idx
    return g
G2=secgroups(sec); GY=secgroups(secy)

def sector_rank(sv,groups,metric,topk):
    """각 날짜별 상위 topk 섹터 소속이면 True (벡터화)"""
    names=list(groups.keys()); idxs=[groups[s] for s in names]
    K=len(names)
    vals=np.full((T,K),np.nan)
    cnt=np.zeros((T,K))
    for j,idx in enumerate(idxs):
        sub=np.where(MEM[:,idx],metric[:,idx],np.nan)
        cnt[:,j]=np.isfinite(sub).sum(1)
        vals[:,j]=np.nanmedian(sub,axis=1)
    vals=np.where(cnt>=3,vals,np.nan)
    out=np.zeros((T,N),dtype=bool)
    order=np.argsort(np.where(np.isfinite(vals),vals,-np.inf),axis=1)[:,::-1]
    nok=np.isfinite(vals).sum(1)
    for t in range(T):
        k=min(topk,nok[t])
        if k<=0: continue
        for j in order[t,:k]:
            out[t,idxs[j]]=True
    return out

TOFLOW=np.where(TO60>0,TO20/TO60,np.nan)

def build(cfg):
    """cfg dict → (mask, rankscore)"""
    m=MEM.copy()
    m &= np.isfinite(C)&np.isfinite(TO20)&np.isfinite(MA60)
    if cfg.get('gate'): m &= GATE[:,None]
    if cfg.get('s1'):
        m &= cfg['_s1cache']
    if cfg.get('s2')=='hard':   # 선취매: 미급등 (원안)
        m &= (C < HI250*cfg.get('s2_hi',0.90))
        m &= (R60 < np.nanmedian(np.where(MEM,R60,np.nan),axis=1,keepdims=True))
    elif cfg.get('s2')=='soft':
        m &= (C < HI250*cfg.get('s2_hi',0.90))
    elif cfg.get('s2')=='inv':  # 반전: 신고가 근접 (NHI)
        m &= (C >= HI250*cfg.get('s2_hi',0.95))
    if cfg.get('s3'): m &= (SAG>cfg.get('s3_thr',0.0))
    if cfg.get('s4'): m &= (OPG>cfg.get('s4_thr',0.0)) & OPP
    if cfg.get('s5')=='bottom':
        m &= (C < LO250*cfg.get('s5_lo',1.30)) & (MA20_up>0) & (C>MA20)
    elif cfg.get('s5')=='pull':
        m &= (C>MA60) & (C<MA20) & (R5<0)
    elif cfg.get('s5')=='either':
        a=(C < LO250*cfg.get('s5_lo',1.30)) & (MA20_up>0) & (C>MA20)
        b=(C>MA60) & (C<MA20) & (R5<0)
        m &= (a|b)
    rk=cfg.get('rank','to')
    if rk=='to': sc=TO20
    elif rk=='mc': sc=C*SHR
    elif rk=='mom': sc=R20
    elif rk=='rand':
        rs=np.random.RandomState(cfg.get('seed',0)); sc=rs.rand(T,N)
    else: sc=TO20
    return m,sc

def run(m,sc,topn=10,E=None):
    E=EA if E is None else E
    picks=[]; rets=[]
    for t in range(T):
        idx=np.where(m[t]&np.isfinite(E[t])&np.isfinite(sc[t]))[0]
        if len(idx)==0: rets.append(np.nan); picks.append([]); continue
        k=min(topn,len(idx))
        sel=idx[np.argsort(-sc[t][idx])[:k]]
        rets.append(np.nanmean(E[t][sel])); picks.append(sel)
    return np.array(rets),picks

def stats(r,label,start=20200403):
    s=np.searchsorted(dates,start)
    rr=r[s:]; d=dates[s:]
    v=rr[np.isfinite(rr)]
    if len(v)<10: return dict(label=label,n=0)
    # 비중복(20거래일 간격) 계열
    ii=np.arange(s,T,20); nv=r[ii]; nv=nv[np.isfinite(nv)]
    tstat=nv.mean()/ (nv.std(ddof=1)/np.sqrt(len(nv))) if len(nv)>2 else np.nan
    return dict(label=label,n_all=len(v),mean=round(v.mean()*100,3),med=round(np.median(v)*100,3),
                win=round((v>0).mean()*100,1),n_ne=len(nv),mean_ne=round(nv.mean()*100,3),
                t_ne=round(tstat,2))
