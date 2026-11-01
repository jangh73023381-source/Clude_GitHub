# -*- coding: utf-8 -*-
"""채널 위치를 '필터'가 아니라 '선정 기준'으로 쓰는 백테스트.

bt_robust.py (3)에서 채널 위치별 익일 수익률이 U자형(저점권·고점권 우수, 중간 열위)으로
나타났다. 이는 mom20 위에 얹는 필터가 아니라 선정 스코어 자체로 써야 잡히는 구조다.

선정 방식
  MOM        : mom20 상위 5종                      (현행 baseline)
  POS-HI(N)  : 채널 위치 상위 5종
  POS-LO(N)  : 채널 위치 하위 5종
  POS-U(N)   : |pos - 0.5| 상위 5종  (양 끝단 = 지지선+저항선 동시 활용)
  POS-BAND(N): pos 가 0.80~0.95 구간인 종목 우선, 부족분은 mom20 차순위
  BLEND(N)   : mom20 순위와 pos 순위의 평균 랭크 상위 5종

전부 Rule H 과열필터 적용, D 종가 선정 → D→D+1 보유 → 왕복 10bp → KODEX200 대비 초과.
"""
import os
import sys
import math
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channel_engine import load, Channel, BENCH, LOOKBACKS, LB_LABEL
import bt_channel as BC

HERE = os.path.dirname(os.path.abspath(__file__))
COST = 0.0010
NPICK = 5
START = BC.START


def pool(C, codes, d):
    out = []
    for c in codes:
        m = C.mom(c, d, 20)
        if m is None or not BC.rule_h_ok(C, c, d):
            continue
        out.append((c, m))
    return out


def sel_mom(C, codes, d, N=None):
    p = pool(C, codes, d)
    p.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in p[:NPICK]]


def mk_pos(N, mode):
    def f(C, codes, d):
        p = pool(C, codes, d)
        arr = []
        for c, m in p:
            v = C.pos(c, d, N)
            if v is None:
                continue
            arr.append((c, v, m))
        if len(arr) < NPICK:
            return sel_mom(C, codes, d)
        if mode == 'hi':
            arr.sort(key=lambda x: x[1], reverse=True)
        elif mode == 'lo':
            arr.sort(key=lambda x: x[1])
        elif mode == 'u':
            arr.sort(key=lambda x: abs(x[1] - 0.5), reverse=True)
        return [c for c, _, _ in arr[:NPICK]]
    return f


def mk_band(N, lo=0.80, hi=0.95):
    def f(C, codes, d):
        p = pool(C, codes, d)
        p.sort(key=lambda x: x[1], reverse=True)
        inband, rest = [], []
        for c, m in p:
            v = C.pos(c, d, N)
            (inband if (v is not None and lo <= v <= hi) else rest).append(c)
        return (inband + rest)[:NPICK]
    return f


def mk_blend(N):
    def f(C, codes, d):
        p = pool(C, codes, d)
        arr = [(c, m, C.pos(c, d, N)) for c, m in p]
        arr = [x for x in arr if x[2] is not None]
        if len(arr) < NPICK:
            return sel_mom(C, codes, d)
        rm = {c: i for i, (c, _, _) in enumerate(sorted(arr, key=lambda x: x[1], reverse=True))}
        rp = {c: i for i, (c, _, _) in enumerate(sorted(arr, key=lambda x: x[2], reverse=True))}
        order = sorted(rm, key=lambda c: rm[c] + rp[c])
        return order[:NPICK]
    return f


def run(C, codes, dates, selfn, start=START):
    bm_x, bk_x = [], []
    for i in range(start, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        picks = selfn(C, codes, d)
        if len(picks) < NPICK:
            continue
        rets, ok = {}, True
        for c in codes:
            a, b = C.close(c, d), C.close(c, dn)
            if not (a and b):
                ok = False
                break
            rets[c] = b / a - 1.0
        a, b = C.close(BENCH, d), C.close(BENCH, dn)
        if not ok or not (a and b):
            continue
        bmr = b / a - 1.0
        basket = sum(rets.values()) / len(rets)
        port = sum(rets[c] for c in picks) / NPICK
        bm_x.append(port - COST - bmr)
        bk_x.append(port - COST - basket)
    return {'bm': bm_x, 'bask': bk_x}


def stt(r, lo=None, hi=None):
    xs = r['bm'][slice(lo, hi)]
    ys = r['bask'][slice(lo, hi)]
    if not xs:
        return None
    return {'n': len(xs), 'bm': statistics.mean(xs) * 100,
            'bask': statistics.mean(ys) * 100,
            'win': sum(1 for x in xs if x > 0) / len(xs) * 100}


def main():
    bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    C = Channel(bars, dates, codes)
    base = run(C, codes, dates, sel_mom)
    half = len(base['bm']) // 2
    b, btr, bte = stt(base), stt(base, 0, half), stt(base, half, None)

    print('=' * 104)
    print(f"패널 {len(dates)}일 {dates[0]}~{dates[-1]} | 채점 {b['n']}일 "
          f"(train {btr['n']} / test {bte['n']}) | 워밍업 {START}일")
    print(f"baseline MOM(mom20+RuleH): {b['bm']:+.4f}%/일 (train {btr['bm']:+.4f} / test {bte['bm']:+.4f}), "
          f"바스켓초과 {b['bask']:+.4f}%, 승률 {b['win']:.1f}%")
    print('=' * 104)

    fams = [
        ('POS-HI   채널위치 상위5', lambda N: mk_pos(N, 'hi')),
        ('POS-LO   채널위치 하위5', lambda N: mk_pos(N, 'lo')),
        ('POS-U    |pos-0.5| 상위5 (양끝단)', lambda N: mk_pos(N, 'u')),
        ('POS-BAND pos 0.80~0.95 우선', lambda N: mk_band(N)),
        ('BLEND    mom20+pos 평균랭크', lambda N: mk_blend(N)),
    ]

    print('\n[표 1] 룩백 스윕 — KODEX200 대비 일평균 초과수익 % (괄호 = baseline 대비 순증%p)')
    hdr = f"{'선정방식':34s}" + ''.join(f'{LB_LABEL[N]:>18s}' for N in LOOKBACKS)
    print(hdr)
    print('-' * len(hdr))
    store = {}
    for label, mk in fams:
        cells = []
        for N in LOOKBACKS:
            r = run(C, codes, dates, mk(N))
            store[(label, N)] = r
            s = stt(r)
            cells.append(f"{s['bm']:>10.4f}({s['bm']-b['bm']:+.3f})")
        print(f'{label:34s}' + ''.join(c.rjust(18) for c in cells))

    print('\n[표 2] 3분할 가드 — full·train·test 전부 baseline 초과')
    print(f"{'선정방식 / 룩백':40s}{'full':>9s}{'train':>9s}{'test':>9s}"
          f"{'바스켓':>9s}{'승률%':>8s}{'t':>7s}{'p':>8s}{'판정':>10s}")
    print('-' * 104)
    passers = []
    for label, mk in fams:
        for N in LOOKBACKS:
            r = store[(label, N)]
            s, tr, te = stt(r), stt(r, 0, half), stt(r, half, None)
            m, t, p = BC.paired_t(r['bm'], base['bm'])
            ok = s['bm'] > b['bm'] and tr['bm'] > btr['bm'] and te['bm'] > bte['bm']
            if ok or s['bm'] > b['bm'] + 0.02:
                tag = '통과' if ok else '부분'
                if ok:
                    passers.append((label, N, s, t, p))
                print(f"{label.split()[0] + ' / ' + LB_LABEL[N]:40s}{s['bm']:>9.4f}"
                      f"{tr['bm']:>9.4f}{te['bm']:>9.4f}{s['bask']:>9.4f}"
                      f"{s['win']:>8.1f}{t:>7.2f}{p:>8.3f}{tag:>10s}")
    if not passers:
        print('  (3분할 전부 통과한 조합 없음)')

    print(f"\n총 시험 {len(fams)*len(LOOKBACKS)}조합 → Bonferroni 임계 p < "
          f"{0.05/(len(fams)*len(LOOKBACKS)):.4f}")


if __name__ == '__main__':
    main()
