"""후보 정밀 검정: R1 창 격자 · R3 정의 교체 · 무관 신호 대조군 분포 · 연도별 · Rule BRD 위 증분."""
import numpy as np, pandas as pd
from signals import y, f, pct, lret, chg, align, netliq, naaim
from bt import P, perf, prep, rand_timing
import warnings; warnings.filterwarnings('ignore')
Y = pd.read_csv('raw/y_069500.KS.csv', dtype={'date': str}); Y.index = pd.to_datetime(Y.date); Y = Y[(Y.index >= '2010-01-01') & (Y.index <= '2026-10-28') & (Y.close > 0) & (Y.open > 0)]
def dsh(px, sig):
    r = prep(px)[0]; s = sig.reindex(px.index).values.astype(float); m = np.isfinite(s) & np.isfinite(r)
    i0 = np.argmax(m); m[:i0] = False; pos = 1 - s[m]; rr = r[m]
    return perf(pos * rr)[2] - perf(rr)[2], perf(pos * rr)[1] - perf(rr)[1], pos, rr, px.index[m]
def rise(s, n, lag, thr=80, up=True):
    q = pct(lret(s, n)) if (s > 0).all() else pct(chg(s, n))
    return align(q >= thr if up else q <= 100 - thr, lag, None)
def A(sig_on_native, lag, kd): return align(sig_on_native, lag, kd)
CANDS = {
 '10년물 상승': lambda n, kd: A(pct(chg(y('TNX'), n)) >= 80, 'yahoo', kd),
 '10년물 상승[R3 FRED DGS10]': lambda n, kd: A(pct(chg(f('DGS10'), n)) >= 80, 'fred', kd),
 '10년물 상승[R3 IEF 하락]': lambda n, kd: A(pct(lret(y('IEF'), n)) <= 20, 'yahoo', kd),
 '원/달러 상승': lambda n, kd: A(pct(lret(y('KRW_X'), n)) >= 80, 'yahoo', kd),
 '원/달러 상승[R3 FRED]': lambda n, kd: A(pct(lret(f('DEXKOUS'), n)) >= 80, 'fred', kd),
 '달러지수 상승': lambda n, kd: A(pct(lret(y('DX-Y.NYB'), n)) >= 80, 'yahoo', kd),
 '달러지수 상승[R3 EURUSD 하락]': lambda n, kd: A(pct(lret(y('EURUSD_X'), n)) <= 20, 'yahoo', kd),
 'NAAIM 과열': lambda n, kd: A(pct(naaim().rolling(max(1, n // 5)).mean(), 100) >= 80, 'naaim', kd),
 '순유동성 감소': lambda n, kd: A(pct(chg(netliq(), max(1, n // 5)), 100) <= 20, 'h41', kd),
}
NS = (10, 20, 40, 60)
rows = []
for nm, fn in CANDS.items():
    for n in NS:
        a7 = dsh(P, fn(n, P.index)); ae = dsh(Y, fn(n, Y.index))
        rows.append(dict(후보=nm, 창=n, ΔSh_7y=a7[0], ΔMDD_7y=a7[1], ΔSh_ext=ae[0], ΔMDD_ext=ae[1]))
G = pd.DataFrame(rows); pd.set_option('display.width', 250)
print(G.pivot(index='후보', columns='창', values='ΔSh_7y').round(3).to_string()); print(G.pivot(index='후보', columns='창', values='ΔSh_ext').round(3).to_string())
G.to_csv('result_grid.csv', index=False)
# 무관 신호 대조군: 농산물·축산 선물 6종 × 창 4 × 방향 2 = 48 규칙
NULL = []
for s in ('KC_F', 'SB_F', 'CC_F', 'OJ_F', 'ZW_F', 'LE_F'):
    px = y(s); px = px[px > 0]
    for n in NS:
        for up in (True, False):
            q = pct(lret(px, n)); sig = (q >= 80) if up else (q <= 20)
            NULL.append((s, n, up, dsh(P, A(sig, 'yahoo', P.index))[0], dsh(Y, A(sig, 'yahoo', Y.index))[0]))
N = pd.DataFrame(NULL, columns=['자산', '창', '상승', 'ΔSh_7y', 'ΔSh_ext']); N.to_csv('result_null.csv', index=False)
print('무관 대조군 48규칙 ΔSh 분위 7y', np.round(np.percentile(N.ΔSh_7y, [50, 90, 95, 100]), 3), ' ext', np.round(np.percentile(N.ΔSh_ext, [50, 90, 95, 100]), 3))
for c in ('ΔSh_7y', 'ΔSh_ext'):
    for nm in ('10년물 상승', '원/달러 상승', '달러지수 상승', 'NAAIM 과열', '순유동성 감소'):
        v = G[(G.후보 == nm) & (G.창 == 20)][c].iloc[0]; print(f'  {c} {nm} 20일 {v:+.3f} → 대조군 중 이보다 큰 비율 {(N[c] >= v).mean():.3f}')
# 연도별 (확장 표본, 창 20)
for nm in ('10년물 상라'.replace('라', '승'), '원/달러 상승', '달러지수 상승'):
    _, _, pos, rr, idx = dsh(Y, CANDS[nm](20, Y.index)); df = pd.DataFrame({'s': pos * rr, 'b': rr, 'cash': pos == 0}, idx)
    yr = df.groupby(df.index.year).apply(lambda g: pd.Series({'초과%': (np.prod(1 + g.s) - np.prod(1 + g.b)) * 100, '현금일%': g.cash.mean() * 100}))
    print(nm, '연도별 초과(%p):', ' '.join(f"{i}:{v:+.1f}" for i, v in yr['초과%'].items()), '| 양수', int((yr['초과%'] > 0).sum()), '/', len(yr))
# Rule BRD 위 증분 (7년)
B = pd.read_csv('breadth_b200.csv', dtype={'date': str}); B.index = pd.to_datetime(B.date)
brd_on = (B.b200 >= 50).astype(float).shift(1)          # D 폭 → D+1 종가 집행 (Rule BRD 1일 지연)
r = prep(P)[0]; kd = P.index; bo = brd_on.reindex(kd).values; m = np.isfinite(bo) & np.isfinite(r); rr = r[m]
sb = bo[m] * rr; print('\nRule BRD 단독 CAGR/MDD/Sh', np.round(perf(sb), 3), '| 보유', np.round(perf(rr), 3), '| 노출', round(bo[m].mean() * 100, 1))
for nm in ('10년물 상승', '원/달러 상승', '달러지수 상승', 'NAAIM 과열', '순유동성 감소'):
    ro = CANDS[nm](20, kd).reindex(kd).values.astype(float); ro = np.where(np.isfinite(ro), ro, 0)[m]
    pos = bo[m] * (1 - ro); st = pos * rr
    rs = np.array([perf(rand_timing((1 - ro).astype(int)) * bo[m] * rr)[2] for _ in range(300)])
    k = len(rr) // 3; fd = [perf(st[i*k:(i+1)*k])[2] - perf(sb[i*k:(i+1)*k])[2] for i in range(3)]
    print(f'  BRD∧not {nm}: CAGR/MDD/Sh', np.round(perf(st), 3), f'ΔSh vs BRD {perf(st)[2] - perf(sb)[2]:+.3f}', f'p(같은 노출 무작위 겹침) {(rs >= perf(st)[2]).mean():.3f}',
          'fold', '/'.join(f'{x:+.2f}' for x in fd), f'| 현금일 겹침률 {((ro == 1) & (bo[m] == 0)).sum() / max((ro == 1).sum(), 1):.2f}')
