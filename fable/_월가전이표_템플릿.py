# -*- coding: utf-8 -*-
"""데일리 브리핑 [1-3] 미국장 전이 참고표 + 발표 일정 — 생성 조각
(2026-09-08 신설, fable/CLAUDE.md 19번).

성격: **참고 정보 전용 — 예측 신호 아님.** 선정 로직 반영 금지.
근거: `C:\\agent\\Claude\\loop\\월가정보_이벤트캘린더_검토_20260908.md`
      (7년 1,822 한국거래일 · 22섹터 전부 5구간 단조 · 충격은 D+1 하루로 종료)

**1절(전일 시장 요약)의 세 번째 소제목**으로 넣는다. 새 절을 만들지 않는 이유는
2절 이하 번호가 전부 밀리기 때문이다(CLAUDE.md 7번 "번호 이동 주의").

브리핑 생성기(`_gen_briefing_YYYYMMDD.py`)에서 아래처럼 쓴다.

    import json, subprocess, sys
    blk = json.loads(subprocess.run(
        [sys.executable, 'wallst_ref.py', '--json'],
        capture_output=True, text=True, cwd=FABLE).stdout)
    add_wallst_table(blk, subsection, make_table, note)
"""

# 구간별로 브리핑 본문에 붙일 한 줄 해설 — 표를 잘못 읽는 것을 막는다.
_READ = {
    'SOX ≤ -2%': "AI·AI전력·반도체가 지수의 **2~2.5배**로 맞는 구간입니다. "
                 "방어처는 **귀금속·채권뿐**이며 은행·자동차는 지수와 큰 차이가 없습니다.",
    '-2 ~ -1%':  "약세지만 섹터 간 격차가 작은 구간입니다. 성장 계열만 -0.4~-0.9% 수준입니다.",
    '-1 ~ +1%':  "전이가 사실상 없는 구간입니다. 이날의 한국장은 미국장이 아니라 "
                 "국내 수급·개별 재료가 결정합니다.",
    '+1 ~ +2%':  "성장 계열이 앞서는 구간입니다. 다만 이 크기는 개장 갭에 상당 부분 들어갑니다.",
    'SOX ≥ +2%': "AI 상승확률 88.7%·반도체 77.7%로 방향은 강하지만, **대부분 갭으로 열립니다** — "
                 "추격 매수의 근거가 아니라 **매수상단을 넓히지 말아야 할 근거**로 읽습니다.",
}


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


def add_wallst_table(blk, subsection, make_table, note):
    bucket = blk.get('bucket')
    sox = blk.get('sox') or {}
    head = f"[1-3] 미국장 전이 참고표 — 전일 SOX 구간 [{bucket}]" if bucket else \
           "[1-3] 미국장 전이 참고표 — 구간 판정 불가"
    if blk.get('stale'):
        head += " ※캐시(갱신 실패)"
    subsection(head + " (7년 실측 · 참고 전용, 종목 선정 미적용)")

    # 구간 판정 근거
    if sox:
        note(f"※ 구간 판정 근거 — **필라델피아 반도체(SOX) {sox['close']:,.2f} "
             f"({sox['chg']:+.2f}%, {sox['date']} 종가)**. 미국 지수 3종은 마지막 정규장 종가이고 "
             f"10년물·VIX는 조회 시점 값이라 기준일이 다를 수 있습니다. "
             f"**구간을 정하는 것은 SOX 하나**입니다.")

    if blk.get('rows'):
        body = []
        for r in blk['rows']:
            body.append([r['sector'], f"{r['exp']:+.2f}%", f"{r['win']:.1f}%", f"{r['beta']:.3f}"])
        make_table(['섹터', '익일 참고 평균', '익일 상승확률', 'SOX 베타'],
                   body, [2400, 2000, 2000, 1600])
        note(f"※ 위 수치는 같은 구간이었던 과거 **{blk['bucket_n']}일**의 평균입니다. "
             f"{_READ.get(bucket, '')}")
        note(_부록('wallst'), size=9)

    # 발표 일정
    cal = blk.get('calendar') or []
    if cal:
        body = [[f"D{c['dday']:+d}", c['date'], c['event'], c['time'], c['note'] or '—'] for c in cal]
        make_table(['D-day', '날짜', '이벤트', '한국시각', '비고'],
                   body, [900, 1500, 2600, 1300, 3300])

    # 아래 각주는 fable/CLAUDE.md 19번 (d) 규칙상 누락 금지
