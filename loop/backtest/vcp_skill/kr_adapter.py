"""VCP 스크리너(tradermonty/claude-trading-skills) 한국 데이터 어댑터.
FMP 호출 없이 일봉 배열을 원 스킬의 analyze_stock()에 그대로 넣는다(스킬 로직 무수정).
- 벤치마크: S&P500 대신 KODEX200(069500)
- pre_filter 의 '가격>$10'·'거래량>20만주'는 미국 기준이라 한국 유동성 기준으로 대체:
  20일 평균 거래대금 >= 10억원, 주가 >= 1,000원 (52주 위치 조건은 원본 그대로)
"""
import sys
sys.path.insert(0, '/tmp/claude-0/ext/claude-trading-skills/skills/vcp-screener/scripts')
from screen_vcp import analyze_stock, passes_trend_filter  # noqa: E402
from calculators.trend_template_calculator import calculate_trend_template  # noqa
from calculators.relative_strength_calculator import calculate_relative_strength  # noqa

LOOKBACK = 260


def to_hist(dates, o, h, l, c, v, end):
    """end 인덱스(포함)까지 최근 LOOKBACK 봉을 최신순 dict 리스트로."""
    s = max(0, end - LOOKBACK + 1)
    out = []
    for i in range(end, s - 1, -1):
        out.append({"date": str(dates[i]), "open": float(o[i]), "high": float(h[i]),
                    "low": float(l[i]), "close": float(c[i]), "adjClose": float(c[i]),
                    "volume": float(v[i])})
    return out


def prefilter(c, h, l, v, end):
    if end < 252:
        return False
    px = c[end]
    if px < 1000:
        return False
    val20 = (c[end-19:end+1] * v[end-19:end+1]).mean()
    if val20 < 1e9:
        return False
    yh = h[end-251:end+1].max(); yl = l[end-251:end+1].min()
    if yl <= 0 or (px - yl) / yl < 0.20 or (yh - px) / yh > 0.30:
        return False
    return True


def run_one(code, dates, o, h, l, c, v, end, bench_hist, trend_min=85.0):
    hist = to_hist(dates, o, h, l, c, v, end)
    yh = h[end-251:end+1].max(); yl = l[end-251:end+1].min()
    quote = {"price": float(c[end]), "yearHigh": float(yh), "yearLow": float(yl), "marketCap": 0}
    # 원 스킬 Phase 2: 트렌드 템플릿 통과분만 Phase 3
    rs = calculate_relative_strength(hist, bench_hist)
    tt = calculate_trend_template(hist, quote, rs_rank=rs.get("rs_rank_estimate", 0))
    if not passes_trend_filter(tt, trend_min):
        return None
    r = analyze_stock(code, hist, quote, bench_hist)
    if not r:
        return None
    return {"code": code, "date": int(dates[end]), "price": float(c[end]),
            "score": r["composite_score"], "rating": r["rating"], "valid_vcp": r["valid_vcp"],
            "state": r["execution_state"], "pattern": r["pattern_type"],
            "pivot": r["vcp_pattern"].get("pivot_price"),
            "dist_pivot": r["distance_from_pivot_pct"],
            "stop": r["pivot_proximity"].get("stop_loss_price"),
            "ncon": r["vcp_pattern"].get("num_contractions"),
            "rs": r["relative_strength"].get("rs_rank_estimate")}
