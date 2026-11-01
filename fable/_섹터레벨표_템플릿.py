# -*- coding: utf-8 -*-
"""데일리 브리핑 [8-1] 섹터 대표 종목 지지·저항 참고표 — 생성 조각.

2026-07-31 사용자 지시로 [6-3]·[7-3] 표를 폐지하고 이 표 하나로 대체했다.
브리핑 생성기(`_gen_briefing_YYYYMMDD.py`)에서 아래처럼 쓴다.

    import json, subprocess, sys
    rows = json.loads(subprocess.run(
        [sys.executable, 'sector_levels.py', '--json'],
        capture_output=True, text=True, cwd=FABLE).stdout)
    add_sector_table(rows, section, subsection, make_table, note)

`make_table` 등 헬퍼는 `_데일리브리핑_양식템플릿.py` 의 것을 그대로 받는다.
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


def _cell(x):
    """지지·저항 셀 — '가격 (±%, ±ATR) 근거'. 후보가 없으면 사유를 적는다."""
    if not x:
        return '— 없음'
    return f"{x['price']:,.0f} ({x['pct']:+.1f}%, {x['atr']:+.1f}A)\n{x['label']}"


def add_sector_table(rows, section, subsection, make_table, note):
    section('8-1. 섹터 대표 종목 지지·저항 참고표')
    subsection('Rule SU 유니버스 15종 — 그날 추천 여부와 무관하게 매일 전체를 싣는다')
    body = []
    for r in rows:
        if r.get('error'):
            body.append([r['sector'], f"{r['name']}({r['code']})", '조회 실패',
                         r['error'], '—', '—', '—', '—'])
            continue
        p120 = f"{r['p120']:.2f}" if r['p120'] is not None else '—'
        p250 = f"{r['p250']:.2f}" if r['p250'] is not None else '—'
        ch = f'{p120} / {p250}'
        if r['zone']:
            ch += f"\n{r['zone']}"
        body.append([
            r['sector'],
            f"{r['name']}({r['code']})",
            f"{r['close']:,.0f}",
            f"{r['atr']:,.0f}\n({r['atr_pct']:.1f}%)",
            ch,
            _cell(r['s1']), _cell(r['s2']),
            _cell(r['r1']), _cell(r['r2']),
        ])
    make_table(['섹터분야', '종목명(코드)', '현재가', 'ATR14', '채널위치(6M/12M)',
                '1차 지지', '2차 지지', '1차 저항', '2차 저항'], body,
               [900, 1700, 1000, 800, 1200, 1300, 1300, 1300, 1300])

    # 아래 두 각주는 fable/CLAUDE.md 15번 (f)(g) 규칙상 누락 금지
    note(_부록('levels'), size=9)
