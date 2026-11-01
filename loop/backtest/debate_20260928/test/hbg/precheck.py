# HBG 선행 점검 P1·P2·P3 — 과거 가격(선정 목표집합)만 사용. 전방 수익 계산 없음.
from hbg_lib import *
import warnings; warnings.filterwarnings('ignore')
tb = targets(MOM[150], START)
def ov_turn(tg):
    ov = []; tb_turn = []; th_turn = []
    ks = sorted(tg)
    for j, i in enumerate(ks):
        ov.append(len(set(tg[i]) & set(tb[i])))
        if j:
            th_turn.append(len(set(tg[i]) - set(tg[ks[j-1]])))
            tb_turn.append(len(set(tb[i]) - set(tb[ks[j-1]])))
    return np.mean(ov), np.mean(th_turn), np.mean(tb_turn)
for nm, K in [('기본 {120,150,200,250}', (120,150,200,250)), ('인접 {150,200,250}', (150,200,250)), ('인접 {120,250}', (120,250))]:
    S = hbg_score(K); tg = tg_of(S)
    o, th, tbb = ov_turn(tg)
    print(f"{nm}: P1 겹침 {o:.3f}/5 | P2 교체 HBG {th:.3f}/일 vs mom150 {tbb:.3f}/일 → 감소율 {1-th/tbb:.3f}")
# P3: mom150 상위5 탈락 이벤트의 기준일 항 비중
lC = np.log(C); ks = sorted(tb); ev = []; hotdrop = 0
for j in range(1, len(ks)):
    i, ip = ks[j], ks[j-1]
    for c in set(tb[ip]) - set(tb[i]):
        cur = lC[i, c] - lC[i-5, c]; base = lC[i-150, c] - lC[i-155, c]
        if not (np.isfinite(cur) and np.isfinite(base)):
            continue
        h = not okH[i, c]
        hotdrop += h
        ev.append((abs(base) / (abs(base) + abs(cur)) if abs(base)+abs(cur) > 0 else 0, h))
ev = np.array(ev)
sh = ev[:, 0]
print(f"P3: 탈락 이벤트 {len(ev)}건 (Rule H 배제로 인한 탈락 {hotdrop}건) | 기준일 항 비중>0.5 이벤트 비율 {np.mean(sh>0.5):.3f} "
      f"(RuleH 탈락 제외 시 {np.mean(sh[ev[:,1]==0]>0.5):.3f}) | 비중 중앙값 {np.median(sh):.3f}")
