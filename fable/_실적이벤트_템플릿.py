# -*- coding: utf-8 -*-
"""데일리 브리핑 [1-6] 실적 이벤트 달력 — 생성 조각 (2026-10-28 신설, fable/CLAUDE.md 29번).

성격: **참고 전용 — 선정 로직 반영 금지.** 1절 여섯 번째 소제목(새 절을 만들지 않는다 — 19번 (a)와 같은 취지).

생성기에서:
    blk = json.loads(subprocess.run([sys.executable, 'earnings_event_ref.py', '--json'],
                     capture_output=True, text=True, cwd=FABLE).stdout)
    add_earnings_cal(blk, subsection, make_table, note)
"""


def _md(d):
    return f"{d[4:6]}/{d[6:]}"


def add_earnings_cal(blk, subsection, make_table, note):
    if not blk:
        subsection("[1-6] 실적 이벤트 달력 — 산출 실패")
        note("※ `earnings_event_ref.py` 결손 — 10절 검증표에 기록합니다.")
        return
    head = f"[1-6] 실적 이벤트 달력 — 앞으로 {blk.get('horizon_days', 10)}일 (코스피 시총 상위 · DART IR 안내공시)"
    if blk.get('stale'):
        head += " ※캐시(갱신 실패)"
    subsection(head + " · 참고 전용")
    rows = blk.get('rows') or []
    if not rows:
        note("※ 앞으로 10일 안에 예정된 시총 상위 기업의 실적 발표(IR 안내공시)가 없습니다.")
    else:
        today = blk.get('asof', '')
        body = [[(_md(r['date']) + (' **오늘**' if r['date'] == today else '')), r.get('time') or '-', r['name'], r.get('purpose') or '실적 발표',
                 _md(r['filed'])] for r in rows]
        make_table(['날짜', '시각', '기업', '내용', '안내공시일'], body, [1500, 900, 1800, 3000, 1300])
        for r in rows:
            if r.get('stat'):
                note(f"※ **과거 반응** — {r['stat']}")
    note(blk.get('footnote', ''), size=9)


def kakao_line(blk):
    rows = (blk or {}).get('rows') or []
    if not rows:
        return ''
    s = ' · '.join(f"{_md(r['date'])} {r['name']}" for r in rows[:4])
    return f"실적 일정: {s} — 발표일 반도체 변동 확대(방향 신호 아님) ※참고 전용"
