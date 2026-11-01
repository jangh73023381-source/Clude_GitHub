# -*- coding: utf-8 -*-
"""견고성 검정 — 개별종목 유니버스 우위가 특정 종목 하나에 의존하는가?

(1) 종목 단위 잭나이프: 15종 중 1종씩 빼고 14종으로 재계산 (동일 구간 ETF와 비교)
(2) 연도별 분해
(3) 채널 위치(POS) 구간별 익일 수익률 — 지지·저항 가설의 원자료 확인
"""
import os
import sys
import statistics
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channel_engine import load, Channel, BENCH, LOOKBACKS, LB_LABEL
import bt_channel as BC

HERE = os.path.dirname(os.path.abspath(__file__))


def sec1():
    print('=' * 92)
    print('(1) 종목 단위 잭나이프 — 1종씩 제외하고 14종으로 재계산 (공통구간 496일)')
    print('=' * 92)
    sb, sm, sd, sc = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    eb, em, ed, ec = load(os.path.join(HERE, 'ohlc_sector15.csv'))
    common = sorted(set(sd) & set(ed))
    CE = Channel(eb, common, ec)
    etf = BC.st(BC.run(CE, ec, common, None, 125))

    CS = Channel(sb, common, sc)
    full = BC.st(BC.run(CS, sc, common, None, 125))
    print(f"전체 15종  : KODEX200초과 {full['bm']:+.4f}%  바스켓초과 {full['bask']:+.4f}%")
    print(f"ETF 15종   : KODEX200초과 {etf['bm']:+.4f}%  바스켓초과 {etf['bask']:+.4f}%")
    print(f"{'제외 종목':22s}{'KODEX초과%':>11s}{'바스켓초과%':>12s}{'vs ETF':>10s}{'판정':>10s}")
    print('-' * 92)
    worst = None
    for drop in sc:
        sub = [c for c in sc if c != drop]
        s = BC.st(BC.run(CS, sub, common, None, 125))
        gap = s['bm'] - etf['bm']
        ok = '우위 유지' if gap > 0 else '역전'
        if worst is None or s['bm'] < worst[1]:
            worst = (sm[drop][1], s['bm'])
        print(f"{sm[drop][0] + ' ' + sm[drop][1][:9]:22s}{s['bm']:>11.4f}"
              f"{s['bask']:>12.4f}{gap:>+10.4f}{ok:>10s}")
    print(f"\n최악 케이스: {worst[0]} 제외 시 {worst[1]:+.4f}% "
          f"(ETF {etf['bm']:+.4f}% 대비 {worst[1]-etf['bm']:+.4f}%p)")


def sec2():
    print()
    print('=' * 92)
    print('(2) 연도별 분해 — 개별종목 baseline (전체 1096일 패널)')
    print('=' * 92)
    bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    C = Channel(bars, dates, codes)
    byyear = defaultdict(list)
    for i in range(BC.START, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        picks = BC.select(C, codes, d, None)
        rets = {}
        ok = True
        for c in codes:
            a, b = C.close(c, d), C.close(c, dn)
            if not (a and b):
                ok = False
                break
            rets[c] = b / a - 1.0
        a, b = C.close(BENCH, d), C.close(BENCH, dn)
        if not ok or not (a and b):
            continue
        bm = b / a - 1.0
        port = sum(rets[c] for c in picks) / len(picks)
        byyear[d[:4]].append((port - 0.0010 - bm, port - 0.0010 - sum(rets.values()) / len(rets)))
    print(f"{'연도':8s}{'일수':>7s}{'KODEX초과%/일':>15s}{'바스켓초과%/일':>16s}")
    print('-' * 92)
    for y in sorted(byyear):
        xs = byyear[y]
        print(f"{y:8s}{len(xs):>7d}{statistics.mean(x[0] for x in xs)*100:>15.4f}"
              f"{statistics.mean(x[1] for x in xs)*100:>16.4f}")


def sec3():
    print()
    print('=' * 92)
    print('(3) 채널 위치별 익일 수익률 — 지지·저항 가설의 원자료 (종목·일 전수)')
    print('    pos = 0 은 N일 저점(지지선), 1 은 N일 고점(저항선)')
    print('=' * 92)
    bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    C = Channel(bars, dates, codes)
    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 0.95), (0.95, 1.01)]
    labels = ['0.0~0.2 저점권', '0.2~0.4', '0.4~0.6', '0.6~0.8', '0.8~0.95', '0.95~1.0 고점권']
    print(f"{'채널 위치':18s}" + ''.join(f'{LB_LABEL[N]:>14s}' for N in LOOKBACKS))
    print('-' * 92)
    tables = {N: defaultdict(list) for N in LOOKBACKS}
    for i in range(BC.START, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        for c in codes:
            a, b = C.close(c, d), C.close(c, dn)
            if not (a and b):
                continue
            r = b / a - 1.0
            for N in LOOKBACKS:
                pv = C.pos(c, d, N)
                if pv is None:
                    continue
                for bi, (lo, hi) in enumerate(bins):
                    if lo <= pv < hi:
                        tables[N][bi].append(r)
                        break
    for bi, lab in enumerate(labels):
        cells = []
        for N in LOOKBACKS:
            xs = tables[N][bi]
            cells.append(f'{statistics.mean(xs)*100:+.3f}%({len(xs)})' if len(xs) >= 30 else '  -  ')
        print(f'{lab:18s}' + ''.join(c.rjust(14) for c in cells))
    print('\n  괄호 = 표본수(종목·일). 저점권이 높으면 "지지선 매수" 가설,')
    print('  고점권이 높으면 "고점 돌파 추종" 가설이 지지된다.')


if __name__ == '__main__':
    sec1()
    sec2()
    sec3()
