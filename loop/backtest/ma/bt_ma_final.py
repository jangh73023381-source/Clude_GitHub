# -*- coding: utf-8 -*-
"""최종 확인 — (A) 발동일 한정 성과, (B) 실제 201종 ETF 유니버스 교차확인.

(A) 게이트가 픽을 실제로 바꾼 날만 모아 baseline과 비교 (v2.2 B 교차검증 게이트 요건).
(B) 15섹터는 대리 표본이므로, 실제 선정 유니버스인 201종 ETF 패널
    (panel_close_0724.csv, 종가만·99일)에서 같은 룰이 같은 부호를 내는지 확인.
"""
import csv
import os
import sys
import math
import statistics
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ma_engine import load, Panel
import bt_ma_support as B

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL201 = os.path.join(HERE, '..', 'panel_close_0724.csv')
BENCH = '069500'
COST = 0.0010


# ------------------------------------------------------------------ (A)
def fired_only(P, codes, dates, gate, start=B.WARMUP):
    """게이트 발동일(픽 변화일)만 모아 baseline vs 변형 초과수익 비교."""
    bl, vl, days = [], [], []
    for i in range(start, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        pb = B.select(P, codes, d, None)
        pv = B.select(P, codes, d, gate)
        if set(pb) == set(pv):
            continue
        rets = {}
        ok = True
        for c in codes:
            a, b = P.close(c, d), P.close(c, dn)
            if not (a and b):
                ok = False
                break
            rets[c] = b / a - 1.0
        a, b = P.close(BENCH, d), P.close(BENCH, dn)
        if not ok or not (a and b):
            continue
        bm = b / a - 1.0
        bl.append(sum(rets[c] for c in pb) / len(pb) - COST - bm)
        vl.append(sum(rets[c] for c in pv) / len(pv) - COST - bm)
        days.append(d)
    return bl, vl, days


def sec_a():
    bars, meta, dates, codes = load()
    P = Panel(bars, dates)
    gates = [
        ('MA-T  MA20 기울기>0', B.g_ma20_slope),
        ('MA-A  정배열', B.g_aligned),
        ('MA-R3 MA60 터치반락 2회+ 배제', B.g_rejected),
        ('MA-S1 MA20 이탈깊이<=1%', B.mk_g_support(0.01)),
    ]
    print('=' * 90)
    print('(A) 발동일 한정 성과 — 게이트가 픽을 실제로 바꾼 날만')
    print('=' * 90)
    print(f"{'변형':30s}{'발동일':>7s}{'base초과%':>10s}{'변형초과%':>10s}"
          f"{'순증%p':>9s}{'개선일':>7s}{'악화일':>7s}")
    print('-' * 90)
    for label, g in gates:
        bl, vl, days = fired_only(P, codes, dates, g)
        if not bl:
            print(f'{label:30s} 발동 0일')
            continue
        imp = sum(1 for x, y in zip(vl, bl) if y > x)
        wor = sum(1 for x, y in zip(vl, bl) if y < x)
        print(f"{label:30s}{len(bl):>7d}{statistics.mean(bl)*100:>10.4f}"
              f"{statistics.mean(vl)*100:>10.4f}"
              f"{(statistics.mean(vl)-statistics.mean(bl))*100:>9.4f}{imp:>7d}{wor:>7d}")


# ------------------------------------------------------------------ (B)
def load201():
    px = defaultdict(dict)
    name = {}
    for r in csv.DictReader(open(PANEL201, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except Exception:
            continue
        name[r['code']] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, name, dates


def is_spot(nm):
    n = (nm or '').replace(' ', '')
    return not any(k in n for k in ('인버스', '곱버스', '레버리지', '2배', '숏')) \
        and '2X' not in n.upper()


def ma(px, c, d, dates, k, idx):
    i = idx[d]
    if i < k - 1:
        return None
    vals = [px[c].get(dates[j]) for j in range(i - k + 1, i + 1)]
    if any(v is None for v in vals):
        return None
    return sum(vals) / k


def sec_b():
    px, name, dates = load201()
    idx = {d: i for i, d in enumerate(dates)}

    def mom(c, d, k):
        i = idx[d]
        if i < k:
            return None
        a, b = px[c].get(dates[i - k]), px[c].get(d)
        return (b / a - 1.0) if (a and b) else None

    def rule_h(c, d):
        s, c3 = mom(c, d, 1), mom(c, d, 3)
        if s is not None and s > 0.10:
            return False
        if c3 is not None and c3 > 0.20:
            return False
        return True

    def slope20(c, d, s=5):
        i = idx[d]
        if i < s:
            return None
        a = ma(px, c, dates[i - s], dates, 20, idx)
        b = ma(px, c, d, dates, 20, idx)
        return (b / a - 1.0) if (a and b) else None

    def sel(d, gate):
        cand = []
        for c in px:
            p = px[c].get(d)
            if not p or p < 10000 or not is_spot(name.get(c, '')):
                continue
            m = mom(c, d, 20)
            if m is None or not rule_h(c, d):
                continue
            cand.append((c, m))
        cand.sort(key=lambda x: x[1], reverse=True)
        ranked = [c for c, _ in cand]
        if gate is None:
            return ranked[:5]
        keep = [c for c in ranked if gate(c, d) is not False]
        if len(keep) >= 5:
            return keep[:5]
        rest = [c for c in ranked if c not in keep]
        return (keep + rest)[:5]

    g_T = lambda c, d: (None if slope20(c, d) is None else slope20(c, d) > 0)

    start = 26
    rows = {'baseline': [], 'MA-T': []}
    fired = 0
    fb, fv = [], []
    for i in range(start, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        a, b = px[BENCH].get(d), px[BENCH].get(dn)
        if not (a and b):
            continue
        bm = b / a - 1.0
        pb, pv = sel(d, None), sel(d, g_T)
        for key, picks in (('baseline', pb), ('MA-T', pv)):
            rs = [px[c][dn] / px[c][d] - 1.0 for c in picks
                  if px[c].get(d) and px[c].get(dn)]
            if len(rs) == 5:
                rows[key].append(sum(rs) / 5 - COST - bm)
        if set(pb) != set(pv):
            fired += 1
            rsb = [px[c][dn] / px[c][d] - 1.0 for c in pb if px[c].get(d) and px[c].get(dn)]
            rsv = [px[c][dn] / px[c][d] - 1.0 for c in pv if px[c].get(d) and px[c].get(dn)]
            if len(rsb) == 5 and len(rsv) == 5:
                fb.append(sum(rsb) / 5 - COST - bm)
                fv.append(sum(rsv) / 5 - COST - bm)

    n = len(rows['baseline'])
    half = n // 2
    print()
    print('=' * 90)
    print(f'(B) 실제 201종 ETF 유니버스 교차확인 — {dates[0]}~{dates[-1]}, 채점 {n}일')
    print('=' * 90)
    print(f"{'전략':16s}{'KODEX초과%':>11s}{'train':>9s}{'test':>9s}{'승률%':>8s}")
    print('-' * 90)
    for key in ('baseline', 'MA-T'):
        xs = rows[key]
        print(f"{key:16s}{statistics.mean(xs)*100:>11.4f}"
              f"{statistics.mean(xs[:half])*100:>9.4f}"
              f"{statistics.mean(xs[half:])*100:>9.4f}"
              f"{sum(1 for x in xs if x>0)/len(xs)*100:>8.1f}")
    if fb:
        print(f"\n발동일 {fired}일 한정 : base {statistics.mean(fb)*100:+.4f}% "
              f"→ MA-T {statistics.mean(fv)*100:+.4f}% "
              f"(순증 {(statistics.mean(fv)-statistics.mean(fb))*100:+.4f}%p, "
              f"개선 {sum(1 for x,y in zip(fv,fb) if x>y)}일 / "
              f"악화 {sum(1 for x,y in zip(fv,fb) if x<y)}일)")
    else:
        print(f'\n발동일 {fired}일 — 표본 부족')


if __name__ == '__main__':
    sec_a()
    sec_b()
