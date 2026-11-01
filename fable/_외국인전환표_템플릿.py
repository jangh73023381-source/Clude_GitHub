# -*- coding: utf-8 -*-
"""데일리 브리핑 [1-5] 외국인 수급 전환 확률표 — 생성 조각 (2026-10-21 신설, fable/CLAUDE.md 28번).

성격: **참고 전용 — 선정 로직 반영 금지.** 1절 다섯 번째 소제목(새 절을 만들지 않는다 — 19번 (a)와 같은 취지).

생성기에서:
    blk = json.loads(subprocess.run([sys.executable, 'foreign_turn_ref.py', '--json'],
                     capture_output=True, text=True, cwd=FABLE).stdout)
    add_foreign_turn(blk, subsection, make_table, note)
"""
import os


def _부록(key):
    import sys, importlib
    d = os.path.dirname(os.path.abspath(__file__))
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        return importlib.import_module('_각주_부록').short(key)
    except Exception:
        return ''


def _jo(eok):
    return f"{eok/1e4:+.1f}조"


def add_foreign_turn(blk, subsection, make_table, note):
    if not blk or not blk.get('rows'):
        subsection("[1-5] 외국인 수급 전환 확률 — 산출 실패")
        note("※ `foreign_turn_ref.py` 결손 — 10절 검증표에 기록합니다.")
        return
    a = blk['asof']
    head = f"[1-5] 외국인 수급 전환 확률 — 앞으로 {blk['horizon']}거래일, 주별 (기준 {a[4:6]}/{a[6:]} 종가)"
    if blk.get('stale'):
        head += " ※캐시(갱신 실패)"
    subsection(head + " · 참고 전용")
    note(f"※ 코스피 외국인 **직전 20거래일 누적 {_jo(blk['s20_eok'])}** · 순매도 국면 **{blk['regime_days']}거래일째** · "
         f"이번 주 누적 {_jo(blk['week_now_eok'])}. '전환' = **20거래일 누적 순매수가 플러스**로 바뀌는 첫날.")
    body = [[r['week'], f"{r['ndays']}일", f"{r['prob']:.0f}%", f"{r['cum']:.0f}%", f"{r['regime']:.0f}% / {r['y2026']:.0f}%"]
            for r in blk['rows']]
    make_table(['주', '거래일', '그 주 첫 전환', '누적', '표본별(순매도 국면 / 올해)'], body, [2000, 1000, 1700, 1300, 2600])
    if blk.get('need'):
        nd = ' · '.join(f"{x['date']}까지 하루 {_jo(x['eok'])}" for x in blk['need'])
        note(f"※ **산술 기준** — 매일 같은 금액을 순매수한다고 할 때 전환에 필요한 하루 평균: {nd}. "
             "큰 매도일이 20일 창에서 빠지는 주에 확률이 몰립니다.")
    wb = blk.get('weekly_base') or {}
    if wb:
        note(f"※ 한 주 단위로 '그 주를 순매수로 마칠' 기저 확률은 순매도 국면 {wb.get('regime', 0):.0f}% · 올해 {wb.get('y2026', 0):.0f}%입니다 — "
             "하루이틀·한 주 순매수는 전환이 아닙니다.")
    note(_부록('foreign'), size=9)


def kakao_line(blk):
    if not blk or not blk.get('rows'):
        return ''
    pk = max(blk['rows'], key=lambda r: r['prob'])
    return (f"외국인 수급: 20일 누적 {_jo(blk['s20_eok'])} · 전환 확률 최고 {pk['week']} {pk['prob']:.0f}% · "
            f"{blk['horizon']}거래일 누적 {blk['yr_end_cum']:.0f}% ※참고 전용")
