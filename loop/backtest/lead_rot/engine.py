from base import *
rng=np.random.default_rng(7)
def cs_mean(M,mask,t):
    v=M[t][mask[t]]; v=v[np.isfinite(v)]; return v.mean() if len(v) else np.nan
uni_intra=np.array([cs_mean(INTRA,UNI,t) for t in range(T)])
uni_gap=np.array([cs_mean(GAP,UNI,t) for t in range(T)])
# E3: t+1 시가 → t+2 종가
E3=np.full_like(C,np.nan); E3[:-2]=C[2:]/O[1:-1]-1; E3[np.abs(E3)>0.6]=np.nan
uni_e3=np.full(T,np.nan)
for t in range(T-2):
    m=UNI[t+1]&np.isfinite(E3[t]); uni_e3[t]=E3[t][m].mean() if m.any() else np.nan
# 사전 베타·변동성 (t0 이전 120일)
def pre_stats(t0,w=120):
    a=max(1,t0-w); x=semi_r[a:t0]; Y=R[a:t0]
    ok=np.isfinite(Y); cnt=ok.sum(0)
    xm=np.where(ok,x[:,None],np.nan)
    cov=np.nanmean((Y-np.nanmean(Y,0))*(xm-np.nanmean(xm,0)),0)
    beta=cov/np.nanvar(xm,0); vol=np.nanstd(Y,0)
    beta[cnt<60]=np.nan; vol[cnt<60]=np.nan
    return beta,vol
V=np.load(S+'/V.npy').astype('f8'); TOV=C*V
def liq_mask(t0,top):
    tv=np.nanmean(TOV[max(0,t0-20):t0],0); tv=np.where(UNI[t0]&np.isfinite(tv),tv,-1)
    m=np.zeros(N,bool); m[np.argsort(tv)[::-1][:top]]=True; return m
LIQ=None
def leaders(t0,mode,k=3,npool=20,Z=0.05):
    u=UNI[t0]&MEM[min(t0+k-1,T-1)]
    if LIQ: u=u&liq_mask(t0,LIQ)
    ex=R[t0:t0+k]-uni_ew[t0:t0+k,None]
    ce=np.nancumsum(ex,0); ce[:,~u]=np.nan
    if mode=='A':        # 반등 k일 누적 초과수익 상위
        s=ce[-1]
    elif mode=='B':      # 가장 먼저 +Z 초과 도달(빠른 날 우선, 같은 날은 크기순)
        hit=ce>=Z; first=np.where(hit.any(0),hit.argmax(0),99)
        s=np.where(first<99,(k-first)*10+ce[-1],np.nan)
    elif mode=='B1':     # 반등 첫날 초과수익 상위
        s=ce[0]
    s=np.where(np.isfinite(s),s,-np.inf)
    idx=np.argsort(s)[::-1][:npool]; idx=idx[np.isfinite(s[idx])]
    return idx
def ctrl(t0,kind,npool=20):
    beta,vol=pre_stats(t0); u=UNI[t0]
    v={'beta':beta,'vol':vol}[kind]; v=np.where(u&np.isfinite(v),v,-np.inf)
    return np.argsort(v)[::-1][:npool]
def day_metrics(idx,t,rule='down'):
    """t일 신호 → (종가진입 1일초과, 갭초과, 장중초과, 시가진입 2일초과, n)"""
    r=R[t,idx]; ok=np.isfinite(r)&np.isfinite(R[t+1,idx])
    if rule=='down': sel=ok&(r<0)
    elif rule=='up': sel=ok&(r>0)
    elif rule=='all': sel=ok
    elif rule=='worst3':
        sel=np.zeros(len(idx),bool); rr=np.where(ok,r,np.inf); o=np.argsort(rr)[:3]; sel[o]=ok[o]&(r[o]<0)
    if sel.sum()==0: return None
    j=idx[sel]
    return (np.nanmean(R[t+1,j])-uni_ew[t+1], np.nanmean(GAP[t+1,j])-uni_gap[t+1],
            np.nanmean(INTRA[t+1,j])-uni_intra[t+1], np.nanmean(E3[t,j])-uni_e3[t], sel.sum())
def rotation(idx,t):
    a=R[t,idx]; b=R[t+1,idx]; ok=np.isfinite(a)&np.isfinite(b)
    if ok.sum()<8: return np.nan
    a=a[ok]-a[ok].mean(); b=b[ok]-b[ok].mean()
    return (a*b).sum()/np.sqrt((a*a).sum()*(b*b).sum())
def run(X=0.08,Y=0.02,k=3,H=40,npool=20,modes=('A','B','B1'),nrand=200,rules=('down','all','up','worst3')):
    ev=events(X,Y); rows=[]
    for e,t0 in enumerate(ev):
        I=t0+k-1
        pools={m:leaders(t0,m,k if m!='B' else max(k,5),npool) for m in modes}
        if 'B' in modes: I_b=t0+max(k,5)-1
        pools['CB']=ctrl(t0,'beta',npool); pools['CV']=ctrl(t0,'vol',npool)
        for name,idx in pools.items():
            start=(I_b if name=='B' else I)+1
            # 주도 지속: 창 누적 풀초과
            for t in range(start,min(start+H,T-2)):
                rot=rotation(idx,t)
                for rule in rules:
                    m=day_metrics(idx,t,rule)
                    if m is None: continue
                    rows.append((e,t,name,rule)+m+(rot,))
        # 무작위 풀 (down 규칙만, 종가진입 1일 초과 평균)
        u=np.where(UNI[t0])[0]
        for d in range(nrand):
            idx=rng.choice(u,npool,replace=False)
            for t in range(I+1,min(I+1+H,T-2)):
                m=day_metrics(idx,t,'down')
                if m is None: continue
                rows.append((e,t,'RND%d'%d,'down')+m+(np.nan,))
    import pandas as pd
    return ev,pd.DataFrame(rows,columns=['ev','t','pool','rule','ex1','gap','intra','ex2o','n','rot'])
