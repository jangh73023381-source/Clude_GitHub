#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_krx_2y_20260818.py — KRX 개별종목·ETF·업종지수를 **ETF 2년 패널과 같은 구간**으로 확장.

왜 필요한가
  2026-08-18 회차에서 KRX 파생 축(BRD·TVQ·LIS·EFF·SRV·SBR)이 전부 기각됐는데, 공통 한계가
  **표본 113~114일**이었다. 8/13 절차("후보는 반드시 더 긴 별도 패널에서 재검정")를 KRX 축에는
  적용할 수 없었던 이유가 바로 이것이다. KRX OPEN API 는 2024년치까지 정상 응답하므로
  (실측: 20240213 stock 953행 · etf 825행 · idx 38행) **604거래일로 늘려 이 한계를 없앤다.**

대상 구간은 `backtest/panel_ohlc_2y.csv` 의 거래일(20240221~20260814, 604일)이다.
멱등이며 이미 받은 날짜는 건너뛴다. 중간에 끊겨도 같은 명령으로 이어받는다.
조회 전용.
"""
import csv, os, sys, threading, queue
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import krx_api as K

PANEL2Y = os.path.join(HERE, 'panel_ohlc_2y.csv')
STK = os.path.join(HERE, 'krx_stock_panel.csv')
ETF = os.path.join(HERE, 'krx_etf_panel.csv')
IDX = os.path.join(HERE, 'krx_sector_idx.csv')

STK_COLS = ['date', 'code', 'name', 'market', 'open', 'high', 'low', 'close',
            'chg_pct', 'volume', 'value', 'mktcap', 'sector']
ETF_COLS = ['date', 'code', 'name', 'close', 'chg_pct', 'nav', 'value', 'volume',
            'mktcap', 'netasset', 'list_shrs', 'base_idx']
IDX_COLS = ['date', 'name', 'close', 'chg_pct', 'value', 'mktcap']


def f(x):
    return (x or '').replace(',', '').strip()


def target_dates():
    return sorted({r['date'] for r in csv.DictReader(open(PANEL2Y, encoding='utf-8'))})


def have(path):
    if not os.path.exists(path):
        return set()
    return {r['date'] for r in csv.DictReader(open(path, encoding='utf-8'))}


def fetch_stk(d):
    out = []
    for mk, path in (('KOSPI', 'sto/stk_bydd_trd'), ('KOSDAQ', 'sto/ksq_bydd_trd')):
        st, data = K.call(path, basDd=d)
        if st != 'ok':
            return d, st, []
        for r in list(data.values())[0]:
            out.append([d, r['ISU_CD'], r.get('ISU_NM', ''), mk, f(r['TDD_OPNPRC']),
                        f(r['TDD_HGPRC']), f(r['TDD_LWPRC']), f(r['TDD_CLSPRC']),
                        f(r['FLUC_RT']), f(r['ACC_TRDVOL']), f(r['ACC_TRDVAL']),
                        f(r['MKTCAP']), ''])
    return d, 'ok', out


def fetch_etf(d):
    st, data = K.call('etp/etf_bydd_trd', basDd=d)
    if st != 'ok':
        return d, st, []
    return d, 'ok', [[d, r['ISU_CD'], r['ISU_NM'], f(r['TDD_CLSPRC']), f(r['FLUC_RT']),
                      f(r['NAV']), f(r['ACC_TRDVAL']), f(r['ACC_TRDVOL']), f(r['MKTCAP']),
                      f(r['INVSTASST_NETASST_TOTAMT']), f(r['LIST_SHRS']), r['IDX_IND_NM']]
                     for r in list(data.values())[0]]


def fetch_idx(d):
    st, data = K.call('idx/krx_dd_trd', basDd=d)
    if st != 'ok':
        return d, st, []
    return d, 'ok', [[d, r['IDX_NM'].strip(), f(r['CLSPRC_IDX']), f(r['FLUC_RT']),
                      f(r['ACC_TRDVAL']), f(r['MKTCAP'])] for r in list(data.values())[0]]


def collect(kind, path, cols, fn, todo, workers=8):
    """★ 하루치를 받는 즉시 파일에 append 한다.

    처음에는 전부 메모리에 모았다가 끝에 한 번 썼는데, 200일 요청이 셸 제한(560초)에 걸려
    강제 종료되자 **받은 것이 통째로 날아갔다**(9분 20초 손실). 장시간 수집기는 반드시
    증분 기록이어야 한다 — 중단돼도 이어받을 수 있다."""
    if not todo:
        print(f'[{kind}] 완료 — 받을 날짜 없음')
        return 0
    q = queue.Queue()
    for d in todo:
        q.put(d)
    errs, lock = [], threading.Lock()
    new = not os.path.exists(path)
    fh = open(path, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh)
    if new:
        w.writerow(cols)
    done = [0]

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
                    w.writerows(out)
                    done[0] += 1
                    if done[0] % 20 == 0:
                        fh.flush()
                        print(f'  [{kind}] {done[0]}/{len(todo)}일')
                else:
                    errs.append((d, st))

    ts = [threading.Thread(target=work, daemon=True) for _ in range(workers)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print(f'[{kind}] {done[0]}일 기록 · 실패 {len(errs)}일 {errs[:3]}')
    return len(errs)


def main():
    ds = target_dates()
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    only = sys.argv[2] if len(sys.argv) > 2 else 'all'
    print(f'대상 {len(ds)}일 {ds[0]}~{ds[-1]} · 이번 실행 최대 {lim}일/종류')
    jobs = [('STK', STK, STK_COLS, fetch_stk), ('ETF', ETF, ETF_COLS, fetch_etf),
            ('IDX', IDX, IDX_COLS, fetch_idx)]
    for kind, path, cols, fn in jobs:
        if only != 'all' and only != kind:
            continue
        seen = have(path)          # ★ 반드시 루프 밖에서 1회. 리스트 컴프리헨션 안에 두면
        todo = [d for d in ds if d not in seen]   # 날짜마다 60MB CSV 를 다시 읽어 18분이 된다(실측).
        print(f'[{kind}] 미수집 {len(todo)}일')
        collect(kind, path, cols, fn, todo[:lim])
    return 0


if __name__ == '__main__':
    sys.exit(main())
