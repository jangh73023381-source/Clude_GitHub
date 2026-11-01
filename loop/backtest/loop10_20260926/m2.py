from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
V60=pd.DataFrame(Rd).rolling(60,min_periods=40).std().values
def lvsel(pool,V,sc=150):
    def f(i):
        pl=top(MOM[sc],i,pool)
        if pl is None: return None
        v=V[i,pl]; m=~np.isnan(v)
        if m.sum()<5: return pl[:5]
        return pl[m][np.argsort(v[m],kind='stable')[:5]]
    return f
res=[]
for pool in (10,20,30):
    for nm,V in (('σ20',E.vol(20)),('σ60',V60)):
        o,_=report(f'mom150 pool{pool}→{nm} 하위5',lvsel(pool,V),ref=base); res.append(o)
pickle.dump(res,open('m2.pkl','wb'))
