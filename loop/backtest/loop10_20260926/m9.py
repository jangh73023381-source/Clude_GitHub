from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
inv=pd.read_pickle('inv.pkl')
g=lambda col: inv.pivot(index='dt',columns='code',values=col).reindex(index=dates,columns=codes).values.astype(float)
TV=g('acc_trde_prica'); X=np.nan_to_num(g('samo_fund'))+np.nan_to_num(g('penfnd_etc')); X[np.isnan(TV)]=np.nan
res=[]
for k in (20,60):
    S=pd.DataFrame(X).rolling(k,min_periods=k).sum().values/pd.DataFrame(TV).rolling(k,min_periods=k).sum().values
    def filt(i,S=S):
        pl=top(MOM[150],i,30)
        if pl is None: return None
        s=S[i,pl]; keep=~(s<0)
        c=pl[keep][:5]
        return c if len(c)==5 else pl[:5]
    def blend(i,S=S):
        pl=top(MOM[150],i,30)
        if pl is None: return None
        rk=pd.Series(-MOM[150][i,pl]).rank().values+pd.Series(-S[i,pl]).rank().fillna(15).values
        return pl[np.argsort(rk,kind='stable')[:5]]
    o,_=report(f'mom150 pool30 − 사모+연기금{k}일 순매도 제외',filt,ref=base); res.append(o)
    o,_=report(f'mom150 pool30 − 모멘텀·사모연기금{k}일 랭크합',blend,ref=base); res.append(o)
pickle.dump(res,open('m9.pkl','wb'))
