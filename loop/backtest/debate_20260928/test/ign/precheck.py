# -*- coding: utf-8 -*-
"""Rule IGN 선행 점검 P0·P1 (r3_behav.md §4-2 정본). 선정 성과(IGN 바스켓 vs LV)는 계산하지 않는다.
실행: python precheck.py  → precheck_out.json
"""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/w/test/hys')
from common import load, Engine

P, dates, codes, names = load()
E = Engine(P, dates, codes, names)
C, R, T, N = E.C, E.R, E.T, E.N
SIG = E.vol(20)
lag = lambda X, k: np.vstack([np.full((k, N), np.nan), X[:-k]])
R5 = (C / lag(C, 5) - 1) * 100
RHO, RHO_DUP, BTH, W, H = 0.80, 0.97, 0.6, 20, 10
if len(sys.argv) > 1:
    RHO = float(sys.argv[1])


def universe(i):
    """eligible · Rule H 통과 · 60거래일 수익률 전부 가용 · r5 가용."""
    if i < 60:
        return np.array([], int)
    win = R[i - 59:i + 1]
    full = ~np.isnan(win).any(0)
    return np.where(E.ok[i] & full & ~np.isnan(R5[i]) & ~np.isnan(SIG[i]))[0]


# 날짜별 무리 구성
B = np.full((T, N), np.nan)          # 대표 i 의 breadth (무리 성립 시)
HERD = {}                            # (i, D) -> 구성원(대표 + 복제쌍 원본 포함) 코드 인덱스 배열
TOP5 = {}
stat = []
for i in range(60, T):
    U = universe(i)
    if len(U) < 10:
        continue
    X = R[i - 59:i + 1, U]
    Cm = np.corrcoef(X.T)
    np.fill_diagonal(Cm, 1.0)
    # 복제 쌍 병합 (corr ≥ 0.97 연결요소, σ20 하위가 대표)
    n = len(U); par = list(range(n))
    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    ii, jj = np.where(np.triu(Cm >= RHO_DUP, 1))
    for a, b in zip(ii, jj):
        ra, rb = f(a), f(b)
        if ra != rb: par[ra] = rb
    comp = {}
    for a in range(n): comp.setdefault(f(a), []).append(a)
    reps, twins = [], {}
    for mem in comp.values():
        s = SIG[i, U[mem]]
        r = mem[int(np.argmin(s))]
        reps.append(r); twins[r] = mem
    reps = np.array(sorted(reps))
    q80 = np.quantile(R5[i, U], 0.80)
    Cr = Cm[np.ix_(reps, reps)]
    hot = R5[i, U[reps]] >= q80
    nherd = 0
    # 병합 전 무리 성립 수 (비교용)
    pre_valid = int(((Cm >= RHO).sum(1) - 1 >= 2).sum())
    for k, r in enumerate(reps):
        peers = np.where((Cr[k] >= RHO) & (np.arange(len(reps)) != k))[0]
        if len(peers) < 2:
            continue
        nherd += 1
        grp = np.r_[k, peers]
        B[i, U[r]] = hot[grp].mean()
        mem = np.concatenate([twins[reps[g]] for g in grp])
        HERD[(i, U[r])] = U[mem]
    o = U[np.argsort(-R5[i, U], kind='stable')]
    TOP5[i] = set(o[:5].tolist())
    stat.append(dict(i=i, nU=len(U), nrep=len(reps), merged_share=1 - len(reps) / len(U),
                     herd_post=nherd, herd_pre=pre_valid))
ST = pd.DataFrame(stat)

# 점화: natural(무리 미성립일 = 비점화로 간주) / strict(직전 20일 모두 무리 성립 & B<0.6)
def ignitions(strict):
    ev = []
    for (i, c) in HERD:
        if B[i, c] < BTH or i < 60 + W:
            continue
        prev = B[i - W:i, c]
        if strict:
            ok = (~np.isnan(prev)).all() and (prev < BTH).all()
        else:
            ok = not (prev >= BTH).any()      # NaN 비교는 False
        if ok:
            ev.append((i, c))
    return sorted(ev)


# LV 기준 run 일(fold 경계)
lvdays = E.run(E.sel_lv)['i'].values
fold_edges = [lvdays[j * len(lvdays) // 3] for j in range(3)] + [lvdays[-1] + 1]


def p0(ev):
    act = set()
    for (i, c) in ev:
        for d in range(i, min(i + H, T)):
            act.add(d)
    act = np.array(sorted(a for a in act if a in set(lvdays)))
    cnt = [int(((act >= fold_edges[k]) & (act < fold_edges[k + 1])).sum()) for k in range(3)]
    return cnt, len(ev)


def p1(ev, back, fwd=10):
    leads, cens = [], 0
    seen = set(); leads_d = []
    for (i, c) in ev:
        mem = set(HERD[(i, c)].tolist())
        t0 = None
        for t in range(max(0, i - back), min(T, i + fwd + 1)):
            if t in TOP5 and TOP5[t] & mem:
                t0 = t; break
        if t0 is None:
            cens += 1; continue
        leads.append(i - t0)        # 점화일 − 첫 mom5 top5 편입일 (음수 = IGN 이 빠름)
        key = (i, frozenset(mem))
        if key not in seen:
            seen.add(key); leads_d.append(i - t0)
    L = np.array(leads)
    return dict(n=len(L), censored=cens, median=float(np.median(L)) if len(L) else None,
                mean=float(L.mean()) if len(L) else None,
                share_ign_earlier2=float((L <= -2).mean()) if len(L) else None,
                share_same_or_later=float((L >= 0).mean()) if len(L) else None,
                median_dedup=float(np.median(leads_d)) if leads_d else None,
                median_cens_as_ign_first=float(np.median(np.r_[L, np.full(cens, -(fwd + 1))])) if (len(L) + cens) else None)


out = dict(rho=RHO, universe_mean=float(ST.nU.mean()), merged_share_mean=float(ST.merged_share.mean()),
           herd_pre_mean=float(ST.herd_pre.mean()), herd_post_mean=float(ST.herd_post.mean()),
           herd_lost_share=float(1 - ST.herd_post.sum() / max(1, ST.herd_pre.sum())),
           fold_edges=[dates[k] if k < T else 'end' for k in fold_edges])
for nm, strict in (('natural', False), ('strict', True)):
    ev = ignitions(strict)
    cnt, ne = p0(ev)
    out[nm] = dict(events=ne, fold_active_days=cnt,
                   P1={f'back{b}': p1(ev, b) for b in (5, 10, 20)})
    # fold별 P1 (back10)
    out[nm]['P1_fold'] = []
    for k in range(3):
        evk = [e for e in ev if fold_edges[k] <= e[0] < fold_edges[k + 1]]
        out[nm]['P1_fold'].append(p1(evk, 10))
json.dump(out, open(f'/home/claude/w/test/ign/precheck_out_rho{RHO}.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
