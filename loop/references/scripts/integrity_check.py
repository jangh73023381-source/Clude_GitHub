#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""데이터 무결성 검증관 (2026-07-30 신설, 사용자 지시).

배경: 2026-07-30 저녁 `attention_shadow_picks.csv`가 중복 행으로 오염돼(15행이어야 할 날짜가
90행) 트랙 B 채점이 통째로 왜곡되고 보고서에 틀린 수치가 실렸다. 원인은 `record` 비멱등이었고,
**행 수만 세어봤으면 즉시 잡혔을 오류**였다. 그래서 판단이 필요 없는 기계적 불변식만 검사한다.

  LLM 검증관(loop-goal-verifier)은 '방법이 옳은가'를 판단한다.
  이 스크립트는 '데이터가 규약대로인가'를 확인한다. 역할이 다르므로 둘 다 돌린다.

검사 항목 (전부 결정론적):
  1. 날짜당 행 수 규약 위반 — 중복 append 탐지 (이번 오염의 직접 원인)
  2. 키 중복 — 같은 (날짜, 코드)가 두 번
  3. 패널 신선도 — panel_close 최종일 · kospi_close 해당일 존재
  4. 유니버스 정합 — 선정(morning_run)과 채점(dual_score·rank_etf)의 제외 조건 일치
  5. 배포물 정합 — morning_state 의 picks5 가 current-holdings.md 에 등록돼 있는지

사용:
  python3 references/scripts/integrity_check.py            # 전체 검사
  python3 references/scripts/integrity_check.py --quiet    # 실패만 출력
종료코드: 0=이상 없음 / 1=경고 / 2=오류(루틴을 멈추고 사람이 봐야 함)
"""
import argparse
import collections
import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone

H = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(H, '..'))
LOOP = os.path.abspath(os.path.join(REF, '..'))
KST = timezone(timedelta(hours=9))

# 파일별 '날짜당 정상 행 수'. 실측(2026-07-30)으로 확정했다.
ROW_SPEC = [
    ('references/attention_shadow_picks.csv', 15, 2),      # (경로, 날짜당 행수, 코드컬럼 index)
    ('references/attention_shadow_ns2_picks.csv', 15, 2),
    ('references/attention_pilot_v2_picks.csv', 5, 3),
    ('references/combo_shadow_tracker.csv', 1, None),
    ('references/stock15_oos_tracker.csv', 1, None),
    ('references/close_bet_band_tracker.csv', 1, None),
    ('references/mid_momentum_shadow.csv', 1, None),
    ('references/tv_shadow.csv', 1, None),
    ('references/dr_shadow.csv', 1, None),
    ('references/il_shadow.csv', 1, None),
    ('references/lv_oos_tracker.csv', 1, None),   # Rule LV(v2.9) OOS — 2026-08-22 등록
    ('references/eg_track_tracker.csv', 1, None),  # 트랙 D Rule EG 타점 — 2026-08-31 등록
    ('references/sell_ban_tracker.csv', 1, None),  # Rule SB 매수 금지 목록 OOS — 2026-09-11 등록
    ('references/nhi_shadow.csv', 1, None),  # Rule NHI shadow — 2026-09-17 등록
    ('references/eg_liq_shadow.csv', 1, None),  # Rule EG-LIQ shadow — 2026-09-17 등록
    ('references/mlv_mid_shadow.csv', 1, None),  # Rule MLV shadow — 2026-09-26 등록
    ('references/ibs_shadow.csv', 1, None),  # Rule IBS shadow — 2026-10-21 등록
    ('references/credit_u_shadow.csv', 1, None),  # Rule CRU shadow — 2026-10-22 등록
    ('references/foreign_avoid_shadow.csv', 1, None),  # Rule FIA shadow — 2026-10-22 등록
    ('references/breadth_shadow.csv', 1, None),  # Rule BRD shadow — 2026-10-27 등록
    ('backtest/kospi_close.csv', 1, None),
]

FAIL, WARN, OK = [], [], []


def rec(level, msg):
    {'FAIL': FAIL, 'WARN': WARN, 'OK': OK}[level].append(msg)


def read_rows(path):
    with open(path, encoding='utf-8') as f:
        rows = [r for r in csv.reader(l for l in f if not l.startswith('#')) if r]
    return rows[0], rows[1:]


def check_rows():
    """1·2 — 날짜당 행 수 규약과 키 중복."""
    for rel, per_date, codecol in ROW_SPEC:
        p = os.path.join(LOOP, rel)
        name = os.path.basename(rel)
        if not os.path.exists(p):
            rec('WARN', f'{name}: 파일 없음')
            continue
        _, data = read_rows(p)
        cnt = collections.Counter(r[0] for r in data)
        bad = {d: n for d, n in cnt.items() if n != per_date}
        if bad:
            head = ', '.join(f'{d}={n}행' for d, n in sorted(bad.items())[:4])
            rec('FAIL', f'{name}: 날짜당 {per_date}행이어야 하는데 {len(bad)}개 날짜 위반 — {head}'
                        f'{" …" if len(bad) > 4 else ""}  → 중복 append 의심')
        else:
            rec('OK', f'{name}: {len(cnt)}일 × {per_date}행 규약 준수')
        if codecol is not None:
            keys = collections.Counter((r[0], r[codecol]) for r in data if len(r) > codecol)
            dup = [k for k, n in keys.items() if n > 1]
            if dup:
                rec('FAIL', f'{name}: (날짜,코드) 중복 {len(dup)}건 — 예 {dup[0]}')


def newest_panel():
    d = os.path.join(LOOP, 'backtest')
    c = sorted(f for f in os.listdir(d)
               if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(d, c[-1]) if c else None


def check_panel():
    """3 — 패널이 직전 거래일까지 채워져 있고 코스피 종가도 있는지.
    2026-07-29·30 이틀 연속 이 결손으로 dual_score 가 실패했다."""
    p = newest_panel()
    if not p:
        rec('FAIL', 'panel_close_*.csv 없음')
        return None
    _, data = read_rows(p)
    last = max(r[2] for r in data)
    today = datetime.now(KST).strftime('%Y%m%d')
    rec('OK', f'{os.path.basename(p)}: 최종 거래일 {last}')
    if last >= today:
        rec('WARN', f'패널 최종일({last})이 오늘({today}) 이상 — 장중/미확정 종가 혼입 여부 확인')

    kp = os.path.join(LOOP, 'backtest', 'kospi_close.csv')
    if os.path.exists(kp):
        _, kd = read_rows(kp)
        have = {r[0] for r in kd}
        if last not in have:
            rec('FAIL', f'kospi_close.csv 에 {last} 없음 — dual_score.py 가 rc=1 로 실패한다. '
                        f'yfinance ^KS11 ticker info 의 regularMarketPrice 로 보충할 것')
        else:
            rec('OK', f'kospi_close.csv: {last} 확보')

    check_ohlc(last)
    return last


def check_ohlc(last):
    """3b — OHLC 패널 건전성 (2026-07-31 신설).

    실제 사고: `panel_ohlc_2y.csv` 의 마지막 2거래일이 (1) 고가=저가=종가로 눌려 있고
    (2) 날짜가 하루씩 밀려 있었다. 캔들 분석이 불가능해지고 mom150 이 하루 묵은 가격을
    최신으로 착각한다. 행 수 검사로는 잡히지 않아 전용 검사를 둔다.
    """
    p = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
    if not os.path.exists(p):
        return
    import csv as _csv
    flat = tot = 0
    close_by_day = {}
    days = set()
    for r in _csv.DictReader(open(p, encoding='utf-8')):
        d = r['date']
        days.add(d)
        if d != last:
            continue
        try:
            o, h, l, c = (float(r['open']), float(r['high']),
                          float(r['low']), float(r['close']))
        except (ValueError, KeyError):
            continue
        tot += 1
        if h <= l:
            flat += 1
        if r['code'] == '069500':
            close_by_day[d] = c
    # 절단 탐지 — 이 마운트에서 os.replace 가 원자적이지 않아, 갱신 도중 프로세스가
    # 강제 종료되면 패널이 중간에서 잘린다(실측: 96,692행 → 6,172행). 행 수로 먼저 잡는다.
    if len(days) < 300 or sum(1 for _ in open(p, encoding='utf-8')) < 50000:
        rec('FAIL', f'panel_ohlc_2y.csv 절단 의심 — 거래일 {len(days)}일뿐. '
                    f'rebuild_ohlc_panel.py 로 재구축할 것')
        return
    if not tot:
        rec('FAIL', f'panel_ohlc_2y.csv 에 {last} 행이 없음 — 갱신 실패 또는 절단')
        return
    if flat / tot > 0.5:
        rec('FAIL', f'panel_ohlc_2y.csv {last}: {flat}/{tot}종이 고가=저가 — 꼬리 결손. '
                    f'backtest/rebuild_ohlc_panel.py 로 재구축할 것')
    else:
        rec('OK', f'panel_ohlc_2y.csv {last}: 고가=저가 {flat}/{tot}종 (정상 범위)')

    # 날짜 밀림 탐지 — 같은 날 KODEX200 종가가 panel_close 와 일치해야 한다
    cp = os.path.join(LOOP, 'backtest', f'panel_close_{last[4:]}.csv')
    if os.path.exists(cp) and last in close_by_day:
        for r in _csv.DictReader(open(cp, encoding='utf-8')):
            if r['code'] == '069500' and r['date'] == last:
                if abs(float(r['close']) - close_by_day[last]) > 1:
                    rec('FAIL', f'panel_ohlc_2y.csv {last} 069500 종가 {close_by_day[last]:,.0f} '
                                f'≠ panel_close {float(r["close"]):,.0f} — 날짜 밀림 의심')
                else:
                    rec('OK', f'panel_ohlc_2y.csv {last}: panel_close 와 종가 일치')
                break


def check_universe(last):
    """4 — 선정·채점 스크립트가 같은 제외 조건을 쓰는지."""
    sys.path.insert(0, H)
    try:
        import universe_filters as U
        import morning_run as M
        import dual_score as DS
    except Exception as e:
        rec('FAIL', f'유니버스 모듈 import 실패: {type(e).__name__}: {e}')
        return
    same = (M.is_cash is U.is_cash and DS.is_cash is U.is_cash
            and M.is_deriv is U.is_deriv)
    if same:
        rec('OK', f'제외 키워드 공용 상수 일치 (DERIV {len(U.DERIV)} · CASH {len(U.CASH)})')
    else:
        rec('FAIL', '선정·채점 스크립트가 서로 다른 제외 키워드를 쓴다 — '
                    'universe_filters.py 로 통일할 것 (v2.7 결함 재발)')
    try:
        _, px, nm, dates = M.load_panel()
        d = dates[-1]
        n_sel = sum(1 for c in px if d in px[c] and U.eligible(nm.get(c, '')))
        rec('OK', f'{d} 기준 유니버스 {n_sel}종 (파생·현금성 제외, 최소가격 필터 없음)')
    except Exception as e:
        rec('WARN', f'유니버스 규모 확인 실패: {type(e).__name__}: {e}')


def check_state():
    """5 — 오늘 state 의 picks5 가 current-holdings.md 에 등록돼 있는지."""
    today = datetime.now(KST).strftime('%Y%m%d')
    sp = os.path.join(H, f'morning_state_{today}.json')
    if not os.path.exists(sp):
        rec('WARN', f'morning_state_{today}.json 없음 — 오늘 아침 루틴 미실행(장전 검사면 정상)')
        return
    import json
    s = json.load(open(sp, encoding='utf-8'))
    picks = (s.get('picks') or {}).get('picks5', '')
    hp = os.path.join(LOOP, 'current-holdings.md')
    txt = open(hp, encoding='utf-8').read() if os.path.exists(hp) else ''
    codes = [c for c in picks.split(',') if c]
    missing = [c for c in codes if c not in txt]
    if not codes:
        rec('WARN', 'state 에 picks5 가 비어 있음')
    elif missing:
        rec('FAIL', f'state picks5 중 {missing} 가 current-holdings.md 에 없음 — '
                    f'채점 대상 등록 누락')
    else:
        rec('OK', f'state picks5 {len(codes)}종 전부 current-holdings.md 에 등록됨')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    check_rows()
    last = check_panel()
    check_universe(last)
    check_state()

    print('=' * 72)
    print(f'[무결성 검증관] OK {len(OK)} · 경고 {len(WARN)} · 오류 {len(FAIL)}')
    print('=' * 72)
    if not a.quiet:
        for m in OK:
            print(f'  [OK]   {m}')
    for m in WARN:
        print(f'  [경고] {m}')
    for m in FAIL:
        print(f'  [오류] {m}')
    if FAIL:
        print('\n오류가 있습니다. 채점·보고서 수치가 왜곡될 수 있으니 먼저 해결하십시오.')
        return 2
    return 1 if WARN else 0


if __name__ == '__main__':
    sys.exit(main())
