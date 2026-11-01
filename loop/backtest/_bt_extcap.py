#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rule T 후보: mom20 극단치 컷(20일 모멘텀 자체의 상한 캡).
배경(2026-07-10 루프): mom20 1~3위(TIGER차이나반도체FACTSET +34.4%·KODEX차이나AI반도체TOP10 +20.5%·
TIME차이나AI테크액티브 +15.0%, 전부 협의 中AI반도체 테마)가 익일(7/10) 전원 하위 1~3위(-2.2~-2.9%)로
붕괴한 반면, mom20 상위5에 없던 국내 반도체 소부장/전공정/후공정·원자력·AI전력·방산우주·증권이
익일 상위권을 차지. Rule H(전일+10%·3일누적+20%)는 20일 누적 확장 자체는 잡지 못함 — 새 필터:
mom20 값 자체가 극단적으로 높은 종목(예: 상위 X% 극단치 또는 절대값 임계)을 순위와 무관 제외하고
차순위로 채운다.

패널: panel_close.csv (201종×90일, 2026-03-03~07-10). Rule Q/S와 동일 프레임(65~68일 채점 윈도우).
"""
import csv
import math
from collections import defaultdict

BASE = "/sessions/festive-kind-meitner/mnt/loop"

def load_panel():
    by_code = defaultdict(dict)
    names = {}
    with open(f"{BASE}/panel_close.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by_code[r["code"]][r["date"]] = float(r["close"])
            names[r["code"]] = r["name"]
    dates = sorted({d for v in by_code.values() for d in v})
    return by_code, names, dates

def classify(name):
    n = (name or "").replace(" ", "")
    if "인버스" in n or "곱버스" in n:
        return "인버스"
    if "레버리지" in n or "2X" in n.upper() or "2배" in n:
        return "레버리지"
    return "현물"

def is_short(name):
    return "숏" in (name or "").replace(" ", "")

def main():
    by_code, names, dates = load_panel()
    codes = list(by_code.keys())
    types = {c: classify(names[c]) for c in codes}
    shorts = {c: is_short(names[c]) for c in codes}

    idx = {d: i for i, d in enumerate(dates)}
    LOOKBACK = 20

    # 채점 가능일: D-20 있고 D, D+1 있는 날
    scoreable = []
    for i, d in enumerate(dates):
        if i - LOOKBACK < 0 or i + 1 >= len(dates):
            continue
        scoreable.append(i)

    def get(code, i):
        d = dates[i]
        return by_code[code].get(d)

    # 채점 유니버스(그날 랭킹): rank_etf.py와 동일 — price_D>=10000, 숏 제외(레버/인버스는 포함)
    def universe_ranks(i):
        rows = []
        for c in codes:
            pc = get(c, i); nc = get(c, i + 1)
            if pc is None or nc is None or pc < 10000 or shorts[c]:
                continue
            rows.append((c, nc / pc - 1.0))
        rows.sort(key=lambda x: -x[1])
        N = len(rows)
        cutoff = max(1, math.ceil(N * 0.10))
        rank = {c: (k + 1) for k, (c, r) in enumerate(rows)}
        return rank, N, cutoff

    def candidates_mom20(i):
        # 후보 = 현물, 숏 아님, price_D>=10000
        out = []
        for c in codes:
            if types[c] != "현물" or shorts[c]:
                continue
            pD = get(c, i); pLB = get(c, i - LOOKBACK); pD1 = get(c, i - 1); pD3 = get(c, i - 3)
            if pD is None or pLB is None or pD < 10000:
                continue
            mom20 = pD / pLB - 1.0
            ret1 = (pD / pD1 - 1.0) if pD1 else None
            ret3 = (pD / pD3 - 1.0) if pD3 else None
            out.append({"code": c, "mom20": mom20, "ret1": ret1, "ret3": ret3})
        return out

    def rule_h_ok(x):
        if x["ret1"] is not None and x["ret1"] > 0.10:
            return False
        if x["ret3"] is not None and x["ret3"] > 0.20:
            return False
        return True

    def select_baseline(i):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        return [x["code"] for x in cands[:5]]

    def select_extcap(i, thresh):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        under = [x for x in cands if x["mom20"] <= thresh]
        over = [x for x in cands if x["mom20"] > thresh]
        # 극단치 제외 우선 차순위로 채움, 5종 못 채우면 극단치도 순위순으로 보충(현금 없이 유지)
        picks = [x["code"] for x in under[:5]]
        if len(picks) < 5:
            need = 5 - len(picks)
            picks += [x["code"] for x in over[:need]]
        return picks

    def score(i, picks):
        rank, N, cutoff = universe_ranks(i)
        hit = 0
        pctiles = []
        for c in picks:
            r = rank.get(c)
            if r is None:
                continue
            pctiles.append((r - 1) / N * 100.0)
            if r <= cutoff:
                hit += 1
        return hit, N, cutoff, pctiles

    threshes = [0.20, 0.25, 0.30, 0.35, None]  # None = baseline(무제한)
    results = {t: [] for t in threshes}
    per_day_hits = {t: {} for t in threshes}

    for i in scoreable:
        d = dates[i]
        base_picks = select_baseline(i)
        for t in threshes:
            picks = base_picks if t is None else select_extcap(i, t)
            hit, N, cutoff, pctiles = score(i, picks)
            results[t].append(hit)
            per_day_hits[t][d] = hit

    n = len(scoreable)
    half = n // 2
    print(f"채점일수: {n}  (기간 {dates[scoreable[0]]} ~ {dates[scoreable[-1]]})")
    print("=" * 70)
    for t in threshes:
        vals = results[t]
        avg = sum(vals) / len(vals)
        train = sum(vals[:half]) / half
        test = sum(vals[half:]) / (len(vals) - half)
        five = sum(1 for v in vals if v == 5) / len(vals) * 100
        label = "baseline(무제한)" if t is None else f"mom20 캡 {t*100:.0f}%"
        print(f"{label:20s} 평균적중={avg:.3f}/5  train={train:.3f} test={test:.3f}  5/5={five:.1f}%")

    # 발동일(=baseline과 픽이 달라진 날) 한정 비교 — v2.2 B "발동 5일 이상" 요건
    print("-" * 70)
    print("발동일(baseline 대비 픽 변경) 한정 비교:")
    for i0, i in enumerate(scoreable):
        pass
    # recompute with picks stored
    changed_days = {t: [] for t in threshes if t is not None}
    base_all = {}
    for i in scoreable:
        base_all[i] = select_baseline(i)
    for t in threshes:
        if t is None:
            continue
        for i in scoreable:
            p = select_extcap(i, t)
            if set(p) != set(base_all[i]):
                changed_days[t].append(i)

    for t in threshes:
        if t is None:
            continue
        idxs = changed_days[t]
        if not idxs:
            print(f"  mom20 캡 {t*100:.0f}%: 발동일 0일 (필터 미발동)")
            continue
        base_hits = [results[None][scoreable.index(i)] for i in idxs]
        cap_hits = [results[t][scoreable.index(i)] for i in idxs]
        print(f"  mom20 캡 {t*100:.0f}%: 발동 {len(idxs)}일, baseline avg={sum(base_hits)/len(idxs):.3f} "
              f"-> capped avg={sum(cap_hits)/len(idxs):.3f}  (발동일: {[dates[i] for i in idxs]})")

    # 오늘(7/9 선정->7/10 채점) 케이스 직접 확인
    print("-" * 70)
    target_date = "20260709"
    if target_date in idx:
        i = idx[target_date]
        print(f"D={target_date} (선정) -> D+1={dates[i+1]} (채점):")
        base_picks = select_baseline(i)
        rank, N, cutoff = universe_ranks(i)
        print(f"  baseline picks: {base_picks}")
        for c in base_picks:
            r = rank.get(c)
            print(f"    {c} {names[c][:20]:20s} 순위 {r}/{N}")
        for t in [0.20, 0.25, 0.30, 0.35]:
            picks = select_extcap(i, t)
            hit, N2, cutoff2, pct = score(i, picks)
            print(f"  캡{t*100:.0f}%: picks={picks} hit={hit}/5")

if __name__ == "__main__":
    main()
