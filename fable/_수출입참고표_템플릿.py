# -*- coding: utf-8 -*-
"""데일리 브리핑 [8-2] 월간 수출입 참고표 — 생성 조각 (2026-09-02 신설, fable/CLAUDE.md 18번).

성격: **참고 정보 전용 — 예측 신호 아님.** 선정 로직 반영 금지.
근거: `C:\\agent\\Claude\\loop\\수출입데이터_섹터로테이션_검정_20260902.md`
      (6개 축 전부 기각, 수출↔주가 상관 정점이 k=0 동시점 · 발표는 그보다 한 달 늦음)

브리핑 생성기(`_gen_briefing_YYYYMMDD.py`)에서 아래처럼 쓴다.

    import json, subprocess, sys
    blk = json.loads(subprocess.run(
        [sys.executable, 'trade_ref.py', '--json'],
        capture_output=True, text=True, cwd=FABLE).stdout)
    add_trade_table(blk, section, subsection, make_table, note)

데이터는 월 1회만 바뀌고 `trade_ref.py`가 스스로 캐싱·자동 갱신하므로 매일 호출하면 된다.
`blk['flash']`(산업통상부 1일 잠정치, trade_flash.py)가 있으면 확정표 위에 '속보' 표를 먼저 싣는다.
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


def _fmt_yoy(v):
    return f"{v:+.1f}%" if v is not None else "—"


def add_trade_table(blk, section, subsection, make_table, note):
    ym = blk.get('data_month', '')
    title = f"{ym[:4]}년 {int(ym[4:]):d}월 확정" if len(ym) == 6 else "기준월 미상"
    if blk.get('stale'):
        title += " ※캐시(갱신 실패)"

    section('8-2. 월간 수출입 참고표')

    # (2026-10-03 신설, fable CLAUDE.md 18-(i)) 산업통상부 1일 잠정치가 확정월보다 새로우면 먼저 싣는다.
    # 관세청 확정치는 15일경에야 들어오므로, 그 사이 2주간 표가 '두 달 전' 숫자로만 남던 공백을 메운다.
    fl = blk.get('flash')
    if fl:
        fm = fl['data_month']
        ft = f"{fm[:4]}년 {int(fm[4:]):d}월 잠정"
        if fl.get('stale'):
            ft += " ※캐시(갱신 실패)"
        subsection(f'속보 — 산업통상부 수출입 동향 {ft} (확정치는 관세청 공개 후 아래 표로 교체)')
        note(f"※ 총수출 {fl['총수출']:,.1f}억$({fl['총수출YoY']:+.1f}%) · 총수입 {fl['총수입']:,.1f}억$"
             f"({fl['총수입YoY']:+.1f}%) · 무역수지 {fl['무역수지']:+,.1f}억$")
        make_table(['품목(산업부 분류)', '수출(십억$)', '전년동월비'],
                   [[r['품목'], f"{r['수출']:,.2f}", _fmt_yoy(r['YoY'])] for r in fl.get('rows', [])],
                   [2600, 1700, 1600])
        note("※ 잠정치는 산업통상부 분류(MTI)라 아래 관세청 HS 기준 확정표와 품목 범위가 다르다"
             "(예: 일반기계 ≠ HS84 전체, 바이오헬스 ≠ HS3004). 디램 단가는 확정치에서만 산출한다.", size=9)

    subsection(f'관세청 품목별 수출입실적 — {title} (시황 서술 전용, 종목 선정 미적용)')

    body = []
    for r in blk.get('rows', []):
        body.append([
            r['품목'],
            f"{r['수출']:,.2f}",
            _fmt_yoy(r['YoY']),
            f"{r['수입']:,.2f}",
            f"{r['무역수지']:+,.2f}",
        ])
    make_table(['품목', '수출(십억$)', '전년동월비', '수입(십억$)', '무역수지(십억$)'],
               body, [2200, 1500, 1400, 1500, 1600])

    asp = blk.get('asp')
    if asp:
        note(f"※ {asp['품목']} 실현단가(수출금액÷중량) {asp['단가']:,.0f}$/kg "
             f"— 전년동월 {asp['전년동월']:,.0f}$/kg 대비 {asp['증감률']:+.1f}%. "
             f"단가는 구성 아티팩트를 피하기 위해 동질적 단일 HS10 코드에서만 산출합니다"
             f"(HS 8541에는 태양전지가 섞여 있어 섹터 단위 단가는 왜곡됩니다).")

    if blk.get('summary'):
        note(f"※ 요약 — {blk['summary']}")

    # 아래 각주는 fable/CLAUDE.md 18번 (e) 규칙상 누락 금지
    note(_부록('trade'), size=9)
