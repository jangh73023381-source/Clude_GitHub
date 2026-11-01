#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_ohlc_long.py — 7년 패널(panel_ohlc_long.csv)을 **단일 스냅샷으로** 재구축한다.

왜 재구축인가 (2026-08-22 실측)
  `panel_ohlc_long.csv`(2026-07-29 생성)와 `panel_ohlc_2y.csv`(2026-08-20 전량 재구축)의
  겹치는 구간을 전량 대조한 결과 **OHLC 377,944값 중 150,840개(40%)가 불일치**했다.
  두 패널 모두 키움 수정주가 기준이지만 **조정 스냅샷 시점이 다르다** — 그 사이 분배금이
  반영돼 2년 패널의 과거값이 0.2~0.4% 더 낮다(배당형 ETF 에서 특히 크다).
  → **두 패널을 이어붙이면 2026-07-29/07-30 경계에 가짜 수익률이 생긴다. 이어붙이지 말 것.**
  참고로 KRX 공식 ETF 패널과도 30~43% 불일치한다. 이는 결함이 아니라 **조정 vs 원가**의
  차이이며, 백테스트에는 조정 기준이 맞다(분배금을 반영해야 실제 보유 수익이다).

왜 야후로 대체하지 않는가
  야후 adjclose 로 조정 OHLC 를 복원해 봤으나 **381560 에서 음수 가격(-268,609원)** 이 나왔다
  (배당 레코드 오류). 기존 패널은 |일간변동|>50% 사건이 0건으로 깨끗하다. **소스를 바꾸지 않는다.**

재개 가능 — 45초 셸 제한 안에서 반복 실행하면 이어서 받는다. 조회 전용.
ka10081 은 1회 호출당 최근 약 600봉을 준다. 7년(약 1,800봉)을 채우려면 가장 오래된 날짜를
`base_dt` 로 넘겨 **역방향 페이징**해야 한다 — `rebuild_ohlc_panel.py`(2년)와 다른 점은 이것뿐이다.

사용:
  python3 backtest/rebuild_ohlc_long.py 32     # 완료될 때까지 반복 실행
"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, LOOP)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
import kiwoom_api as k  # noqa: E402
from ensure_data import settled  # noqa: E402  (미확정 당일 봉 배제)

TARGET = os.path.join(HERE, 'panel_ohlc_long.csv')
PART = os.path.join(HERE, '_ohlc_long_rebuild_part.csv')
FIELDS = ['code', 'name', 'date', 'open', 'high', 'low', 'close', 'volume']
FROM = '20190401'          # 기존 7년 패널의 시작일 — 유니버스·기간을 바꾸지 않는다
PAGES = 4                  # 코드당 최대 페이징 횟수(600봉 × 4 ≈ 2,400봉)


def universe():
    """기존 패널의 코드·종목명을 그대로 쓴다(유니버스를 바꾸지 않는다)."""
    seen = {}
    for r in csv.DictReader(open(TARGET, encoding='utf-8')):
        seen.setdefault(r['code'], r['name'])
    return sorted(seen.items())


def parse(resp):
    out = {}
    for x in (resp or {}).get('stk_dt_pole_chart_qry') or []:
        try:
            dt = x['dt']
            out[dt] = (
                abs(float(str(x['open_pric']).replace('+', '').replace('-', ''))),
                abs(float(str(x['high_pric']).replace('+', '').replace('-', ''))),
                abs(float(str(x['low_pric']).replace('+', '').replace('-', ''))),
                abs(float(str(x['cur_prc']).replace('+', '').replace('-', ''))),
                float(x.get('trde_qty') or 0))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def fetch(code):
    """역방향 페이징으로 FROM 까지 긁는다."""
    bars, base = {}, '00000000'
    for _ in range(PAGES):
        resp = None
        for att in range(4):
            try:
                time.sleep(0.25)
                resp = k.get_daily_chart(code, base)
                break
            except Exception as e:                       # noqa: BLE001
                if '429' in str(e) and att < 3:
                    time.sleep(1.0 + att)
                    continue
                raise
        page = parse(resp)
        new = {d: v for d, v in page.items() if d not in bars}
        if not new:
            break
        bars.update(new)
        oldest = min(bars)
        if oldest <= FROM:
            break
        base = oldest                                     # 그 날짜 이전으로 한 페이지 더
    return {d: v for d, v in bars.items() if d >= FROM}


def main(budget=32.0):
    uni = universe()
    done = set()
    if os.path.exists(PART):
        done = {r['code'] for r in csv.DictReader(open(PART, encoding='utf-8'))}
    todo = [(c, n) for c, n in uni if c not in done]
    print(f'코드 {len(uni)}종 · 완료 {len(done)} · 남은 {len(todo)}')

    t0, rows, cnt = time.time(), [], 0
    for c, name in todo:
        if time.time() - t0 > budget:
            break
        try:
            b = fetch(c)
        except Exception as e:                            # noqa: BLE001
            print(f'  {c} {name[:20]}: 실패 {type(e).__name__} — 다음 실행에서 재시도')
            continue
        # 미확정 봉 유입 금지 (CLAUDE.md §6) — 키움은 장중·장전에도 당일 일봉을 돌려준다.
        # 2026-08-28 07:24 KST 실측: 개장 전인데 49종 전부 20260828 봉이 실려 왔다.
        for d, (o, h, lo, cl, v) in sorted(b.items()):
            if not settled(d):
                continue
            rows.append({'code': c, 'name': name, 'date': d, 'open': o, 'high': h,
                         'low': lo, 'close': cl, 'volume': v})
        cnt += 1
        print(f'  {c} {name[:24]:24s} {len(b):4d}봉 ({min(b) if b else "-"}~{max(b) if b else "-"})')

    if rows:
        exist = os.path.exists(PART)
        with open(PART, 'a', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if not exist:
                w.writeheader()
            w.writerows(rows)
    remaining = len(todo) - cnt
    print(f'이번 실행 {cnt}종 · 남은 {remaining}종')
    if remaining > 0:
        print('아직 남았다 — 같은 명령을 다시 실행할 것.')
        return 1

    # ── 완주: 교체 전 검증 후 원자적 치환 ───────────────────────────────
    part = list(csv.DictReader(open(PART, encoding='utf-8')))
    codes = {r['code'] for r in part}
    dates = sorted({r['date'] for r in part})
    print(f'\n[검증] {len(part):,}행 · 코드 {len(codes)} · 일자 {len(dates)} ({dates[0]}~{dates[-1]})')
    if len(codes) < len(uni):
        print(f'  [중단] 코드 부족 {len(codes)} < {len(uni)} — 교체하지 않는다.'); return 2
    # 분할 미반영 등으로 생기는 |일간변동|>50% 사건은 0이어야 한다(기존 패널 실측 0건).
    by = {}
    for r in part:
        by.setdefault(r['code'], []).append((r['date'], float(r['close'])))
    jumps = 0
    for c, v in by.items():
        v.sort()
        for i in range(1, len(v)):
            if v[i - 1][1] and abs(v[i][1] / v[i - 1][1] - 1) > 0.5:
                jumps += 1
    print(f'  |일간변동|>50% 사건 {jumps}건 (기대 0)')
    if jumps:
        print('  [중단] 분할·권리락 미반영 의심 — 교체하지 않는다.'); return 2

    sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
    import safe_io
    safe_io.snapshot(TARGET, tag='pre_rebuild_long')
    tmp = TARGET + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(part, key=lambda x: (x['code'], x['date'])):
            w.writerow({kk: r[kk] for kk in FIELDS})
    safe_io.safe_replace(tmp, TARGET)
    # 2026-09-02: 이 마운트는 unlink 를 거부한다(PermissionError: Operation not permitted).
    # 교체가 이미 끝난 뒤 remove 에서 예외가 나면 성공 실행이 오류로 보이고, 무엇보다
    # PART 가 남아 다음 실행의 재개 로직이 "전 종목 완료"로 오판한다.
    # → 지우지 못하면 헤더만 남겨 '빈 PART'로 리셋한다(다음 실행이 처음부터 받는다).
    try:
        os.remove(PART)
    except OSError:
        with open(PART, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        print('  [주의] PART 삭제 불가(마운트 권한) — 헤더만 남겨 리셋했다.')
    print(f'[교체 완료] {TARGET}')
    print('다음: python3 backtest/bt_base_long_20260819.py · bt_lv_full_20260819.py 로 재확인')
    return 0


if __name__ == '__main__':
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 32.0))
