# -*- coding: utf-8 -*-
"""ETF 유니버스 201종의 일봉 OHLC(수정주가) 2년치 수집 — 조회 전용.

출력: backtest/panel_ohlc_2y.csv (code,name,date,open,high,low,close,volume)
키움 ka10081은 1회 호출로 600거래일을 반환하므로 페이지네이션 없이 코드당 1콜.
"""
import csv, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

OUT = os.path.join(HERE, 'panel_ohlc_2y.csv')
UNIV = os.path.join(LOOP, 'etf_universe.csv')


def load_universe():
    rows = []
    with open(UNIV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append((r['티커'].strip(), r['종목명'].strip()))
    return rows


def fetch(code, retries=3):
    for a in range(retries):
        try:
            res = k.get_daily_chart(code)
            arr = res.get('stk_dt_pole_chart_qry') or []
            out = []
            for x in arr:
                try:
                    out.append((
                        x['dt'],
                        abs(float(x['open_pric'])), abs(float(x['high_pric'])),
                        abs(float(x['low_pric'])), abs(float(x['cur_prc'])),
                        float(x.get('trde_qty') or 0),
                    ))
                except Exception:
                    continue
            return out
        except Exception as e:
            if a == retries - 1:
                print(f'  FAIL {code}: {e}', flush=True)
                return []
            time.sleep(1.5 * (a + 1))
    return []


def main():
    univ = load_universe()
    done = set()
    mode = 'w'
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                done.add(r['code'])
        mode = 'a'
    f = open(OUT, mode, newline='', encoding='utf-8')
    w = csv.writer(f)
    if mode == 'w':
        w.writerow(['code', 'name', 'date', 'open', 'high', 'low', 'close', 'volume'])
    n_ok = 0
    for i, (code, name) in enumerate(univ, 1):
        if code in done:
            continue
        rows = fetch(code)
        for dt, o, h, l, c, v in rows:
            w.writerow([code, name, dt, o, h, l, c, v])
        if rows:
            n_ok += 1
        f.flush()
        print(f'[{i}/{len(univ)}] {code} {name} rows={len(rows)}', flush=True)
        time.sleep(0.25)
    f.close()
    print(f'done ok={n_ok}')


if __name__ == '__main__':
    main()
