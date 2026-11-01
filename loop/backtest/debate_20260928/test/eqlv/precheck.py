# -*- coding: utf-8 -*-
"""EQLV 선행 점검 Q1~Q4 (r3_mom.md §3). 성과(수익) 계산 없음."""
import sys; sys.path.insert(0, '/home/claude/w/test')
from common import *
cls = pd.read_csv('/home/claude/w/debate/prereg_mom_classes.csv', dtype={'code': str})
cmap = dict(zip(cls.code, cls.cls)); imap = dict(zip(cls.code, cls.income))
elig_codes = [c for j, c in enumerate(codes) if E.elig[j]]
miss = [c for c in elig_codes if c not in cmap]
print('eligible', len(elig_codes), 'CSV', len(cmap), 'eligible 중 CSV 누락', miss)
isEq = np.array([cmap.get(c) == '주식' for c in codes])
isInc = np.array([imap.get(c, 0) == 1 for c in codes])
fb = {'n': 0}
def sel_eqlv(i, pl, n=5):
    v = E.vol(20)[i, pl]; m = ~np.isnan(v)
    if m.sum() < n: return pl[:n]
    c, vv = pl[m], v[m]
    o = c[np.argsort(vv, kind='stable')]
    eq = [x for x in o if isEq[x]]
    if len(eq) >= n: return np.array(eq[:n])
    fb['n'] += 1
    rest = [x for x in o if not isEq[x]]
    return np.array(eq + rest[:n - len(eq)])
LV = picks(E.sel_lv); fb['n'] = 0; EQ = picks(sel_eqlv); nfb = fb['n']
slots = np.concatenate(list(LV.values()))
q1 = (~isEq[slots]).mean() * 100
q2, nd = overlap(EQ, LV)
print(f'Q1 LV 비주식 슬롯 비율 = {q1:.2f}%  (종결 <10%)')
print(f'Q2 EQLV∩LV 일평균 겹침 = {q2:.3f}/5  (n={nd}, 종결 ≥4.0)')
print(f'EQLV 폴백 발동 {nfb}일 / {len(EQ)}일')
# 비주식 LV 슬롯 구성
from collections import Counter
cc = Counter(cmap.get(codes[x]) for x in slots); print('LV 슬롯 자산군', dict(cc))
top = Counter(codes[x] for x in slots if not isEq[x]).most_common(8)
print('LV 비주식 상위', [(c, names[c], k) for c, k in top])
eqs = np.concatenate(list(EQ.values()))
print(f'Q3 인컴명칭 비중 LV {isInc[slots].mean()*100:.1f}%  EQLV {isInc[eqs].mean()*100:.1f}%  차 {(isInc[eqs].mean()-isInc[slots].mean())*100:+.1f}%p (≥+20%p 이면 주도테마 메커니즘 반증)')
for nm, pk in (('LV', LV), ('EQLV', EQ)):
    print('Q4', nm, liq(pk))
# fold별 Q1/Q2
ks = sorted(LV); K = len(ks)
for f in range(3):
    kk = ks[f*K//3:(f+1)*K//3]
    s = np.concatenate([LV[k] for k in kk])
    print(f' fold{f+1} {dates[kk[0]]}~{dates[kk[-1]]} 비주식 {(~isEq[s]).mean()*100:.1f}% 겹침 {np.mean([len(set(LV[k])&set(EQ.get(k,[]))) for k in kk]):.2f}')
