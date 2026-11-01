import numpy as np, os, warnings; warnings.filterwarnings('ignore')
S=os.path.expanduser('~/mnt/loop/backtest/sjh')
dates=np.load(S+'/dates.npy'); codes=np.load(S+'/codes.npy',allow_pickle=True)
C=np.load(S+'/C.npy').astype('f8'); O=np.load(S+'/O.npy').astype('f8')
MEM=np.load(S+'/MEM.npy'); sec=np.load(S+'/sec.npy',allow_pickle=True)
T,N=C.shape
R=np.full_like(C,np.nan); R[1:]=C[1:]/C[:-1]-1
R[np.abs(R)>0.305]=np.nan           # 가격제한 초과 = 조정 인공물
GAP=np.full_like(C,np.nan); GAP[1:]=O[1:]/C[:-1]-1   # t일 시가/전일종가
O[O<=0]=np.nan
INTRA=C/O-1
INTRA[np.abs(INTRA)>0.305]=np.nan
GAP[~np.isfinite(R)|(np.abs(GAP)>0.305)]=np.nan
ci={c:i for i,c in enumerate(codes)}
SEMI2=[ci['005930'],ci['000660']]
semi_r=np.nanmean(R[:,SEMI2],1); semi_r[0]=0
SI=np.cumprod(1+np.nan_to_num(semi_r))
NONSEMI=(sec!='26'); NONSEMI[SEMI2]=False
UNI=MEM & NONSEMI[None,:] & np.isfinite(R)
uni_ew=np.array([np.nanmean(R[t,UNI[t]]) if UNI[t].any() else np.nan for t in range(T)])
def events(X=0.08,Y=0.02,cool=40):
    ev=[];last=-999
    for t in range(21,T):
        dd=SI[t-1]/SI[t-21:t].max()-1
        if dd<=-X and semi_r[t]>=Y and t-last>=cool:
            if UNI[t].sum()>300: ev.append(t); last=t
    return ev
