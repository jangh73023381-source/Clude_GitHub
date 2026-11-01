# -*- coding: utf-8 -*-
"""briefing_core.py — 데일리 브리핑 docx 저수준 빌더 헬퍼 (2026-11-01 추출).

`_gen_briefing_0814.py` 1~142행(2026-08-14 작성)에 하드코딩돼 있던 것을
**한 글자도 바꾸지 않고** 그대로 옮긴 모듈이다. 그 파일은 2026-08-18~2026-10-30
사이 51개 `_gen_briefing_*.py`/`_gen_eg_*.py` 스크립트가
`exec(open('_gen_briefing_0814.py', ...).read().split('# 데일리브리핑 2026-08-14 본문')[0])`
방식으로 "임포트"해 오던 유일한 공유 지점이었다 — 이름·위치가 전혀 그렇게 보이지
않는 숨은 핵심 인프라였다. 이 모듈로 분리해 표준 `import`로 바꾼다
(상세: /tmp 스크래치패드의 `gen_briefing_consolidation_plan.md`).

사용법(기존 51개 파일과 동일한 효과):

    from briefing_core import *

`doc = Document()`를 모듈 임포트 시점에 생성하는 것까지 원본과 동일한 동작이다
(각 브리핑 스크립트는 독립된 프로세스로 실행되므로 스크립트마다 새 `doc`를 받는다).
"""
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_LINE_SPACING

FONT = "Noto Sans CJK KR"
NAVY = RGBColor(0x1F, 0x38, 0x64)
GREEN_TXT = RGBColor(0x1E, 0x7B, 0x34)
RED_TXT = RGBColor(0xC0, 0x00, 0x00)

doc = Document()
for s in doc.sections:
    s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = 457200


def shade(elem, hexcolor):
    sh = OxmlElement('w:shd')
    sh.set(qn('w:val'), 'clear')
    sh.set(qn('w:fill'), hexcolor)
    elem.append(sh)


def _fix_line_spacing(p):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.15


def add_run(para, text, size, bold=False, color=None):
    r = para.add_run(text)
    r.font.name = FONT
    r.font.size = Pt(size)
    r.bold = bold
    if color:
        r.font.color.rgb = color
    r._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    return r


def para(runs, space_before=0, space_after=60, shading=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    _fix_line_spacing(p)
    for (text, size, bold, color) in runs:
        add_run(p, text, size, bold, color)
    if shading:
        shade(p._p.get_or_add_pPr(), shading)
    return p


def title(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    _fix_line_spacing(p)
    add_run(p, text, 16, True, NAVY)
    return p


def section(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(5)
    _fix_line_spacing(p)
    add_run(p, text, 13, True, NAVY)
    return p


def subsection(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(3)
    _fix_line_spacing(p)
    add_run(p, text, 10.5, True)
    return p


def note(text, size=8.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    _fix_line_spacing(p)
    add_run(p, text, size, False)
    return p


def labelpara(label, rest, size=10):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    _fix_line_spacing(p)
    add_run(p, label, size, True)
    add_run(p, rest, size, False)
    return p


def bullet(text, size=9.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    _fix_line_spacing(p)
    add_run(p, text, size, False)
    return p


def set_table_borders(t, color="BFBFBF", sz=2):
    tblPr = t._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), str(sz))
        el.set(qn('w:color'), color)
        borders.append(el)
    tblPr.append(borders)


def make_table(headers, rows, colwidths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    set_table_borders(t)
    t.autofit = True
    hdr = t.rows[0]
    for i, htext in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = ""
        add_run(cell.paragraphs[0], htext, 8, True, RGBColor(0xFF, 0xFF, 0xFF))
        shade(cell._tc.get_or_add_tcPr(), "1F3864")
    for rdata in rows:
        cells = t.add_row().cells
        for i, val in enumerate(rdata):
            cells[i].text = ""
            add_run(cells[i].paragraphs[0], str(val), 8, False)
    return t


def px(v):
    return f"{v:,.0f}"


def band(c, up, e1, sl, tg):
    return px(round(c * up)), px(round(c * e1)), px(round(c * sl)), px(round(c * tg))
