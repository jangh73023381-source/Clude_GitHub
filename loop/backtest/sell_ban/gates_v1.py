#!/usr/bin/env python3
"""5차 — V1(역배열 진입 → 최대 20거래일 매수 금지, 역배열 해소 시 조기 해제) 목록 단위 관문 검정 (조회 전용, 2026-09-11)."""
import json, time
import numpy as np, pandas as pd
import engine as E, signals as SG
from list_level import ban_state, X1, validT
t0 = time.time()
d = E.load(); I = E.indicators(d); C = I['C']; M, N = C.shape; dates = d['dates']; codes = d['codes']
R1raw = E.sh(C, -1) / C - 1


def prev1(b):
    p = np.zeros_like(b); p[:, 1:] = b[:, :-1]; return p


def v1_ban(ma_s, ma_m, ma_l, h=20):
    st = (ma_s < ma_m) & (ma_m < ma_l)
    st = np.nan_to_num(st, nan=0).astype(bool)
    sig = SG.cross(st)
    return ban_state(sig, h) & prev1(st)


def lst(B, XX=X1, h=20):
    B = B & ~np.isnan(XX); cnt = B.sum(axis=0)
    e = np.where(cnt > 0, np.where(B, XX, 0).sum(axis=0) / np.maximum(cnt, 1), np.nan)
    ok = ~np.isnan(e); y = e[ok] * 1e4; srt = np.sort(y); th = np.array_split(y, 3)
    return dict(bp=round(float(y.mean()), 2), t=round(float(E.nw_t(y, h)), 2), days=int(ok.sum()),
                avg_list=round(float(cnt[ok].mean()), 1), med=round(float(np.median(y)), 2),
                folds=[round(float(z.mean()), 2) for z in th], r5_3=round(float(srt[3:].mean()), 2),
                r5_10=round(float(srt[10:].mean()), 2), r5_20=round(float(srt[20:].mean()), 2)), e, cnt


MA = {w: E.rmean(C, w) for w in (3, 5, 7, 15, 20, 25, 50, 60, 90)}
B = v1_ban(MA[5], MA[20], MA[60])
res = {}
res['V1'], e, cnt = lst(B)
print('V1', res['V1'])
# 연도별
ok = ~np.isnan(e); yr = dates // 10000
res['years'] = {int(k): round(float(v.mean() * 1e4), 2) for k, v in pd.Series(e[ok]).groupby(yr[ok])}
print('years', res['years'])
# R1 고원 — 이평 길이 27조합 + 금지기간
g = {}
for a in (3, 5, 7):
    for b in (15, 20, 25):
        for c in (50, 60, 90):
            o, _, _ = lst(v1_ban(MA[a], MA[b], MA[c]))
            g[f'{a}/{b}/{c}'] = (o['bp'], o['t'])
res['r1_ma'] = g
print('R1 MA', ' '.join(f'{k}:{v[0]:+.1f}(t{v[1]:+.1f})' for k, v in g.items()))
g = {}
for h in (5, 10, 15, 20, 25, 30, 40, 60):
    st = np.nan_to_num((MA[5] < MA[20]) & (MA[20] < MA[60]), nan=0).astype(bool)
    o, _, _ = lst(ban_state(SG.cross(st), h) & prev1(st), h=h)
    g[h] = (o['bp'], o['t'], o['avg_list'])
res['r1_H'] = g
print('R1 H', g)
# R3 정의 교체 — EMA
ema = lambda w: pd.DataFrame(C.T).ewm(span=w, adjust=False, min_periods=w).mean().values.T
res['r3_ema'], _, _ = lst(v1_ban(ema(5), ema(20), ema(60)))
print('R3 EMA', res['r3_ema'])
# 통제 — mom20 5분위 · 종목 고정효과 · pool30 내부
pr = E.xrank(I['MOM20']); q = np.floor(np.clip(pr, 0, .9999) * 5)
XQ = np.full_like(R1raw, np.nan)
for t in range(N):
    r, qq = R1raw[:, t], q[:, t]; k = ~np.isnan(r) & ~np.isnan(qq)
    for j in range(5):
        s = k & (qq == j)
        if s.sum() >= 3:
            XQ[s, t] = r[s] - r[s].mean()
res['ctrl_momq5'], _, _ = lst(B, XQ)
FE = np.nanmean(X1, axis=1)
res['ctrl_fe'], _, _ = lst(B, X1 - FE[:, None])
rk = pd.DataFrame(-I['MOM20']).rank(axis=0, method='first').values
pool = rk <= 30
XP = np.full_like(R1raw, np.nan)
for t in range(N):
    s = pool[:, t] & ~np.isnan(R1raw[:, t])
    if s.sum() >= 10:
        XP[s, t] = R1raw[s, t] - R1raw[s, t].mean()
res['ctrl_pool30'], _, cntp = lst(B & pool, XP)
res['ctrl_pool30']['share_of_pool'] = round(float(cntp[cntp > 0].mean()), 2)
for k in ('ctrl_momq5', 'ctrl_fe', 'ctrl_pool30'):
    print(k, res[k])
# 국면
Bc = C[codes.index('069500')]; bear = Bc < pd.Series(Bc).rolling(60).mean().values
for lab, msk in [('bear', bear), ('bull', ~bear)]:
    o, _, _ = lst(B & msk[None, :]); res[f'regime_{lab}'] = o; print(lab, o)
# 무관 신호 대조군 — 금지 행렬을 종목별로 시차 이동(같은 빈도·다른 시점)
for k in (60, 120, 250):
    Bs = np.zeros_like(B); Bs[:, k:] = B[:, :-k]
    o, _, _ = lst(Bs); res[f'shift+{k}'] = o; print('shift', k, o['bp'], o['t'])
# R4 플라시보 — 날짜별 같은 수를 무작위 선택, 500회
rng = np.random.default_rng(20260911)
V = validT; Xz = np.where(V, X1, 0.0); kt = (B & V).sum(axis=0); days = kt > 0
sims = []
for _ in range(500):
    key = rng.random((M, N)); key[~V] = 2.0
    pick = key.argsort(axis=0).argsort(axis=0) < kt[None, :]
    ee = (np.where(pick, Xz, 0).sum(axis=0)[days] / kt[days]) * 1e4
    sims.append(ee.mean())
sims = np.array(sims)
res['placebo'] = dict(obs=res['V1']['bp'], sim_mean=round(float(sims.mean()), 3), sim_sd=round(float(sims.std()), 3),
                      p=float((sims <= res['V1']['bp']).mean()))
print('placebo', res['placebo'])
json.dump(res, open('gates_v1.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('done', f'{time.time()-t0:.1f}s')
