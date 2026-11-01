# -*- coding: utf-8 -*-
"""Rule HYS (TRN 축) 사전등록 검정 — r3_micro.md §1 정본.
실행: python hys.py  → hys_out.json, 화면 출력
"""
import json, numpy as np, pandas as pd
from common import *

P, dates, codes, names = load()
E = Engine(P, dates, codes, names)
SIG = E.vol(20)
F = {'A': E.fA, 'OO': E.fOO, 'L1': E.fL1, 'OOx': E.fOOx}
TV = P['close'] * P['volume']          # D일 거래대금(원)


def lv_pick(i, p30):
    return E.sel_lv(i, p30)


def hys_pick(i, prev, p30, p40, K):
    s = SIG[i]
    nn = p30[~np.isnan(s[p30])]
    if len(nn) < 5:
        return lv_pick(i, p30), True
    set40 = set(p40.tolist()); set30 = set(p30.tolist())
    kept = []
    for h in prev:
        if h in set40 and not np.isnan(s[h]):
            sp = s[nn]
            if h in set30:
                r = int((sp < s[h]).sum()) + 1 + int(((sp == s[h]) & (nn != h)).sum())  # 동률 불리하게
            else:
                r = int((sp <= s[h]).sum()) + 1
            if r <= K:
                kept.append(h)
    o = nn[np.argsort(s[nn], kind='stable')]
    fill = [c for c in o if c not in kept][:5 - len(kept)]
    return np.array(kept + fill, dtype=int), False


def track(kind, K=8, poolkeep=40, retain=None, rng=None):
    """모형 트래커: 매 선정일 상태 갱신. 반환 rows(DataFrame), picks(dict i->array)"""
    prev = np.array([], dtype=int)
    rows, picks = [], {}
    for i in range(20, E.T - 3):
        p30 = E.pool(i, 30)
        if len(p30) < 5:
            prev = np.array([], dtype=int); continue
        fb = False
        if kind == 'LV':
            pk = lv_pick(i, p30)
        elif kind == 'HYS':
            p40 = E.pool(i, poolkeep)
            pk, fb = hys_pick(i, prev, p30, p40, K)
        elif kind == 'RND':
            k = retain.get(i, 0)
            s = SIG[i]
            nn = p30[~np.isnan(s[p30])]
            if len(nn) < 5:
                pk = lv_pick(i, p30); fb = True
            else:
                cand = [h for h in prev if E.ok[i, h] and not np.isnan(s[h])]
                kk = min(k, len(cand))
                kept = list(rng.choice(cand, kk, replace=False)) if kk > 0 else []
                o = nn[np.argsort(s[nn], kind='stable')]
                fill = [c for c in o if c not in kept][:5 - kk]
                pk = np.array(kept + fill, dtype=int)
        prev = pk
        picks[i] = pk
        if len(pk) < 5 or np.isnan(E.fA[i, pk]).any():
            continue
        row = {'i': i, 'date': dates[i], 'fb': fb}
        for m, X in F.items():
            v = X[i, pk]
            row[m] = np.nanmean(v) if (~np.isnan(v)).any() else np.nan
        tv = TV[i, pk]
        row['tv1'] = np.mean(tv < 1e8); row['tv5'] = np.mean(tv < 5e8)
        rows.append(row)
    return pd.DataFrame(rows), picks


def turnover(picks):
    ks = sorted(picks); rep = {}; ret = {}
    for a, b in zip(ks[:-1], ks[1:]):
        if b != a + 1:
            continue
        inter = len(set(picks[a].tolist()) & set(picks[b].tolist()))
        rep[b] = len(picks[b]) - inter; ret[b] = inter
    return rep, ret


if __name__ == '__main__':
    out = {}
    LV, lvp = track('LV')
    base = E.run(E.sel_lv)
    # 기준선 재현 확인
    for m in ('OO', 'A', 'L1'):
        p = prof(LV[m]); out[f'LV_{m}'] = p
        print('LV', m, f"CAGR {p['cagr']:+.1f} MDD {p['mdd']:.1f} Sh {p['sharpe']:.2f}")
    assert len(LV) == len(base) and np.allclose(LV['OO'].values, base['OO'].values, equal_nan=True)
    # 구현 검증: K=5, 풀30 → LV 100% 일치
    H5, h5p = track('HYS', K=5, poolkeep=30)
    mism = sum(1 for i in lvp if set(lvp[i].tolist()) != set(h5p.get(i, np.array([])).tolist()))
    print('구현검증 K5/풀30 불일치 일수:', mism, '/', len(lvp))
    out['verify_mismatch'] = mism; out['verify_days'] = len(lvp)
    assert mism == 0
    pickle_obj = {'LV': (LV, lvp)}
    for K in (8, 6, 10):
        H, hp = track('HYS', K=K, poolkeep=40)
        pickle_obj[K] = (H, hp)
    import pickle
    pickle.dump(pickle_obj, open('/home/claude/w/test/hys/tracks.pkl', 'wb'))
    print('saved')
