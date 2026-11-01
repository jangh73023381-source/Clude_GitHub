# -*- coding: utf-8 -*-
"""데일리 브리핑 [8-4] 송재호식 참고표 — 생성 조각 (2026-09-12 신설, fable/CLAUDE.md 21번).

성격: **참고 전용 — 선정·우선순위·청산 반영 금지.** 8-1 지지·저항, 8-2 수출입, 8-3 매수금지와 같은 취급.
규칙: Rule SJH v1.0 — 게이트(KODEX200>MA20) · 실적필터(매출·영업이익 YoY>0 & 흑자) · 20일 거래대금 상위 10종 ·
      20거래일 비중복 리밸런싱(바스켓 통째 교체, 손절 없음).
근거: `C:\\agent\\Claude\\loop\\송재호식_종목선정_백테스트_2026-09-12.docx`
      (개별종목 3,101종·7.7년 486만행. 6축 중 4축 기각, 생존 2축의 상호작용 +1.46%p/20일. **승격 불가**)

브리핑 생성기(`_gen_briefing_YYYYMMDD.py`)에서 아래처럼 쓴다. 수기 재계산·수기 선별 금지.

    blk = json.loads(subprocess.run([sys.executable, 'sjh_ref.py', '--json'],
                                    capture_output=True, text=True, cwd=FABLE).stdout)
    add_sjh_table(blk, section, subsection, make_table, note)
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
    """이 표만 열 너비를 고정한다(make_table 은 autofit 이라 LibreOffice 에서 종목명이 깨진다)."""
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
    s = str(d or '')
    return f"{s[4:6]}/{s[6:]}" if len(s) == 8 else (s or '—')


def _pct(v):
    if v is None:
        return '—'
    return f"{v:+,.1f}%" if abs(v) < 1000 else f"{v:+,.0f}%"


def kakao_line(blk):
    """카카오톡 요약 한 줄 (없으면 None)."""
    return (blk or {}).get('kakao') or None


def add_sjh_table(blk, section, subsection, make_table, note):
    section('8-4. 송재호식 참고표 — 실적 확인 × 주도주 집중 (참고 전용, 실매수 아님)')

    if not blk or not blk.get('items') and blk.get('gate') is None:
        note("※ **송재호식 참고표 산출에 실패해 이 표를 싣지 못했습니다** — 10절 데이터 검증에 결손으로 적습니다.")
        return

    stale = ' ※캐시(갱신 실패)' if blk.get('stale') else ''
    gate = blk.get('gate')
    gtxt = ('**게이트 ON** (KODEX200 %s > MA20 %s)' % (f"{blk.get('bench_close',0):,.0f}", f"{blk.get('bench_ma20',0):,.0f}")
            if gate else
            '**게이트 OFF — 신규 편입 없음(현금)**. KODEX200 %s ≤ MA20 %s' % (f"{blk.get('bench_close',0):,.0f}", f"{blk.get('bench_ma20',0):,.0f}"))
    if blk.get('is_rebalance'):
        rb = '**오늘이 리밸런싱일**'
    else:
        rb = '다음 리밸런싱 **%d거래일 후**' % blk.get('days_to_rebalance', 0)
    note("※ **%s 종가 기준%s** — %s · 실적 필터 통과 풀 **%d종** · %s."
         % (_md(blk.get('asof')), stale, gtxt, blk.get('pool', 0), rb), size=9)

    items = list(blk.get('items') or []) + list(blk.get('candidates') or [])
    if not items:
        note("※ **게이트 OFF 구간이라 오늘 보유 종목이 없습니다(현금).** 규칙상 게이트가 다시 켜지는 리밸런싱일에만 편입합니다.")
    else:
        rows = [[i.get('gubun', ''), i.get('name', ''), i.get('code', ''),
                 f"{i['close']:,}" if i.get('close') else '—',
                 f"{i['to20']/1e8:,.0f}억" if i.get('to20') else '—',
                 str(i['rank']) if i.get('rank') else '—',
                 _pct(i.get('sa_g')), _pct(i.get('op_g')),
                 _md(i.get('entry')),
                 ('—' if i.get('left') is None else f"{i['left']}일")] for i in items]
        w = [1150, 2350, 820, 950, 1000, 620, 1000, 1100, 780, 780]
        _apply_widths(make_table(
            ["구분", "종목명", "코드", "종가", "20일 거래대금", "순위", "매출 YoY", "영업이익 YoY", "편입일", "잔여"],
            rows, w), w)
        note("※ **구분** — 신규/유지/청산은 20거래일 리밸런싱일에만 바뀝니다. '후보'는 오늘 랭킹 상위지만 "
             "현재 바스켓에 없는 종목으로, **다음 리밸런싱 전까지는 편입하지 않습니다**(중간 교체는 검정된 적이 없습니다). "
             "'순위'는 실적 필터 통과 풀 안에서의 20일 평균 거래대금 순위입니다.", size=9)

    note(_부록('sjh'), size=9)



    if blk.get('warn'):
        note("※ 데이터 경고 — " + ' / '.join(blk['warn']) + " (10절 데이터 검증에 함께 적습니다).", size=9)
