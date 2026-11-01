"""과적합 지표: (A) [6-1] 변형 가족 CSCV-PBO + Rule LV Deflated Sharpe (B) KODEX200 타이밍 shadow(IBS·FIA·CRU) DSR.
DSR = P(진짜 SR > SR*), SR* = 귀무 시도들의 Sharpe 평균 + 표준편차×E[max of N] (Bailey & López de Prado 2014). 일 단위 SR, 왜도·첨도 보정."""
import os,sys,itertools,numpy as np,pandas as pd
from math import erf,sqrt,e
from statistics import NormalDist
N01=NormalDist()
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
def sr(x): x=np.asarray(x,float); x=x[~np.isnan(x)]; return x.mean()/x.std(ddof=1)
def emax(N):
    g=0.5772156649; return (1-g)*N01.inv_cdf(1-1/N)+g*N01.inv_cdf(1-1/(N*e))
def dsr(x,sr_star):
    x=np.asarray(x,float); x=x[~np.isnan(x)]; T=len(x); s=sr(x)
    g3=((x-x.mean())**3).mean()/x.std()**3; g4=((x-x.mean())**4).mean()/x.std()**4
    z=(s-sr_star)*sqrt(T-1)/sqrt(1-g3*s+(g4-1)/4*s*s); return N01.cdf(z)
A=lambda s:s*sqrt(250)
# ---------- (A)
M=pd.read_csv(os.path.join(HERE,'fam_OO.csv'),index_col=0)
S=M.apply(sr); print(f'(A) [6-1] 변형 {M.shape[1]}개 · {M.shape[0]}일 · 연환산 Sharpe 평균 {A(S.mean()):.2f} 표준편차 {A(S.std()):.2f} 최고 {S.idxmax()} {A(S.max()):.2f}')
lv='LV p30 σ20 n5'; print(f'    Rule LV(현행) Sharpe {A(S[lv]):.2f} · 가족 내 순위 {int((S>S[lv]).sum())+1}/{len(S)}')
for N in (M.shape[1],843):
    ss=S.mean()+S.std()*emax(N); print(f'    DSR(N={N}): SR* 연 {A(ss):.2f} → DSR {dsr(M[lv],ss):.3f}')
# 기준을 '모멘텀 상위5(=저변동 정렬 없음)'로: LV 의 Sharpe 가 이 정도 가족의 운 좋은 최대치를 넘는가 — 위에서 처리. PSR(>MOM20 top5)
print(f"    PSR(LV Sharpe > MOM20 top5 Sharpe {A(S['MOM20 top5']):.2f}) = {dsr(M[lv],S['MOM20 top5']):.3f}")
# CSCV PBO
Sg=16; T=len(M); idx=np.array_split(np.arange(T),Sg); logits=[]
for comb in itertools.combinations(range(Sg),Sg//2):
    tr=np.concatenate([idx[j] for j in comb]); te=np.concatenate([idx[j] for j in range(Sg) if j not in comb])
    s_tr=M.iloc[tr].apply(sr); s_te=M.iloc[te].apply(sr); best=s_tr.idxmax()
    rk=(s_te.rank()[best])/(len(s_te)+1); logits.append(np.log(rk/(1-rk)))
logits=np.array(logits); print(f'    PBO(CSCV, S=16, {len(logits)}조합) = {(logits<=0).mean():.3f}  (학습 1등이 검증에서 중앙 이하로 떨어질 확률)')
# 학습 1등이 무엇이었나
# ---------- (B) KODEX200 타이밍
px=pd.read_csv(os.path.join(BT,'panel_ohlc_long.csv'),dtype={'code':str,'date':str}); k=px[px.code=='069500'].sort_values('date').reset_index(drop=True)
k['r']=k.close.pct_change().shift(-1)*100          # D 종가 → D+1 종가
k['ibs']=(k.close-k.low)/(k.high-k.low).replace(0,np.nan)
st=0; pos=[]
for x in k.ibs.fillna(.5):
    if st==0 and x<0.2: st=1
    elif st==1 and x>0.8: st=0
    pos.append(st)
k['ibs_pos']=pos
# FIA: 외국인 강매도(확장창 하위20%) 다음 날 장중 회피 → D→D+1 수익 = 갭만
f=pd.read_csv(os.path.join(BT,'foreign_mkt','merged.csv'),dtype={'date':str})[['date','foreign','kospi']]; f['fn']=f.foreign/f.kospi
f['sig']=(f.fn<=f.fn.expanding(120).quantile(.2).shift(1)).astype(int)
k=k.merge(f[['date','sig']],on='date',how='left'); k['sig']=k.sig.fillna(0)
k['gap1']=(k.open.shift(-1)/k.close-1)*100
# CRU: 신용 z250(D-2) 확장창 20/80
c=pd.read_csv(os.path.join(BT,'credit_20261022','merged.csv'),dtype={'date':str}); z=(c.credit-c.credit.rolling(250).mean())/c.credit.rolling(250).std(); s=z.shift(2)
ql=s.expanding(500).quantile(.2).shift(1); qh=s.expanding(500).quantile(.8).shift(1); c['cru']=np.where((s>ql)&(s<qh),.5,1.0); c.loc[ql.isna(),'cru']=np.nan
k=k.merge(c[['date','cru']],on='date',how='left')
k=k[k.date>='20200401'].dropna(subset=['r']).reset_index(drop=True)
rules={'IBS (N=31)':(k.ibs_pos*k.r, k.ibs_pos.values, 31),
       'FIA (N=5)':(np.where(k.sig==1,k.gap1,k.r), None, 5),
       'CRU (N=12)':(k.cru*k.r, k.cru.values, 12)}
bh=k.r.values; print(f'\n(B) KODEX200 타이밍 {k.date.iloc[0]}~{k.date.iloc[-1]} {len(k)}일 · 보유 Sharpe {A(sr(bh)):.2f}')
rng=np.random.default_rng(0)
for nm,(x,expo,N) in rules.items():
    x=np.asarray(x,float); ok=~np.isnan(x)
    # 귀무: 같은 노출 시계열을 원형으로 밀어 붙인 무작위 타이밍 300회 (FIA 는 신호열을 밀기)
    sims=[]
    for _ in range(300):
        sh=rng.integers(250,len(k)-250)
        if nm.startswith('FIA'):
            sg=np.roll(k.sig.values,sh); y=np.where(sg==1,k.gap1,k.r)
        else:
            y=np.roll(expo,sh)*k.r.values
        sims.append(sr(y[ok]))
    sims=np.array(sims); ss=sims.mean()+sims.std()*emax(N)
    print(f"    {nm:12s} Sharpe {A(sr(x[ok])):.2f} · 무작위 타이밍 평균 {A(sims.mean()):.2f}±{A(sims.std()):.2f} · SR*(N) {A(ss):.2f} → DSR {dsr(x[ok],ss):.3f} | N=843 이면 SR* {A(sims.mean()+sims.std()*emax(843)):.2f} DSR {dsr(x[ok],sims.mean()+sims.std()*emax(843)):.3f}")
