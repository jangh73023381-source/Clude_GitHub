#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 관심모멘텀 파일럿 shadow 트랙 — 기존 v2 픽/결과 파일을 건드리지 않고 base/contra/inter 3변형을
# 15섹터 전량에 대해 병렬 기록·채점(rank-IC + top3_hits + 무작위 베이스라인)한다. 방법 교체가 아니라
# 전방검증용 병렬 관찰. 판정은 20영업일 누적 후.
"""
사용:
  record --date YYYYMMDD --raw <raw csv>         # 3변형 15섹터 컴포짓·랭크 기록
  score  --date YYYYMMDD --prices <prices csv>   # 변형별 top3_hits·rank-IC 기록
  status                                         # 누적 요약

변형 정의(raw 신호는 v2.3와 동일: sent=(news_buy-news_sell)/max(news_total,1), search 원값,
ytnet=yt_buy-yt_sell, yt20net=yt20_buy-yt20_sell; 각 z는 15섹터 횡단면 pstdev):
  comp_base  = z(sent) + z(search) + z(ytnet) + z(yt20net)          # 현행 v2.3 재현(검증용)
  comp_contra= -comp_base                                            # 부호 반전(컨트래리언)
  comp_inter = z(sent) + (z(search)+z(ytnet)+z(yt20net))*sign(sent)  # 관심을 뉴스감성 방향으로 조건화(C2)
"""
import argparse, csv, os, sys, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(BASE)
THEMES = os.path.join(REF, "attention_pilot_themes.csv")
S_PICKS = os.path.join(REF, "attention_shadow_picks.csv")
S_RESULTS = os.path.join(REF, "attention_shadow_results.csv")

VARIANTS = ["base", "clean", "contra", "inter"]
PICK_HEADER = ["date", "theme", "code", "etf", "sent", "z_search", "z_ytnet", "z_yt20",
               "comp_base", "rk_base", "comp_clean", "rk_clean",
               "comp_contra", "rk_contra", "comp_inter", "rk_inter"]
RESULT_HEADER = ["score_date", "variant", "top5", "top3_hits", "rank_ic", "n_themes"]
K0 = 5.0          # B3: 감성 소표본 수축 상수. sent = (buy-sell)/(total+K0)
LIVE_MIN = 3      # B2: 모달리티가 최소 이만큼 nonzero여야 살아있는 신호로 인정



def _f(x, default=0.0):
    """빈 문자열은 '미수집'을 뜻한다(v2.3에서 유튜브 수집 폐지 — 0으로 채우면 '진짜 0'과 구분이
    안 된다). 산술에서는 0으로 처리하되, 15테마가 전부 0이면 zscores()가 전부 0을 돌려주고
    shadow 의 liveness 게이트(_live)도 해당 모달리티를 자동 제외하므로 결과적으로
    '컴포짓에서 빠지는' 올바른 동작이 된다."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

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


def _sign(x):
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def _ranks(vals):
    # 큰 값 = rank 1 (동점은 평균순위)
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


def _live(z_vec, raw_vec):
    """B2: 모달리티가 LIVE_MIN 미만 nonzero면 수집실패/무의미로 보고 0 벡터로 대체."""
    if sum(1 for v in raw_vec if v != 0) < LIVE_MIN:
        return [0.0] * len(z_vec)
    return z_vec


def _composites(rows):
    """raw rows(theme dict list) -> theme별 변형 컴포짓 + 구성 z 딕셔너리.
    base/contra/inter = 현행 v2.3 raw 신호. clean = B2(모달리티 liveness)+B3(감성 수축) 적용."""
    has_yt20 = len(rows) > 0 and all("yt20_total" in r for r in rows)
    sent, sent_c, search, ytnet, yt20net = [], [], [], [], []
    for r in rows:
        buy, sell, tot = _f(r["news_buy"]), _f(r["news_sell"]), _f(r["news_total"])
        sent.append((buy - sell) / max(tot, 1.0))          # 현행
        sent_c.append((buy - sell) / (tot + K0))            # B3 수축
        search.append(_f(r["search"]))
        ytnet.append(_f(r["yt_buy"]) - _f(r["yt_sell"]))
        yt20net.append((float(r.get("yt20_buy", 0) or 0) - float(r.get("yt20_sell", 0) or 0)) if has_yt20 else 0.0)
    zs, zq, zy = zscores(sent), zscores(search), zscores(ytnet)
    zt = zscores(yt20net) if has_yt20 else [0.0] * len(rows)
    # clean: 감성은 수축본 z, 관심 모달리티는 liveness 게이트
    zsc = zscores(sent_c)
    zy_l, zt_l = _live(zy, ytnet), _live(zt, yt20net)
    out = []
    for i, r in enumerate(rows):
        att = zq[i] + zy[i] + zt[i]
        base = zs[i] + att
        inter = zs[i] + att * _sign(sent[i])
        clean = zsc[i] + zq[i] + zy_l[i] + zt_l[i]
        out.append({"theme": r["theme"], "sent": sent[i], "zq": zq[i], "zy": zy[i], "zt": zt[i],
                    "base": base, "clean": clean, "contra": -base, "inter": inter})
    return out


def cmd_record(date, raw_path):
    themes = {t["theme"]: t for t in load_themes()}
    with open(raw_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    comps = _composites(rows)
    rk = {v: {c["theme"]: i + 1 for i, c in enumerate(sorted(comps, key=lambda x: -x[v]))} for v in VARIANTS}
    exists = os.path.exists(S_PICKS)
    # 멱등 보장(2026-07-30 신설) — 같은 날짜 행이 있으면 다시 쓰지 않는다.
    # 종전에는 하루에 record 를 여러 번 돌리면 같은 날짜가 그대로 덧붙여져,
    # 트랙 B 채점 시 mom20 순위표가 중복 행으로 부풀어 픽이 1종에 몰리는 왜곡이 생겼다.
    if exists:
        with open(S_PICKS, encoding="utf-8") as f0:
            if any(r and r[0] == date for r in csv.reader(f0)):
                print(f"  [shadow] {date} 이미 기록됨 — 생략(멱등)")
                return
    with open(S_PICKS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(PICK_HEADER)
        for c in comps:
            t = themes.get(c["theme"], {})
            w.writerow([date, c["theme"], t.get("code", ""), t.get("etf", ""),
                        f"{c['sent']:+.3f}", f"{c['zq']:.2f}", f"{c['zy']:.2f}", f"{c['zt']:.2f}",
                        f"{c['base']:+.3f}", rk["base"][c["theme"]],
                        f"{c['clean']:+.3f}", rk["clean"][c["theme"]],
                        f"{c['contra']:+.3f}", rk["contra"][c["theme"]],
                        f"{c['inter']:+.3f}", rk["inter"][c["theme"]]])
    for v in VARIANTS:
        top5 = [c["theme"] for c in sorted(comps, key=lambda x: -x[v])[:5]]
        print(f"[{date}] {v:6s} top5 = {top5}")
    return 0


def cmd_score(date, prices_path):
    themes = load_themes()
    code2theme = {t["code"]: t["theme"] for t in themes}
    prices = {}
    with open(prices_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                prices[r["code"]] = (_f(r["prev_close"]), _f(r["next_close"]))
            except (ValueError, KeyError):
                pass
    ret_by_theme = {}
    for t in themes:
        p = prices.get(t["code"])
        if p and p[0] > 0:
            ret_by_theme[t["theme"]] = 100.0 * (p[1] / p[0] - 1.0)
    scored_themes = [t for t in [x["theme"] for x in themes] if t in ret_by_theme]
    if len(scored_themes) < 3:
        print(f"[{date}] 가격 매칭 부족(n={len(scored_themes)}) — 스킵"); return 1
    ranked = sorted(scored_themes, key=lambda th: -ret_by_theme[th])
    top3 = ranked[:3]

    # shadow_picks에서 해당 date의 변형별 컴포짓 로드
    comp_rows = {}
    with open(S_PICKS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["date"] == date:
                comp_rows[r["theme"]] = r
    if not comp_rows:
        print(f"[{date}] shadow picks 없음 — record 먼저"); return 1

    exists = os.path.exists(S_RESULTS)
    with open(S_RESULTS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(RESULT_HEADER)
        rets = [ret_by_theme[th] for th in scored_themes]
        for v in VARIANTS:
            key = "comp_" + v
            comps = [float(comp_rows[th][key]) for th in scored_themes]
            top5 = [th for th in sorted(scored_themes, key=lambda x: -float(comp_rows[x]["comp_" + v]))[:5]]
            hit3 = sum(1 for t in top3 if t in top5)
            ic = _spearman(comps, rets)
            w.writerow([date, v, "|".join(top5), hit3, f"{ic:+.3f}", len(scored_themes)])
        # 무작위 베이스라인(해석적): top3_hits 기대 1.0, ic 0
        w.writerow([date, "random", "", "1.00", "+0.000", len(scored_themes)])

    print(f"[{date}] TOP3 = {top3} (n={len(scored_themes)})")
    for v in VARIANTS:
        comps = [float(comp_rows[th]["comp_" + v]) for th in scored_themes]
        top5 = [th for th in sorted(scored_themes, key=lambda x: -float(comp_rows[x]["comp_" + v]))[:5]]
        hit3 = sum(1 for t in top3 if t in top5)
        ic = _spearman(comps, [ret_by_theme[th] for th in scored_themes])
        print(f"  {v:6s} top3_hit={hit3}/3  rank_ic={ic:+.3f}  top5={top5}")
    return 0


def cmd_status():
    if not os.path.exists(S_RESULTS):
        print("no shadow results yet"); return 0
    with open(S_RESULTS, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    days = sorted(set(r["score_date"] for r in rows))
    print(f"scored_days={len(days)} ({days[0]}~{days[-1] if days else '-'})")
    print(f"{'variant':8s} {'mean_hit3':>10s} {'mean_ic':>9s} {'ic>0_days':>10s}")
    seen = set()
    order = VARIANTS + ["mom20", "random"]
    all_variants = order + sorted(v for v in {r["variant"] for r in rows} if v not in order)
    for v in all_variants:
        if v in seen:
            continue
        seen.add(v)
        vr = [r for r in rows if r["variant"] == v]
        if not vr:
            continue
        mh = sum(_f(r["top3_hits"]) for r in vr) / len(vr)
        is_baseline_random = v == "random"
        ics = [_f(r["rank_ic"]) for r in vr] if not is_baseline_random else []
        mic = sum(ics) / len(ics) if ics else 0.0
        icpos = sum(1 for r in vr if _f(r["rank_ic"]) > 0) if not is_baseline_random else 0
        print(f"{v:8s} {mh:10.2f} {mic:+9.3f} {icpos:7d}/{len(vr)}")
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
