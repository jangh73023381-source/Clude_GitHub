# -*- coding: utf-8 -*-
"""ETF 201종 일봉 OHLC 장기 수집 (ka10081 base_dt 페이지네이션, 조회 전용).

600행/콜 한계를 base_dt를 뒤로 밀며 최대 3청크(≈1,800거래일 ≈ 7년)까지 확장한다.
중기(보유 20일) 전략은 독립 관측이 적어 표본 확장이 결론 신뢰도를 좌우한다.

출력: backtest/panel_ohlc_long.csv
"""
import csv, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

OUT = os.path.join(HERE, 'panel_ohlc_long.csv')
UNIV = os.path.join(LOOP, 'etf_universe.csv')
CHUNKS = 3


def load_universe():
    out = []
    with open(UNIV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            out.append((r['티커'].strip(), r['종목명'].strip()))
    return out


def dec1(d):
    y, m, dd = int(d[:4]), int(d[4:6]), int(d[6:])
    dd -= 1
    if dd < 1:
        m -= 1; dd = 28
        if m < 1:
            m = 12; y -= 1
    return f'{y:04d}{m:02d}{dd:02d}'


def fetch(code):
    got = {}
    base = '00000000'
    for _ in range(CHUNKS):
        try:
            r = k.get_daily_chart(code, base)
        except Exception as e:
            print(f'  err {code} {base}: {e}', flush=True)
            break
        arr = r.get('stk_dt_pole_chart_qry') or []
        if not arr:
            break
        oldest = None; new = 0
        for x in arr:
            d = x.get('dt')
            if not d or d in got:
                continue
            try:
                got[d] = (abs(float(x['open_pric'])), abs(float(x['high_pric'])),
                          abs(float(x['low_pric'])), abs(float(x['cur_prc'])),
                          float(x.get('trde_qty') or 0))
            except Exception:
                continue
            new += 1
            if oldest is None or d < oldest:
                oldest = d
        if oldest is None or new == 0:
            break
        base = dec1(oldest)
        time.sleep(0.2)
    return got


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
    for i, (code, name) in enumerate(univ, 1):
        if code in done:
            continue
        g = fetch(code)
        for d in sorted(g):
            o, h, l, c, v = g[d]
            w.writerow([code, name, d, o, h, l, c, v])
        f.flush()
        print(f'[{i}/{len(univ)}] {code} {name} days={len(g)}', flush=True)
        time.sleep(0.1)
    f.close()
    print('done')


if __name__ == '__main__':
    main()
