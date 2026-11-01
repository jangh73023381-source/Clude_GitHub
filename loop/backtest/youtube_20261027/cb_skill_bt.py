"""종가 베팅 추천 스킬(kr-daily-briefing-picks-opus:closing-bet-picks) 규칙 일봉 재현 백테스트 — 2026-10-27 사용자 요청 점검.
재현 못 한 조건: 외국인·기관 순매수, 익일 카탈리스트(정성), 미국 선물·환율 게이트, 시총 3,000억(→20일 평균 거래대금 100억으로 대체), 영업이익 적자·악재공시(현재 상장사 재무만 있어 미적용).
개별주 dense 7.7년(비수정, ±31% 보유구간 제외) · ETF 7년 패널. 비용: 개별주 왕복 0.25%, ETF 0.05%.
청산 모형(D=베팅일 종가 C 매수):
 E0 익일 시가 전량.
 E1 스킬 원안: 익일 시가 ≤ C(갭하락)→시가 전량 손절 / 갭상승→절반 시가 익절, 나머지 절반은 목표 C×(1+tg)·손절 C×(1−sl) (D+1, D+2 고저가로 판정,
    같은 날 둘 다 닿으면 손절 먼저=보수) 미도달 시 D+2 종가.
 E2 절반 익절 없이: 갭하락 시가 손절, 그 외 목표·손절·D+2 종가.
기준선: 같은 날 유동 유니버스 전 종목에 같은 청산 모형을 적용한 평균(= '아무거나 종가에 샀을 때')."""
import sys, numpy as np, pandas as pd
from gh_stats import nw_se
SPLIT = 20230630


def exits(O, H, L, C, tg, sl):
    """전 종목·전 날짜 행렬에 청산 모형 적용 → dict(E0,E1,E2) (%, 비용 전). 입력 (T,N)."""
    sh = lambda A, d: np.vstack([A[d:], np.full((d,) + A.shape[1:], np.nan)])
    O1, H1, L1, C1 = sh(O, 1), sh(H, 1), sh(L, 1), sh(C, 1); O2, H2, L2, C2 = sh(O, 2), sh(H, 2), sh(L, 2), sh(C, 2)
    up, dn = C * (1 + tg), C * (1 - sl)
    E0 = O1 / C - 1
    # 나머지 포지션(갭상승 이후) 경로: D+1 장중(시가 이후) → D+2
    def rest(start_open):
        r = np.full(C.shape, np.nan)
        # D+1: 시가가 이미 목표 이상이면 시가에 목표 이상 체결(시가), 손절 이하면 시가
        hit_o_up = O1 >= up; hit_o_dn = O1 <= dn
        s1 = L1 <= dn; u1 = H1 >= up
        s2 = L2 <= dn; u2 = H2 >= up; o2u = O2 >= up; o2d = O2 <= dn
        r = np.where(hit_o_up, O1 / C - 1, np.where(hit_o_dn, O1 / C - 1,
            np.where(s1, -sl, np.where(u1, tg,
            np.where(o2u, O2 / C - 1, np.where(o2d, O2 / C - 1,
            np.where(s2, -sl, np.where(u2, tg, C2 / C - 1))))))))
        return r
    R = rest(True)
    gapdn = O1 <= C
    E1 = np.where(gapdn, O1 / C - 1, 0.5 * (O1 / C - 1) + 0.5 * R)
    E2 = np.where(gapdn, O1 / C - 1, R)
    return {k: v * 100 for k, v in dict(E0=E0, E1=E1, E2=E2).items()}


def report(tag, sig, E, LIQ, dates, bad2, cost, top=None, rankv=None, kx=None):
    out = []
    pick = sig.copy()
    if top is not None:
        rk = pd.DataFrame(np.where(sig, rankv, np.nan)).rank(axis=1, ascending=False).values
        pick = sig & (rk <= top)
    for k, M in E.items():
        M = np.where(bad2, np.nan, M)
        um = np.nanmean(np.where(LIQ & np.isfinite(M), M, np.nan), 1)
        t, j = np.where(pick & np.isfinite(M))
        if len(t) < 50: continue
        v = M[t, j]; d = pd.DataFrame({'t': t, 'v': v, 'ex': v - um[t]}).groupby('t').mean().sort_index()
        te = d[dates[d.index] > SPLIT]; n = len(d); k3 = n // 3; srt = np.sort(d.ex.values)[::-1]
        yr = pd.Series(d.v.values - cost, index=dates[d.index] // 10000).groupby(level=0).mean()
        o = dict(대상=tag, 청산=k, 건수=len(t), 신호일=n, 건평균=v.mean(), 비용후=v.mean() - cost, 승률=(v > 0).mean() * 100, 중앙=np.median(v),
                 유니버스대비=d.ex.mean(), t=d.ex.mean() / nw_se(d.ex.values, 1), fold='/'.join(f'{d.ex.values[i*k3:(i+1)*k3].mean():.2f}' for i in range(3)),
                 뒤_비용후=te.v.mean() - cost, 뒤_대비=te.ex.mean(), 상위5pct제거=srt[max(1, int(n * .05)):].mean(),
                 최저연도=f'{yr.idxmin()}:{yr.min():.2f}', 양수연도=f'{(yr > 0).sum()}/{len(yr)}')
        out.append(o)
    return out


# ================= 개별주 =================
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); O, H, L, C, V = (Z[k].astype(float) for k in 'OHLCV'); bench = Z['bench'].astype(float)
T, N = C.shape; VAL = C * V
shf = lambda A, d: np.vstack([np.full((d, N), np.nan), A[:-d]])
with np.errstate(all='ignore'):
    cs = np.cumsum(np.nan_to_num(VAL), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
    val5p = np.full((T, N), np.nan); val5p[6:] = (cs[5:-1] - cs[:-6]) / 5          # 직전 5일 평균(당일 제외)
    LIQ = (C >= 1000) & (val20 >= 1e9)
    r1 = C / shf(C, 1) - 1; chg = r1 * 100; r5 = C / shf(C, 5) - 1
    bad = np.abs(r1) > 0.31
    bad2 = np.vstack([bad[1:], np.zeros((1, N), bool)]) | np.vstack([bad[2:], np.zeros((2, N), bool)])
    kchg = np.r_[np.nan, bench[1:] / bench[:-1] - 1] * 100
    gate = (kchg > -2)[:, None]
    hi20 = shf(pd.DataFrame(H).rolling(20).max().values, 1)
    surge = VAL / val5p
    core = gate & (chg >= 3) & (chg < 25) & (C >= H * 0.98) & (VAL >= 1e10) & (val5p >= 1e10) & (surge >= 1.5) & (np.abs(r5) < 0.25) & LIQ
    core[:260] = False
    E = exits(O, H, L, C, 0.05, 0.04)
rows = []
rows += report('단일 · 스킬 핵심조건 전체', core, E, LIQ, dates, bad2, 0.25)
rows += report('단일 · 스킬 핵심조건 상위5(거래대금 급증 순)', core, E, LIQ, dates, bad2, 0.25, top=5, rankv=surge)
rows += report('단일 · + 직전 20일 고점 돌파', core & (C > hi20), E, LIQ, dates, bad2, 0.25)
rows += report('단일 · 상승 3~10%만', core & (chg < 10), E, LIQ, dates, bad2, 0.25)
rows += report('단일 · 상승 10~25%만', core & (chg >= 10), E, LIQ, dates, bad2, 0.25)
# 대조: 상한가권 포함(스킬이 제외하는 것) — 체결 불가 참고
with np.errstate(all='ignore'):
    lim = gate & (chg >= 25) & (C >= H * 0.98) & (VAL >= 1e10) & LIQ; lim[:260] = False
rows += report('(참고·체결불가) 상승 25%↑ 상한가권', lim, E, LIQ, dates, bad2, 0.25)
# 대안 청산 격자(E2 목표/손절) — 상위5
for tg, sl in ((0.03, 0.03), (0.05, 0.05), (0.08, 0.04), (0.03, 0.02)):
    with np.errstate(all='ignore'):
        Eg = exits(O, H, L, C, tg, sl)
    rr = report(f'단일 상위5 · 목표{int(tg*100)}/손절{int(sl*100)}', core, {'E2': Eg['E2'], 'E1': Eg['E1']}, LIQ, dates, bad2, 0.25, top=5, rankv=surge)
    rows += rr
# ================= ETF =================
sys.path.insert(0, '/mnt/user-data/uploads/loop/references/scripts')
from universe_filters import is_cash
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/panel_ohlc_long.csv', dtype={'code': str})
names = p.drop_duplicates('code', keep='last').set_index('code').name
P = {k: p.pivot(index='date', columns='code', values=k) for k in ('open', 'high', 'low', 'close', 'volume')}
ed = P['close'].index.values.astype(int); codes = P['close'].columns
okc = np.array([not is_cash(names[c]) for c in codes])
eO, eH, eL, eC, eV = (P[k].values[:, okc].astype(float) for k in ('open', 'high', 'low', 'close', 'volume'))
lev = np.array(['레버리지' in names[c] or '2X' in names[c].upper() for c in codes[okc]])
inv = np.array(['인버스' in names[c] for c in codes[okc]])
eT, eN = eC.shape; eVAL = eC * eV
eshf = lambda A, d: np.vstack([np.full((d, eN), np.nan), A[:-d]])
with np.errstate(all='ignore'):
    ecs = np.cumsum(np.nan_to_num(eVAL), 0); e5 = np.full((eT, eN), np.nan); e5[6:] = (ecs[5:-1] - ecs[:-6]) / 5
    e20 = np.full((eT, eN), np.nan); e20[20:] = (ecs[20:] - ecs[:-20]) / 20
    eLIQ = (e20 >= 1e9) & ~inv[None, :]
    echg = (eC / eshf(eC, 1) - 1) * 100
    k200 = P['close']['069500'].values.astype(float); egate = (np.r_[np.nan, k200[1:] / k200[:-1] - 1] * 100 > -2)[:, None]
    esurge = eVAL / e5
    ecore = egate & (echg >= 1.5) & (eC >= eH * 0.98) & (eVAL >= 5e9) & (e5 >= 5e9) & (esurge >= 1.5) & eLIQ & ~inv[None, :]
    ecore[:260] = False
    eE = exits(eO, eH, eL, eC, 0.03, 0.03)
ebad = np.zeros_like(ecore)
rows += report('ETF · 스킬 핵심조건 전체', ecore, eE, eLIQ, ed, ebad, 0.05)
rows += report('ETF · 스킬 상위5(거래대금 급증 순)', ecore, eE, eLIQ, ed, ebad, 0.05, top=5, rankv=esurge)
rows += report('ETF · 레버리지 제외', ecore & ~lev[None, :], eE, eLIQ, ed, ebad, 0.05)
o = pd.DataFrame(rows); pd.set_option('display.width', 340); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 32)
print('개별주', dates[260], '~', dates[-3], '| ETF', ed[260], '~', ed[-3])
print(o.round(2).to_string(index=False)); o.to_csv('cb_skill_bt.csv', index=False)
