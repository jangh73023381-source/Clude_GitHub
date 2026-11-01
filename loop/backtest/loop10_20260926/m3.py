from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
def skip(L,S): return (lag(C,S)/lag(C,L)-1)*100
res=[]
for L,S in ((150,10),(150,20),(250,20),(250,40)):
    sc=skip(L,S)
    o,_=report(f'스킵모멘텀 {L}-{S}',lambda i,sc=sc: top(sc,i),ref=base); res.append(o)
pickle.dump(res,open('m3.pkl','wb'))
