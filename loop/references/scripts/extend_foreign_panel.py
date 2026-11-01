#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""외국인 매매동향 패널 연장기 (조회 전용) — 45초 셸 제한 안에서 재개 가능.

키움 ka10008(주식외국인종목별매매동향)은 호출당 최근 약 50거래일을 돌려주므로,
201종을 한 번씩만 다시 받으면 패널이 최신까지 채워진다. 다만 201종 × 0.4초 ≈ 80초라
한 번에 끝나지 않아 부분 결과를 _foreign_ext_part.csv 에 누적하고 이미 받은 코드는
건너뛴다(멱등·재개 가능).

사용:
  python3 references/scripts/extend_foreign_panel.py --budget 35     # 반복 실행
  python3 references/scripts/extend_foreign_panel.py --finalize      # 기존 패널과 병합
주의: 조회 전용. 주문·매매 기능은 호출하지 않는다.
"""
import argparse
import csv
import os
import sys
import time

LOOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

REF = os.path.join(LOOP, 'references')
PART = os.path.join(REF, 'scripts', '_foreign_ext_part.csv')
PANEL = os.path.join(REF, 'foreign_trend_panel.csv')
FIELDS = ['code', 'name', 'date', 'chg_qty', 'wght', 'poss_stkcnt']


def universe():
    out = []
    with open(os.path.join(LOOP, 'etf_universe.csv'), encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            out.append((r['티커'].strip(), r['종목명'].strip()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--budget', type=float, default=35.0)
    ap.add_argument('--finalize', action='store_true')
    a = ap.parse_args()

    codes = universe()
    done = set()
    if os.path.exists(PART):
        with open(PART, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                done.add(r['code'])
    todo = [c for c in codes if c[0] not in done]
    print(f'코드 {len(codes)}종 · 완료 {len(done)} · 남은 {len(todo)}')

    if a.finalize:
        if todo:
            print(f'[중단] 아직 {len(todo)}종 남음 — finalize 불가')
            return 1
        old = []
        if os.path.exists(PANEL):
            with open(PANEL, encoding='utf-8') as f:
                old = list(csv.DictReader(f))
        with open(PART, encoding='utf-8') as f:
            new = list(csv.DictReader(f))
        merged = {}
        for r in old + new:          # 신규가 뒤 → 같은 (code,date)는 신규로 덮인다
            merged[(r['code'], r['date'])] = r
        rows = sorted(merged.values(), key=lambda r: (r['code'], r['date']))
        tmp = PANEL + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k2: r.get(k2, '') for k2 in FIELDS})
        if os.path.exists(PANEL):
            import safe_io
            safe_io.safe_replace(tmp, PANEL)  # 2026-11-01: 생 open(..,'w') 직접 덮어쓰기 대신 §6 safe_replace
        else:
            os.rename(tmp, PANEL)
        last = max(r['date'] for r in rows)
        print(f'[완료] {PANEL} — {len(rows)}행 · {len({r["code"] for r in rows})}종 · 최종일 {last}')
        return 0

    t0 = time.time()
    n_ok = 0
    write_header = not os.path.exists(PART)
    with open(PART, 'a', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(FIELDS)
        for code, name in todo:
            if time.time() - t0 > a.budget:
                break
            try:
                r = k.get_foreign_trend(code)
                for x in (r.get('stk_frgnr') or []):
                    w.writerow([code, name, x.get('dt', ''), x.get('chg_qty', '0'),
                                x.get('wght', ''), x.get('poss_stkcnt', '')])
                n_ok += 1
            except Exception as e:
                print(f'  [실패] {code} {name}: {str(e)[:60]}')
            time.sleep(0.05)
    print(f'이번 실행 {n_ok}종 · {time.time()-t0:.1f}초 · 남은 {len(todo)-n_ok}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
