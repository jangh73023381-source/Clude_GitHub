from mid import *
import pickle
from etf_sector_map import *
import etf_sector_map as M
fn=[getattr(M,x) for x in dir(M) if x in ('sector_of','sector','classify','get_sector')][0]
SEC=np.array([fn(names.get(c,'')) for c in codes])
print(pd.Series(SEC[E.elig]).value_counts().head(8).to_dict())
base=pickle.load(open('mbase.pkl','rb'))
def cap(k, score=MOM[150]):
    def f(i):
        pl=top(score,i,60)
        if pl is None: return None
        cnt={}; out=[]
        for c in pl:
            s=SEC[c]
            if cnt.get(s,0)<k: out.append(c); cnt[s]=cnt.get(s,0)+1
            if len(out)==5: break
        return np.array(out) if len(out)==5 else None
    return f
res=[]
for k in (1,2):
    o,_=report(f'mom150 섹터당 최대 {k}종',cap(k),ref=base); res.append(o)
pickle.dump(res,open('m7.pkl','wb'))
# 진단: 기준선 5종의 평균 섹터 수
ns=[len(set(SEC[p])) for p in (base_sel(i) for i in range(START,T-1,5)) if p is not None]
print('기준선 픽5 평균 섹터 수 %.2f'%np.mean(ns))
