#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETF NAV·괴리율 수집 (ka40003, 조회 전용) — Rule NV 가설 스크리닝용.

- 유니버스: panel_ohlc_2y.csv 에서 universe_filters 통과 종목 (+ KODEX200 제외 없음, 신호만).
- 종목당 --pages 페이지(30행/페이지) 수집, 출력 backtest/etf_nav_disp.csv 에 append.
- 멱등: 이미 수집된 (code,date) 는 건너뛰고, 이미 --pages 만큼 있는 종목은 호출 생략.
  중간에 끊겨도 같은 명령 재실행으로 이어받는다.
- 토큰·키는 출력하지 않는다. 주문·매매 기능 없음.
"""
import argparse, csv, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, LOOP)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
import kiwoom_api as k
import universe_filters as uf
import pandas as pd

OUT = os.path.join(HERE, 'etf_nav_disp.csv')
FIELDS = ['code', 'date', 'close', 'nav', 'disp']   # disp = navetfdispty_rt (%)


def call(code, cont='N', nk='', tok=None):
    req = urllib.request.Request(
        'https://api.kiwoom.com/api/dostk/etf',
        data=json.dumps({'stk_cd': code}).encode(),
        headers={'content-type': 'application/json;charset=UTF-8',
                 'authorization': f'Bearer {tok}', 'api-id': 'ka40003',
                 'cont-yn': cont, 'next-key': nk}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as r:
        h = {kk.lower(): vv for kk, vv in r.getheaders()}
        b = json.loads(r.read())
    if str(b.get('return_code', 0)) not in ('0', '0.0'):
        raise RuntimeError(b.get('return_msg'))
    return h, b


def num(s):
    if s in (None, ''):
        return None
    return float(str(s).replace('+', '').replace('-', '')) if False else float(s.replace('+', ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', type=int, default=3)
    ap.add_argument('--sleep', type=float, default=0.25)
    ap.add_argument('--budget', type=float, default=480.0)
    a = ap.parse_args()

    df = pd.read_csv(os.path.join(HERE, 'panel_ohlc_2y.csv'), dtype={'code': str})
    names = df.groupby('code')['name'].last()
    codes = sorted(c for c, n in names.items() if not (uf.is_deriv(n) or uf.is_cash(n)))

    have = {}
    if os.path.exists(OUT):
        old = pd.read_csv(OUT, dtype={'code': str, 'date': str})
        have = old.groupby('code')['date'].count().to_dict()
        seen = set(zip(old['code'], old['date']))
    else:
        seen = set()
        with open(OUT, 'w', newline='') as f:
            csv.writer(f).writerow(FIELDS)

    tok = k.get_access_token()
    t0 = time.time()
    done = skip = 0
    fout = open(OUT, 'a', newline='')
    w = csv.writer(fout)
    for code in codes:
        if have.get(code, 0) >= a.pages * 28:      # 이미 충분 — 생략(멱등)
            skip += 1
            continue
        if time.time() - t0 > a.budget:
            print(f'[예산 소진] {done}종 수집 후 중단 — 같은 명령으로 재개 가능')
            break
        cont, nk = 'N', ''
        try:
            for pg in range(a.pages):
                h, b = call(code, cont, nk, tok)
                for r in b.get('etfdaly_trnsn', []):
                    key = (code, r['cntr_dt'])
                    if key in seen:
                        continue
                    seen.add(key)
                    # cur_prc/nav 는 부호 접두가 등락 표시라 절댓값, disp 는 실제 부호
                    w.writerow([code, r['cntr_dt'],
                                abs(float(r['cur_prc'].replace('+', ''))),
                                abs(float(r['nav'].replace('+', ''))),
                                float(r['navetfdispty_rt'].replace('+', ''))])
                if h.get('cont-yn') != 'Y':
                    break
                cont, nk = 'Y', h.get('next-key', '')
                time.sleep(a.sleep)
            done += 1
            time.sleep(a.sleep)
        except Exception as e:                     # noqa: BLE001
            print(f'  {code} 실패(건너뜀): {e}', file=sys.stderr)
    fout.close()
    total = sum(1 for _ in open(OUT)) - 1
    print(f'완료: 신규 {done}종 · 기수집 생략 {skip}종 · 누적 {total}행 → {OUT}')


if __name__ == '__main__':
    main()
