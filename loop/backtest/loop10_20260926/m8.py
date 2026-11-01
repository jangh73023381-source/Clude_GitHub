from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
b=pd.Series(C[:,bi])
res=[]
for L in (60,120,200):
    MA=b.rolling(L).mean().values
    for w0,lab in ((0.5,'절반'),(0.0,'현금')):
        o,_=report(f'국면 게이트 KODEX200<MA{L} → {lab}',base_sel,weight=lambda i,MA=MA,w0=w0: w0 if C[i,bi]<MA[i] else 1.0,ref=base); res.append(o)
pickle.dump(res,open('m8.pkl','wb'))
