"""잔여 확인: 2026 제외 · BRD 위 달러/금리 R1 창·R3·R5·무관 대조군."""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from bt2 import CANDS, dsh, P, Y, perf, prep, A, y, pct, lret, NS
P25 = P[P.index < '2026-01-01']; Y25 = Y[Y.index < '2026-01-01']
for nm in ('10년물 상승', '원/달러 상승', '달러지수 상승'):
    print(f'{nm} 2026 제외 ΔSh 7y', round(dsh(P25, CANDS[nm](20, P25.index))[0], 3), ' ext', round(dsh(Y25, CANDS[nm](20, Y25.index))[0], 3))
B = pd.read_csv('breadth_b200.csv', dtype={'date': str}); B.index = pd.to_datetime(B.date)
bo_all = (B.b200 >= 50).astype(float).shift(1)
def on_brd(sig, px=P):
    r = prep(px)[0]; kd = px.index; bo = bo_all.reindex(kd).values; m = np.isfinite(bo) & np.isfinite(r)
    ro = sig.reindex(kd).values.astype(float); ro = np.where(np.isfinite(ro), ro, 0)[m]; rr = r[m]
    sb = bo[m] * rr; st = bo[m] * (1 - ro) * rr; base = perf(sb)[2]
    d = st - sb; o = np.argsort(-d); r5 = []
    for k in (3, 5, 10):
        s2 = st.copy(); s2[o[:k]] = sb[o[:k]]; r5.append(perf(s2)[2] - base)
    return perf(st)[2] - base, r5
for nm in ('달러지수 상승', '달러지수 상승[R3 EURUSD 하락]', '10년물 상승', '10년물 상승[R3 IEF 하락]', '원/달러 상승'):
    out = [on_brd(CANDS[nm](n, P.index)) for n in NS]
    print(f'BRD∧not {nm}: 창10/20/40/60 ΔSh', ' '.join(f'{a:+.3f}' for a, _ in out), '| 창20 R5 상위3/5/10일 제거', ' '.join(f'{x:+.3f}' for x in out[1][1]))
# 무관 대조군을 BRD 위에 얹은 분포
NULL = []
for s in ('KC_F', 'SB_F', 'CC_F', 'OJ_F', 'ZW_F', 'LE_F'):
    px = y(s); px = px[px > 0]
    for n in NS:
        for up in (True, False):
            q = pct(lret(px, n)); NULL.append(on_brd(A((q >= 80) if up else (q <= 20), 'yahoo', P.index))[0])
print('BRD 위 무관 대조군 48규칙 ΔSh 분위 50/90/95/max', np.round(np.percentile(NULL, [50, 90, 95, 100]), 3))
