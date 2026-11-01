#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_krx_etf_idx_20260818.py — KRX ETF 일별매매 · KRX 시리즈 업종지수 수집(멱등).

2026-08-18 2차 세션(iteration 6~10)에서 신설. 승인된 서비스 2종만 쓴다.
  etp/etf_bydd_trd  → backtest/krx_etf_panel.csv   (거래대금·상장좌수·순자산 = 설정/환매)
  idx/krx_dd_trd    → backtest/krx_sector_idx.csv  (KRX 17 업종지수 — 코스피·코스닥 통합)

조회 전용. 키는 krx_api 가 읽고 출력하지 않는다.
"""
import csv, os, sys, threading, queue
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import krx_api as K

ETF_OUT = os.path.join(HERE, 'krx_etf_panel.csv')
IDX_OUT = os.path.join(HERE, 'krx_sector_idx.csv')
ETF_COLS = ['date', 'code', 'name', 'close', 'chg_pct', 'nav', 'value', 'volume',
            'mktcap', 'netasset', 'list_shrs', 'base_idx']
IDX_COLS = ['date', 'name', 'close', 'chg_pct', 'value', 'mktcap']


def dates_from_panel():
    ds = set()
    for r in csv.DictReader(open(os.path.join(HERE, 'krx_stock_panel.csv'), encoding='utf-8')):
        ds.add(r['date'])
    return sorted(ds)


def have(path, col='date'):
    if not os.path.exists(path):
        return set()
    return {r[col] for r in csv.DictReader(open(path, encoding='utf-8'))}


def f(x):
    return (x or '').replace(',', '').strip()


def fetch_etf(d):
    st, data = K.call('etp/etf_bydd_trd', basDd=d)
    if st != 'ok':
        return d, st, []
    out = []
    for r in list(data.values())[0]:
        out.append([d, r['ISU_CD'], r['ISU_NM'], f(r['TDD_CLSPRC']), f(r['FLUC_RT']),
                    f(r['NAV']), f(r['ACC_TRDVAL']), f(r['ACC_TRDVOL']), f(r['MKTCAP']),
                    f(r['INVSTASST_NETASST_TOTAMT']), f(r['LIST_SHRS']), r['IDX_IND_NM']])
    return d, 'ok', out


def fetch_idx(d):
    st, data = K.call('idx/krx_dd_trd', basDd=d)
    if st != 'ok':
        return d, st, []
    out = []
    for r in list(data.values())[0]:
        out.append([d, r['IDX_NM'].strip(), f(r['CLSPRC_IDX']), f(r['FLUC_RT']),
                    f(r['ACC_TRDVAL']), f(r['MKTCAP'])])
    return d, 'ok', out


def collect(kind, path, cols, fn, todo, workers=4):
    q = queue.Queue()
    for d in todo:
        q.put(d)
    rows, errs, lock = [], [], threading.Lock()

    def work():
        while True:
            try:
                d = q.get_nowait()
            except queue.Empty:
                return
            try:
                d, st, out = fn(d)
            except Exception as e:
                st, out = type(e).__name__, []
            with lock:
                if st == 'ok' and out:
                    rows.extend(out)
                else:
                    errs.append((d, st))
            q.task_done()

    ts = [threading.Thread(target=work, daemon=True) for _ in range(workers)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    new = not os.path.exists(path)
    with open(path, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(cols)
        w.writerows(sorted(rows))
    print(f'[{kind}] +{len(rows)}행 / {len(todo)}일 요청 · 실패 {len(errs)}일 {errs[:5]}')


def main():
    ds = dates_from_panel()
    todo_e = [d for d in ds if d not in have(ETF_OUT)]
    todo_i = [d for d in ds if d not in have(IDX_OUT)]
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    print(f'대상 {len(ds)}일 {ds[0]}~{ds[-1]} · ETF 미수집 {len(todo_e)} · IDX 미수집 {len(todo_i)}')
    if todo_e:
        collect('ETF', ETF_OUT, ETF_COLS, fetch_etf, todo_e[:lim])
    if todo_i:
        collect('IDX', IDX_OUT, IDX_COLS, fetch_idx, todo_i[:lim])
    return 0


if __name__ == '__main__':
    sys.exit(main())
