#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rule V 후보: 외국인 순매수(수급) 신호를 mom20+RuleH 베이스라인에 결합.
데이터: references/foreign_trend_panel.csv (ka10008, 201종×50일 2026-04-28~07-10, chg_qty=외국인
보유 변화 수량[일별], wght=외국인 보유비중[%]).

변형:
  V1 (게이팅): mom20+RuleH top-15 후보군 중 D일 chg_qty<0(외국인 순매도)인 종목은 배제 후 mom20 재정렬,
               5종 못 채우면 chg_qty 부호 무관하게 mom20 순위로 채움.
  V2 (2일 누적 게이팅): 위와 동일하되 D+D-1 chg_qty 합계 <0 이면 배제.
  V3 (블렌드 스코어): score = mom20_pctile*0.7 + frgn_flow_pctile*0.3 (그날 후보군 내 percentile).
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

def load_foreign():
    fg = defaultdict(dict)
    with open(f"{BASE}/references/foreign_trend_panel.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                fg[r["code"]][r["date"]] = float(r["chg_qty"])
            except ValueError:
                pass
    return fg

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
    fg = load_foreign()
    codes = list(by_code.keys())
    types = {c: classify(names[c]) for c in codes}
    shorts = {c: is_short(names[c]) for c in codes}

    fg_dates = sorted({d for v in fg.values() for d in v})
    LOOKBACK = 20
    idx = {d: i for i, d in enumerate(dates)}

    # 수급 데이터 있는 날짜만 채점 대상(D, D+1 종가·D-20 종가 모두 필요)
    scoreable = []
    for d in fg_dates:
        if d not in idx:
            continue
        i = idx[d]
        if i - LOOKBACK < 0 or i + 1 >= len(dates):
            continue
        scoreable.append(i)

    def get(code, i):
        return by_code[code].get(dates[i])

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

    def flow(code, i, days=1):
        d_list = dates[max(0, i - days + 1): i + 1]
        vals = [fg[code].get(d) for d in d_list]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None

    def select_v1(i):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        pool = cands[:15]
        good = [x for x in pool if (flow(x["code"], i, 1) or 0) >= 0]
        picks = [x["code"] for x in good[:5]]
        if len(picks) < 5:
            rest = [x["code"] for x in pool if x["code"] not in picks]
            picks += rest[:5 - len(picks)]
        return picks

    def select_v2(i):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        pool = cands[:15]
        good = [x for x in pool if (flow(x["code"], i, 2) or 0) >= 0]
        picks = [x["code"] for x in good[:5]]
        if len(picks) < 5:
            rest = [x["code"] for x in pool if x["code"] not in picks]
            picks += rest[:5 - len(picks)]
        return picks

    def select_v3(i, w=0.3):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        pool = cands[:20]
        if not pool:
            return []
        n = len(pool)
        for k, x in enumerate(pool):
            x["mom_pct"] = 1 - k / n
        flows = [(x["code"], flow(x["code"], i, 1) or 0) for x in pool]
        flows_sorted = sorted(flows, key=lambda t: -t[1])
        frank = {c: k for k, (c, v) in enumerate(flows_sorted)}
        for x in pool:
            x["flow_pct"] = 1 - frank[x["code"]] / n
            x["score"] = x["mom_pct"] * (1 - w) + x["flow_pct"] * w
        pool.sort(key=lambda x: -x["score"])
        return [x["code"] for x in pool[:5]]

    def score(i, picks):
        rank, N, cutoff = universe_ranks(i)
        hit = 0
        for c in picks:
            r = rank.get(c)
            if r is not None and r <= cutoff:
                hit += 1
        return hit

    variants = {
        "baseline": select_baseline,
        "V1(1일게이팅)": select_v1,
        "V2(2일누적게이팅)": select_v2,
        "V3(블렌드30%)": lambda i: select_v3(i, 0.3),
        "V3(블렌드50%)": lambda i: select_v3(i, 0.5),
    }
    results = {k: [] for k in variants}
    for i in scoreable:
        for k, fn in variants.items():
            picks = fn(i)
            results[k].append(score(i, picks))

    n = len(scoreable)
    half = n // 2
    print(f"채점일수: {n}  (기간 {dates[scoreable[0]]} ~ {dates[scoreable[-1]]}, 수급데이터 가용구간 한정)")
    print("=" * 70)
    for k, vals in results.items():
        avg = sum(vals) / len(vals)
        train = sum(vals[:half]) / half
        test = sum(vals[half:]) / (len(vals) - half)
        five = sum(1 for v in vals if v == 5) / len(vals) * 100
        print(f"{k:18s} 평균적중={avg:.3f}/5  train={train:.3f} test={test:.3f}  5/5={five:.1f}%")

    print("-" * 70)
    print("발동일(baseline 대비 픽 변경) 한정 비교:")
    base_all = {i: select_baseline(i) for i in scoreable}
    for k, fn in variants.items():
        if k == "baseline":
            continue
        idxs = [i for i in scoreable if set(fn(i)) != set(base_all[i])]
        if not idxs:
            print(f"  {k}: 발동일 0일")
            continue
        bh = [results["baseline"][scoreable.index(i)] for i in idxs]
        vh = [results[k][scoreable.index(i)] for i in idxs]
        print(f"  {k}: 발동 {len(idxs)}일, baseline avg={sum(bh)/len(idxs):.3f} -> avg={sum(vh)/len(idxs):.3f}")

    print("-" * 70)
    target_date = "20260709"
    i = idx[target_date]
    print(f"D={target_date} (선정) -> D+1={dates[i+1]} (채점):")
    for k, fn in variants.items():
        picks = fn(i)
        hit = score(i, picks)
        print(f"  {k}: picks={picks} hit={hit}/5")

if __name__ == "__main__":
    main()
