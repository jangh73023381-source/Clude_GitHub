from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
r=lambda k:(C/lag(C,k)-1)
W=(0.4*r(63)+0.2*r(126)+0.2*r(189)+0.2*r(252))*100
RL=C/C[:,[bi]]; RLmax=pd.DataFrame(RL).rolling(250,min_periods=120).max().values
nh=RL>=RLmax*0.98
res=[]
o,_=report('RS(IBD 40/20/20/20) 상위5',lambda i: top(W,i),ref=base); res.append(o)
o,_=report('RS 상위5 ∩ RS라인 신고가(2%)',lambda i: top(W,i,mask=nh[i]) ,ref=base); res.append(o)
MA20=pd.Series(C[:,bi]).rolling(20).mean().values
g=lambda i: top(W,i,mask=nh[i]) if C[i,bi]>MA20[i] else np.array([],int)
o,_=report('RS∩RS라인신고가 + 지수MA20 게이트(현금)',g,ref=base); res.append(o)
pickle.dump(res,open('m4.pkl','wb'))
