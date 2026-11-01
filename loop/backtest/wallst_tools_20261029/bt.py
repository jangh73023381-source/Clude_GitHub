"""월가 시장분석 도구 KODEX200 타이밍 검정 (2026-10-29). 신호 K(한국일) 장중까지 공개된 미국 정보 → K 종가 집행 → K+1 종가 수익.
위험회피면 현금(0), 아니면 KODEX200 보유. 비용 0. 주판정 = 7년 패널(panel_ohlc_long), 보조 = 야후 069500.KS 2010~ 확장표본."""
import numpy as np, pandas as pd, sys
from signals import build
P = pd.read_csv('../panel_ohlc_long.csv', dtype={'code': str, 'date': str}); P = P[P.code == '069500'].copy()
P.index = pd.to_datetime(P.date); P = P.sort_index()
def prep(px):
    c, o = px.close.values, px.open.values
    r = np.r_[c[1:] / c[:-1] - 1, np.nan]; gap = np.r_[o[1:] / c[:-1] - 1, np.nan]; intra = np.r_[c[1:] / o[1:] - 1, np.nan]
    return r, gap, intra
def perf(r):
    eq = np.cumprod(1 + r); yy = len(r) / 245
    return (eq[-1] ** (1 / yy) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, (r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0)
rng = np.random.default_rng(29)
def rand_timing(pos):
    blocks = []; t = 0
    while t < len(pos):
        u = t
        while u < len(pos) and pos[u] == pos[t]: u += 1
        blocks.append((pos[t], u - t)); t = u
    a = [b for b in blocks if b[0] == 1]; b_ = [b for b in blocks if b[0] == 0]
    rng.shuffle(a); rng.shuffle(b_); seq = []; first = blocks[0][0]
    while a or b_:
        for src in ((a, b_) if first == 1 else (b_, a)):
            if src: v, l = src.pop(); seq += [v] * l
    return np.array(seq[:len(pos)])
def evaluate(px, S, G, sims=500, full=True):
    r, gap, intra = prep(px); kd = px.index; rows = []
    for nm, sig in S.items():
        s = sig.reindex(kd).values.astype(float)
        ok = np.isfinite(s) & np.isfinite(r)
        i0 = np.argmax(ok); m = np.zeros(len(r), bool); m[i0:] = True; m &= np.isfinite(r)
        s2 = np.where(np.isfinite(s), s, 0.0)[m]; pos = 1 - s2; rr = r[m]
        st = pos * rr; cs, ms, ss = perf(st); ch, mh, sh = perf(rr)
        row = dict(묶음=G[nm], 규칙=nm, 시작=str(kd[m][0].date()), 일수=int(m.sum()), 노출=pos.mean() * 100,
                   CAGR=cs, MDD=ms, Sh=ss, 보유CAGR=ch, 보유MDD=mh, 보유Sh=sh, ΔSh=ss - sh, ΔMDD=ms - mh)
        if full:
            if 0 < pos.mean() < 1:
                rs = np.array([perf(rand_timing(pos) * rr)[2] for _ in range(sims)]); row['p'] = (rs >= ss).mean()
            else: row['p'] = np.nan
            k = len(rr) // 3
            fs = [perf(st[i*k:(i+1)*k])[2] - perf(rr[i*k:(i+1)*k])[2] for i in range(3)]
            row['fold ΔSh'] = '/'.join(f'{x:+.2f}' for x in fs); row['fold우위'] = sum(x > 0 for x in fs)
            d = st - rr; o = np.argsort(-d)
            for kk in (3, 5, 10):
                st2 = st.copy(); st2[o[:kk]] = rr[o[:kk]]; row[f'R5 상위{kk}일제거 ΔSh'] = perf(st2)[2] - sh
            cash = pos == 0; g, it = gap[m], intra[m]
            av_g, av_i = -(g[cash]).sum(), -(it[cash]).sum()   # 현금일에 피한 수익(+면 손실 회피)
            row['회피 갭%'] = av_g * 100; row['회피 장중%'] = av_i * 100
        rows.append(row)
    return pd.DataFrame(rows)
if __name__ == '__main__':
    kd = P.index
    S, G = build(kd, 80)
    out = evaluate(P, S, G)
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
    print(out.round(3).to_string(index=False)); out.to_csv('result_main.csv', index=False)
    # R1 문턱 격자
    g = {}
    for thr in (70, 75, 85, 90):
        S2, _ = build(kd, thr); o2 = evaluate(P, S2, G, full=False); g[thr] = o2.set_index('규칙').ΔSh
    g[80] = out.set_index('규칙').ΔSh; R1 = pd.DataFrame(g)[[70, 75, 80, 85, 90]]; R1['고원(ΔSh>0 칸)'] = (R1 > 0).sum(1)
    print(R1.round(3).to_string()); R1.to_csv('result_R1.csv')
    # 확장 표본 (야후 2010~)
    Y = pd.read_csv('raw/y_069500.KS.csv', dtype={'date': str}); Y.index = pd.to_datetime(Y.date); Y = Y[(Y.index >= '2010-01-01') & (Y.index <= '2026-10-28')]
    Y = Y[(Y.close > 0) & (Y.open > 0)]
    S3, _ = build(Y.index, 80); o3 = evaluate(Y, S3, G, sims=300)
    print(o3[['규칙', '시작', '일수', '노출', 'CAGR', 'MDD', 'Sh', '보유Sh', 'ΔSh', 'ΔMDD', 'p', 'fold ΔSh']].round(3).to_string(index=False)); o3.to_csv('result_ext.csv', index=False)
