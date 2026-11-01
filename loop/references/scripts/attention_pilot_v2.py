#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
관심 모멘텀 파일럿 v2.0/v2.3 — 섹터(테마) 단위 추천·채점
변경점(v2.0 → v2.3, 2026-07-14): yt20 신호 추가.
  composite_v3 = z(sent_news) + z(search_mom) + z(yt_net) + z(yt20_net)
  raw csv에 yt20_total 컬럼이 있으면 v3(4항), 없으면 v2(3항)로 자동 폴백.
  PICKS csv 헤더는 하위호환을 위해 기존 15열 뒤에
  yt20_buy, yt20_sell, yt20_z, composite_ver 4열을 추가(기존 행은 빈값+"v2").
사용:
  record --date YYYYMMDD --raw <raw csv>
  score  --date YYYYMMDD --prices <prices csv>
  status
"""
import argparse, csv, os, sys, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(BASE)
THEMES = os.path.join(REF, "attention_pilot_themes.csv")
PICKS = os.path.join(REF, "attention_pilot_v2_picks.csv")
RESULTS = os.path.join(REF, "attention_pilot_v2_results.csv")

OLD_HEADER = ["date", "rank", "theme", "code", "etf", "composite_v2",
              "sent_news", "sent_z", "search_z", "yt_z",
              "news_buy", "news_sell", "news_neutral", "yt_buy", "yt_sell"]
NEW_COLS = ["yt20_buy", "yt20_sell", "yt20_z", "composite_ver"]
V3_HEADER = OLD_HEADER + NEW_COLS



def _f(x, default=0.0):
    """빈 문자열은 '미수집'을 뜻한다(v2.3에서 유튜브 수집 폐지 — 0으로 채우면 '진짜 0'과 구분이
    안 된다). 산술에서는 0으로 처리하되, 15테마가 전부 0이면 zscores()가 전부 0을 돌려주고
    shadow 의 liveness 게이트(_live)도 해당 모달리티를 자동 제외하므로 결과적으로
    '컴포짓에서 빠지는' 올바른 동작이 된다."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

def _migrate_picks_header():
    if not os.path.exists(PICKS):
        return
    with open(PICKS, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    header = rows[0]
    if header == V3_HEADER:
        return
    if header != OLD_HEADER:
        return
    new_rows = [V3_HEADER]
    for r in rows[1:]:
        new_rows.append(r + ["", "", "", "v2"])
    with open(PICKS, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(new_rows)


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


def cmd_record(date, raw_path):
    themes = {t["theme"]: t for t in load_themes()}
    with open(raw_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    has_yt20 = len(rows) > 0 and all("yt20_total" in r for r in rows)
    sent, search, ytnet, yt20net = [], [], [], []
    for r in rows:
        total = max(_f(r["news_total"]), 1.0)
        sent.append((_f(r["news_buy"]) - _f(r["news_sell"])) / total)
        search.append(_f(r["search"]))
        ytnet.append(_f(r["yt_buy"]) - _f(r["yt_sell"]))
        if has_yt20:
            yt20net.append(float(r.get("yt20_buy", 0) or 0) - float(r.get("yt20_sell", 0) or 0))
    zs, zq, zy = zscores(sent), zscores(search), zscores(ytnet)
    zt = zscores(yt20net) if has_yt20 else [0.0] * len(rows)
    version = "v3" if has_yt20 else "v2"
    scored = []
    for i, r in enumerate(rows):
        comp = zs[i] + zq[i] + zy[i] + (zt[i] if has_yt20 else 0.0)
        scored.append((comp, r["theme"], zs[i], zq[i], zy[i], zt[i], sent[i], r))
    scored.sort(reverse=True)

    _migrate_picks_header()
    exists = os.path.exists(PICKS)
    # 멱등 보장(2026-07-30 신설) — 같은 날짜 행이 있으면 다시 쓰지 않는다(shadow 와 동일 사유).
    if exists:
        with open(PICKS, encoding="utf-8") as f0:
            if any(r and r[0] == date for r in csv.reader(f0)):
                print(f"  [v2] {date} 이미 기록됨 — 생략(멱등)")
                return
    with open(PICKS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(V3_HEADER)
        for rank, (comp, th, a, b, c, ty, sn, r) in enumerate(scored[:5], 1):
            t = themes.get(th, {})
            w.writerow([date, rank, th, t.get("code", ""), t.get("etf", ""),
                        f"{comp:.3f}", f"{sn:.3f}", f"{a:.2f}", f"{b:.2f}", f"{c:.2f}",
                        r["news_buy"], r["news_sell"], r["news_neutral"],
                        r["yt_buy"], r["yt_sell"],
                        r.get("yt20_buy", "") if has_yt20 else "",
                        r.get("yt20_sell", "") if has_yt20 else "",
                        f"{ty:.2f}" if has_yt20 else "",
                        version])
    print(f"[composite_{version}] {'yt20 반영' if has_yt20 else 'yt20 미반영(raw v2 폴백)'}")
    for rank, (comp, th, *_rest) in enumerate(scored, 1):
        mark = " *" if rank <= 5 else ""
        print(f"{rank:2d}. {th:6s} comp={comp:+.3f}{mark}")
    return 0


def cmd_score(date, prices_path):
    themes = load_themes()
    prices = {}
    with open(prices_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                prices[r["code"]] = (_f(r["prev_close"]), _f(r["next_close"]))
            except (ValueError, KeyError):
                pass
    rets = []
    for t in themes:
        p = prices.get(t["code"])
        if p and p[0] > 0:
            rets.append((100.0 * (p[1] / p[0] - 1.0), t["theme"], t["code"], t["etf"]))
        else:
            rets.append((None, t["theme"], t["code"], t["etf"]))
    ranked = sorted([r for r in rets if r[0] is not None], reverse=True)
    rank_of = {r[1]: i + 1 for i, r in enumerate(ranked)}
    top3 = [r[1] for r in ranked[:3]]
    picks = []
    with open(PICKS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["date"] == date:
                picks.append(r["theme"])
    if not picks:
        print(f"no v2 picks recorded for {date}"); return 1
    hit3 = sum(1 for t in top3 if t in picks)
    success = int(hit3 == 3)
    exists = os.path.exists(RESULTS)
    with open(RESULTS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["score_date", "picks", "top3_sectors", "top3_hits",
                        "success", "pick_ranks", "sector_N"])
        w.writerow([date, "|".join(picks), "|".join(top3), hit3, success,
                    "|".join(str(rank_of.get(p, "-")) for p in picks), len(ranked)])
    print(f"[{date}] 섹터 수익률 순위 (N={len(ranked)})")
    for i, (ret, th, code, etf) in enumerate(ranked, 1):
        m = " <PICK" if th in picks else ""
        t3 = " [TOP3]" if i <= 3 else ""
        print(f"{i:2d}. {th:6s} {ret:+.2f}%{t3}{m}")
    print(f"\nTOP3 = {top3} / picks5 = {picks}")
    print(f"top3 hit {hit3}/3 -> {'SUCCESS' if success else 'FAIL'}")
    return 0


def cmd_status():
    if not os.path.exists(RESULTS):
        print("no results yet"); return 0
    with open(RESULTS, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    s = sum(int(r["success"]) for r in rows)
    h = sum(int(r["top3_hits"]) for r in rows)
    print(f"scored_days={n} SUCCESS={s}/{n} top3_slot_hits={h}/{3*n}")
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
