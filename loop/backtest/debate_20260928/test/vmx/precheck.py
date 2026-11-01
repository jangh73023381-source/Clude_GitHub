# VMX 선행 점검 P1·P2·P3 — 슬리브 원수익·KODEX200 원수익만 사용. 스케일 성과 계산 없음.
from vmx_lib import *
S = sleeve('exit')
r = S.r; ev = S.index >= EVAL0
M = bench_by_i(S.index)
out = {}
for L in (126, 63, 252):
    sS = sig_hat(r, L); sM = sig_hat(M, L)
    m = ev & sS.notna().values & sM.notna().values
    corr = np.corrcoef(np.log(sS[m]), np.log(sM[m]))[0, 1]
    ratio = (sS / sM)[m]; cv = ratio.std(ddof=1) / ratio.mean()
    for K in ((5, 1) if L == 126 else (5,)):
        w = weights(sS, K)
        # MA60 게이트: KODEX200 종가 < MA60 (D 종가 기준)
        cb = pd.Series(C[:, bi]); ma = cb.rolling(60).mean()
        below = (cb < ma).values[S.index]
        we = w[ev]; be = below[ev]
        p2 = be[(we < 0.9).values].mean() if (we < 0.9).any() else np.nan
        p3 = (we < 1).mean()
        print(f"L={L} K={K}: P1 corr(logσS,logσM)={corr:.3f} CV(σS/σM)={cv:.3f} 비율평균={ratio.mean():.2f} "
              f"| P2 w<0.9일 중 MA60아래 비율={p2:.3f} (w<0.9 {int((we<0.9).sum())}일, 기저 MA60아래 {be.mean():.3f}) "
              f"| P3 w<1 비율={p3:.3f} 평균w={we.mean():.3f} | 평가일 {int(ev.sum())} ({dates[EVAL0]}~)")
