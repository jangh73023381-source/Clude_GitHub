#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rank_etf.py — 전체 ETF 익일 상승률 순위 채점 보조 스크립트.

입력: prices CSV (헤더: code,name,type,prev_close,next_close)
      - prev_close: 추천일(전날) 종가
      - next_close: 익일(D+1) 종가
      - type: 현물/레버리지/인버스 (표기용. 순위에는 전부 포함)
옵션:
  --prices  PATH        가격 CSV 경로 (필수)
  --picks   c1,c2,...   채점할 단기 추천 ETF 코드(보통 5개)
  --min-price N         유니버스 최소 전날 종가 (기본 10000)
  --top-pct P           상위 P% 컷오프 (기본 10)

규칙:
  - 전날 종가 >= min-price 인 종목만 유니버스에 포함(레버리지·인버스 포함, 채점 전용).
  - 상승률 = next_close/prev_close - 1, 내림차순 순위.
  - 상위 P% 컷오프 = ceil(N * P/100) 위.
  - 추천 5종이 '전부' 컷오프 이내면 목표 달성.

주의: 이 스크립트는 채점(평가)만 한다. 종목 '선정'은 analysis-method.md의 규칙으로,
      전날까지 가용 정보만 사용해 별도로 수행한다. next_close(결과)를 선정에 쓰지 말 것.
"""
import argparse, csv, math, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", required=True)
    ap.add_argument("--picks", default="")
    ap.add_argument("--min-price", type=float, default=10000)
    ap.add_argument("--top-pct", type=float, default=10.0)
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
            rows.append({
                "code": r["code"].strip().zfill(6),
                "name": r.get("name", "").strip(),
                "type": r.get("type", "").strip(),
                "ret": nc / pc - 1.0,
            })
    if not rows:
        sys.exit("유효한 유니버스 행이 없습니다 (전날 종가>=min-price 확인).")

    rows.sort(key=lambda x: x["ret"], reverse=True)
    N = len(rows)
    for i, x in enumerate(rows, 1):
        x["rank"] = i
        x["pctile"] = (i - 1) / N * 100.0  # 0=최상위
    cutoff = max(1, math.ceil(N * a.top_pct / 100.0))

    print(f"유니버스: {N}종 (전날 종가 >= {int(a.min_price):,}원)")
    print(f"상위 {a.top_pct:.0f}% 컷오프 = 상위 {cutoff}위 "
          f"(상승률 {rows[cutoff-1]['ret']*100:+.2f}% 이상)")
    print("-" * 64)
    print(f"{'순위':>4} {'코드':<8}{'종목':<22}{'유형':<6}{'상승률':>9}")
    for x in rows[:cutoff]:
        print(f"{x['rank']:>4} {x['code']:<8}{x['name'][:20]:<22}{x['type']:<6}{x['ret']*100:>8.2f}%")

    picks = [p.strip().zfill(6) for p in a.picks.split(",") if p.strip()]
    if picks:
        print("=" * 64)
        print("추천 종목 채점:")
        bycode = {x["code"]: x for x in rows}
        hit = 0
        for c in picks:
            x = bycode.get(c)
            if not x:
                print(f"  {c}: 유니버스에 없음(전날 종가<{int(a.min_price):,} 또는 데이터 누락)")
                continue
            ok = x["rank"] <= cutoff
            hit += 1 if ok else 0
            print(f"  {c} {x['name'][:18]:<18} 순위 {x['rank']:>3}/{N} "
                  f"(상위 {x['pctile']:.1f}%) 상승률 {x['ret']*100:+.2f}% "
                  f"{'✅상위10%' if ok else '❌미달'}")
        print("-" * 64)
        achieved = (hit == len(picks)) and len(picks) > 0
        print(f"적중: {hit}/{len(picks)}  →  목표(5종 전부 상위10%): "
              f"{'달성 ✅' if achieved else '미달 ❌'}")

if __name__ == "__main__":
    main()
