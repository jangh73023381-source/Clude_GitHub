#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 관심모멘텀 파일럿 ns2 사이드카 — '뉴스감성+검색'(유튜브 제외) 2축 변형을 전방검증한다.
# 2026-07-23 백테스트(정보소스비교) 결과 채택된 후보. 기존 shadow/v2 파일은 절대 건드리지 않고
# 신규 파일(attention_shadow_ns2_*.csv)에만 append. 20영업일 누적 후 base 대비 판정(G_ns2).
"""
사용:
  record --date YYYYMMDD --raw <raw csv>       # ns2 컴포짓·랭크 15섹터 기록
  score  --date YYYYMMDD --prices <prices csv> # top3_hit·rank-IC·픽5바스켓수익·시장초과 기록
  status                                        # ns2 vs base(참고) 누적 요약

정의(raw 신호는 v2.3와 동일):
  sent = (news_buy - news_sell) / max(news_total, 1)
  search = 원값(네이버 데이터랩)
  comp_ns2 = z(sent) + z(search)      # 유튜브(yt/yt20) 제외
z는 15섹터 횡단면 pstdev.
"""
import argparse, csv, os, sys, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(BASE)
THEMES = os.path.join(REF, "attention_pilot_themes.csv")
NS2_PICKS = os.path.join(REF, "attention_shadow_ns2_picks.csv")
NS2_RESULTS = os.path.join(REF, "attention_shadow_ns2_results.csv")
# 참고용(읽기 전용): 기존 shadow base 결과와 병렬 비교
SHADOW_RESULTS = os.path.join(REF, "attention_shadow_results.csv")

PICK_HEADER = ["date", "theme", "code", "etf", "sent", "z_sent", "z_search", "comp_ns2", "rk_ns2"]
RESULT_HEADER = ["score_date", "variant", "top5", "top3_hits", "rank_ic",
                 "pick5_ret", "excess_vs_mkt", "n_themes"]


def load_themes():
    with open(THEMES, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def zscores(vals):
    if len(vals) < 2:
        return [0.0] * len(vals)
    m = statistics.mean(vals)
    s = statistics.pstdev(vals)
    if s == 0:
        return [0.0] * len(vals)
    return [(v - m) / s for v in vals]


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


def _composites(rows):
    sent, search = [], []
    for r in rows:
        buy, sell, tot = float(r["news_buy"]), float(r["news_sell"]), float(r["news_total"])
        sent.append((buy - sell) / max(tot, 1.0))
        search.append(float(r["search"]))
    zs, zq = zscores(sent), zscores(search)
    out = []
    for i, r in enumerate(rows):
        out.append({"theme": r["theme"], "sent": sent[i], "zs": zs[i], "zq": zq[i],
                    "ns2": zs[i] + zq[i]})
    return out


def cmd_record(date, raw_path):
    themes = {t["theme"]: t for t in load_themes()}
    with open(raw_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or "news_buy" not in rows[0]:
        print(f"[{date}] raw 스키마가 v2 미만(news_buy 없음) — ns2 스킵"); return 1
    comps = _composites(rows)
    rk = {c["theme"]: i + 1 for i, c in enumerate(sorted(comps, key=lambda x: -x["ns2"]))}
    # 멱등: 같은 date가 이미 있으면 재기록 안 함
    if os.path.exists(NS2_PICKS):
        with open(NS2_PICKS, encoding="utf-8") as f:
            if any(r["date"] == date for r in csv.DictReader(f)):
                print(f"[{date}] ns2 picks 이미 존재 — 스킵"); 
                top5 = [c["theme"] for c in sorted(comps, key=lambda x: -x["ns2"])[:5]]
                print(f"[{date}] ns2 top5 = {top5}"); return 0
    exists = os.path.exists(NS2_PICKS)
    with open(NS2_PICKS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(PICK_HEADER)
        for c in comps:
            t = themes.get(c["theme"], {})
            w.writerow([date, c["theme"], t.get("code", ""), t.get("etf", ""),
                        f"{c['sent']:+.3f}", f"{c['zs']:.2f}", f"{c['zq']:.2f}",
                        f"{c['ns2']:+.3f}", rk[c["theme"]]])
    top5 = [c["theme"] for c in sorted(comps, key=lambda x: -x["ns2"])[:5]]
    print(f"[{date}] ns2 top5 = {top5}")
    return 0


def cmd_score(date, prices_path):
    themes = load_themes()
    prices = {}
    with open(prices_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                prices[r["code"]] = (float(r["prev_close"]), float(r["next_close"]))
            except (ValueError, KeyError):
                pass
    ret_by_theme = {}
    for t in themes:
        p = prices.get(t["code"])
        if p and p[0] > 0:
            ret_by_theme[t["theme"]] = 100.0 * (p[1] / p[0] - 1.0)
    scored = [t["theme"] for t in themes if t["theme"] in ret_by_theme]
    if len(scored) < 3:
        print(f"[{date}] 가격 매칭 부족(n={len(scored)}) — 스킵"); return 1
    top3 = sorted(scored, key=lambda th: -ret_by_theme[th])[:3]

    comp_rows = {}
    if os.path.exists(NS2_PICKS):
        with open(NS2_PICKS, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["date"] == date:
                    comp_rows[r["theme"]] = r
    if not comp_rows:
        print(f"[{date}] ns2 picks 없음 — record 먼저"); return 1
    # 멱등: 이미 채점된 date면 스킵
    if os.path.exists(NS2_RESULTS):
        with open(NS2_RESULTS, encoding="utf-8") as f:
            if any(r["score_date"] == date and r["variant"] == "ns2" for r in csv.DictReader(f)):
                print(f"[{date}] ns2 results 이미 존재 — 스킵"); return 0

    comps = [float(comp_rows[th]["comp_ns2"]) for th in scored]
    rets = [ret_by_theme[th] for th in scored]
    top5 = [th for th in sorted(scored, key=lambda x: -float(comp_rows[x]["comp_ns2"]))[:5]]
    hit3 = sum(1 for t in top3 if t in top5)
    ic = _spearman(comps, rets)
    pick5 = sum(ret_by_theme[t] for t in top5) / len(top5)
    mkt = sum(rets) / len(rets)

    exists = os.path.exists(NS2_RESULTS)
    with open(NS2_RESULTS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(RESULT_HEADER)
        w.writerow([date, "ns2", "|".join(top5), hit3, f"{ic:+.3f}",
                    f"{pick5:+.2f}", f"{pick5 - mkt:+.2f}", len(scored)])
        w.writerow([date, "mkt_mean", "", "", "", f"{mkt:+.2f}", "+0.00", len(scored)])

    print(f"[{date}] ns2 top3_hit={hit3}/3 rank_ic={ic:+.3f} pick5={pick5:+.2f}% "
          f"exc={pick5 - mkt:+.2f}%p top5={top5}")
    return 0


def cmd_status():
    if not os.path.exists(NS2_RESULTS):
        print("no ns2 results yet"); return 0
    with open(NS2_RESULTS, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["variant"] == "ns2"]
    if not rows:
        print("no ns2 rows"); return 0
    days = sorted(set(r["score_date"] for r in rows))
    n = len(rows)
    mh = sum(float(r["top3_hits"]) for r in rows) / n
    mic = sum(float(r["rank_ic"]) for r in rows) / n
    icp = sum(1 for r in rows if float(r["rank_ic"]) > 0)
    mp5 = sum(float(r["pick5_ret"]) for r in rows) / n
    mex = sum(float(r["excess_vs_mkt"]) for r in rows) / n
    print(f"[ns2] scored_days={len(days)} ({days[0]}~{days[-1]})  target=20영업일")
    print(f"  mean_hit3={mh:.2f}  mean_IC={mic:+.3f}  IC>0={icp}/{n}  "
          f"mean_pick5={mp5:+.2f}%  mean_excess={mex:+.2f}%p")
    # 참고: base 병렬(있으면)
    if os.path.exists(SHADOW_RESULTS):
        with open(SHADOW_RESULTS, encoding="utf-8") as f:
            br = [r for r in csv.DictReader(f) if r["variant"] == "base"]
        common = sorted(set(r["score_date"] for r in rows) & set(r["score_date"] for r in br))
        if common:
            bsub = [r for r in br if r["score_date"] in common]
            bmh = sum(float(r["top3_hits"]) for r in bsub) / len(bsub)
            bmic = sum(float(r["rank_ic"]) for r in bsub) / len(bsub)
            print(f"  [참고 base 동일{len(common)}일] mean_hit3={bmh:.2f}  mean_IC={bmic:+.3f}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("record"); p1.add_argument("--date", required=True); p1.add_argument("--raw", required=True)
    p2 = sub.add_parser("score"); p2.add_argument("--date", required=True); p2.add_argument("--prices", required=True)
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "record":
        sys.exit(cmd_record(a.date, a.raw))
    elif a.cmd == "score":
        sys.exit(cmd_score(a.date, a.prices))
    else:
        sys.exit(cmd_status())
