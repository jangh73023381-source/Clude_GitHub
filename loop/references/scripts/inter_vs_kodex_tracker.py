#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INTER(순수 관심·감성조건화) 섹터 픽5 vs KODEX200 일일 워크포워드 트래커.

관심 파일럿 shadow가 매일 기록하는 `attention_shadow_picks.csv`(comp_inter)에서 그날 INTER 상위 5섹터를
뽑아, 각 섹터 대표 ETF의 당일 수익(동일가중)과 KODEX200(069500) 당일 수익을 비교해 초과수익을
`inter_vs_kodex_tracker.csv`에 한 줄씩 누적한다.

- 멱등: 이미 기록된 date는 다시 추가하지 않는다(매일/여러 번 실행해도 안전).
- 데이터 소스: 키움 REST 일봉(get_daily_chart, 코드별 1회 호출로 전체 이력 확보). 조회 전용.
- 수익 정의: score_date 종가 / 직전 거래일 종가 − 1 (파일럿 장전윈도 선정 → 당일 종가 청산 가정).
- 룩어헤드 없음: INTER 픽은 파일럿이 장전 신호로 사전 확정한 것, 수익은 채점만.

사용법:
  python3 inter_vs_kodex_tracker.py            # 신규 파일럿일 자동 감지·누적
  python3 inter_vs_kodex_tracker.py --show     # 누적 트래커만 출력(수집 없이)
"""
import argparse, csv, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(os.path.dirname(HERE))          # .../loop
REF = os.path.join(LOOP, "references")
PICKS = os.path.join(REF, "attention_shadow_picks.csv")
TRACKER = os.path.join(REF, "inter_vs_kodex_tracker.csv")
BENCH = "069500"
FIELDS = ["date", "inter_pick5_sectors", "inter_pick5_codes",
          "pick5_ret_pct", "kodex200_ret_pct", "excess_vs_kodex_pct", "note"]

sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402


def load_tracker():
    if not os.path.exists(TRACKER):
        return []
    with open(TRACKER, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_inter_picks():
    """date -> [(theme, code, comp_inter)]; INTER 상위 5섹터 반환."""
    if not os.path.exists(PICKS):
        sys.exit("attention_shadow_picks.csv 없음 — 파일럿 shadow 기록 먼저 필요")
    by = {}
    with open(PICKS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by.setdefault(r["date"], []).append(
                (r["theme"], r["code"].strip().zfill(6), float(r["comp_inter"])))
    picks = {}
    for d, rows in by.items():
        top5 = sorted(rows, key=lambda x: x[2], reverse=True)[:5]
        picks[d] = [(t, c) for t, c, _ in top5]
    return picks


def fetch_closes(codes):
    """코드별 일봉 1회 호출 → {code: {dt: close}}. 429 재시도."""
    out = {}
    for c in sorted(codes):
        for attempt in range(4):
            try:
                d = k.get_daily_chart(c, "00000000")  # 최신 기준 전체 이력
                arr = d.get("stk_dt_pole_chart_qry", [])
                out[c] = {x["dt"]: abs(float(x["cur_prc"])) for x in arr}
                break
            except Exception as e:
                if "429" in str(e) and attempt < 3:
                    time.sleep(1.5); continue
                out[c] = {}
        time.sleep(0.15)
    return out


def prior_trading_day(cal, d):
    if d not in cal:
        return None
    i = cal.index(d)
    return cal[i - 1] if i > 0 else None


def ret(px, code, d, cal):
    pd = prior_trading_day(cal, d)
    if pd is None:
        return None
    a = px.get(code, {}).get(pd); b = px.get(code, {}).get(d)
    return (b / a - 1.0) if (a and b) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="누적 트래커만 출력")
    a = ap.parse_args()

    existing = load_tracker()
    done = {r["date"] for r in existing}

    if a.show:
        _summary(existing)
        return

    picks = load_inter_picks()
    new_dates = sorted(d for d in picks if d not in done)
    if not new_dates:
        print("신규 파일럿일 없음 — 트래커 %d행 유지." % len(existing))
        _summary(existing)
        return

    codes = {BENCH}
    for d in new_dates:
        codes.update(c for _, c in picks[d])
    print("신규 %d일 %s / 조회 코드 %d개 …" % (len(new_dates), new_dates, len(codes)))
    px = fetch_closes(codes)
    cal = sorted(px.get(BENCH, {}).keys())

    rows = list(existing)
    for d in new_dates:
        sectors = [t for t, _ in picks[d]]
        pcodes = [c for _, c in picks[d]]
        rets = [ret(px, c, d, cal) for c in pcodes]
        got = [r for r in rets if r is not None]
        miss = [pcodes[i] for i, r in enumerate(rets) if r is None]
        kd = ret(px, BENCH, d, cal)
        if not got or kd is None:
            note = "결측(픽결측%d, KODEX%s)" % (len(miss), "없음" if kd is None else "OK")
            rows.append({"date": d, "inter_pick5_sectors": "|".join(sectors),
                         "inter_pick5_codes": "|".join(pcodes), "pick5_ret_pct": "",
                         "kodex200_ret_pct": "" if kd is None else "%.2f" % (kd * 100),
                         "excess_vs_kodex_pct": "", "note": note})
            continue
        pr = sum(got) / len(got)
        note = "" if not miss else "픽결측:" + ",".join(miss)
        rows.append({"date": d, "inter_pick5_sectors": "|".join(sectors),
                     "inter_pick5_codes": "|".join(pcodes),
                     "pick5_ret_pct": "%.2f" % (pr * 100),
                     "kodex200_ret_pct": "%.2f" % (kd * 100),
                     "excess_vs_kodex_pct": "%.2f" % ((pr - kd) * 100), "note": note})

    rows.sort(key=lambda r: r["date"])
    with open(TRACKER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print("트래커 갱신: +%d행 (총 %d행) -> %s" % (len(new_dates), len(rows), os.path.basename(TRACKER)))
    _summary(rows)


def _summary(rows):
    ex = [float(r["excess_vs_kodex_pct"]) for r in rows
          if r.get("excess_vs_kodex_pct") not in (None, "")]
    if not ex:
        print("(누적 초과수익 데이터 없음)")
        return
    n = len(ex); mean = sum(ex) / n; win = sum(1 for x in ex if x > 0)
    print("-" * 64)
    print("누적 %d일 | vs KODEX200 평균초과 %+.2f%%p | 지수이김 %d/%d(%.0f%%) | 20일까지 %d일 남음"
          % (n, mean, win, n, win / n * 100, max(0, 20 - n)))
    print("판정 기준(orchestration): 20영업일 누적 후 KODEX200 대비 유의 초과 시에만 루프 편입 검토.")


if __name__ == "__main__":
    main()
