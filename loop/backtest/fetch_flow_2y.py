# -*- coding: utf-8 -*-
"""기관·외국인 순매매 시계열 2년치 수집 (ka10045, 조회 전용).

ka10045는 1회 호출당 최대 100행(end_dt 기준 과거 방향)을 반환하므로
end_dt를 뒤로 밀며 청크 반복한다. 재실행 시 이미 받은 코드는 건너뛴다.

출력: backtest/flow_2y.csv
  code,name,date,close,volume,orgn_net,for_net,limit_exh
"""
import csv, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

OUT = os.path.join(HERE, 'flow_2y.csv')
UNIV = os.path.join(LOOP, 'etf_universe.csv')
START = '20240206'
FIRST_END = '20260728'


def load_universe():
    rows = []
    with open(UNIV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append((r['티커'].strip(), r['종목명'].strip()))
    return rows


def num(s):
    try:
        return float(str(s).replace('+', '').replace(',', ''))
    except Exception:
        return None


def fetch_code(code, max_chunks=8):
    got = {}
    end = FIRST_END
    for _ in range(max_chunks):
        try:
            r = k.get_institution_trend(code, START, end)
        except Exception as e:
            print(f'  err {code} {end}: {e}', flush=True)
            break
        arr = r.get('stk_orgn_trde_trnsn') or []
        if not arr:
            break
        oldest = None
        new = 0
        for x in arr:
            d = x.get('dt')
            if not d or d in got:
                continue
            got[d] = (
                abs(num(x.get('close_pric')) or 0),
                num(x.get('trde_qty')) or 0,
                num(x.get('orgn_daly_nettrde_qty')) or 0,
                num(x.get('for_daly_nettrde_qty')) or 0,
                num(x.get('limit_exh_rt')),
            )
            new += 1
            if oldest is None or d < oldest:
                oldest = d
        if oldest is None or oldest <= START or new == 0:
            break
        # 다음 청크는 현재 최고(最古)일 직전까지
        y, m, dd = int(oldest[:4]), int(oldest[4:6]), int(oldest[6:])
        dd -= 1
        if dd < 1:
            m -= 1; dd = 28
            if m < 1:
                m = 12; y -= 1
        end = f'{y:04d}{m:02d}{dd:02d}'
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
        w.writerow(['code', 'name', 'date', 'close', 'volume',
                    'orgn_net', 'for_net', 'limit_exh'])
    for i, (code, name) in enumerate(univ, 1):
        if code in done:
            continue
        g = fetch_code(code)
        for d in sorted(g):
            c, v, o, fo, le = g[d]
            w.writerow([code, name, d, c, v, o, fo, le if le is not None else ''])
        f.flush()
        print(f'[{i}/{len(univ)}] {code} {name} days={len(g)}', flush=True)
        time.sleep(0.15)
    f.close()
    print('done')


if __name__ == '__main__':
    main()
