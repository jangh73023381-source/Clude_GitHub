# -*- coding: utf-8 -*-
"""패널 201종의 시가(open) 시계열 수집 — 재개 가능(45초 셸 제한 대응).

미국→한국 섹터 전이 검정에서 '시가 매수'가 가능한지 재려면 시가가 필요하다.
`get_daily_chart` 는 한 번 호출에 전 기간을 돌려주므로 코드당 1회면 된다.
조회 전용 — 주문·매매 기능은 호출하지 않는다.
"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

OUT = os.path.join(HERE, 'panel_open.csv')
PANEL = os.path.join(HERE, 'panel_close_0731.csv')


def main(budget=32.0):
    codes = sorted({r['code'] for r in csv.DictReader(open(PANEL, encoding='utf-8'))})
    done = set()
    if os.path.exists(OUT):
        done = {r['code'] for r in csv.DictReader(open(OUT, encoding='utf-8'))}
    todo = [c for c in codes if c not in done]
    print(f'코드 {len(codes)}종 · 완료 {len(done)} · 남은 {len(todo)}')

    t0, rows, n = time.time(), [], 0
    for c in todo:
        if time.time() - t0 > budget:
            break
        try:
            resp = None
            for att in range(4):
                try:
                    time.sleep(0.25)
                    resp = k.get_daily_chart(c)
                    break
                except Exception as e:                        # noqa: BLE001
                    if '429' in str(e) and att < 3:
                        time.sleep(1.0 + att)
                        continue
                    raise
            for it in (resp or {}).get('stk_dt_pole_chart_qry') or []:
                try:
                    o = abs(float(str(it['open_pric']).replace('+', '').replace('-', '')))
                except (KeyError, ValueError):
                    continue
                if o > 0:
                    rows.append({'code': c, 'date': str(it['dt']), 'open': o})
            n += 1
        except Exception as e:                                # noqa: BLE001
            print(f'  [실패] {c}: {e}')
    if rows:
        new = not os.path.exists(OUT)
        with open(OUT, 'a', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['code', 'date', 'open'])
            if new:
                w.writeheader()
            w.writerows(rows)
    left = len(todo) - n
    print(f'이번 실행 {n}종 · {time.time() - t0:.1f}초 · 남은 {left}')
    return 0 if left == 0 else 3


if __name__ == '__main__':
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 32.0))
