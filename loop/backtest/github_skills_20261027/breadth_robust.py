"""시장 폭(breadth) KODEX200 타이밍 강건성 — tradermonty market-breadth-analyzer 정량화.
폭 = 유동 종목 중 종가 > MA_n 비율(%). 신호 D 종가 확정 → D 종가 보유 → D+1 종가 수익. 현금 0, 비용 0.
R1 격자(문턱·이동평균쌍) / R2 3분할 vs 보유 / R3 정의 교체(MA50·MA100·MA200, 코스피 대형 300만) / R4 무작위 타이밍 / R5 상위 10일 제거.
+ IBS shadow 와의 겹침(상관·동시 보유)."""
import numpy as np, pandas as pd
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); C, V = Z['C'].astype(float), Z['V'].astype(float); bench = Z['bench'].astype(float)
T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
rk = np.r_[bench[1:] / bench[:-1] - 1, np.nan]
D = lambda A: pd.DataFrame(A)
def breadth(n, big=None):
    ma = D(C).rolling(n).mean().values; ok = LIQ & np.isfinite(ma)
    if big is not None: ok &= big
    with np.errstate(all='ignore'):
        return np.nansum(ok & (C > ma), 1) / np.maximum(ok.sum(1), 1) * 100
rank_val = D(val20).rank(axis=1, ascending=False).values; BIG = rank_val <= 300
B = {n: breadth(n) for n in (50, 100, 200)}; B['200big'] = breadth(200, BIG)
s0, s1 = 470, T - 1; bh = rk[s0:s1]
def perf(r):
    eq = np.cumprod(1 + r); y = len(r) / 245
    return (eq[-1] ** (1 / y) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0
rng = np.random.default_rng(11)
def rand_timing(pos):
    blocks = []; t = 0
    while t < len(pos):
        u = t
        while u < len(pos) and pos[u] == pos[t]: u += 1
        blocks.append((pos[t], u - t)); t = u
    ins = [b for b in blocks if b[0] == 1]; outs = [b for b in blocks if b[0] == 0]
    rng.shuffle(ins); rng.shuffle(outs); seq = []; a, b = list(ins), list(outs); first = blocks[0][0]
    while a or b:
        for src in ((a, b) if first == 1 else (b, a)):
            if src: v, l = src.pop(); seq += [v] * l
    return np.array(seq[:len(pos)])
k3 = len(bh) // 3
bhf = [perf(bh[i*k3:(i+1)*k3])[2] for i in range(3)]
print('기간', dates[s0], '~', dates[s1 - 1], '| 보유 CAGR/MDD/Sh', np.round(perf(bh), 2), '| 보유 3분할 Sh', np.round(bhf, 2))
rows = []
def ev(name, sig, sims=300):
    pos = sig[s0:s1].astype(float); r = pos * bh; cg, md, sh = perf(r)
    f = [perf(r[i*k3:(i+1)*k3])[2] for i in range(3)]
    srt = np.argsort(-bh)[:10]; r5 = np.delete(r, srt); b5 = np.delete(bh, srt)
    p = (np.array([perf(rand_timing(pos) * bh)[2] for _ in range(sims)]) >= sh).mean() if sims else np.nan
    rows.append(dict(규칙=name, CAGR=cg, MDD=md, Sharpe=sh, 노출=pos.mean() * 100, 거래=int((np.diff(pos) == 1).sum()), p=p,
                     분할Sh='/'.join(f'{x:.2f}' for x in f), 분할우위=sum(a > b for a, b in zip(f, bhf)),
                     상위10일제거_Sh=perf(r5)[2], 보유_상위10일제거_Sh=perf(b5)[2],
                     보유일평균=bh[pos == 1].mean() * 100, 현금일평균=bh[pos == 0].mean() * 100))
# 원안 2종
ev('원안A 폭200 8MA>200MA', pd.Series(B[200]).rolling(8).mean().values > pd.Series(B[200]).rolling(200).mean().values, 1000)
ev('원안B 폭200 ≥ 50%', B[200] >= 50, 1000)
# R1 격자
for th in (40, 45, 55, 60): ev(f'R1 폭200 ≥ {th}%', B[200] >= th, 0)
for a, b in ((5, 100), (5, 200), (10, 150), (20, 200), (8, 100), (8, 300)):
    s = pd.Series(B[200]); ev(f'R1 폭200 {a}MA>{b}MA', s.rolling(a).mean().values > s.rolling(b).mean().values, 0)
# R3 정의 교체
for n in (50, 100):
    ev(f'R3 폭{n} ≥ 50%', B[n] >= 50, 300)
    s = pd.Series(B[n]); ev(f'R3 폭{n} 8MA>200MA', s.rolling(8).mean().values > s.rolling(200).mean().values, 300)
ev('R3 대형300 폭200 ≥ 50%', B['200big'] >= 50, 300)
s = pd.Series(B['200big']); ev('R3 대형300 폭200 8MA>200MA', s.rolling(8).mean().values > s.rolling(200).mean().values, 300)
# 단순 KODEX200 MA200 (가격 추세) 대조 — 폭이 가격 추세 이상인가
kma = pd.Series(bench).rolling(200).mean().values
ev('대조 KODEX200 > MA200 (가격추세)', bench > kma, 300)
ev('대조 KODEX200 > MA60', bench > pd.Series(bench).rolling(60).mean().values, 300)
o = pd.DataFrame(rows); pd.set_option('display.width', 300); pd.set_option('display.max_columns', 20)
print(o.round(3).to_string(index=False)); o.to_csv('breadth_robust.csv', index=False)
pos_b = (B[200] >= 50)[s0:s1]; pos_t = (bench > kma)[s0:s1]
print('폭≥50% vs 가격>MA200 동일상태 비율', (pos_b == pos_t).mean().round(3))
