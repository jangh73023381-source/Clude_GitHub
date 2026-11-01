# 구현 검증: 공유 탈락청산 엔진으로 reset.py ①(Rule H 없음, start 200)을 재현
import numpy as np
from dx import *
maskE = np.broadcast_to(elig[None, :], C.shape)
tg = targets(MOM[150], 200, mask=maskE, min_univ=20)
df = run_exit(tg, 200)
s = stats(df.r.values)
b = FWD[200:T-1, bi]; sb = stats(b)
d = df.r.values - b
print(f"[엔진] RuleH 없음 start200: 누적 {s['cum']:+.1f}% MDD {s['mdd']:.1f}% Sh {s['sh']:.2f} 초과 {100*d.mean():+.4f} fold {[round(100*x.mean(),3) for x in np.array_split(d,3)]}")
print(f"[KODEX200] 누적 {sb['cum']:+.1f}% MDD {sb['mdd']:.1f}% Sh {sb['sh']:.2f}")
# Rule H 적용 판 (본 검정의 기준선 슬리브)
for st in (200, 250):
    tgH = targets(MOM[150], st)
    dh = run_exit(tgH, st); sh_ = stats(dh.r.values)
    print(f"[엔진] RuleH 적용 start{st}: 누적 {sh_['cum']:+.1f}% CAGR {sh_['cagr']:+.1f} MDD {sh_['mdd']:.1f}% Sh {sh_['sh']:.2f}")
