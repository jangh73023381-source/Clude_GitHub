from ev import *
C,O=E.C,E.O; H,Lo=E.P['high'],E.P['low']; N=E.N
prevC=np.vstack([np.full((1,N),np.nan),C[:-1]])
gap=(O/prevC-1)*100; intra=(C/O-1)*100
park=np.sqrt((np.log(H/Lo))**2/(4*np.log(2)))*100
def roll(X,k,f='std'):
    D=pd.DataFrame(X)
    return (D.rolling(k,min_periods=max(5,k//3)).std() if f=='std' else D.rolling(k,min_periods=max(5,k//3)).mean()).values
S={'갭σ20':roll(gap,20),'일중σ20':roll(intra,20),'Parkinson20':roll(park,20,'mean')}
def sel_sig(M):
    def f(i,pl):
        v=M[i,pl]; m=~np.isnan(v)
        if m.sum()<5: return E.sel_lv(i,pl)
        return pl[m][np.argsort(v[m],kind='stable')[:5]]
    return f
res=[]
for k,M in S.items():
    o,_=evaluate(f'LV σ정의={k}',sel_sig(M)); res.append(o)
import pickle; pickle.dump(res,open('it6.pkl','wb'))
