# -*- coding: utf-8 -*-
"""generate_briefing.py — 날짜만 바꿔 쓰는 데일리 브리핑 생성기 (2026-11-01, v1).

**포지션**: 67개 `_gen_briefing_<날짜>.py`를 지우거나 대체하지 않는다. 그 파일들은
과거 산출물 재현용으로 그대로 보존한다. **앞으로 새 날짜부터는 이 스크립트로 간다**
— `python3 generate_briefing.py --date YYYYMMDD`.

이 스크립트가 다루는 범위(설계 보고서 §4-4 그대로):
- **현재(2026-10-30 기준) 확정된 섹션 구성 하나만** 지원한다. 과거 특정 날짜의 폐지된
  섹션(7절·[8-1]·[8-3]·[8-4] 등)을 재현하지 않는다 — 그건 git 히스토리와 기존
  `_gen_briefing_<날짜>.py` 파일로 충분하다(설계 보고서 §4-4).
- `briefing_core.py`(docx 저수준 빌더) + 기존 13개 `_*_템플릿.py`를 그대로 재사용한다.
- **자동화되는 입력**: `morning_state_<D>.json`(news5·fall5·eg_track 등),
  `_wallst_*.json`/`_flow_*.json`/`_fturn_*.json`/`_earn_*.json`/`_trade_ref_*.json`/
  `_pool_*.json`(각 ref 스크립트의 `--json` 출력) — 파일이 있으면 그대로 읽고, 없으면
  해당 섹션을 "결손"으로 표시하고 건너뛴다(morning_run.py와 같은 원칙 — 결손이
  전체 실패가 되지 않는다).
- **자동화되지 않는 입력**(실측: `_gen_briefing_1030.py` 기준 — PICKS5·GATES·헤드라인
  문단·중기 5종 목록·트랙D 보유 테이블·게이트 발동 근거 서술·4절 회고 해설 등은 지금도
  매일 사람이 코드에 직접 타이핑한다): `briefing_input_<D>.json`이라는 **데이터** 파일로
  분리한다. 코드가 아니라 데이터이므로, 잘못 채워도 docx 빌더 호출 자체는 깨지지 않는다.
  없는 키는 그 섹션만 "[입력 결손]"으로 표시하고 전체를 중단하지 않는다.

**TODO (다음에 사람이 직접 확인할 것, 아래 "알려진 제약" 참고)**:
  - 각 ref 모듈(wallst_ref.py 등)을 직접 호출해 `_wallst_<D>.json` 등을 그 자리에서
    새로 만드는 단계는 아직 넣지 않았다 — 지금은 "이미 그 날짜의 JSON이 fable/에
    있다"고 가정하고 읽기만 한다(기존 `_gen_briefing_*.py`도 마찬가지로 미리 만들어진
    파일을 읽었다 — 네트워크 호출 자체는 이번 작업 범위 밖).
  - fable/CLAUDE.md 26번 "[한눈에 보기] 요약 페이지"는 PICKS5/GATES를 5절과 **같은
    변수**로 한 번만 넘기게 돼 있다 — 이 스크립트는 그 원칙을 그대로 지킨다
    (아래 `briefing_input["picks5"]`/`["gates"]`를 두 곳에 그대로 전달).
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util as _il
import json
import sys
from pathlib import Path

FABLE_DIR = Path(__file__).resolve().parent
STATE_DIR = FABLE_DIR.parent / "loop" / "references" / "scripts"

sys.path.insert(0, str(FABLE_DIR))

from briefing_core import (  # noqa: E402
    doc, title, section, subsection, para, note, labelpara, bullet,
    make_table, px, band, NAVY, GREEN_TXT, RED_TXT,
)


# ---------------------------------------------------------------------------
# 입력 로딩 — 전부 "없으면 결손, 중단하지 않는다"
# ---------------------------------------------------------------------------
class Missing:
    """결손 표시용 — bool(Missing()) == False 라 `if data:` 가드가 그대로 동작한다."""
    def __init__(self, why):
        self.why = why

    def __bool__(self):
        return False

    def get(self, *a, **k):
        return None


def _load_json(path: Path, label: str):
    if not path.exists():
        return Missing(f"{label} 결손 — {path.name} 없음")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — 입력 파일 문제는 결손으로 흡수
        return Missing(f"{label} 결손 — {path.name} 파싱 실패({e})")


def load_state(date: str) -> dict:
    return _load_json(STATE_DIR / f"morning_state_{date}.json", "morning_state")


def prev_trading_date(date: str) -> str | None:
    """가장 가까운 과거 morning_state 파일명에서 날짜를 역산한다(휴장일 스킵).
    확정 로직은 없다 — ensure_data.py가 아는 거래일 캘린더를 쓰는 것이 정본이고,
    여기서는 '하루 전'을 기본으로 시도만 한다(없으면 결손으로 처리되므로 안전하다)."""
    d = datetime.datetime.strptime(date, "%Y%m%d")
    for back in range(1, 5):
        cand = (d - datetime.timedelta(days=back)).strftime("%Y%m%d")
        if (STATE_DIR / f"morning_state_{cand}.json").exists():
            return cand
    return None


def load_briefing_input(date: str) -> dict:
    """그날 손으로 채우는 입력(PICKS5·GATES·헤드라인·서술 문단·중기 5종·트랙D 보유 등).
    파일이 없으면 빈 dict — 전부 '[입력 결손]'으로 표시되고 섹션은 생략될 뿐,
    스크립트 자체는 끝까지 돈다."""
    path = FABLE_DIR / f"briefing_input_{date}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_template(filename: str, name: str):
    spec = _il.spec_from_file_location(name, FABLE_DIR / filename)
    mod = _il.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _missing_note(why: str):
    note(f"※ [입력 결손] {why} — 이 섹션은 생략했다. 전체 브리핑 생성은 중단하지 않는다.")


# ---------------------------------------------------------------------------
# 섹션 렌더 함수 — 함수 하나당 섹션 하나(설계 보고서 §4-3). 새 섹션 추가/제거는
# 함수 추가/호출부 주석 처리로 끝나야 한다("날짜 파일 통째로 복붙" 대신).
# ---------------------------------------------------------------------------
def render_summary_page(ctx):
    inp = ctx["input"]
    if "picks5" not in inp or "gates" not in inp:
        _missing_note("요약 페이지 — briefing_input의 picks5/gates 없음")
        return
    sp = _load_template("_요약페이지_템플릿.py", "summary_tpl")
    sp.add_summary_page(
        state_path=str(STATE_DIR / f"morning_state_{ctx['date']}.json"),
        picks=inp["picks5"], gates=inp["gates"],
        exec_date=inp.get("exec_date", ctx["date"]),
        headlines=inp.get("headlines", []),
        para=para, make_table=make_table, note=note, doc=doc,
        RED=RED_TXT, GREEN=GREEN_TXT, NAVY=NAVY,
    )


def render_head_notes(ctx):
    """title() 직후, 1절 앞의 채점기준일 note + 게이트 발동 서술 문단.
    fable/CLAUDE.md 4·8·11번 — 매일 다른 판단이 들어가는 서술이라 자동 생성하지
    않고 briefing_input의 'head_note'/'gate_commentary'/'prev_score_commentary'를
    그대로 옮긴다."""
    inp = ctx["input"]
    if inp.get("head_note"):
        note(inp["head_note"])
    if inp.get("gate_commentary"):
        para([(inp["gate_commentary"].get("label", "[게이트]"), 11, True, RED_TXT),
              (inp["gate_commentary"].get("body", ""), 9.5, False, None)],
             space_after=4, shading="FCE4E4")
    if inp.get("prev_score_commentary"):
        c = inp["prev_score_commentary"]
        para([(c.get("label", "[직전 채점]"), 10.5, True, GREEN_TXT),
              (c.get("body", ""), 9.5, False, None)],
             space_after=6, shading="E2EFDA")


def render_section1_market_summary(ctx):
    section("1. 전일 시장 요약")
    inp = ctx["input"]
    us = inp.get("market_table_us")
    if us:
        subsection(us.get("title", "미국 증시"))
        make_table(us["headers"], us["rows"], us.get("colwidths"))
        if us.get("note"):
            note(us["note"])
    else:
        _missing_note("[1] 미국 증시 표 — briefing_input.market_table_us 없음")

    kr = inp.get("market_table_kr")
    if kr:
        subsection(kr.get("title", "한국 증시"))
        make_table(kr["headers"], kr["rows"], kr.get("colwidths"))
        if kr.get("note"):
            note(kr["note"])
    else:
        _missing_note("[1] 한국 증시 표 — briefing_input.market_table_kr 없음")

    fa = _load_template("_각주_부록.py", "_fa")

    wallst = ctx["aux"]["wallst"]
    if wallst:
        tw = _load_template("_월가전이표_템플릿.py", "wallst_tpl")
        tw.add_wallst_table(wallst, subsection, make_table, note)
        if inp.get("wallst_note"):
            note(inp["wallst_note"])
        note(fa.short("wallst"), size=9)
    else:
        _missing_note(f"[1-3] 미국장 전이표 — {wallst.why}")

    flow = ctx["aux"]["flow"]
    if flow:
        tf = _load_template("_섹터자금흐름_템플릿.py", "flow_tpl")
        if inp.get("flow_note"):
            note(inp["flow_note"])
        tf.add_sector_flow(flow, subsection, note, doc, out_dir=str(FABLE_DIR / "_flow_snap"))
    else:
        _missing_note(f"[1-4] 테마별 자금 흐름 — {flow.why}")

    fturn = ctx["aux"]["fturn"]
    tft = _load_template("_외국인전환표_템플릿.py", "fturn_tpl")
    tft.add_foreign_turn(fturn if fturn else {}, subsection, make_table, note)
    if not fturn:
        note(f"※ [입력 결손] [1-5] 외국인 전환 확률 — {fturn.why}", size=8.5)

    earn = ctx["aux"]["earn"]
    te6 = _load_template("_실적이벤트_템플릿.py", "earn_tpl")
    te6.add_earnings_cal(earn if earn else {}, subsection, make_table, note)
    if earn:
        note(fa.short("earn"), size=9)
    else:
        note(f"※ [입력 결손] [1-6] 실적 이벤트 달력 — {earn.why}", size=8.5)


def render_section2_news(ctx):
    """2절 — news5를 그대로 옮긴다(수기 재작성 금지, fable/CLAUDE.md 9번·16번)."""
    section("2. 주요 뉴스 5선")
    state = ctx["state"]
    news5 = state.get("news5") if state else None
    if not news5:
        _missing_note(f"[2] 주요 뉴스 5선 — morning_state.news5 없음"
                       + (f" ({state.why})" if isinstance(state, Missing) else ""))
        return
    bucket_label = {"추천테마": "추천 테마", "보도급증": "보도 점유율 급증", "악재": "악재"}
    sent_label = {"buy": "긍정", "sell": "부정", "neutral": "중립"}
    rows = []
    for it in news5["items"]:
        theme = it["disp_theme"]
        if it.get("theme") and it["theme"] != theme:
            theme = f"{theme} (수집:{it['theme']})"
        rows.append([
            bucket_label.get(it["bucket"], it["bucket"]), theme,
            it["title"].replace("&quot;", '"').replace("&amp;", "&"),
            it["pub"], sent_label.get(it.get("label"), "—"),
        ])
    make_table(["구분", "테마", "제목", "발행시각(KST)", "감성"], rows,
               [1300, 1500, 4200, 1400, 860])
    note(f"※ **네이버 뉴스 API 수집 풀에서 자동 생성**했습니다(0-C 단계, 풀 "
         f"**{news5.get('pool_size', 0):,}건**). 배분은 추천 테마 2 + 보도 점유율 "
         f"급증 2 + 악재 1 이며 발행시각이 응답값이라 날짜가 보장됩니다.")
    inp = ctx["input"]
    if inp.get("news_commentary"):
        note(inp["news_commentary"])
    else:
        _missing_note("[2] 뉴스 해설 문단(선택) — briefing_input.news_commentary 없음")


def render_section3_gate(ctx):
    """3절 — 급락/금리 게이트 판정표. 표 자체는 briefing_input에서, 서술은 head_notes에서."""
    section("3. 급락 게이트 판정표")
    inp = ctx["input"].get("gate_tables")
    if not inp:
        _missing_note("[3] 급락 게이트 판정표 — briefing_input.gate_tables 없음")
        return
    for blk in inp:
        subsection(blk["title"])
        make_table(blk["headers"], blk["rows"], blk.get("colwidths"))
        if blk.get("note"):
            note(blk["note"])


def render_section4_review(ctx):
    """4절 — 직전 추천 회고. 손익표는 state/prev_state 교차검증값, 해설 문단은 input."""
    section("4. 직전 추천 회고 (검증)")
    inp = ctx["input"].get("review")
    if not inp:
        _missing_note("[4] 직전 추천 회고 — briefing_input.review 없음")
        return
    for blk in inp.get("tables", []):
        subsection(blk["title"])
        make_table(blk["headers"], blk["rows"], blk.get("colwidths"))
        for n in blk.get("notes", []):
            note(n)


def render_section5_entry_strategy(ctx):
    inp = ctx["input"]
    if "picks5" not in inp or "gates" not in inp:
        section("5. 진입 전략 — 케이스별 안내")
        _missing_note("[5] 진입 전략 — briefing_input.picks5/gates 없음(요약 페이지와 공유하는 값)")
        return
    entry_tpl = _load_template("_진입전략_템플릿.py", "entry_tpl")
    entry_tpl.add_entry_strategy(
        section, subsection, make_table, note, para, bullet,
        picks=inp["picks5"], gates=inp["gates"],
        RED=RED_TXT, GREEN=GREEN_TXT, px=lambda v: f"{v:,.0f}원",
    )
    fa = _load_template("_각주_부록.py", "_fa")
    for extra in inp.get("entry_notes", []):
        note(extra)
    note(fa.short("entry"), size=9)


def render_section6_etf_picks(ctx):
    """6-1/6-2/6-3 — pool은 _pool_<D>.json(ref 스크립트 출력)을 그대로 쓴다
    (손으로 재입력하지 않는다, fable/CLAUDE.md 공통 원칙)."""
    section("6. ETF 추천")
    pool = ctx["aux"]["pool"]
    prev5 = set((ctx["input"].get("picks5_prev_codes")) or [])
    if pool:
        by_srank = sorted(pool["pool"], key=lambda r: r["srank"])

        def tag61(r):
            if r["srank"] <= 5:
                return "**실매수** · " + ("유지" if r["code"] in prev5 else "**신규**")
            if r["code"] in prev5:
                return "**종가 청산**"
            return "차순위 — 담지 않음"

        subsection("[6-1] 단기 추천 ETF 10종 — σ20 순위 (Rule LV 정렬 · 실매수 대상)")
        make_table(
            ["σ20 순위", "종목명", "코드", "종가", "σ20(변동성)", "mom20", "mom20 순위", "등락", "비고"],
            [[f"**{r['srank']}**" if r["srank"] <= 5 else str(r["srank"]), r["name"], r["code"],
              f"{r['close']:,.0f}", f"{r['sig']:.2f}%", f"{r['mom20']:+.2f}%", f"{r['mrank']}위",
              f"{r['r1']:+.2f}%", tag61(r)] for r in by_srank[:10]],
            [800, 2500, 800, 1000, 1000, 900, 900, 900, 1560],
        )
        note("※ **★ 실매수 대상은 이 표의 1~5위입니다.**")

        subsection("[6-2] 단기 추천 ETF 10종 — mom20 순위 (참고 전용 · 실매수 아님)")
        make_table(
            ["mom20 순위", "종목명", "코드", "종가", "mom20", "σ20(변동성)", "σ20 순위", "등락", "비고"],
            [[str(r["mrank"]), r["name"], r["code"], f"{r['close']:,.0f}", f"{r['mom20']:+.2f}%",
              f"{r['sig']:.2f}%", f"{r['srank']}위", f"{r['r1']:+.2f}%",
              "MOM 대조군 픽" if r["mrank"] <= 5 else ""] for r in pool["pool"][:10]],
            [800, 2500, 800, 1000, 900, 1000, 900, 900, 1560],
        )
        note("※ **★★ 이 표는 참고용이며 실매수는 [6-1] 1~5위입니다. mom20 순위로 매수하면 "
             "확정방법 v2.9(Rule LV)를 위반합니다.**")
    else:
        subsection("[6-1]·[6-2] 단기 ETF 10종")
        _missing_note(f"[6-1]/[6-2] — {pool.why}")

    mid = ctx["input"].get("mid5")
    if mid:
        subsection("[6-3] 중기 추천 ETF 5종 (Rule MM mom150 → Rule CB 밴드 판정 후 종가 매수)")
        mh = _load_template("mid_hold_ref.py", "mid_hold")
        hold = {r["code"]: mh.fmt(r) for r in mh.rows(ctx.get("prev_date") or ctx["date"])}

        def h(code, i):
            return hold.get(code, ("—", "—", "—"))[i]

        make_table(
            ["순위", "종목명", "코드", "종가", "mom150", "등락", "편입일", "만기(D+20)", "잔여"],
            [[str(i + 1), m["name"], m["code"], m["close"], m["mom150"], m["r1"],
              h(m["code"], 0), h(m["code"], 1), h(m["code"], 2)] for i, m in enumerate(mid)],
            [600, 2500, 800, 1100, 1000, 900, 900, 1100, 1200],
        )
        note(mh.NOTE, size=9)
    else:
        subsection("[6-3] 중기 추천 ETF 5종")
        _missing_note("[6-3] — briefing_input.mid5 없음(여전히 수기 입력 항목 — 설계 보고서 §4-2 리스크)")


def render_section8_downside(ctx):
    section("8. 하락 예상 ETF")
    state = ctx["state"]
    fall5 = (state.get("picks") or {}).get("fall5") if state else None
    if fall5:
        make_table(
            ["순위", "종목명", "코드", "종가", "mom20", "등락", "비고"],
            [[str(k), r["name"], r["code"], f"{r['close']:,.0f}",
              f"{r['mom20']:+.2f}%", f"{r['r1']:+.2f}%", ""] for k, r in enumerate(fall5, 1)],
            [700, 3200, 900, 1200, 1200, 1100, 1960],
        )
    else:
        _missing_note("[8] 하락 예상 ETF — morning_state.picks.fall5 없음")
    note("※ **이 표는 공매도·인버스 권유가 아니며 '매수를 피할 목록'**이고, mom20 하위 5종을 "
         "기계적으로 나열한 것이지 하락을 예측하는 검정된 규칙이 아닙니다.")
    note("※ fable/CLAUDE.md 24번(2026-09-17)에 따라 [8-1]·[8-3]·[8-4]는 싣지 않는다(번호 결번).")

    trade = ctx["aux"]["trade"]
    if trade:
        tt = _load_template("_수출입참고표_템플릿.py", "trade_tpl")
        tt.add_trade_table(trade, section, subsection, make_table, note)
    else:
        _missing_note(f"[8-2] 월간 수출입 참고표 — {trade.why}")


def render_section9_track_d(ctx):
    """9절 — eg_track.out을 그대로 옮긴다(수기 재계산 금지, fable/CLAUDE.md 7번).
    ①~⑤ 소블록 구성은 지금도 _gen_briefing_*.py가 state['eg_track']['out']의 파싱
    없이 손으로 다시 표를 짜는 부분이 많아(보유중 평가손익 테이블 등), 여기서는
    briefing_input.track_d 로 그 블록들을 넘겨받는다."""
    section("9. 매수·매도 타점 (트랙 D · Rule EG)")
    state = ctx["state"]
    eg_out = (state.get("eg_track") or {}).get("out") if state else None
    if eg_out:
        note("※ **`morning_run.py` 0-G 단계(`eg_picks.py --record`) 출력을 그대로 옮긴 것입니다**"
             "(수기 재계산 금지).")
    else:
        _missing_note("[9] eg_track 산출 — morning_state.eg_track.out 없음(9절 전체 결손)")
        return
    td = ctx["input"].get("track_d", {})
    for blk in td.get("blocks", []):
        subsection(blk["title"])
        if blk.get("note"):
            note(blk["note"])
        if blk.get("table"):
            make_table(blk["table"]["headers"], blk["table"]["rows"], blk["table"].get("colwidths"))
    if not td.get("blocks"):
        _missing_note("[9] ①~⑤ 소블록 — briefing_input.track_d.blocks 없음")


def render_verification(ctx):
    """10절 — 정상은 표 한 줄, 서술은 경고·결손·조치에만(fable/CLAUDE.md 23번)."""
    tv = _load_template("_데이터검증_템플릿.py", "verif_tpl")
    OK, WARN, MISS = tv.OK, tv.WARN, tv.MISS
    rows = list(ctx["input"].get("verification_rows", []))
    # 이 생성기가 직접 아는 결손만 자동으로 더한다(아는 범위에서는 손으로 또 적지 않는다).
    for key, aux_key, label in [
        ("[1-3] 미국장 전이표", "wallst", "wallst"),
        ("[1-4] 테마 자금 흐름", "flow", "flow"),
        ("[1-5] 외국인 전환 확률", "fturn", "fturn"),
        ("[1-6] 실적 이벤트 달력", "earn", "earn"),
        ("[8-2] 월간 수출입", "trade", "trade"),
        ("[6-1]/[6-2] pool", "pool", "pool"),
    ]:
        v = ctx["aux"].get(aux_key)
        if isinstance(v, Missing):
            rows.append((key, MISS, v.why))
    rows.append(("[6-3] 보유 경과 열", OK if ctx["input"].get("mid5") else MISS,
                 "`mid_hold_ref.py` 출력 그대로" if ctx["input"].get("mid5") else "briefing_input.mid5 결손"))
    prose = list(ctx["input"].get("verification_prose", []))
    tv.add_verification(rows=rows, prose=prose, section=section, make_table=make_table, note=note)


# ---------------------------------------------------------------------------
SECTION_PIPELINE = [
    render_head_notes,
    render_section1_market_summary,
    render_section2_news,
    render_section3_gate,
    render_section4_review,
    render_section5_entry_strategy,
    render_section6_etf_picks,
    render_section8_downside,
    render_section9_track_d,
    render_verification,
]


def build(date: str) -> Path:
    state = load_state(date)
    prev_date = prev_trading_date(date)
    briefing_input = load_briefing_input(date)

    aux = {
        "wallst": _load_json(FABLE_DIR / f"_wallst_{date}.json", "[1-3] wallst"),
        "flow": _load_json(FABLE_DIR / f"_flow_{date[4:]}.json", "[1-4] flow"),
        "fturn": _load_json(FABLE_DIR / f"_fturn_{date}.json", "[1-5] fturn"),
        "earn": _load_json(FABLE_DIR / f"_earn_{date}.json", "[1-6] earn"),
        "trade": _load_json(FABLE_DIR / f"_trade_ref_{date}.json", "[8-2] trade"),
        "pool": _load_json(FABLE_DIR / f"_pool_{prev_date or date}.json", "[6-1]/[6-2] pool"),
    }

    ctx = {"date": date, "prev_date": prev_date, "state": state,
           "input": briefing_input, "aux": aux}

    title(briefing_input.get("title", f"데일리 브리핑 — {date}"))
    render_summary_page(ctx)
    for fn in SECTION_PIPELINE:
        fn(ctx)

    out_path = FABLE_DIR / f"데일리브리핑_{date[:4]}-{date[4:6]}-{date[6:]}.docx"
    doc.save(str(out_path))
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="YYYYMMDD (예: 20261030)")
    args = ap.parse_args()
    out = build(args.date)
    print(f"[완료] {out}")


if __name__ == "__main__":
    main()
