# -*- coding: utf-8 -*-
"""(1) 동일 구간 개별종목 vs ETF 유니버스 비교
   (2) 근접 후보 3분할 상세
   (3) 이평선 룰 vs 채널 룰 동일 유니버스 비교
   (4) 플라시보 (채널 게이트 반전)
"""
import os
import sys
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channel_engine import load, Channel, BENCH, LOOKBACKS, LB_LABEL
import bt_channel as BC

HERE = os.path.dirname(os.path.abspath(__file__))


def sub_dates(dates, start_ymd):
    return [d for d in dates if d >= start_ymd]


def basic(C, codes, dates, gate, start):
    r = BC.run(C, codes, dates, gate, start)
    s = BC.st(r)
    half = len(r['bm']) // 2
    return r, s, BC.st(r, 0, half), BC.st(r, half, None)


def sec1():
    print('=' * 96)
    print('(1) 동일 구간 개별종목 vs ETF 유니버스 — 어느 쪽이 선정 대상으로 우월한가')
    print('=' * 96)
    sb, sm, sd, sc = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    eb, em, ed, ec = load(os.path.join(HERE, 'ohlc_sector15.csv'))
    common = sorted(set(sd) & set(ed))
    print(f'공통 구간 {common[0]}~{common[-1]}, {len(common)}거래일')

    CS = Channel(sb, common, sc)
    CE = Channel(eb, common, ec)
    start = 125     # ETF 패널 워밍업과 동일
    for tag, C, codes in (('개별종목 15종', CS, sc), ('섹터 ETF 15종', CE, ec)):
        r, s, tr, te = basic(C, codes, common, None, start)
        print(f'  {tag:14s} baseline: KODEX200초과 {s["bm"]:+.4f}%/일  '
              f'바스켓초과 {s["bask"]:+.4f}%/일  승률 {s["win"]:.1f}%  '
              f'(train {tr["bm"]:+.4f} / test {te["bm"]:+.4f}, {s["n"]}일)')

    # 바스켓 자체 성과
    for tag, C, codes in (('개별종목 바스켓', CS, sc), ('섹터ETF 바스켓', CE, ec)):
        xs = []
        for i in range(start, len(common) - 1):
            d, dn = common[i], common[i + 1]
            rr = []
            for c in codes:
                a, b = C.close(c, d), C.close(c, dn)
                if a and b:
                    rr.append(b / a - 1.0)
            a, b = C.close(BENCH, d), C.close(BENCH, dn)
            if len(rr) == len(codes) and a and b:
                xs.append(sum(rr) / len(rr) - (b / a - 1.0))
        print(f'  {tag:14s} 등가중 보유만: KODEX200 대비 {statistics.mean(xs)*100:+.4f}%/일')


def sec2():
    print()
    print('=' * 96)
    print('(2) 근접 후보 3분할 상세 — 왜 가드를 통과하지 못했는가')
    print('=' * 96)
    bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    C = Channel(bars, dates, codes)
    base = BC.run(C, codes, dates, None)
    half = len(base['bm']) // 2
    b, btr, bte = BC.st(base), BC.st(base, 0, half), BC.st(base, half, None)
    print(f"{'후보':30s}{'full':>10s}{'train':>10s}{'test':>10s}{'t':>7s}{'p':>8s}{'실패지점':>12s}")
    print('-' * 96)
    print(f"{'baseline':30s}{b['bm']:>10.4f}{btr['bm']:>10.4f}{bte['bm']:>10.4f}"
          f"{'-':>7s}{'-':>8s}{'-':>12s}")
    cands = [
        ('POS-LO 12개월 (채널하단)', BC.mk_pos_lo(250)),
        ('SUP-HOLD 6개월 (지지방어)', BC.mk_sup_hold(120)),
        ('POS-HI 24개월 (채널상단)', BC.mk_pos_hi(500)),
        ('SUP-HOLD 3개월', BC.mk_sup_hold(60)),
        ('POS-LO 24개월', BC.mk_pos_lo(500)),
    ]
    for label, g in cands:
        r = BC.run(C, codes, dates, g)
        s, tr, te = BC.st(r), BC.st(r, 0, half), BC.st(r, half, None)
        m, t, p = BC.paired_t(r['bm'], base['bm'])
        fails = []
        if s['bm'] <= b['bm']:
            fails.append('full')
        if tr['bm'] <= btr['bm']:
            fails.append('train')
        if te['bm'] <= bte['bm']:
            fails.append('test')
        print(f"{label:30s}{s['bm']:>10.4f}{tr['bm']:>10.4f}{te['bm']:>10.4f}"
              f"{t:>7.2f}{p:>8.3f}{('/'.join(fails) or '통과'):>12s}")


def sec3():
    print()
    print('=' * 96)
    print('(3) 이평선 룰 vs 채널 룰 — 개별종목 유니버스에서 직접 비교')
    print('=' * 96)
    bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    C = Channel(bars, dates, codes)
    base = BC.run(C, codes, dates, None)
    half = len(base['bm']) // 2
    b = BC.st(base)

    def g_aligned(C, c, d):
        a, bb, e = C.MA(c, d, 20), C.MA(c, d, 60), None
        p = C.close(c, d)
        if None in (a, bb, p):
            return None
        return p > a > bb

    def g_ma20up(C, c, d):
        i = C.idx[d]
        if i < 5:
            return None
        x, y = C.MA(c, d, 20), C.MA(c, C.dates[i - 5], 20)
        if None in (x, y):
            return None
        return x > y

    rules = [
        ('MA  종가>MA20>MA60 (정배열)', g_aligned),
        ('MA  MA20 기울기>0', g_ma20up),
        ('CH  POS-LO 12개월', BC.mk_pos_lo(250)),
        ('CH  SUP-HOLD 6개월', BC.mk_sup_hold(120)),
        ('CH  POS-HI 24개월', BC.mk_pos_hi(500)),
        ('CH  RES-BREAK 6개월', BC.mk_res_break(120)),
    ]
    print(f"{'룰':32s}{'초과%':>9s}{'순증%p':>9s}{'발동일':>8s}{'t':>7s}{'p':>8s}")
    print('-' * 96)
    for label, g in rules:
        r = BC.run(C, codes, dates, g)
        s = BC.st(r)
        m, t, p = BC.paired_t(r['bm'], base['bm'])
        print(f"{label:32s}{s['bm']:>9.4f}{s['bm']-b['bm']:>9.4f}"
              f"{r['fired']:>8d}{t:>7.2f}{p:>8.3f}")


def sec4():
    print()
    print('=' * 96)
    print('(4) 플라시보 — 채널 게이트 반전 시 대칭적으로 나빠지는가')
    print('=' * 96)
    bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    C = Channel(bars, dates, codes)
    base = BC.run(C, codes, dates, None)
    b = BC.st(base)

    def inv(g):
        def f(C, c, d):
            v = g(C, c, d)
            return None if v is None else (not v)
        return f

    pairs = [
        ('POS-LO 12개월 (채널하단 선호)', BC.mk_pos_lo(250)),
        ('POS-HI 24개월 (채널상단 선호)', BC.mk_pos_hi(500)),
        ('SUP-HOLD 6개월 (지지방어 선호)', BC.mk_sup_hold(120)),
        ('RES-BLOCK 6개월 (머리위저항 배제)', BC.mk_res_block(120, 0.03)),
    ]
    print(f"{'룰':36s}{'정방향%':>10s}{'반전%':>10s}{'격차%p':>10s}{'해석':>14s}")
    print('-' * 96)
    for label, g in pairs:
        rf = BC.st(BC.run(C, codes, dates, g))
        ri = BC.st(BC.run(C, codes, dates, inv(g)))
        gap = rf['bm'] - ri['bm']
        v = '방향성 있음' if gap > 0.03 else ('역방향' if gap < -0.03 else '무의미')
        print(f"{label:36s}{rf['bm']:>10.4f}{ri['bm']:>10.4f}{gap:>10.4f}{v:>14s}")
    print(f"\n  baseline {b['bm']:+.4f}%")


if __name__ == '__main__':
    sec1()
    sec2()
    sec3()
    sec4()
