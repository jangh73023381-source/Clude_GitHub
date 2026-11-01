import warnings; warnings.filterwarnings('ignore')
from bt import *
rng=np.random.default_rng(7)
res={}
def full(s,label):
    o,t,i,r,ex=stats(s); o2=stats(s,RC,UNIV_RC)[0]
    hit_any=float((Hn[t,i]>C[t,i]).mean()*100) if len(t) else None
    hit_vi=float((Hn[t,i]>=C[t,i]*1.1).mean()*100) if len(t) else None
    gap=float(np.mean(On[t,i]/C[t,i]-1)*100) if len(t) else None
    o.update(closeonly_mean=o2['mean'],closeonly_ex=o2['ex'],p_high_above=hit_any,p_vi=hit_vi,gap=gap)
    res[label]=o; return o,t,i,r,ex
o,t,i,r,ex=full(sig(),'main')
full(sig(excl_limit=False)&LIMIT,'limit_close')
full(sig(excl_limit=False),'main_incl_limit')
# 조건 분해 (상한가 제외)
base=valid & ~LIMIT
A=vr>=15; Bc=C>hh(60); Cw=wick<=0.01
for nm,m in [('all',base),('vol',base&A),('brk',base&Bc),('wick',base&Cw),('vol+brk',base&A&Bc),('vol+wick',base&A&Cw),('brk+wick',base&Bc&Cw),('3cond',base&A&Bc&Cw)]:
    res['dec_'+nm]=stats(m)[0]
# 급등 대조 — 같은 날 r1 ±2%p·조건② ③ 충족·거래량 조건 미충족
ctl=[]
for tt,ii in zip(t,i):
    pool=np.nonzero(base[tt]&~A[tt]&(np.abs(r1[tt]-r1[tt,ii])<=0.02))[0]
    if len(pool): ctl.append(np.mean(RX[tt,pool])-COST)
res['matched_r1_ctl']=dict(n=len(ctl),mean=float(np.mean(ctl)*100))
# 플라시보: 같은 날 유니버스 무작위 동수 1000회
sims=[]
byday={}
for tt in t: byday[tt]=byday.get(tt,0)+1
for _ in range(1000):
    v=[]
    for tt,k in byday.items():
        pool=np.nonzero(base[tt])[0]; v.extend(RX[tt,rng.choice(pool,k,replace=False)]-COST)
    sims.append(np.mean(v))
sims=np.array(sims); res['placebo']=dict(p=float((sims>=np.mean(r)).mean()),p95=float(np.percentile(sims,95)*100),mean=float(sims.mean()*100))
# R2 3분할 · 연도
for k,(a,b) in enumerate([(0,T//3),(T//3,2*T//3),(2*T//3,T)],1):
    m=(t>=a)&(t<b); res[f'fold{k}']=dict(n=int(m.sum()),mean=float(np.mean(r[m])*100) if m.sum() else None,ex=float(np.mean(ex[m])*100) if m.sum() else None,span=f'{dates[a]}~{dates[b-1]}')
yrs={}
for y in range(2019,2027):
    m=np.array([str(dates[x])[:4]==str(y) for x in t]); yrs[y]=dict(n=int(m.sum()),mean=float(np.mean(r[m])*100) if m.sum() else None)
res['years']=yrs
# R5 꼬리
srt=np.sort(ex)[::-1]
res['R5']={f'drop{k}':float(np.mean(srt[k:])*100) for k in (1,3,5,10)}; res['R5']['median_ex']=float(np.median(ex)*100)
# R1 격자
grid=[]
for kk in (5,10,15,20,30):
    for nn in (40,60,120,250):
        for ww in (0.005,0.01,0.02,0.03):
            g=stats(sig(kk,nn,ww))[0]; grid.append((kk,nn,ww,g['n'],g['mean'],g['ex']))
res['grid']=grid
# 포트폴리오: 신호일 동일가중, 아니면 현금
dr=np.zeros(T)
for tt in set(t): dr[tt]=np.mean(r[t==tt])
eq=np.cumprod(1+dr); mdd=float(np.min(eq/np.maximum.accumulate(eq)-1)*100)
b=bench[:,1]; bret=np.nancumprod(np.r_[1,b[1:]/b[:-1]])
res['port']=dict(cum=float((eq[-1]-1)*100),mdd=mdd,active_days=int((dr!=0).sum()),kodex200=float((b[-1]/b[0]-1)*100))
# 상위 사례
top=sorted(zip(r,t,i),key=lambda x:-x[0])[:8]
res['examples']=[dict(date=str(dates[tt]),code=str(codes[ii]),r1=float(r1[tt,ii]*100),vr=float(vr[tt,ii]),ret=float(rr*100)) for rr,tt,ii in top]
res['worst']=[dict(date=str(dates[tt]),code=str(codes[ii]),r1=float(r1[tt,ii]*100),vr=float(vr[tt,ii]),ret=float(rr*100)) for rr,tt,ii in sorted(zip(r,t,i),key=lambda x:x[0])[:5]]
res['sig_r1']=dict(mean=float(np.mean(r1[t,i])*100),q=[float(x*100) for x in np.percentile(r1[t,i],[10,50,90])])
json.dump(res,open('result.json','w'),ensure_ascii=False,indent=1,default=float)
print(json.dumps({k:v for k,v in res.items() if k not in('grid','examples','worst')},ensure_ascii=False,default=float))
