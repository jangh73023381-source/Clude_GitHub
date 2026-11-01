#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_krx_ind_idx.py — 코스피·코스닥 **업종지수** 수집(멱등).
SRV 축의 분류체계 강건성 검정용(KRX 시리즈 17종 vs 코스피/코스닥 업종 40여종)."""
import csv, os, sys, threading, queue
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import krx_api as K
OUT = os.path.join(HERE, 'krx_ind_idx.csv')
COLS = ['date', 'market', 'name', 'chg_pct']


def dates():
    return sorted({r['date'] for r in csv.DictReader(
        open(os.path.join(HERE, 'krx_stock_panel.csv'), encoding='utf-8'))})


def have():
    if not os.path.exists(OUT):
        return set()
    return {r['date'] for r in csv.DictReader(open(OUT, encoding='utf-8'))}


def one(d):
    out = []
    for mk, path in (('KOSPI', 'idx/kospi_dd_trd'), ('KOSDAQ', 'idx/kosdaq_dd_trd')):
        st, data = K.call(path, basDd=d)
        if st != 'ok' or not data:
            return d, st, []
        for r in list(data.values())[0]:
            v = (r['FLUC_RT'] or '').strip()
            if v:
                out.append([d, mk, r['IDX_NM'].strip(), v])
    return d, 'ok', out


def main():
    todo = [d for d in dates() if d not in have()]
    print(f'미수집 {len(todo)}일')
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
                d, st, o = one(d)
            except Exception as e:
                st, o = type(e).__name__, []
            with lock:
                (rows.extend(o) if st == 'ok' and o else errs.append((d, st)))

    ts = [threading.Thread(target=work, daemon=True) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COLS)
        w.writerows(sorted(rows))
    print(f'+{len(rows)}행 · 실패 {len(errs)} {errs[:5]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
