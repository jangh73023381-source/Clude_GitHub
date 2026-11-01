from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
Hh=pd.DataFrame(P['high']).rolling(250,min_periods=200).max().values
prox=C/Hh
def selB(th,fill='cash'):
    def f(i):
        pl=top(MOM[150],i,200,mask=prox[i]>=th) if False else None
        s=MOM[150][i]; m=okH[i]&~np.isnan(s)&(prox[i]>=th); idx=np.where(m)[0]
        idx=idx[np.argsort(-s[idx],kind='stable')][:5]
        if len(idx)==5: return idx
        if fill=='cash': return None
        if fill=='partial': return idx if len(idx)>0 else None
    return f
def wB(th):
    def w(i):
        s=MOM[150][i]; m=okH[i]&~np.isnan(s)&(prox[i]>=th); return min(m.sum(),5)/5
    return w
res=[]
for th in (0.90,0.93,0.95,0.97):
    f=selB(th); cashfreq=np.mean([f(i) is None for i in range(START,T-1)])
    o,_=report(f'52주고가≥{th} 5종 미만=현금 (현금일 {cashfreq:.0%})',f,ref=base); res.append(o)
for th in (0.93,0.95):
    o,_=report(f'52주고가≥{th} 부족분 슬롯만 현금',selB(th,'partial'),weight=wB(th),ref=base); res.append(o)
pickle.dump(res,open('gB.pkl','wb'))
# 플라시보: 같은 현금 빈도의 무작위 현금일(연속 구간 보존 위해 블록 셔플)
f=selB(0.95); cash=np.array([f(i) is None for i in range(START,T-1)])
real=report('',f,quiet=True)[0]
rng=np.random.default_rng(3); out=[]
blocks=[]; i=0
while i<len(cash):
    j=i
    while j<len(cash) and cash[j]==cash[i]: j+=1
    blocks.append(cash[i:j]); i=j
for rep in range(200):
    order=rng.permutation(len(blocks)); cz=np.concatenate([blocks[k] for k in order])
    cm={START+k:v for k,v in enumerate(cz)}
    o,_=report('',lambda i: None if cm.get(i,False) else base_sel(i),quiet=True); out.append((o['mdd'],o['sh'],o['cagr']))
out=np.array(out)
for j,k in enumerate(('mdd','sh','cagr')):
    print('현금시점 블록셔플',k,'귀무평균 %.2f p95 %.2f 실제 %.2f p=%.3f'%(out[:,j].mean(),np.quantile(out[:,j],.95),real[k],(out[:,j]>=real[k]).mean()))
