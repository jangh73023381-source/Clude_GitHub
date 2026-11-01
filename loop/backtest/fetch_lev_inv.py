# -*- coding: utf-8 -*-
"""레버리지·인버스 ETF 일봉 수집 (조회 전용).

검토2용 — 이 종목들은 추천 유니버스에서 제외되므로 기존 패널(201종)에 없다.
시장 방향 신호(센티먼트) 검정에만 쓴다. 주문·매매 기능은 호출하지 않는다.
45초 셸 제한 대응: 부분 저장 + 재실행 시 이어받기(멱등).
"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

OUT = os.path.join(HERE, 'panel_lev_inv.csv')
TARGETS = [
    ('122630', 'KODEX 레버리지'),
    ('114800', 'KODEX 인버스'),
    ('252670', 'KODEX 200선물인버스2X'),
    ('233740', 'KODEX 코스닥150레버리지'),
    ('251340', 'KODEX 코스닥150선물인버스'),
    ('069500', 'KODEX 200'),
]
START = '20240101'


def load():
    rows = {}
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                rows[(r['code'], r['date'])] = r
    return rows


def save(rows):
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['code', 'name', 'date', 'open', 'high', 'low', 'close', 'volume'])
        for kk in sorted(rows):
            r = rows[kk]
            w.writerow([r['code'], r['name'], r['date'], r['open'], r['high'],
                        r['low'], r['close'], r['volume']])
    os.replace(tmp, OUT)


def fetch(code, name, rows, budget=30.0):
    t0 = time.time()
    base = '00000000'
    got = 0
    while time.time() - t0 < budget:
        try:
            res = k.get_daily_chart(code, base_dt=base)
        except Exception as e:
            print(f'  {code} 오류 {e}')
            return got
        arr = res.get('stk_dt_pole_chart_qry') or []
        if not arr:
            return got
        oldest = None
        for a in arr:
            d = a.get('dt')
            if not d:
                continue
            oldest = d if oldest is None or d < oldest else oldest
            if d < START:
                continue
            rows[(code, d)] = dict(
                code=code, name=name, date=d,
                open=abs(float(a.get('open_pric', 0))),
                high=abs(float(a.get('high_pric', 0))),
                low=abs(float(a.get('low_pric', 0))),
                close=abs(float(a.get('cur_prc', 0))),
                volume=abs(float(a.get('trde_qty', 0))))
            got += 1
        if oldest is None or oldest < START:
            return got
        base = oldest
    return got


def main():
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    rows = load()
    t0 = time.time()
    for code, name in TARGETS:
        have = [d for (c, d) in rows if c == code]
        if have and min(have) <= START:
            print(f'  {code} {name}: 이미 {len(have)}일 확보 — 건너뜀')
            continue
        left = budget - (time.time() - t0)
        if left <= 3:
            print('  예산 소진 — 같은 명령을 다시 실행하면 이어받습니다')
            break
        n = fetch(code, name, rows, left)
        print(f'  {code} {name}: +{n}행')
        save(rows)
    save(rows)
    codes = sorted({c for c, _ in rows})
    print(f'저장 {len(rows)}행 / {len(codes)}종목 -> {OUT}')
    for c in codes:
        ds = sorted(d for (cc, d) in rows if cc == c)
        print(f'  {c}: {len(ds)}일 {ds[0]}~{ds[-1]}')


if __name__ == '__main__':
    main()
