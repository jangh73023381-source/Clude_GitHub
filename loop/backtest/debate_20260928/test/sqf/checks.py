# -*- coding: utf-8 -*-
"""SQF 선행 점검 A(σ 과소측정)·B(수익 평활화). r3_micro.md §3. SQF 규칙의 성과는 계산하지 않는다."""
import sys; sys.path.insert(0, '/home/claude/w/test')
from common import *
import statsmodels.api as sm
R = E.R; S20 = E.vol(20)
Vv = V
# Z20: 최근 20거래일(D 포함) 중 |종가→종가 수익률|<1e-9 또는 거래량=0 비율
zero = ((np.abs(R) < 1e-9) & ~np.isnan(R)) | (Vv == 0)
valid = ~np.isnan(R)
Z20 = pd.DataFrame(zero.astype(float)).rolling(20, min_periods=20).sum().values / 20
# 사후 σ(D+1..D+20)
Rf = pd.DataFrame(R).rolling(20, min_periods=15).std().values          # 행 t = t-19..t
SPOST = np.vstack([Rf[20:], np.full((20, E.N), np.nan)])               # 행 D = D+1..D+20
rows = []
for i in range(20, E.T - 3):
    pl = E.pool(i)
    if len(pl) < 5: continue
    for j in pl:
        rows.append((i, j, dates[i][:6], Z20[i, j], S20[i, j], SPOST[i, j], TV[i, j]))
df = pd.DataFrame(rows, columns=['i', 'j', 'ym', 'z', 's20', 'spost', 'tv'])
n0 = len(df)
df = df.dropna(); df = df[(df.s20 > 0) & (df.spost > 0)]
print(f'표본 pool30 종목-일 {n0} → 유효 {len(df)} (결측·σ=0 제외)')
df['lr'] = np.log(df.spost / df.s20)
# Z20 3분위(풀드) 기술통계
q = df.z.rank(pct=True, method='first')   # 동률(0) 다수 → 순서 기준 분할(기술통계 전용)
df['zt'] = np.where(q <= 1/3, 'low', np.where(q > 2/3, 'high', 'mid'))
print('Z20 분포: 평균 %.3f, 0 비율 %.1f%%, >0.25 비율 %.1f%%' % (df.z.mean(), (df.z == 0).mean()*100, (df.z > 0.25).mean()*100))
for t in ('low', 'mid', 'high'):
    s = df[df.zt == t]; print(f'  Z20 {t}: n={len(s)} Z평균 {s.z.mean():.3f} 비율(σ사후/σ20) 중앙 {np.exp(s.lr.median()):.3f} 기하평균 {np.exp(s.lr.mean()):.3f}')
print(f'  상위1/3 − 하위1/3 log비율 차 {df[df.zt=="high"].lr.mean()-df[df.zt=="low"].lr.mean():+.4f}')
# Z20 이 동률(0)이 많아 3분위가 치우칠 수 있음 → 보조: Z20=0 vs >0
print(f'  보조 Z20=0: {np.exp(df[df.z==0].lr.mean()):.3f} · Z20>0: {np.exp(df[df.z>0].lr.mean()):.3f}')

def reg(df, ctrl, how):
    X = pd.DataFrame({'z': df.z.values}, index=df.index)
    if how == 'pooled':
        qs = {c: pd.qcut(df[c], 5, labels=False, duplicates='drop') for c in ctrl}
    else:   # 일자별 pool 내 횡단면 5분위
        qs = {c: df.groupby('i')[c].transform(lambda x: pd.qcut(x.rank(method='first'), 5, labels=False)) for c in ctrl}
    for c in ctrl:
        X = X.join(pd.get_dummies(qs[c], prefix=c, drop_first=True).astype(float))
    X = sm.add_constant(X)
    m = sm.OLS(df.lr.values, X.values).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(df.ym)[0]})
    return m.params[1], m.tvalues[1], m.nobs
res = {}
for how in ('pooled', 'daily'):
    for ctrl in (['s20'], ['s20', 'tv']):
        b, t, nn = reg(df, ctrl, how); res[(how, tuple(ctrl))] = (b, t)
        print(f'점검A 회귀 [{how} 5분위, 통제={"+".join(ctrl)}] Z20 계수 {b:+.4f} (비율 ×{np.exp(b*0.25):.3f} @Z=0.25) 월클러스터 t={t:+.2f} n={int(nn)}')
passA = all(res[(h, ('s20', 'tv'))][1] >= 2.5 for h in ('pooled', 'daily'))
sOnly = all(res[(h, ('s20',))][1] >= 2.5 for h in ('pooled', 'daily'))
print(f'점검A 판정(거래대금 통제 포함, 두 5분위 정의 모두 t≥2.5): {"통과" if passA else "미달"} · σ20 통제만: {"t≥2.5" if sOnly else "미달"}')

# ---------- 점검 B ----------
base = {'LV': rets(picks(E.sel_lv), ('OO',)), 'MOM': rets(picks(E.sel_mom), ('OO',))}
ci = base['LV'].i.values
assert (ci == base['MOM'].i.values).all()
kb = E.fOO[ci, E.bi]
series = {'LV': base['LV'].OO.values, 'MOM': base['MOM'].OO.values, 'KODEX200': kb}
def acf(x, k):
    x = x - np.nanmean(x); return np.nansum(x[k:] * x[:-k]) / np.nansum(x * x)
def glm_ma2(x):
    from statsmodels.tsa.arima.model import ARIMA
    f = ARIMA(x, order=(0, 0, 2)).fit()
    b1, b2 = f.maparams; th = np.array([1, b1, b2]) / (1 + b1 + b2)
    return th, np.sqrt((th ** 2).sum())
out = {}
for k, x in series.items():
    x = np.asarray(x, float); ok = ~np.isnan(x); x = x[ok]
    rho = [acf(x, l) for l in range(1, 6)]
    sr_d = x.mean() / x.std(ddof=1); srA = sr_d * 252 ** .5
    q = 252; eta = q / np.sqrt(q + 2 * sum((q - l) * rho[l - 1] for l in range(1, 6)))
    th, fac = glm_ma2(x)
    out[k] = rho
    print(f'점검B {k:8s} ρ1 {rho[0]:+.3f} ρ2 {rho[1]:+.3f} ρ3..5 {rho[2]:+.3f} {rho[3]:+.3f} {rho[4]:+.3f} | Sharpe 원 {srA:.2f} · Lo/NW5 보정 {sr_d*eta:.2f} · GLM MA(2) θ={np.round(th,3).tolist()} 보정 {srA*fac:.2f}')
# ρ1 차 CI (쌍 블록 부트스트랩)
x, y = series['LV'], series['MOM']
P1 = np.c_[x[1:], x[:-1], y[1:], y[:-1]]
IDX = sbb_idx(len(P1))
def c(a, b):
    a = a - a.mean(1, keepdims=True); b = b - b.mean(1, keepdims=True)
    return (a * b).sum(1) / np.sqrt((a * a).sum(1) * (b * b).sum(1))
S = P1[IDX]
d = c(S[..., 0], S[..., 1]) - c(S[..., 2], S[..., 3])
print(f'점검B ρ1(LV)−ρ1(MOM) = {out["LV"][0]-out["MOM"][0]:+.3f}  90% CI [{np.quantile(d,.05):+.3f}, {np.quantile(d,.95):+.3f}] → {"LV Sharpe 일부 평활화" if np.quantile(d,.05)>0 else "평활화 증거 불충분"}')
# 정적 시가 감사
LVp = picks(E.sel_lv); L = liq(LVp)
dayst = np.mean([STATIC[i, p].any() for i, p in LVp.items()]) * 100
print(f'LV 7년 OO 정적 시가: 슬롯 {L["static"]:.1f}% · 1개 이상 정적 시가 픽이 있는 날 {dayst:.1f}% · 거래대금<1억 {L["lt1"]:.1f}% <5억 {L["lt5"]:.1f}% 중앙 {L["med_tv"]:.1f}억')
import pickle; pickle.dump(dict(passA=passA, res=res), open('/home/claude/w/test/sqf/checks.pkl', 'wb'))
