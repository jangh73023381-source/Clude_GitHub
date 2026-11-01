from common import *
E,base=setup(); res={}; C,R=E.C,E.R
mom=E.run(lambda i,pl:E.sel_mom(i,pl),start=S)
B=base.set_index('date'); M=mom.set_index('date').reindex(B.index); idx=[E.dates.index(d) for d in B.index]
def mix(mask):
    df=B[['A','OO']].copy()
    for k in ('A','OO'): df[k]=np.where(mask,M[k].values,B[k].values)
    return df.reset_index()
print('== R1 RVOL 고변동→MOM (창 × 임계)')
for w in (10,20,40,60):
    bv=pd.Series(R[:,E.bi]).rolling(w,min_periods=max(5,w*3//4)).std()
    for lb in (126,252,504):
        bp=bv.rolling(lb,min_periods=lb//2).rank(pct=True).values
        row=[]
        for th in (0.6,0.7,0.8,0.9):
            d=mix(bp[idx]>=th); dd=d.OO.values-B.OO.values; p=prof(d.OO)
            row.append(f"th{th}:{np.nanmean(dd):+.4f}(t{tstat(dd):+.1f},Sh{p['sharpe']:.2f},MDD{p['mdd']:.0f})")
        print(f'w{w} lb{lb}',' '.join(row),flush=True)
print('== R1 정기변경 창')
ds=pd.to_datetime(B.index); ev=[]
for y in range(2019,2027):
    for mth in (6,12):
        d=pd.Timestamp(y,mth,1); ev.append([d+pd.Timedelta(days=k) for k in range(31) if (d+pd.Timedelta(days=k)).month==mth and (d+pd.Timedelta(days=k)).weekday()==3][1])
pos=np.array([np.searchsorted(ds,e) for e in ev])
for a,b in ((-3,3),(-5,5),(-7,7),(-10,10),(-10,0),(0,10),(-5,0),(0,5)):
    win=np.zeros(len(ds),bool)
    for p_ in pos:
        if 0<p_<len(ds): win[max(0,p_+a):p_+b+1]=True
    d=mix(win); dd=d.OO.values-B.OO.values; da=d.A.values-B.A.values
    # 사건별 기여
    per=[np.nansum(dd[max(0,p_+a):p_+b+1]) for p_ in pos if 0<p_<len(ds)]
    print(f'[{a},{b}] OO {np.nanmean(dd):+.4f} t{tstat(dd):+.2f} A {np.nanmean(da):+.4f} | 사건 {len(per)}개 중 양수 {sum(x>0 for x in per)} · 최대 사건 기여 {max(per)/max(1e-9,sum(per))*100:.0f}%',flush=True)
print('== MAX20 제외 동수 무작위 제외 대조')
mx=pd.DataFrame(R).rolling(20,min_periods=15).max().values
def excl_idx(i,pl,frac,rng=None):
    v=mx[i,pl]; ok=~np.isnan(v); c,v=pl[ok],v[ok]
    if len(c)<8: return E.sel_lv(i,pl)
    k=max(5,int(round(len(c)*(1-frac))))
    keep=c[np.argsort(v,kind='stable')[:k]] if rng is None else rng.permutation(c)[:k]
    return E.sel_lv(i,keep)
for fr in (0.2,1/3,0.5):
    real=E.run(lambda i,pl:excl_idx(i,pl,fr),start=S).set_index('date'); j=real.index
    rd=(real.OO-B.OO.reindex(j)).mean(); same=np.mean([set(E.run.__self__ and [])==set() for _ in [0]])
    rng=np.random.default_rng(5); sims=[]
    for s in range(200):
        df=E.run(lambda i,pl:excl_idx(i,pl,fr,rng),start=S).set_index('date'); sims.append((df.OO-B.OO.reindex(df.index)).mean())
    sims=np.array(sims); print(f'제외 {fr:.2f}: dOO {rd:+.4f} 귀무평균 {sims.mean():+.4f} p={np.mean(sims>=rd):.3f}',flush=True)
