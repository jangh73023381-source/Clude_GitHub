import numpy as np, pandas as pd, os
R = pd.read_pickle(os.environ['HOME']+'/work/ep.pkl')
def pct(x): return 100*x
for H in [5,10,20]:
    g = R[R.H==H]
    trig = g.t>0
    bh  = g.CH/g.C0
    half_held = g.CH/g.C0
    f = np.where(trig, g.fill/g.C0, g.CH/g.C0)
    # A. 절반매도 후 재매수 안 함
    A = 0.5*f + 0.5*half_held
    # B. 절반매도 후 다음날 종가 재매수
    reb = np.where(trig, (g.fill/g.C0)*(g.CH/g.ct1), g.CH/g.C0)
    B = 0.5*reb + 0.5*half_held
    # C. 절반매도 후 당일 종가 재매수
    rec = np.where(trig, (g.fill/g.C0)*(g.CH/g.ct), g.CH/g.C0)
    C = 0.5*rec + 0.5*half_held
    # D. 반등 확인(다음날 종가 > 스톱가)일 때만 재매수, 아니면 현금
    cond = trig & (g.ct1 > g.fill)
    reb_d = np.where(cond, (g.fill/g.C0)*(g.CH/g.ct1), np.where(trig, g.fill/g.C0, g.CH/g.C0))
    D = 0.5*reb_d + 0.5*half_held
    print(f'=== H={H}일 보유  n={len(g):,}  발동률={100*trig.mean():.2f}%')
    ft = g.t[trig]
    print(f'   첫 발동일 분포: 1일차 {100*(ft==1).mean():.1f}% / 2일차까지 {100*(ft<=2).mean():.1f}% / 3일차까지 {100*(ft<=3).mean():.1f}% / 중앙 {ft.median():.0f}일차')
    print(f'   방치(보유)        {pct(bh.mean()-1):+.4f}%   승률 {100*(bh>1).mean():.1f}%')
    for nm,S in [('A 재매수안함',A),('B 익일종가재매수',B),('C 당일종가재매수',C),('D 반등확인재매수',D)]:
        d = S-bh
        t = d.mean()/ (d.std(ddof=1)/np.sqrt(len(d)))
        print(f'   {nm:14s} {pct(S.mean()-1):+.4f}%   방치대비 {pct(d.mean()):+.4f}%p  t={t:6.1f}  이긴비율 {100*(d>0).mean():.1f}%')
    # 발동 후 잔여구간 수익
    sub = g[trig]
    print(f'   [발동분만] 스톱가→만기 종가 평균 {pct((sub.CH/sub.fill).mean()-1):+.3f}%  (상승확률 {100*(sub.CH>sub.fill).mean():.1f}%)')
    print(f'   [발동분만] 스톱가→익일 종가 평균 {pct((sub.ct1/sub.fill).mean()-1):+.3f}%  (상승확률 {100*(sub.ct1>sub.fill).mean():.1f}%)')
