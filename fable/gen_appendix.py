# -*- coding: utf-8 -*-
"""『참고표 읽는 법』 상설 부록 발행기 (2026-09-12 신설, fable/CLAUDE.md 22번).

일일 브리핑에서 걷어낸 **근거·한계 각주 전문**을 한 문서로 모은다.
내용이 바뀔 때만(= 규칙 개정·재검정 시에만) 다시 발행한다. 매일 만들지 않는다.

    python3 gen_appendix.py            # docx + pdf
    python3 gen_appendix.py --no-pdf   # docx 만
"""
import io, os, sys, datetime as dt
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

F = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, F)
import _각주_부록 as 부록

NAVY = RGBColor(0x1F, 0x38, 0x64)
FONT = '맑은 고딕'


def _run(p, text, size=10, bold=False, color=None):
    """**굵게** 마크업을 인라인으로 처리한다."""
    for i, seg in enumerate(text.split('**')):
        if not seg:
            continue
        r = p.add_run(seg)
        r.font.name = FONT
        r.font.size = Pt(size)
        r.bold = bold or (i % 2 == 1)
        if color:
            r.font.color.rgb = color
        r._element.rPr.rFonts.set(
            __import__('docx').oxml.ns.qn('w:eastAsia'), FONT)


def build(path):
    doc = Document()
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Inches(0.7)
        s.left_margin = s.right_margin = Inches(0.8)

    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
    _run(p, '데일리 브리핑 부속', size=9, color=RGBColor(0x6B, 0x76, 0x84))
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
    _run(p, '참고표 읽는 법', size=20, bold=True, color=NAVY)
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(14)
    _run(p, '발행 %s · 참고표의 근거·한계 전문. 일일 브리핑에는 경고 한 줄만 싣고 상세는 이 문서를 본다.'
         % dt.date.today().isoformat(), size=9, color=RGBColor(0x40, 0x40, 0x40))

    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(10)
    _run(p, '이 문서들은 전부 참고 전용이다. 어느 표의 수치도 [6-1]·[6-2]·[6-3]·9절의 종목 선정·'
            '우선순위·청산에 반영하지 않는다. 표는 이미 정해진 종목의 집행(매수상단·손절선·비중)과 '
            '시황 서술에만 쓴다.', size=9.5)

    for key in ['wallst', 'flow', 'foreign', 'entry', 'trade']:   # 2026-09-17 levels·sellban·sjh 폐지(CLAUDE.md 24번)
        it = 부록.ITEMS[key]
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(3)
        _run(p, '%s %s' % (it['sec'], it['title']), size=13, bold=True, color=NAVY)
        p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(6)
        _run(p, '일일 브리핑에 실리는 줄: ' + 부록.short(key).lstrip('※ '),
             size=8.5, color=RGBColor(0x6B, 0x76, 0x84))
        for para in 부록.body(key):
            p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(5)
            p.paragraph_format.left_indent = Inches(0.12)
            _run(p, '· ' + para, size=9.5)

    doc.save(path)
    return path


if __name__ == '__main__':
    out = os.path.join(F, '참고표_읽는_법.docx')
    build(out)
    print('saved', out, os.path.getsize(out))
    if '--no-pdf' not in sys.argv:
        import subprocess
        # 2026-09-30 — /sessions 디스크 100% 시 LibreOffice 프로필(~/.config·~/.cache) 생성 실패로
        # 변환이 죽는다. HOME·TMPDIR 을 루트 디스크(/tmp)로 돌려서 실행한다.
        # 2026-10-27 — /tmp 는 세션 간 공유라 남의 세션 소유 /tmp/lohome 이면 무응답 타임아웃(실측) → 세션별 경로로 폴백.
        lohome = '/tmp/lohome'
        os.makedirs(lohome, exist_ok=True)
        if not os.access(lohome, os.W_OK):
            lohome = f'/tmp/lohome_{os.getuid()}'
            os.makedirs(lohome, exist_ok=True)
        r = subprocess.run(['soffice', '--headless', '--convert-to', 'pdf',
                            '--outdir', F, out], capture_output=True, text=True, timeout=160,
                           env=dict(os.environ, HOME=lohome, TMPDIR='/tmp'))
        pdf = out.replace('.docx', '.pdf')
        print('pdf', pdf, os.path.getsize(pdf) if os.path.exists(pdf) else r.stderr[:200])
