from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
Hh=pd.DataFrame(P['high']).rolling(250,min_periods=200).max().values
prox=C/Hh
res=[]
sc=prox*1000+MOM[150]/1000   # 근접도 우선, 동률은 mom150
o,_=report('52주고가 근접도 상위5 (George-Hwang)',lambda i: top(np.where(np.isnan(MOM[150]),np.nan,sc),i),ref=base); res.append(o)
for th in (0.95,0.90):
    o,_=report(f'mom150 상위5 ∩ 52주고가×{th} 이상',lambda i,th=th: top(MOM[150],i,mask=prox[i]>=th),ref=base); res.append(o)
pickle.dump(res,open('m6.pkl','wb'))
