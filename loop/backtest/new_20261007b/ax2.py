"""신축 2: 국면 전환형 — DISP(횡단면 분산도) · RVOL(지수 실현변동성 백분위) · HMM(2상태) · 정기변경 캘린더
LV↔MOM 일별 전환. 귀무 = 국면 라벨 원형 이동(빈도·지속 보존) 200회."""
from common import *
from hmmlearn.hmm import GaussianHMM
E,base=setup(); res={}; C,R=E.C,E.R
mom=E.run(lambda i,pl:E.sel_mom(i,pl),start=S)
B=base.set_index('date'); M=mom.set_index('date').reindex(B.index)
idx=[E.dates.index(d) for d in B.index]
def mix(mask):
    df=B[['A','OO']].copy()
    for k in ('A','OO'): df[k]=np.where(mask,M[k].values,B[k].values)
    return df.reset_index()
def null(mask,name,n=200):
    real=comp(base,name,mix(mask),res)
    rng=np.random.default_rng(7); sims=[]
    for s in range(n):
        sh=np.roll(mask,rng.integers(60,len(mask)-60)); d=mix(sh)
        sims.append((np.nanmean(d.OO-B.OO.values),prof(d.OO)['sharpe'],np.nanmean(d.A-B.A.values)))
    sims=np.array(sims); p=dict(dO=float(np.mean(sims[:,0]>=real['OO']['diff'])),shO=float(np.mean(sims[:,1]>=real['OO']['sh'])),dA=float(np.mean(sims[:,2]>=real['A']['diff'])))
    res[name]['null_p']=p; res[name]['on_frac']=float(np.mean(mask))
    print(f"   ↳ MOM 사용 {np.mean(mask)*100:.0f}% · 귀무(원형이동) p: dOO {p['dO']:.3f} ShOO {p['shO']:.3f} dA {p['dA']:.3f}",flush=True)
print('MOM 단독', prof(mom.OO))
# DISP: pool 바깥 포함 eligible mom20 횡단면 표준편차, 과거 252일 백분위
disp=np.array([np.nanstd(E.mom[i][E.ok[i]]) for i in range(E.T)])
dp=pd.Series(disp).rolling(252,min_periods=120).rank(pct=True).values
for th in (0.5,0.7):
    null(dp[idx]>=th,f'6 DISP 상위{int((1-th)*100)}%→MOM',)
    null(dp[idx]<1-th,f'6 DISP 하위{int((1-th)*100)}%→MOM')
# RVOL: KODEX200 σ20 의 252일 백분위
bv=pd.Series(R[:,E.bi]).rolling(20,min_periods=15).std(); bp=bv.rolling(252,min_periods=120).rank(pct=True).values
for th in (0.5,0.7):
    null(bp[idx]<1-th,f'7 RVOL 하위{int((1-th)*100)}%(저변동장)→MOM')
    null(bp[idx]>=th,f'7 RVOL 상위{int((1-th)*100)}%(고변동장)→MOM')
# HMM 2상태: 워크포워드(연 1회 재적합, 확장창, 필터확률만 사용 — 룩어헤드 없음)
r=np.nan_to_num(R[:,E.bi]); st=np.full(E.T,np.nan)
for y0 in range(252,E.T,252):
    m=GaussianHMM(2,covariance_type='diag',n_iter=200,random_state=0).fit(r[:y0].reshape(-1,1))
    hi=int(np.argmax(m.covars_.ravel()))
    for t in range(y0,min(y0+252,E.T)):
        pr=m.predict_proba(r[max(0,t-250):t+1].reshape(-1,1))[-1]   # 과거 250일 창에서 필터 확률(t까지)
        st[t]=pr[hi]
null(st[idx]<0.5,'8 HMM 저변동상태→MOM')
null(st[idx]>=0.5,'8 HMM 고변동상태→MOM')
# KOSPI200 정기변경: 6·12월 둘째 목요일(선물만기) 다음 거래일 반영. 창 [-5,+5] 거래일 현금(벤치) 대신 MOM / 현금
ds=pd.to_datetime(B.index)
ev=[]
for y in range(2019,2027):
    for mth in (6,12):
        d=pd.Timestamp(y,mth,1); th=[d+pd.Timedelta(days=k) for k in range(31) if (d+pd.Timedelta(days=k)).month==mth and (d+pd.Timedelta(days=k)).weekday()==3][1]
        ev.append(th)
pos=np.array([np.searchsorted(ds,e) for e in ev]); win=np.zeros(len(ds),bool)
for p_ in pos:
    if 0<p_<len(ds): win[max(0,p_-5):p_+6]=True
null(win,'9 정기변경 ±5일→MOM')
cash=B[['A','OO']].copy(); cash.loc[win,['A','OO']]=0.0
comp(base,'9 정기변경 ±5일→현금',cash.reset_index(),res)
json.dump(res,open('res_ax2.json','w'),default=float,indent=1); print('DONE')
