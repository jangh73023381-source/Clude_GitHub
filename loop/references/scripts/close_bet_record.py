#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rule CB OOS 트래커 기록기 (조회 전용) — close_bet_band_tracker.csv 멱등 누적.

규칙(loop/CLAUDE.md 2026-07-26·3차):
  date  = 종가 매수일(= 그날 브리핑 [6-2] 중기 후보를 종가 단일가로 산다)
  수익률 = 그 다음 거래일 종가 기준 (date → date+1)
  method = 그날의 '선정 레이어' 이름 (mom20+RuleH 등)

사용:
  python3 references/scripts/close_bet_record.py 20260723 20260724
  python3 references/scripts/close_bet_record.py --all      # picks_mid_etf.json 전체 스캔
"""
import argparse
import csv
import json
import os
import sys

H = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(H, '..'))
ROOT = os.path.abspath(os.path.join(REF, '..'))
FABLE = os.path.join(os.path.dirname(ROOT), 'fable')
sys.path.insert(0, FABLE)

TRACKER = os.path.join(REF, 'close_bet_band_tracker.csv')
MIDPICKS = os.path.join(ROOT, 'backtest', 'picks_mid_etf.json')
KOSPI = os.path.join(ROOT, 'backtest', 'kospi_close.csv')
FIELDS = ['date', 'method', 'candidates', 'stage', 'band',
          'n_buy', 'port_ret', 'kospi_ret', 'excess', 'note']


def newest_panel():
    d = os.path.join(ROOT, 'backtest')
    c = sorted(f for f in os.listdir(d)
               if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(d, c[-1])


def load_panel():
    data, names = {}, {}
    for row in csv.DictReader(open(newest_panel(), encoding='utf-8')):
        data.setdefault(row['code'], {})[row['date']] = float(row['close'])
        names.setdefault(row['code'], row.get('name', ''))
    return data, names


def mid_shadow_fallback():
    """picks_mid_etf.json 결손분을 mid_momentum_shadow.csv 로 보완한다.

    재현 조건(2026-09-11 실측): 아침 루틴이 하루 통째로 걸러지면(9/10 미실행)
    picks_mid_etf.json 은 morning_run.py 만 쓰므로 그날 D 키가 영구 결손되고,
    --all 이 "중기 후보 없음"으로 건너뛴 뒤 다음 실행에서도 영원히 회수되지 않는다.
    mid_momentum_shadow.csv 는 --record <날짜> 로 사후 백필이 가능하므로
    이를 2차 소스로 쓴다(같은 mom150 산출물이라 값이 동일하다).
    """
    path = os.path.join(REF, 'mid_momentum_shadow.csv')
    out = {}
    if not os.path.exists(path):
        return out
    for r in csv.DictReader(open(path, encoding='utf-8')):
        ymd = (r.get('date') or '').strip()
        if len(ymd) != 8:
            continue
        codes = [c for c in (r.get('codes') or '').split(';') if c]
        if not codes:
            continue
        iso = f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}'
        out[iso] = {'src': 'mid_momentum_shadow.csv(fallback)',
                    'codes': codes,
                    'names': [n for n in (r.get('names') or '').split(';') if n]}
    return out


def load_kospi():
    return {r['date']: float(r['close'])
            for r in csv.DictReader(open(KOSPI, encoding='utf-8'))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dates', nargs='*')
    ap.add_argument('--all', action='store_true')
    # 2026-07-31 [6-2] 선정축이 mom150(Rule MM)으로 교체됨 → 표본 분절을 위해 기본값 변경.
    # 종전 표본(method=mom20+RuleH, 21일)은 그대로 두고 이 시점부터 새로 센다.
    ap.add_argument('--method', default='mom150')
    a = ap.parse_args()

    import close_bet_filter as cb  # noqa: E402

    mid = json.load(open(MIDPICKS, encoding='utf-8'))
    # 결손분만 2차 소스로 채운다(기존 키는 덮어쓰지 않는다) — 위 mid_shadow_fallback 주석 참조.
    for k, v in mid_shadow_fallback().items():
        mid.setdefault(k, v)
    panel = load_panel()
    closes, _ = panel
    kospi = load_kospi()
    sessions = sorted(kospi)

    existing = []
    if os.path.exists(TRACKER):
        existing = list(csv.DictReader(open(TRACKER, encoding='utf-8')))
    have = {r['date'] for r in existing}

    want = a.dates or (sorted(mid) if a.all else [])
    if not want:
        print('대상 날짜 없음 — 날짜 인자나 --all 을 지정하세요')
        return 1

    added = []
    for ds in want:
        iso = ds if '-' in ds else f'{ds[:4]}-{ds[4:6]}-{ds[6:]}'
        ymd = iso.replace('-', '')
        if iso in have:
            print(f'{iso} 이미 기록됨 — 멱등 처리(생략)')
            continue
        entry = mid.get(iso)
        if not entry:
            print(f'{iso} 중기 후보 없음(picks_mid_etf.json 미등록) — 건너뜀')
            continue
        if ymd not in sessions or sessions.index(ymd) + 1 >= len(sessions):
            print(f'{iso} 익일 종가 미확보 — 채점 보류')
            continue
        nxt = sessions[sessions.index(ymd) + 1]

        codes = entry['codes']
        res = cb.apply_close_bet_band(codes, ymd, panel)
        buy = [x['code'] for x in res['buy']]

        def ret(c):
            s = closes.get(c, {})
            if ymd in s and nxt in s:
                return s[nxt] / s[ymd] - 1.0
            return None

        rr = [r for r in (ret(c) for c in buy) if r is not None]
        port = sum(rr) / len(rr) * 100 if rr else 0.0
        kr = (kospi[nxt] / kospi[ymd] - 1.0) * 100
        lo, hi = res['band']
        row = {
            'date': iso, 'method': a.method, 'candidates': len(codes),
            'stage': res['stage'], 'band': f'{lo * 100:+.1f}%~{hi * 100:+.1f}%',
            'n_buy': len(buy), 'port_ret': f'{port:.2f}', 'kospi_ret': f'{kr:.2f}',
            'excess': f'{port - kr:.2f}',
            'note': f'OOS 실기록(익일 {nxt} 종가 기준)' + ('' if buy else ' · 관망'),
        }
        existing.append(row)
        added.append(row)
        print(f"{iso} stage{res['stage']} 매수{len(buy)}종 "
              f"포트 {port:+.2f}% · 코스피 {kr:+.2f}% · 초과 {port - kr:+.2f}%p")

    if added:
        existing.sort(key=lambda r: r['date'])
        with open(TRACKER, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(existing)
        print(f'\n{len(added)}행 기록 → {TRACKER}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
