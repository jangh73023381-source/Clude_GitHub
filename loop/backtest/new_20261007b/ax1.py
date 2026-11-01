"""신축 1: 조합 구성형 — MINV(최소분산 탐욕) · CLUST(상관 클러스터 대표) · MAX(복권성 제외) · GK(레인지 변동성 추정량) · KAL(칼만 추세 pool)"""
from common import *
import scipy.cluster.hierarchy as h
E,base=setup(); res={}; C,R=E.C,E.R; H,L,O=E.P['high'],E.P['low'],E.P['open']
s20=E.vol(20)
def minv(win,start_n=None):
    def f(i,pl):
        X=R[i-win+1:i+1][:,pl]; ok=(~np.isnan(X)).sum(0)>=win*0.8
        c=pl[ok]; X=X[:,ok]
        if len(c)<5: return E.sel_lv(i,pl)
        X=np.where(np.isnan(X),np.nanmean(X,0),X); S_=np.cov(X.T)
        sel=[int(np.argmin(np.diag(S_)))]
        while len(sel)<5:
            best=None;bv=1e18
            for j in range(len(c)):
                if j in sel: continue
                s=sel+[j]; w=np.ones(len(s))/len(s); v=w@S_[np.ix_(s,s)]@w
                if v<bv: bv=v;best=j
            sel.append(best)
        return c[sel]
    return f
for w in (40,60,120):
    comp(base,f'1 MINV 탐욕 cov{w}',E.run(minv(w),start=S),res)
def clust(win,k=5):
    def f(i,pl):
        X=R[i-win+1:i+1][:,pl]; ok=(~np.isnan(X)).sum(0)>=win*0.8; c=pl[ok]; X=X[:,ok]
        if len(c)<8: return E.sel_lv(i,pl)
        X=np.where(np.isnan(X),np.nanmean(X,0),X); cr=np.corrcoef(X.T); d=1-cr; np.fill_diagonal(d,0)
        Z=h.linkage(d[np.triu_indices(len(c),1)],'average'); lab=h.fcluster(Z,k,'maxclust')
        v=s20[i,c]; out=[]
        for g in np.unique(lab):
            m=np.where(lab==g)[0]; out.append(m[np.argmin(v[m])])
        out=sorted(out,key=lambda j:v[j])[:5]
        if len(out)<5:
            rest=[j for j in np.argsort(v) if j not in out]; out+=rest[:5-len(out)]
        return c[out]
    return f
for w in (60,120):
    comp(base,f'2 CLUST 상관클러스터5 대표 w{w}',E.run(clust(w),start=S),res)
mx=pd.DataFrame(R).rolling(20,min_periods=15).max().values
def excl(score,frac):
    def f(i,pl):
        v=score[i,pl]; ok=~np.isnan(v); c,v=pl[ok],v[ok]
        if len(c)<8: return E.sel_lv(i,pl)
        k=max(5,int(round(len(c)*(1-frac)))); return E.sel_lv(i,c[np.argsort(v,kind='stable')[:k]])
    return f
for fr in (1/3,1/2):
    comp(base,f'3 MAX20 상위{fr:.2f} 제외→σ5',E.run(excl(mx,fr),start=S),res)
# 4 Garman-Klass σ20 / Parkinson
lc=np.log(C/np.vstack([np.full((1,C.shape[1]),np.nan),C[:-1]]))
gk=0.5*np.log(H/L)**2-(2*np.log(2)-1)*np.log(C/O)**2
gk=np.sqrt(pd.DataFrame(gk).rolling(20,min_periods=10).mean().values)
pk=np.sqrt(pd.DataFrame(np.log(H/L)**2/(4*np.log(2))).rolling(20,min_periods=10).mean().values)
iv=pd.DataFrame(np.log(C/O)).rolling(20,min_periods=10).std().values
def bysc(score):
    def f(i,pl):
        v=score[i,pl]; ok=~np.isnan(v)
        if ok.sum()<5: return E.sel_lv(i,pl)
        c,v=pl[ok],v[ok]; return c[np.argsort(v,kind='stable')[:5]]
    return f
comp(base,'4 GK σ20 하위5',E.run(bysc(gk),start=S),res)
comp(base,'4 Parkinson σ20 하위5',E.run(bysc(pk),start=S),res)
comp(base,'4 장중(O→C) σ20 하위5',E.run(bysc(iv),start=S),res)
# 5 칼만 국소선형추세 기울기(로그가격) → pool30 → σ5
def kal_slope(q=1e-4,r=1e-2):
    Y=np.log(pd.DataFrame(C).ffill().values); T,N=Y.shape; out=np.full((T,N),np.nan)
    x=np.zeros((N,2)); P=np.tile(np.eye(2)*1.0,(N,1,1)); init=np.zeros(N,bool)
    F=np.array([[1,1],[0,1]]); Q=np.eye(2)*q
    for t in range(T):
        y=Y[t]; m=~np.isnan(y)
        new=m&~init; x[new,0]=y[new]; x[new,1]=0; init|=new
        x=x@F.T; P=F@P@F.T+Q
        Sx=P[:,0,0]+r; K=P[:,:,0]/Sx[:,None]
        inn=np.where(m,y-x[:,0],0)
        x=x+K*inn[:,None]*m[:,None]
        P=np.where(m[:,None,None],P-K[:,:,None]*P[:,0,:][:,None,:],P)
        out[t]=np.where(init,x[:,1],np.nan)
    return out
for q,r in ((1e-5,1e-3),(1e-4,1e-3),(1e-5,1e-2)):
    ks=kal_slope(q,r)*100
    ks[np.isnan(E.mom)]=np.nan
    comp(base,f'5 칼만기울기 pool30(q{q},r{r})→σ5',E.run(lambda i,pl,ks=ks:E.sel_lv(i,E.pool(i,score=ks)),start=S),res)
json.dump(res,open('res_ax1.json','w'),default=float,indent=1); print('DONE')
