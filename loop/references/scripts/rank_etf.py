#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rank_etf.py — 전체 ETF 익일 상승률 순위 채점 보조 스크립트.
채점만 수행하며 next_close(결과)를 선정에 쓰지 않는다.

유니버스(2026-07-30 정렬): 파생(레버리지·인버스·숏, v1.2)과 현금성(v2.7)을 제외한다.
종전에는 '숏'만 제외해 dual_score.py 와 컷오프가 어긋났다 — 과최적화 가드가 "방법 확정 판단은
rank_etf OOS 누적"으로 정한 만큼, 채점 유니버스는 선정 유니버스와 같아야 한다.
최소가격 필터는 2026-07-30 사용자 지시로 폐지(--min-price 기본 0).
'은선물/골드선물'은 '숏' 미포함이라 그대로 유지된다."""
import argparse, csv, math, sys

from universe_filters import eligible

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", required=True)
    ap.add_argument("--picks", default="")
    ap.add_argument("--min-price", type=float, default=0)  # 2026-07-30 최소가격 필터 폐지
    ap.add_argument("--top-pct", type=float, default=10.0)
    ap.add_argument("--context", choices=["oos", "insample", ""], default="",
                    help="oos=워크포워드(방법 확정 후 미래 관측, 유효증거) / insample=개발중 재선정(선택편의 주의)")
    ap.add_argument("--trials", type=int, default=0,
                    help="지금까지 시도한 distinct 규칙 변형 누적 수 N(과최적화 경고용)")
    a = ap.parse_args()

    rows = []
    with open(a.prices, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                pc = float(r["prev_close"]); nc = float(r["next_close"])
            except (ValueError, KeyError):
                continue
            if pc < a.min_price or pc <= 0:
                continue
            if not eligible(r.get("name", "")):
                continue
            rows.append({"code": r["code"].strip().zfill(6),
                         "name": r.get("name", "").strip(),
                         "type": r.get("type", "").strip(),
                         "ret": nc / pc - 1.0})
    if not rows:
        sys.exit("no valid universe rows")

    rows.sort(key=lambda x: x["ret"], reverse=True)
    N = len(rows)
    for i, x in enumerate(rows, 1):
        x["rank"] = i
        x["pctile"] = (i - 1) / N * 100.0
    cutoff = max(1, math.ceil(N * a.top_pct / 100.0))

    print("유니버스: %d종 (전날종가>=%s원, 파생·현금성 제외 — dual_score.py 와 동일 기준)"
          % (N, format(int(a.min_price), ",")))
    print("상위 %.0f%% 컷오프 = 상위 %d위 (상승률 %+.2f%% 이상)" % (a.top_pct, cutoff, rows[cutoff-1]["ret"]*100))
    print("-" * 60)
    for x in rows[:cutoff]:
        print("%4d %-8s %-22s %-6s %7.2f%%" % (x["rank"], x["code"], x["name"][:20], x["type"], x["ret"]*100))

    picks = [p.strip().zfill(6) for p in a.picks.split(",") if p.strip()]
    if picks:
        print("=" * 60)
        print("추천 종목 채점:")
        bycode = {x["code"]: x for x in rows}
        hit = 0
        for c in picks:
            x = bycode.get(c)
            if not x:
                print("  %s: 유니버스에 없음(종가<min, 숏선물, 또는 데이터 누락)" % c)
                continue
            ok = x["rank"] <= cutoff
            hit += 1 if ok else 0
            print("  %s %-18s 순위 %3d/%d (상위 %.1f%%) 상승률 %+.2f%% %s" % (
                c, x["name"][:18], x["rank"], N, x["pctile"], x["ret"]*100,
                "[적중]" if ok else "[미달]"))
        print("-" * 60)
        achieved = (hit == len(picks)) and len(picks) > 0
        print("적중: %d/%d  ->  목표(5종 전부 상위10%%): %s" % (hit, len(picks), "달성" if achieved else "미달"))
        # 과최적화 가드(2026-07-17 추가): in-sample 재선정 결과는 시도 수 N에 따라 선택편의로 부풀 수 있음.
        if a.context == "insample":
            msg = "IN-SAMPLE 재선정(개발셋) - 단일일 결과는 방법 확정 근거가 아님."
            if a.trials > 0:
                msg += " 지금까지 distinct 시도 N=%d -> best-of-N 선택편의. OOS(워크포워드)로 재확인 필요." % a.trials
            print("[과최적화 가드] " + msg)
        elif a.context == "oos":
            print("[워크포워드/OOS] 방법 확정 후 미래 관측치 - 유효 증거(loop-log 워크포워드 트래커에 기입).")

if __name__ == "__main__":
    main()
