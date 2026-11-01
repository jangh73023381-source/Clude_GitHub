#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rule U 후보: 해외추종형(overseas-underlying) ETF 캡.
배경(2026-07-10 루프): mom20+RuleH 베이스라인 top5 중 4/5(396520 차이나반도체·0162L0 차이나AI반도체·
0043Y0 차이나AI테크·0181B0 미국AI메모리반도체)가 해외(중국·미국) 종목을 추종하는 ETF였고, 이 4종
전부 익일(7/10) 하위~중위권으로 부진(3종은 하위 2%, 1종은 중위권)한 반면 국내 상장기업을 담는
반도체 소부장·원자력·AI전력·방산우주·증권 ETF가 상위권을 차지. 해외추종형은 원화 환헤지·해외
현지 시차·NAV 산정 방식 등으로 국내 수급 모멘텀(mom20)의 지속성이 약할 수 있다는 가설을 검증.

분류: ETF명에 '차이나/미국/글로벌/S&P/나스닥/필라델피아/다우존스/항셍/베트남/인도/일본/유럽/독일/
대만/TSMC/차스닥' 중 하나라도 포함되면 '해외추종형'으로 분류(휴리스틱, 수작업 라벨 아님).

패널: panel_close.csv (201종×90일). Rule Q/T와 동일 프레임.
"""
import csv
import math
from collections import defaultdict

BASE = "/sessions/festive-kind-meitner/mnt/loop"
OVERSEA_KW = ['차이나','미국','글로벌','S&P','나스닥','필라델피아','다우존스','항셍','베트남','인도','일본','유럽','독일','대만','TSMC','차스닥']

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

def is_oversea(name):
    return any(k in (name or "") for k in OVERSEA_KW)

def main():
    by_code, names, dates = load_panel()
    codes = list(by_code.keys())
    types = {c: classify(names[c]) for c in codes}
    shorts = {c: is_short(names[c]) for c in codes}
    overseas = {c: is_oversea(names[c]) for c in codes}
    n_oversea = sum(overseas.values())
    print(f"해외추종형 분류: {n_oversea}/{len(codes)}종")

    idx = {d: i for i, d in enumerate(dates)}
    LOOKBACK = 20
    scoreable = [i for i in range(len(dates)) if i - LOOKBACK >= 0 and i + 1 < len(dates)]

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

    def select_capped(i, max_oversea):
        cands = [x for x in candidates_mom20(i) if rule_h_ok(x)]
        cands.sort(key=lambda x: -x["mom20"])
        picks = []
        n_ov = 0
        for x in cands:
            if len(picks) >= 5:
                break
            if overseas[x["code"]]:
                if n_ov >= max_oversea:
                    continue
                n_ov += 1
            picks.append(x["code"])
        return picks

    def score(i, picks):
        rank, N, cutoff = universe_ranks(i)
        hit = 0
        for c in picks:
            r = rank.get(c)
            if r is not None and r <= cutoff:
                hit += 1
        return hit, N, cutoff

    caps = [0, 1, 2, None]  # None = baseline
    results = {cap: [] for cap in caps}
    for i in scoreable:
        for cap in caps:
            picks = select_baseline(i) if cap is None else select_capped(i, cap)
            hit, N, cutoff = score(i, picks)
            results[cap].append(hit)

    n = len(scoreable)
    half = n // 2
    print(f"채점일수: {n}  (기간 {dates[scoreable[0]]} ~ {dates[scoreable[-1]]})")
    print("=" * 70)
    for cap in caps:
        vals = results[cap]
        avg = sum(vals) / len(vals)
        train = sum(vals[:half]) / half
        test = sum(vals[half:]) / (len(vals) - half)
        five = sum(1 for v in vals if v == 5) / len(vals) * 100
        label = "baseline(무제한)" if cap is None else f"해외추종 최대{cap}종"
        print(f"{label:20s} 평균적중={avg:.3f}/5  train={train:.3f} test={test:.3f}  5/5={five:.1f}%")

    print("-" * 70)
    print("발동일(baseline 대비 픽 변경) 한정 비교:")
    base_all = {i: select_baseline(i) for i in scoreable}
    for cap in caps:
        if cap is None:
            continue
        idxs = [i for i in scoreable if set(select_capped(i, cap)) != set(base_all[i])]
        if not idxs:
            print(f"  해외추종 최대{cap}종: 발동일 0일")
            continue
        base_hits = [results[None][scoreable.index(i)] for i in idxs]
        cap_hits = [results[cap][scoreable.index(i)] for i in idxs]
        print(f"  해외추종 최대{cap}종: 발동 {len(idxs)}일, baseline avg={sum(base_hits)/len(idxs):.3f} "
              f"-> capped avg={sum(cap_hits)/len(idxs):.3f}")
        print(f"    발동일: {[dates[i] for i in idxs]}")

    print("-" * 70)
    target_date = "20260709"
    i = idx[target_date]
    print(f"D={target_date} (선정) -> D+1={dates[i+1]} (채점):")
    print(f"  baseline picks: {select_baseline(i)}")
    rank, N, cutoff = universe_ranks(i)
    for c in select_baseline(i):
        print(f"    {c} {names[c][:22]:22s} 해외={overseas[c]} 순위 {rank.get(c)}/{N}")
    for cap in [0, 1, 2]:
        picks = select_capped(i, cap)
        hit, N2, cutoff2 = score(i, picks)
        print(f"  해외추종 최대{cap}종: picks={picks} hit={hit}/5")
        for c in picks:
            print(f"      {c} {names[c][:22]:22s} 해외={overseas[c]} 순위 {rank.get(c)}/{N}")

if __name__ == "__main__":
    main()
