# -*- coding: utf-8 -*-
"""데일리 브리핑 [8-3] 매수 금지 목록 — 생성 조각 (2026-09-11 신설, fable/CLAUDE.md 20번).

성격: **참고 정보 + OOS 기록 전용 — 선정·청산 반영 금지.** 목록과 추천이 겹쳐도 선정은 바꾸지 않고 표시만 한다.
규칙: 역배열 진입(MA5<MA20<MA60 첫 성립) 후 최대 20거래일 매수 금지 · 전일 종가 기준 역배열 해소 시 조기 해제 ·
      이미 보유 중인 종목은 팔지 않는다.
근거: `C:\\agent\\Claude\\fable\\매도신호_매수금지_검토_2026-09-11.pdf` (7년 1,830일, 목록 일평균 −11.24bp/일 · t −4.63)

브리핑 생성기(`_gen_briefing_YYYYMMDD.py`)에서 아래처럼 쓴다. 데이터는 아침 루틴 0-H 가 만든
`morning_state_<T>.json` 의 `sell_ban.data` 를 그대로 넘긴다(수기 재계산 금지).

    st = json.load(open(r'...\\loop\\references\\scripts\\morning_state_<T>.json', encoding='utf-8'))
    add_sellban_table(st['sell_ban']['data'], section, subsection, make_table, note)
"""


def _부록(key):
    """상설 부록(_각주_부록.py)의 일일 1줄 경고. 근거·한계 전문은 부록 문서에 있다."""
    import os, sys, importlib
    d = os.path.dirname(os.path.abspath(__file__))
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        return importlib.import_module('_각주_부록').short(key)
    except Exception:
        return ''


def _apply_widths(t, widths):
    """이 표만 열 너비를 고정한다(양식 템플릿의 make_table 은 autofit 이라 LibreOffice 에서 균등 분할돼 종목명이 여러 줄로 깨진다).
    양식 템플릿 원본은 건드리지 않는다."""
    if t is None:
        return
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Twips
    t.autofit = False
    tot = sum(widths); sc = min(1.0, 10400 / tot)
    lay = OxmlElement('w:tblLayout'); lay.set(qn('w:type'), 'fixed'); t._tbl.tblPr.append(lay)
    for i, gc in enumerate(t._tbl.tblGrid.findall(qn('w:gridCol'))):
        gc.set(qn('w:w'), str(int(widths[i] * sc)))
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Twips(int(w * sc))


def _md(d):
    s = str(d)
    return f"{s[4:6]}/{s[6:]}" if len(s) == 8 else s


def kakao_line(blk):
    """카카오톡 요약 한 줄."""
    if not blk:
        return None
    ov = blk.get('overlaps') or []
    s = f"매수 금지 {blk['n']}종(비중 {blk['share_pct']:.0f}%, 신뢰도 {blk['reliability']})"
    s += (" · 추천과 겹침: " + ", ".join(f"{o['name']}({o['flag']})" for o in ov)) if ov else " · 추천과 겹침 없음"
    return s


def add_sellban_table(blk, section, subsection, make_table, note):
    section('8-3. 매수 금지 목록 — 역배열 진입 후 최대 20거래일 (참고 전용)')
    if not blk:
        note("※ **아침 루틴 0-H(매수 금지 목록) 결과가 없어 이 표를 싣지 못했습니다** — 10절 데이터 검증에 결손으로 적습니다.")
        return
    rel = blk['reliability']
    note(f"※ **D={_md(blk['D'])} 종가 기준 {blk['n']}종 / 유니버스 {blk['universe_n']}종 = 목록 비중 {blk['share_pct']:.1f}% → "
         f"신뢰도 {blk['reliability_text']}**.", size=9)
    ov = blk.get('overlaps') or []
    if ov:
        note("※ **★ 오늘 추천·후보·트랙 D 와 겹치는 종목: " + ", ".join(f"{o['name']}({o['code']} · {o['flag']})" for o in ov)
             + "** — 선정 규칙은 바꾸지 않습니다. 매수 여부·비중은 사용자 판단이며, **EG 보유 종목은 팔지 않습니다**.", size=9)
    else:
        note("※ 오늘 추천(6-1 실매수·6-1표·6-3 중기 후보)·트랙 D 매수 신호·보유와 **겹치는 종목은 없습니다**.", size=9)
    if not blk['n']:
        note("※ **오늘 매수 금지 종목은 없습니다.**")
    else:
        rows = [[r['sec'], r['name'], r['code'], _md(r['sig']), f"최대 {r['remain']}일",
                 f"{r['mom20']:+.1f}%" if r.get('mom20') is not None else "—",
                 f"**★{r['flag']}**" if r.get('flag') else ""] for r in blk['rows']]
        w = [1250, 3950, 850, 800, 1050, 850, 1650]
        _apply_widths(make_table(["섹터", "종목명", "코드", "신호일", "남은 금지", "mom20", "겹침"], rows, w), w)
    note(_부록('sellban'), size=9)
    oos = blk.get('oos') or {}
    oo = (f"OOS 누적 {oos['days']}일 · 평균 {oos['avoid_bp']:+.2f}bp/일(양수 = 금지가 옳았음)" if oos.get('days')
          else f"OOS 채점 0일(기록 시작 {_md(oos.get('start') or blk['D'])})")
