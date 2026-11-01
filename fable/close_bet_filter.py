# -*- coding: utf-8 -*-
"""Rule CB (Close-Bet Band) — 중기 ETF '종가 베팅' 진입 밴드 필터  [확정 2026-07-26]

설계 원칙 — **선정방법 비의존(집행 레이어)**
------------------------------------------------
이 모듈은 "무엇을 후보로 골랐는지"에 전혀 관여하지 않는다. 후보 코드 리스트를 받아
'당일 등락률'만 보고 종가 매수 여부를 판정한다. 따라서 선정 로직이 mom20에서
이동평균(MA) 중심 기술적분석 + 관심종목(검색·뉴스) 조합으로 바뀌어도 이 파일은
수정 없이 그대로 동작한다. 후보 리스트만 새 방법의 출력으로 넘겨주면 된다.

  선정 레이어 (교체 가능)            집행 레이어 (이 파일, 고정)
  mom20 / MA크로스 / 관심종목조합  →  당일등락률 밴드 판정 → 종가 매수 목록

규칙(2026-07-26 승격 / 같은 날 밴드 확대 개정 v1.1, 근거 `중기ETF_종가베팅_백테스트_2026-07-26.pdf`)
  1단계: -0.5% <= 당일등락률 < +1.5% 인 후보만 15:20~15:30 종가 단일가로 동일가중 매수
  2단계: 1단계 통과가 0종이면 밴드를 -1.0% <= r < +1.5% 로 한 번만 완화
  3단계: 그래도 0종이면 그날은 매수하지 않는다(현금 관망)
  ※ 상한 +1.5%는 절대 올리지 않는다 — +1.8%로만 넓혀도 누적 +7.50%→-0.90%로 붕괴(급등 되돌림).
    하한은 -0.5%가 최적이며 -1.5% 이하로 넓히면 잭나이프 하한이 마이너스로 꺾인다.
  적용 범위: 데일리 브리핑 [6-2] 중기 추천 ETF 에 한정(검증 범위). 단기 ETF·단일종목은
            shadow 기록만 하고 실매수 판정에는 쓰지 않는다.
  청산: 급락게이트 발동 국면 = 익일 종가 청산(V1) / 미발동 국면 = 다음 브리핑에 재추천되면
        계속 보유, 빠진 첫날 종가 청산(V2)

데이터 소스: 키움 REST(조회 전용) 우선 → 실패 시 loop 패널 CSV 보조.
            주문·매매·이체 기능은 어떤 경우에도 구현·호출하지 않는다.

CLI:
  python3 close_bet_filter.py 091170 069500 466920 449450 091160         # 실시간(장중) 판정
  python3 close_bet_filter.py --date 20260723 091170 069500 ...          # 과거 종가 기준 판정
"""
from __future__ import annotations

import csv
import os
import sys

BAND_PRIMARY = (-0.005, 0.015)   # 1단계 밴드 (v1.1, 2026-07-26 개정: 하한 0% → -0.5%)
BAND_RELAXED = (-0.010, 0.015)   # 2단계(1회 완화) 밴드

FABLE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.join(os.path.dirname(FABLE), "loop")
def _panel_candidates():
    """패널 파일명을 상수로 박아두면 패널을 연장해도 옛 날짜에서 멈춘다.
    (2026-07-28 실측: 0724 고정 탓에 20260727 판정 불가) → 항상 최신부터 탐색."""
    d = os.path.join(LOOP, "backtest")
    found = []
    if os.path.isdir(d):
        found = sorted((f for f in os.listdir(d)
                        if f.startswith("panel_close_") and f.endswith(".csv")),
                       reverse=True)
    return [os.path.join(d, f) for f in found] + [os.path.join(LOOP, "panel_close.csv")]


PANELS = _panel_candidates()


# ---------------------------------------------------------------- 데이터 조회
def _panel():
    """{code: {yyyymmdd: close}} — 패널 CSV(있는 것 중 최신) 로드."""
    data: dict[str, dict[str, float]] = {}
    names: dict[str, str] = {}
    for p in PANELS:
        if not os.path.exists(p):
            continue
        for row in csv.DictReader(open(p, encoding="utf-8")):
            data.setdefault(row["code"], {})[row["date"]] = float(row["close"])
            names.setdefault(row["code"], row.get("name", ""))
        break
    return data, names


def _kiwoom_intraday(code: str):
    """키움 조회 전용 API로 (현재가, 전일종가) 반환. 실패 시 None."""
    try:
        sys.path.insert(0, LOOP)
        import kiwoom_api  # noqa: WPS433  (loop/kiwoom_api.py, 조회 함수만 사용)

        info = kiwoom_api.get_basic_info(code)
        body = info[1] if isinstance(info, tuple) else info
        cur = abs(float(str(body.get("cur_prc", "")).replace(",", "").replace("+", "")))
        base = body.get("base_pric") or body.get("prev_close") or body.get("pred_pre")
        base = abs(float(str(base).replace(",", "").replace("+", "")))
        if cur and base:
            return cur, base
    except Exception:  # 네트워크·키·필드명 변경 등 — 조용히 패널로 폴백
        return None
    return None


def intraday_return(code: str, date: str | None = None, panel=None):
    """당일 등락률(= 당일가/전일종가 - 1). date=None이면 키움 실시간 우선."""
    panel_data, _ = panel if panel else _panel()
    if date is None:
        live = _kiwoom_intraday(code)
        if live:
            cur, base = live
            return cur / base - 1.0, "kiwoom_live"
    hist = panel_data.get(code, {})
    if not hist:
        return None, "no_data"
    days = sorted(hist)
    if date is None:
        date = days[-1]
    if date not in hist:
        return None, "no_data"
    i = days.index(date)
    if i == 0:
        return None, "no_prev"
    return hist[date] / hist[days[i - 1]] - 1.0, "panel"


# ---------------------------------------------------------------- 판정
def apply_close_bet_band(codes, date=None, panel=None):
    """후보 코드 리스트 → 종가베팅 판정 결과.

    반환: {'stage': 1|2|0, 'band': (lo,hi), 'buy': [...], 'rows': [...]}
      stage 1 = 기본 밴드 통과, 2 = 완화 밴드 통과, 0 = 관망(매수 없음)
    """
    panel = panel or _panel()
    _, names = panel
    rows = []
    for c in codes:
        r, src = intraday_return(c, date, panel)
        rows.append({"code": c, "name": names.get(c, ""), "ret": r, "src": src})

    def pick(band):
        lo, hi = band
        return [x for x in rows if x["ret"] is not None and lo <= x["ret"] < hi]

    buy = pick(BAND_PRIMARY)
    stage, band = 1, BAND_PRIMARY
    if not buy:
        buy = pick(BAND_RELAXED)
        stage, band = (2, BAND_RELAXED) if buy else (0, BAND_PRIMARY)
    for x in rows:
        x["verdict"] = "매수" if x in buy else "제외"
    return {"stage": stage, "band": band, "buy": buy, "rows": rows}


def format_report(res, date=None):
    lo, hi = res["band"]
    head = {1: "1단계 기본 밴드", 2: "2단계 완화 밴드(기본 통과 0종)", 0: "관망(현금) — 통과 0종"}[res["stage"]]
    out = [f"[Rule CB] 기준일 {date or '실시간'} · {head} · 적용밴드 {lo*100:+.1f}% ~ {hi*100:+.1f}%"]
    for x in sorted(res["rows"], key=lambda y: (y["ret"] is None, y["ret"])):
        r = "  n/a  " if x["ret"] is None else f"{x['ret']*100:+6.2f}%"
        out.append(f"  {x['verdict']:>2s}  {x['code']:>6s} {x['name'][:22]:22s} 당일 {r}  ({x['src']})")
    out.append(f"  → 종가 매수 {len(res['buy'])}종 (동일가중): "
               + (", ".join(f"{x['code']}" for x in res["buy"]) or "없음 — 그날은 매수하지 않는다"))
    return "\n".join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    date = None
    if args and args[0] == "--date":
        date = args[1]
        args = args[2:]
    if not args:
        print(__doc__)
        sys.exit(0)
    print(format_report(apply_close_bet_band(args, date), date))
