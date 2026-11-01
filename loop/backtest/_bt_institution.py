#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rule W 후보: 기관+외국인 결합 순매수 신호를 mom20+RuleH 베이스라인에 결합.
Rule V(외국인 단독, ETF 티커 단위, 49일)는 기각됐다. 이번엔 (a) 전체 90일 패널로 표본을 넓히고,
(b) 기관(orgn_net_qty)까지 결합해 재검증한다.
데이터: references/institution_trend_panel.csv (ka10045, 201종×90일 2026-03-03~07-10,
orgn_net_qty=기관 순매매수량, for_net_qty=외국인 순매매수량, 둘 다 일별·부호 +매수/-매도).

변형:
  W1 (기관+외국인 합산 게이팅): mom20+RuleH top-15 후보군 중 D일 (orgn_net_qty+for_net_qty)<0 배제.
  W2 (기관 단독 게이팅): D일 orgn_net_qty<0 배제.
  W3 (블렌드): score = mom20_pctile*(1-w) + (기관+외국인 합산)_pctile*w, w=0.3/0.5.
  W4 (연속 매수일수 게이팅): 최근 3일 기관+외국인 합산이 3일 모두 양수인 종목 가점(요건 미충족 시 배제 안 함, soft 가점).
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

def load_flow():
    fg = defaultdict(dict)
    with open(f"{BASE}/references/institution_trend_panel.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                orgn = float(r["orgn_net_qty"]); frgn = float(r["for_net_qty"])
                fg[r["code"]][r["date"]] = (orgn, frgn)
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
    fg = load_flow()
    codes = list(by_code.keys())
    types = {c: classify(names[c]) for c in codes}
    shorts = {c: is_short(names[c]) for c in codes}

    LOOKBACK = 20
    idx = {d: i for i, d in enumerate(dates)}
    fg_dates = sorted({d for v in fg.values() for d in v})

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

    def combined_flow(code, i, days=1):
        d_list = dates[max(0, i - days + 1): i + 1]
        tot = 0.0
        found = False
        for d in d_list:
            v = fg[code].get(d)
            if v is not None:
                tot += v[0] + v[1]
                found = True
        return tot if found else None

    def orgn_flow(code, i, days=1):
        d_list = dates[max(0, i - days + 1): i + 1]
        tot = 0.0
        found = False
        for d in d_list:
            v = fg[code].get(d)
            if v is not None:
                tot += v[0]
                found = True
        return tot if found else None

    def select_gate(i, flow_fn, days=1):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        pool = cands[:15]
        good = [x for x in pool if (flow_fn(x["code"], i, days) or 0) >= 0]
        picks = [x["code"] for x in good[:5]]
        if len(picks) < 5:
            rest = [x["code"] for x in pool if x["code"] not in picks]
            picks += rest[:5 - len(picks)]
        return picks

    def select_blend(i, w):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        pool = cands[:20]
        if not pool:
            return []
        n = len(pool)
        for k, x in enumerate(pool):
            x["mom_pct"] = 1 - k / n
        flows = [(x["code"], combined_flow(x["code"], i, 1) or 0) for x in pool]
        flows_sorted = sorted(flows, key=lambda t: -t[1])
        frank = {c: k for k, (c, v) in enumerate(flows_sorted)}
        for x in pool:
            x["flow_pct"] = 1 - frank[x["code"]] / n
            x["score"] = x["mom_pct"] * (1 - w) + x["flow_pct"] * w
        pool.sort(key=lambda x: -x["score"])
        return [x["code"] for x in pool[:5]]

    def select_persist3(i):
        # 최근 3일 연속 (기관+외국인) 순매수인 종목을 mom20 top15 풀 내에서 우선 배치
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        pool = cands[:15]
        def persist_ok(code):
            d_list = dates[max(0, i - 2): i + 1]
            vals = []
            for d in d_list:
                v = fg[code].get(d)
                if v is None:
                    return False
                vals.append(v[0] + v[1])
            return all(v > 0 for v in vals)
        good = [x for x in pool if persist_ok(x["code"])]
        picks = [x["code"] for x in good[:5]]
        if len(picks) < 5:
            rest = [x["code"] for x in pool if x["code"] not in picks]
            picks += rest[:5 - len(picks)]
        return picks

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
        "W1(합산1일게이팅)": lambda i: select_gate(i, combined_flow, 1),
        "W1b(합산3일게이팅)": lambda i: select_gate(i, combined_flow, 3),
        "W2(기관단독1일게이팅)": lambda i: select_gate(i, orgn_flow, 1),
        "W3(블렌드30%)": lambda i: select_blend(i, 0.3),
        "W3(블렌드50%)": lambda i: select_blend(i, 0.5),
        "W4(3일연속매수우선)": select_persist3,
    }
    results = {k: [] for k in variants}
    for i in scoreable:
        for k, fn in variants.items():
            picks = fn(i)
            results[k].append(score(i, picks))

    n = len(scoreable)
    half = n // 2
    print(f"채점일수: {n}  (기간 {dates[scoreable[0]]} ~ {dates[scoreable[-1]]})")
    print("=" * 70)
    for k, vals in results.items():
        avg = sum(vals) / len(vals)
        train = sum(vals[:half]) / half
        test = sum(vals[half:]) / (len(vals) - half)
        five = sum(1 for v in vals if v == 5) / len(vals) * 100
        print(f"{k:20s} 평균적중={avg:.3f}/5  train={train:.3f} test={test:.3f}  5/5={five:.1f}%")

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
