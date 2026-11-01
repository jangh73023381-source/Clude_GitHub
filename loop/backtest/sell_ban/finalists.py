#!/usr/bin/env python3
"""2차 — 최종 후보 관문 검정 (조회 전용, 2026-09-11).
후보(1차에서 H=20 · fold 3/3 · R5 상위3일 제거 후에도 음수인 추세붕괴 계열, 커버리지 50% 미만):
  F14 역배열 진입 · F4b MA60 이탈+MA60 하락 · F3c 데드크로스 20/60 · F13 MA20 하락전환+종가<MA20 · F2c MA20 이탈+MA20 하락
참조: F12 mom20 하위 10% 진입(순수 모멘텀) — 후보가 모멘텀 순위 이상의 정보를 갖는지 비교용.
"""
import os, sys, json, time
import numpy as np, pandas as pd
import engine as E, signals as SG
t0 = time.time()
d = E.load(); I = E.indicators(d); C = I['C']; M, N = C.shape
dates = d['dates']; codes = d['codes']
S = SG.build(I)
FIN = ['F14 역배열 진입', 'F4b MA60 이탈+MA60 하락', 'F3c 데드크로스 20/60',
       'F13 MA20 하락전환+종가<MA20', 'F2c MA20 이탈+MA20 하락', 'F12 mom20 하위 10% 진입']
H = 20
R, X = E.fwd(C, H)
valid = ~np.isnan(X)
pr = E.xrank(I['MOM20'])
mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
res = {}


def ev_mean(sig, XX):
    ok = sig & ~np.isnan(XX)
    return float(np.nanmean(XX[ok])) * 100 if ok.sum() else np.nan, int(ok.sum())


if mode in ('all', 'path'):
    # 1) 누적 초과 경로 H=1..60 → 금지 기간 결정
    out = {}
    for name in FIN:
        row = []
        for h in (1, 2, 3, 5, 10, 15, 20, 25, 30, 40, 50, 60):
            _, XX = E.fwd(C, h)
            row.append((h, ev_mean(S[name], XX)[0]))
        out[name] = row
        print(name, ' '.join(f'{h}:{v:+.2f}' for h, v in row))
    res['path'] = out

if mode in ('all', 'ctrl'):
    # 2) 통제 — 종목 고정효과 · 시차 이동 신호 · mom20 5분위/10분위 · pool30 내부 · 국면
    FE = np.nanmean(X, axis=1)
    q5 = np.floor(np.clip(pr, 0, .9999) * 5); q10 = np.floor(np.clip(pr, 0, .9999) * 10)
    def qadj(q, k):
        XQ = np.full_like(R, np.nan)
        for t in range(N):
            r, qq = R[:, t], q[:, t]; ok = ~np.isnan(r) & ~np.isnan(qq)
            for j in range(k):
                s = ok & (qq == j)
                if s.sum() >= 3:
                    XQ[s, t] = r[s] - r[s].mean()
        return XQ
    XQ5, XQ10 = qadj(q5, 5), qadj(q10, 10)
    # pool30: D 기준 mom20 순위 상위 30 (절대 순위)
    rk = pd.DataFrame(-I['MOM20']).rank(axis=0, method='first').values
    pool = rk <= 30
    XP = np.full_like(R, np.nan)
    for t in range(N):
        s = pool[:, t] & ~np.isnan(R[:, t])
        if s.sum() >= 10:
            XP[s, t] = R[s, t] - R[s, t].mean()
    B = C[codes.index('069500')]; bm = pd.Series(B).rolling(60).mean().values
    bear = (B < bm)[None, :] & np.ones((M, 1), bool)
    out = {}
    for name in FIN:
        sg = S[name]
        o = dict(base=ev_mean(sg, X), fe=ev_mean(sg, X - FE[:, None]), q5=ev_mean(sg, XQ5), q10=ev_mean(sg, XQ10),
                 pool30=ev_mean(sg & pool, XP), bear=ev_mean(sg & bear, X), bull=ev_mean(sg & ~bear, X))
        for k in (60, 120, 250):
            sft = np.zeros_like(sg); sft[:, k:] = sg[:, :-k]
            o[f'shift+{k}'] = ev_mean(sft, X)
        yrs = pd.Series(X[sg & valid] * 100).groupby((dates[np.where(sg & valid)[1]] // 10000)).agg(['mean', 'count'])
        o['years'] = {int(y): (round(r['mean'], 2), int(r['count'])) for y, r in yrs.iterrows()}
        out[name] = o
        print(name, {k: (round(v[0], 2), v[1]) if isinstance(v, tuple) else v for k, v in o.items()})
    res['ctrl'] = out

if mode in ('all', 'placebo'):
    # 3) R4 — 날짜 내 셔플 플라시보 500회: 같은 날짜에 같은 수의 종목을 무작위로 뽑는다
    rng = np.random.default_rng(20260911)
    out = {}
    for name in FIN:
        sg = S[name] & valid
        k_t = sg.sum(axis=0); obs = np.nanmean(X[sg]) * 100
        Xz = np.where(valid, X, 0.0); cnt = k_t.sum()
        sims = []
        for _ in range(500):
            key = rng.random((M, N)); key[~valid] = 2.0
            rank = key.argsort(axis=0).argsort(axis=0)
            pick = rank < k_t[None, :]
            sims.append(Xz[pick].sum() / cnt * 100)
        sims = np.array(sims)
        out[name] = dict(obs=obs, sim_mean=sims.mean(), sim_sd=sims.std(), p=float((sims <= obs).mean()))
        print(name, {k: round(v, 4) for k, v in out[name].items()}, f'{time.time()-t0:.0f}s', flush=True)
    res['placebo'] = out

if mode in ('all', 'r1'):
    # 4) R1 고원 — 이동평균 길이·기울기 룩백 격자
    sh, cross = E.sh, SG.cross
    out = {}
    g = {}
    for a in (3, 5, 7):
        for b in (15, 20, 25):
            for c in (50, 60, 90):
                ma = lambda w: E.rmean(C, w)
                g[(a, b, c)] = ev_mean(np.nan_to_num(cross((ma(a) < ma(b)) & (ma(b) < ma(c))), nan=0).astype(bool), X)
    out['F14 (a,b,c)'] = {str(k): v for k, v in g.items()}
    g = {}
    for w in (50, 60, 90):
        for lb in (3, 5, 10):
            ma = E.rmean(C, w)
            s = (C < ma) & (sh(C, 1) >= sh(ma, 1)) & (ma < sh(ma, lb))
            g[(w, lb)] = ev_mean(np.nan_to_num(s, nan=0).astype(bool), X)
    out['F4b (MA,slope)'] = {str(k): v for k, v in g.items()}
    g = {}
    for a in (15, 20, 25):
        for b in (50, 60, 90):
            g[(a, b)] = ev_mean(np.nan_to_num(cross(E.rmean(C, a) < E.rmean(C, b)), nan=0).astype(bool), X)
    out['F3c (fast,slow)'] = {str(k): v for k, v in g.items()}
    g = {}
    for w in (15, 20, 25):
        for lb in (1, 3, 5):
            ma = E.rmean(C, w)
            s = (C < ma) & (sh(C, 1) >= sh(ma, 1)) & (ma < sh(ma, lb))
            g[(w, lb)] = ev_mean(np.nan_to_num(s, nan=0).astype(bool), X)
    out['F2c (MA,slope)'] = {str(k): v for k, v in g.items()}
    for kk, vv in out.items():
        print(kk, ' '.join(f'{k}:{v[0]:+.2f}(n{v[1]})' for k, v in vv.items()))
    res['r1'] = out

json.dump(res, open(os.path.join(E.HERE, f'finalists_{mode}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
print('done', f'{time.time()-t0:.1f}s')
