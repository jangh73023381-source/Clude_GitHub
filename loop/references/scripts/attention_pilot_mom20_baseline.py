#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 관심모멘텀 섹터 채점용 mom20 베이스라인 — 15섹터 ETF의 20거래일 모멘텀으로 상위5를 매일
# 산출·shadow와 동일 rank-IC/top3_hit로 채점한다(병렬 비교용, 방법 변경 아님).
"""
사용:
  backfill --panel <panel_close csv> --results <attention_shadow_results.csv에 append>
    지정 없으면 panel_close_0715.csv, attention_shadow_results.csv 기본값.
"""
import csv, os, sys, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(BASE)
THEMES = os.path.join(REF, "attention_pilot_themes.csv")
DEFAULT_PANEL = os.path.join(os.path.dirname(REF), "backtest", "panel_close_0715.csv")
RESULTS = os.path.join(REF, "attention_shadow_results.csv")

SCORE_DATES = ["20260709", "20260710", "20260713", "20260714", "20260715", "20260716"]
LOOKBACK = 20


def load_themes():
    with open(THEMES, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_panel(path):
    # code -> {date(str YYYYMMDD): close}
    panel = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            panel.setdefault(r["code"], {})[r["date"]] = float(r["close"])
    return panel


def _ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    rk = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            rk[order[k]] = avg
        i = j + 1
    return rk


def _spearman(a, b):
    ra, rb = _ranks(a), _ranks(b)
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def mom20(panel, code, asof_dates, d_index):
    """d_index: asof_dates 내 '전일'(D-1) 위치. D-1과 D-21 종가로 20거래일 모멘텀."""
    if d_index < LOOKBACK:
        return None
    d_minus_1 = asof_dates[d_index]
    d_minus_21 = asof_dates[d_index - LOOKBACK]
    series = panel.get(code, {})
    c1, c21 = series.get(d_minus_1), series.get(d_minus_21)
    if c1 is None or c21 is None or c21 == 0:
        return None
    return 100.0 * (c1 / c21 - 1.0)


def main():
    panel_path = DEFAULT_PANEL
    if "--panel" in sys.argv:
        panel_path = sys.argv[sys.argv.index("--panel") + 1]
    panel = load_panel(panel_path)
    themes = load_themes()
    # 전체 거래일(오름차순) — 아무 코드의 date 합집합
    all_dates = sorted({d for series in panel.values() for d in series})

    exists = os.path.exists(RESULTS)
    rows_out = []
    for d in SCORE_DATES:
        if d not in all_dates:
            print(f"[{d}] panel에 해당일 종가 없음 — mom20 스킵(D-1 기준일 자체가 없음)")
            continue
        d_idx = all_dates.index(d)
        # mom20은 D의 '전일' 기준이어야 하므로 d_idx-1을 D-1로 삼는다
        if d_idx == 0:
            continue
        moms = []
        for t in themes:
            m = mom20(panel, t["code"], all_dates, d_idx - 1)
            moms.append((m, t["theme"], t["code"]))
        valid = [(m, th, c) for m, th, c in moms if m is not None]
        if len(valid) < 3:
            print(f"[{d}] 유효 mom20 부족(n={len(valid)}) — 스킵"); continue
        ranked_mom = sorted(valid, reverse=True)
        top5 = [th for _, th, _ in ranked_mom[:5]]

        # 실현수익(D-1->D)으로 채점 — 기존 shadow 스코어와 동일 소스가 이상적이나 panel_close로 근사
        rets, rthemes = [], []
        for t in themes:
            series = panel.get(t["code"], {})
            c_prev, c_d = series.get(all_dates[d_idx - 1]), series.get(d)
            if c_prev and c_d and c_prev > 0:
                rets.append(100.0 * (c_d / c_prev - 1.0))
                rthemes.append(t["theme"])
        if len(rthemes) < 3:
            print(f"[{d}] 실현수익 부족 — top5만 출력, 채점 스킵: {top5}"); continue
        top3_actual = [th for _, th in sorted(zip(rets, rthemes), reverse=True)[:3]]
        hit3 = sum(1 for th in top3_actual if th in top5)
        mom_by_theme = {th: m for m, th, _ in valid}
        comp_aligned = [mom_by_theme[th] for th in rthemes if th in mom_by_theme]
        ret_aligned = [rets[i] for i, th in enumerate(rthemes) if th in mom_by_theme]
        ic = _spearman(comp_aligned, ret_aligned) if len(comp_aligned) >= 3 else 0.0
        rows_out.append([d, "mom20", "|".join(top5), hit3, f"{ic:+.3f}", len(rthemes)])
        print(f"[{d}] mom20 top5={top5} hit3={hit3}/3 ic={ic:+.3f} (실현수익 panel_close 근사)")

    if rows_out:
        with open(RESULTS, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(["score_date", "variant", "top5", "top3_hits", "rank_ic", "n_themes"])
            w.writerows(rows_out)
        print(f"\n{len(rows_out)}건 attention_shadow_results.csv에 append (variant=mom20)")


if __name__ == "__main__":
    main()
