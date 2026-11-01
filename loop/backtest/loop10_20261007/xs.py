"""축4~10 횡단면: Amihud · 자기상관 · 변동성수축 · σ앙상블 · 상승거래량비중 · 명목가격 · MDD60. 기준 LV."""
from common import *
E,base=setup(); res={}; C,R=E.C,E.R
V=E.P['volume']; RD=pd.DataFrame(R)
print('기준 LV A',prof(base.A)); print('기준 LV OO',prof(base.OO))
s20=E.vol(20); s10=E.vol(10); s60=E.vol(60); s5=E.vol(5)
def two_stage(sec,n1=10,asc=True):
    """σ20 하위 n1 → sec 오름(asc)/내림 5"""
    def f(i,pl):
        c=E.sel_lv(i,pl,n=n1); v=sec[i,c]; ok=~np.isnan(v)
        if ok.sum()<5: return c[:5]
        c,v=c[ok],v[ok]; o=np.argsort(v if asc else -v,kind='stable'); return c[o[:5]]
    return f
def pre_filter(score,keep_frac=2/3,high=True):
    """pool 에서 score 상위(high)/하위 keep_frac 만 남긴 뒤 σ20 하위5"""
    def f(i,pl):
        v=score[i,pl]; ok=~np.isnan(v)
        if ok.sum()<8: return E.sel_lv(i,pl)
        c,v=pl[ok],v[ok]; k=max(5,int(round(len(c)*keep_frac)))
        o=np.argsort(-v if high else v,kind='stable'); return E.sel_lv(i,c[o[:k]])
    return f
def rank_blend(*mats):
    def f(i,pl):
        rs=[]
        for M in mats:
            v=M[i,pl]; r=pd.Series(v).rank(pct=True).values; rs.append(r)
        sc=np.nanmean(np.vstack(rs),axis=0); ok=~np.isnan(sc)
        c,sc=pl[ok],sc[ok]; return c[np.argsort(sc,kind='stable')[:5]]
    return f
# 4 Amihud (|R| / 거래대금) 20일 평균, 낮을수록 유동
dv=C*V; dv[dv<=0]=np.nan
ami=pd.DataFrame(np.abs(R)/dv*1e9).rolling(20,min_periods=10).mean().values
comp(base,'4 Amihud: σ하위10→유동 상위5',E.run(two_stage(ami,10,True),start=S),res)
comp(base,'4 Amihud: σ하위15→유동 상위5',E.run(two_stage(ami,15,True),start=S),res)
comp(base,'4 Amihud: 비유동 1/3 제외→σ5',E.run(pre_filter(ami,2/3,high=False),start=S),res)
comp(base,'4 Amihud: 대조 σ하위10→비유동5',E.run(two_stage(ami,10,False),start=S),res)
# 5 자기상관(60일 lag1) — 추세지속형 선호
ac=RD.rolling(60,min_periods=40).corr(RD.shift(1)).values
comp(base,'5 AC60: σ하위10→AC 상위5',E.run(two_stage(ac,10,False),start=S),res)
comp(base,'5 AC60: AC 하위1/3 제외→σ5',E.run(pre_filter(ac,2/3,True),start=S),res)
comp(base,'5 AC60: 대조 σ하위10→AC 하위5',E.run(two_stage(ac,10,True),start=S),res)
ac120=RD.rolling(120,min_periods=80).corr(RD.shift(1)).values
comp(base,'5 AC120: σ하위10→AC 상위5',E.run(two_stage(ac120,10,False),start=S),res)
# 6 변동성 수축 σ5/σ60
ratio=s5/s60
for n1 in (8,10,15):
    comp(base,f'6 수축: σ하위{n1}→σ5/σ60 하위5',E.run(two_stage(ratio,n1,True),start=S),res)
comp(base,'6 수축: 대조 σ하위10→σ5/σ60 상위5',E.run(two_stage(ratio,10,False),start=S),res)
rng_=(E.P['high']-E.P['low'])/C
nr7=(rng_<=pd.DataFrame(rng_).rolling(7,min_periods=7).min().values+1e-12).astype(float)
comp(base,'6 NR7: σ하위10→NR7 우선',E.run(two_stage(-nr7+ratio*1e-6,10,True),start=S),res)
# 7 σ 앙상블
comp(base,'7 앙상블 σ10+σ20+σ60',E.run(rank_blend(s10,s20,s60),start=S),res)
comp(base,'7 앙상블 σ20+σ60',E.run(rank_blend(s20,s60),start=S),res)
comp(base,'7 앙상블 σ10+σ20',E.run(rank_blend(s10,s20),start=S),res)
s120=E.vol(120)
comp(base,'7 앙상블 σ20+σ60+σ120',E.run(rank_blend(s20,s60,s120),start=S),res)
# 8 상승일 거래량 비중 20일
up=(R>0).astype(float); up[np.isnan(R)]=np.nan
uv=pd.DataFrame(np.where(up==1,V,0.0)).rolling(20,min_periods=10).sum().values/pd.DataFrame(V).rolling(20,min_periods=10).sum().values
comp(base,'8 UVR: σ하위10→UVR 상위5',E.run(two_stage(uv,10,False),start=S),res)
comp(base,'8 UVR: UVR 하위1/3 제외→σ5',E.run(pre_filter(uv,2/3,True),start=S),res)
comp(base,'8 UVR: UVR 하위1/2 제외→σ5',E.run(pre_filter(uv,1/2,True),start=S),res)
comp(base,'8 UVR: 대조 σ하위10→UVR 하위5',E.run(two_stage(uv,10,True),start=S),res)
# 9 명목가격
comp(base,'9 가격: σ하위10→저가5',E.run(two_stage(C,10,True),start=S),res)
comp(base,'9 가격: σ하위10→고가5',E.run(two_stage(C,10,False),start=S),res)
comp(base,'9 가격: 1만5천원↑만→σ5',E.run(lambda i,pl:E.sel_lv(i,pl[C[i,pl]>=15000]) if (C[i,pl]>=15000).sum()>=5 else E.sel_lv(i,pl),start=S),res)
# 10 MDD60(60일 최고가 대비 현재 낙폭이 아니라 60일 구간 최대낙폭)
Cd=pd.DataFrame(C)
def mddroll(w):
    out=np.full(C.shape,np.nan)
    pk=Cd.rolling(w,min_periods=w//2)
    # 근사: 구간 내 '고점→이후 저점' 최대낙폭 = rolling apply (느림) 대신 현재가/구간고점 −1 의 구간 최소
    dd=(Cd/Cd.rolling(w,min_periods=w//2).max()-1)
    return dd.rolling(w,min_periods=w//2).min().values
m60=mddroll(60)
comp(base,'10 MDD60: pool→MDD 작은5',E.run(lambda i,pl:(lambda v,ok:pl[ok][np.argsort(-v[ok],kind="stable")[:5]])(m60[i,pl],~np.isnan(m60[i,pl])),start=S),res)
comp(base,'10 MDD60+σ20 랭크합',E.run(rank_blend(-m60,s20),start=S),res)
m120=mddroll(120)
comp(base,'10 MDD120+σ20 랭크합',E.run(rank_blend(-m120,s20),start=S),res)
json.dump(res,open(os.path.join(HERE,'res_xs.json'),'w'),default=float,indent=1)
print('DONE')
