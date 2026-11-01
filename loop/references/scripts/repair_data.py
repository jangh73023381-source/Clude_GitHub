#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repair_data.py — 데이터 오염 자동 진단·복구 (2026-07-31 신설).

`integrity_check.py` 가 "무엇이 잘못됐는지"를 말해준다면, 이 스크립트는 **그것을 고친다.**
2026-07-30·07-31 사고에서 실제로 손으로 했던 복구 절차를 그대로 자동화했다.

  진단 → 복구 대응표
  ─────────────────────────────────────────────────────────────
  트래커 (날짜,코드) 중복        → 뒤쪽만 남기고 dedupe (7/30 사고)
  OHLC 패널 절단                → 스냅샷 롤백, 없으면 rebuild 안내 (7/31 사고)
  OHLC 패널 꼬리 결손(H=L=C)     → 스냅샷 롤백, 없으면 rebuild 안내
  OHLC 패널 날짜 밀림           → 스냅샷 롤백, 없으면 rebuild 안내
  패널·코스피 종가 결손          → ensure_data.ensure() 호출

기본은 **진단만**(dry-run) 한다. 실제로 고치려면 `--fix` 를 준다.
조회·파일 조작 전용 — 주문·매매 기능 없음.
"""
import argparse
import csv
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import safe_io  # noqa: E402

OHLC = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
# (파일, 중복 판정 키) — 새 트래커를 만들면 여기에 한 줄 추가한다
TRACKERS = [
    ('references/attention_shadow_picks.csv', ('date', 'code')),
    ('references/attention_shadow_ns2_picks.csv', ('date', 'code')),
    ('references/attention_pilot_v2_picks.csv', ('date', 'code')),
    ('references/combo_shadow_tracker.csv', ('date',)),
    ('references/close_bet_band_tracker.csv', ('date',)),
    ('references/stock15_oos_tracker.csv', ('date',)),
    ('references/mid_momentum_shadow.csv', ('date',)),
    ('references/rg_shadow.csv', ('date',)),
    ('references/cd_shadow.csv', ('date',)),
    ('references/sjh_tracker.csv', ('date',)),  # 2026-11-01: Rule SJH 종결(2026-09-17)로 보관 중이나 양쪽 레지스트리 모두 미등록이었음
    ('references/tv_shadow.csv', ('date',)),
    ('references/dr_shadow.csv', ('date',)),
    ('references/il_shadow.csv', ('date',)),
    ('references/lv_oos_tracker.csv', ('date',)),   # Rule LV(v2.9) OOS — 2026-08-22 등록
    ('references/eg_track_tracker.csv', ('date',)),  # 트랙 D Rule EG 타점 — 2026-08-31 등록
    ('references/sell_ban_tracker.csv', ('date',)),  # Rule SB 매수 금지 목록 OOS — 2026-09-11 등록
    ('references/nhi_shadow.csv', ('date',)),  # Rule NHI shadow — 2026-09-17 등록
    ('references/eg_liq_shadow.csv', ('date',)),  # Rule EG-LIQ shadow — 2026-09-17 등록
    ('references/mlv_mid_shadow.csv', ('date',)),  # Rule MLV shadow — 2026-09-26 등록
    ('references/ibs_shadow.csv', ('date',)),  # Rule IBS shadow — 2026-10-21 등록
    ('references/credit_u_shadow.csv', ('date',)),  # Rule CRU shadow — 2026-10-22 등록
    ('references/foreign_avoid_shadow.csv', ('date',)),  # Rule FIA shadow — 2026-10-22 등록
    ('references/breadth_shadow.csv', ('date',)),  # Rule BRD shadow — 2026-10-27 등록
    ('backtest/kospi_close.csv', ('date',)),
]
found, fixed = [], []


def say(kind, msg):
    print(f'  [{kind}] {msg}')


def check_trackers(fix):
    for rel, keys in TRACKERS:
        p = os.path.join(LOOP, rel)
        if not os.path.exists(p):
            continue
        try:
            rows = list(csv.DictReader(open(p, encoding='utf-8')))
        except OSError:
            continue
        if not rows or keys[0] not in rows[0]:
            continue
        c = Counter(tuple(r.get(k, '') for k in keys) for r in rows)
        dup = sum(v - 1 for v in c.values() if v > 1)
        if not dup:
            continue
        found.append(f'{rel}: 중복 {dup}행')
        say('오염', f'{rel} — (날짜{"·코드" if len(keys) > 1 else ""}) 중복 {dup}행')
        if fix:
            n = safe_io.dedupe_csv(p, keys)
            fixed.append(f'{rel} 중복 {n}행 제거')
            say('복구', f'{rel} — {n}행 제거(스냅샷 보관)')


def ohlc_state():
    """(절단, 꼬리결손비율, 마지막날, 069500 종가) 를 돌려준다."""
    if not os.path.exists(OHLC):
        return True, 1.0, None, None
    days, flat, tot, last_close = set(), 0, 0, None
    rows = list(csv.DictReader(open(OHLC, encoding='utf-8')))
    for r in rows:
        if not r.get('date'):
            return True, 1.0, None, None       # 깨진 행 = 절단
        days.add(r['date'])
    if not days:
        return True, 1.0, None, None
    last = max(days)
    for r in rows:
        if r['date'] != last:
            continue
        try:
            h, l, c = float(r['high']), float(r['low']), float(r['close'])
        except (ValueError, KeyError):
            continue
        tot += 1
        if h <= l:
            flat += 1
        if r['code'] == '069500':
            last_close = c
    trunc = len(days) < 300 or len(rows) < 50000
    return trunc, (flat / tot if tot else 1.0), last, last_close


def check_ohlc(fix):
    trunc, flat_r, last, close = ohlc_state()
    problems = []
    if trunc:
        problems.append('절단')
    if flat_r > 0.5:
        problems.append(f'꼬리 결손({flat_r:.0%})')
    if last and close is not None:
        cp = os.path.join(LOOP, 'backtest', f'panel_close_{last[4:]}.csv')
        if os.path.exists(cp):
            for r in csv.DictReader(open(cp, encoding='utf-8')):
                if r['code'] == '069500' and r['date'] == last:
                    if abs(float(r['close']) - close) > 1:
                        problems.append('날짜 밀림')
                    break
    if not problems:
        return
    found.append(f'panel_ohlc_2y.csv: {" · ".join(problems)}')
    say('오염', f'panel_ohlc_2y.csv — {" · ".join(problems)}')
    if not fix:
        return
    for snap in reversed(safe_io.snapshots(OHLC)):
        import shutil
        shutil.copy2(snap, OHLC)
        t, f2, _, _ = ohlc_state()
        if not t and f2 <= 0.5:
            fixed.append(f'panel_ohlc_2y.csv ← {os.path.basename(snap)}')
            say('복구', f'스냅샷 롤백 {os.path.basename(snap)}')
            return
    say('수동', 'OHLC 스냅샷 중 정상본이 없다 → '
        'python3 backtest/rebuild_ohlc_panel.py 32 을 완료될 때까지 반복 실행할 것')


def check_freshness(fix):
    import ensure_data
    from datetime import datetime
    T = datetime.now(ensure_data.KST).strftime('%Y%m%d')
    base = ensure_data.newest_panel()
    if not base:
        return
    last = ensure_data.panel_last_date(base)
    have = set()
    kp = os.path.join(LOOP, 'backtest', 'kospi_close.csv')
    if os.path.exists(kp):
        have = {r['date'] for r in csv.DictReader(open(kp, encoding='utf-8'))}
    if last in have:
        return
    found.append(f'kospi_close.csv: {last} 결손')
    say('오염', f'kospi_close.csv — 패널 최종일 {last} 행 없음')
    if fix:
        r = ensure_data.ensure(T, 30.0)
        fixed.append('ensure_data 호출')
        say('복구', f'ensure_data 실행 · 완료={r["done"]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fix', action='store_true', help='실제로 복구한다(기본은 진단만)')
    a = ap.parse_args()
    print('=' * 66)
    print(f'데이터 진단{"·복구" if a.fix else " (진단만 — 고치려면 --fix)"}')
    print('=' * 66)
    check_trackers(a.fix)
    check_ohlc(a.fix)
    check_freshness(a.fix)
    print('-' * 66)
    if not found:
        print('  오염 없음 — 모든 검사 통과')
        return 0
    print(f'  발견 {len(found)}건 · 복구 {len(fixed)}건')
    if not a.fix:
        print('  → 복구하려면: python3 references/scripts/repair_data.py --fix')
        return 1
    print('  → 확인: python3 references/scripts/integrity_check.py')
    return 0 if len(fixed) == len(found) else 1


if __name__ == '__main__':
    sys.exit(main())
