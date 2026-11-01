from common import *
E,base=setup(); T,N=E.C.shape
rows=[]; rng=np.random.default_rng(0)
for i in range(S,T-3):
    pl=E.pool(i)
    if len(pl)<5: continue
    u=np.where(E.elig&~np.isnan(E.fA[i])&~np.isnan(E.C[i]))[0]
    if len(u)<50: continue
    a=E.fA[i,u]; k=int(np.ceil(len(u)*0.10)); cut=np.sort(a)[::-1][k-1]
    k2=int(np.ceil(len(u)*0.20)); cut2=np.sort(a)[::-1][k2-1]
    lv=E.sel_lv(i,pl); mo=pl[:5]
    def hits(pk,c): v=E.fA[i,pk]; return int(np.sum(v>=c))
    pa=E.fA[i,pl]; orc=int(np.sum(np.sort(pa[~np.isnan(pa)])[::-1][:5]>=cut))   # pool 내 사후 최선 5
    rnd=rng.choice(u,5,replace=False)
    rows.append(dict(lv=hits(lv,cut),mo=hits(mo,cut),rnd=hits(rnd,cut),orc=orc,pooltop=int(np.sum(pa>=cut)),
                     lv20=hits(lv,cut2),mo20=hits(mo,cut2),rnd20=hits(rnd,cut2),n=len(u)))
d=pd.DataFrame(rows); n=len(d)
print('일수',n,'유니버스 평균',d.n.mean())
for c in ('lv','mo','rnd','orc'):
    vc=d[c].value_counts().sort_index(); print(c,'상위10% 5/5 달성률',f"{(d[c]==5).mean()*100:.2f}%",'≥3/5',f"{(d[c]>=3).mean()*100:.1f}%",'평균적중',round(d[c].mean(),2))
print('pool30 안에 상위10% 종목이 5개 이상 있던 날',f"{(d.pooltop>=5).mean()*100:.1f}%  (= 사후 완벽선택으로도 5/5 가능한 날)")
for c in ('lv20','mo20','rnd20'):
    print(c,'상위20% ≥3/5',f"{(d[c]>=3).mean()*100:.1f}%",'5/5',f"{(d[c]==5).mean()*100:.2f}%",'평균',round(d[c].mean(),2))
print('이론 무작위 5/5 확률(상위10%) ≈',f"{0.1**5*100:.4f}%")
