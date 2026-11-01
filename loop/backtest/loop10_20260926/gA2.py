from gA import *
import re
cand=pickle.load(open('mlv.pkl','rb'))
# 지속형 무작위 대조군
rng=np.random.default_rng(11); out=[]
pools={i:top(MOM[150],i,30) for i in range(START,T-1)}
for rep in range(200):
    fx=rng.random(N)
    o,_=report('',lambda i: None if pools[i] is None else pools[i][np.argsort(fx[pools[i]])[:5]],ref=base,quiet=True); out.append((o['mdd'],o['sh'],o['cagr']))
out=np.array(out)
for j,k,rv in ((0,'mdd',-37.41),(1,'sh',1.32),(2,'cagr',34.31)):
    print('지속형',k,'귀무평균 %.2f p95 %.2f p99 %.2f 실제 %.2f p=%.3f'%(out[:,j].mean(),np.quantile(out[:,j],.95),np.quantile(out[:,j],.99),rv,(out[:,j]>=rv).mean()))
# R5 (위험축): 후보-기준 일별차 상위 k일을 기준 값으로 대체해도 MDD 유지되는가
j=cand.merge(base[['date','port']],on='date',suffixes=('','_b')); d=(j.port-j.port_b).values
for k in (5,10,20):
    x=j.port.values.copy(); idx=np.argsort(-d)[:k]; x[idx]=j.port_b.values[idx]
    print(f'R5 상위{k}일 기준으로 대체 → MDD {prof(x)["mdd"]:.1f} Sh {prof(x)["sharpe"]:.2f} (기준 MDD {prof(j.port_b)["mdd"]:.1f} Sh {prof(j.port_b)["sharpe"]:.2f})')
# 1일 지연 진입
report('MLV 익일 종가 진입',lvsel(30,Vs[20]),ref=base,lagd=1)
report('MLV 보유 40일',lvsel(30,Vs[20]),H=40)
# 구성: 채권·금·원자재·배당 비중
kw=re.compile('채|금|은|원자재|골드|배당|커버드콜|리츠|달러|인컴')
f=lvsel(30,Vs[20]); a=b=tot=0
for i in range(START,T-1,5):
    p=f(i); q=base_sel(i)
    if p is None: continue
    a+=sum(bool(kw.search(names[codes[c]])) for c in p); b+=sum(bool(kw.search(names[codes[c]])) for c in q); tot+=5
print('채권·금·배당형 명칭 비중 MLV %.2f / mom150 %.2f'%(a/tot,b/tot))
# 2026 MDD 구간
c=np.cumprod(1+cand.port/100); pk=np.maximum.accumulate(c); k=np.argmin(c/pk); s=np.argmax(c[:k+1])
print('MLV MDD 구간',cand.date[s],'→',cand.date[k])
cb=np.cumprod(1+base.port/100); pb=np.maximum.accumulate(cb); kb=np.argmin(cb/pb); sb=np.argmax(cb[:kb+1])
print('mom150 MDD 구간',base.date[sb],'→',base.date[kb])
# 오늘(최신) 픽
i=T-1
print('최신일',dates[i],'MLV:',[names[codes[c]] for c in f(i)],' | mom150:',[names[codes[c]] for c in base_sel(i)])
