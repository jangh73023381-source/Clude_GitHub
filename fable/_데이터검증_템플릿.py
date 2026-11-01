# -*- coding: utf-8 -*-
"""데일리 브리핑 [10] 데이터 검증 결과 — 표 형식 (2026-09-12 개정, fable/CLAUDE.md 23번).

배경: 2026-09-11 실측에서 10절이 3,183자 산문이었고 대부분이 "정상입니다" 확인이었다.
원칙: **정상 항목은 표 한 줄. 서술은 결손·경고·사고·조치·판정에만 쓴다.**
      정상 항목을 문장으로 다시 설명하지 않는다(같은 내용을 두 번 싣지 않는다).

    from _데이터검증_템플릿 import add_verification, OK, WARN, MISS
    add_verification(
        rows=[('무결성 검증관', OK, 'OK 20 · 경고 0 · 오류 0'),
              ('0-C 뉴스 5선', OK, '풀 1,603건'),
              ('7년 패널', WARN, '최종일 20260908 — 이틀 후행, 오늘 판정에 미사용')],
        prose=['**★ 어제 아침 루틴 미실행분 3건 전부 회수** — …'],
        section=section, make_table=make_table, note=note)
"""

OK, WARN, MISS = '정상', '경고', '결손'
_MARK = {OK: '✓', WARN: '△', MISS: '✕'}

# 매일 반복되는 표준 항목 순서(있는 것만 싣는다). 새 항목은 뒤에 붙인다.
STD_ORDER = [
    '무결성 검증관', '0-B 관심신호 수집', '0-C 뉴스 5선', '0-D 중기 shadow',
    '0-E Rule CB', '0-F Rule LV', '0-G Rule EG', '0-H 매수 금지(SB)',
    '[1-3] 미국장 전이표', '[1-4] 테마 자금 흐름', '[8-2] 월간 수출입', '[8-4] 송재호식(SJH)',
    '2년 패널', '7년 패널', '코스피 종가', '독립 재계산 일치', 'N 대장',
]


def _apply_widths(t, widths):
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


def add_verification(rows, prose, section, make_table, note, title='10. 데이터 검증 결과'):
    """rows = [(항목, 상태, 비고)] · prose = [결손·경고·조치·판정 서술] """
    section(title)
    rows = list(rows or [])
    idx = {n: i for i, n in enumerate(STD_ORDER)}
    rows.sort(key=lambda r: idx.get(r[0], 999))
    n_ok = sum(1 for r in rows if r[1] == OK)
    n_w = sum(1 for r in rows if r[1] == WARN)
    n_m = sum(1 for r in rows if r[1] == MISS)
    note("※ **정상 %d · 경고 %d · 결손 %d** — 정상 항목은 표로만 싣고 따로 서술하지 않습니다. "
         "아래 서술은 **경고·결손·조치·판정**에 한합니다." % (n_ok, n_w, n_m), size=9)
    if rows:
        body = [[r[0], '%s %s' % (_MARK.get(r[1], '·'), r[1]), r[2] or ''] for r in rows]
        w = [2600, 1250, 6550]
        _apply_widths(make_table(['항목', '상태', '비고'], body, w), w)
    for p in (prose or []):
        note('※ ' + p if not str(p).startswith('※') else p)
    if not prose:
        note("※ 경고·결손·조치 사항 없음.", size=9)
