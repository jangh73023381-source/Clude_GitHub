# -*- coding: utf-8 -*-
"""가격채널 지지·저항 룰 백테스트 + 최적 룩백 구간 스윕 (섹터 대표 개별종목 15종).

모든 변형은 동일한 채점 구간(워밍업 525일 고정)에서 평가해 룩백 N 간 비교가 성립하게 한다.
채점은 v2.3 P&L 1차지표 준용: D 종가 선정 → D→D+1 동일가중 → 왕복 10bp → KODEX200 대비 초과.
"""
import os
import sys
import math
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channel_engine import load, Channel, BENCH, LOOKBACKS, LB_LABEL

HERE = os.path.dirname(os.path.abspath(__file__))
COST = 0.0010
NPICK = 5
START = 525          # max(LOOKBACK)=500 + 여유 25 — 모든 변형 공통


# ------------------------------------------------------------------ 선정
def rule_h_ok(C, c, d):
    s, c3 = C.mom(c, d, 1), C.mom(c, d, 3)
    if s is not None and s > 0.10:
        return False
    if c3 is not None and c3 > 0.20:
        return False
    return True


def ranked(C, codes, d):
    cand = []
    for c in codes:
        m = C.mom(c, d, 20)
        if m is None or not rule_h_ok(C, c, d):
            continue
        cand.append((c, m))
    cand.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in cand]


def select(C, codes, d, gate):
    r = ranked(C, codes, d)
    if gate is None:
        return r[:NPICK]
    keep = [c for c in r if gate(C, c, d) is not False]
    if len(keep) >= NPICK:
        return keep[:NPICK]
    return (keep + [c for c in r if c not in keep])[:NPICK]


# ------------------------------------------------------------------ 게이트
def mk_sup_near(N, thr):
    def g(C, c, d):
        v = C.sup(c, d, N)
        return None if v is None else v <= thr
    return g


def mk_sup_hold(N):
    def g(C, c, d):
        v = C.hold_cnt(c, d, N, 20)
        return None if v is None else v >= 1
    return g


def mk_res_block(N, thr):
    def g(C, c, d):
        v = C.res(c, d, N)
        return None if v is None else not (0 < v <= thr)
    return g


def mk_res_break(N):
    def g(C, c, d):
        return C.is_break(c, d, N)
    return g


def mk_pos_hi(N, thr=0.75):
    def g(C, c, d):
        v = C.pos(c, d, N)
        return None if v is None else v >= thr
    return g


def mk_pos_lo(N, thr=0.25):
    def g(C, c, d):
        v = C.pos(c, d, N)
        return None if v is None else v <= thr
    return g


# ------------------------------------------------------------------ 채점
def run(C, codes, dates, gate, start=START):
    ex_bm, ex_bask, fired = [], [], 0
    for i in range(start, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        picks = select(C, codes, d, gate)
        if len(picks) < NPICK:
            continue
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
        basket = sum(rets.values()) / len(rets)
        port = sum(rets[c] for c in picks) / NPICK
        ex_bm.append(port - COST - bm)
        ex_bask.append(port - COST - basket)
        if gate is not None and set(picks) != set(ranked(C, codes, d)[:NPICK]):
            fired += 1
    return {'bm': ex_bm, 'bask': ex_bask, 'fired': fired}


def st(res, lo=None, hi=None):
    xs = res['bm'][slice(lo, hi)]
    ys = res['bask'][slice(lo, hi)]
    if not xs:
        return None
    return {'n': len(xs), 'bm': statistics.mean(xs) * 100,
            'bask': statistics.mean(ys) * 100,
            'win': sum(1 for x in xs if x > 0) / len(xs) * 100}


def paired_t(a, b):
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    if n < 3:
        return 0.0, float('nan'), float('nan')
    m, sd = statistics.mean(d), statistics.stdev(d)
    if sd == 0:
        return 0.0, float('nan'), float('nan')
    t = m / (sd / math.sqrt(n))
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return m * 100, t, p


def main():
    bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
    C = Channel(bars, dates, codes)
    base = run(C, codes, dates, None)
    b_all, b_tr, b_te = st(base), st(base, 0, len(base['bm']) // 2), st(base, len(base['bm']) // 2, None)
    half = len(base['bm']) // 2

    print('=' * 100)
    print(f"패널 {len(dates)}거래일 {dates[0]}~{dates[-1]} | 종목 15종 | 워밍업 {START}일 고정")
    print(f"채점 {b_all['n']}일 (train {b_tr['n']} / test {b_te['n']})")
    print(f"baseline(mom20+RuleH): KODEX200초과 {b_all['bm']:+.4f}%/일, "
          f"바스켓초과 {b_all['bask']:+.4f}%/일, 승률 {b_all['win']:.1f}%")
    print('=' * 100)

    families = [
        ('SUP-NEAR  지지선(N일저점) +10% 이내만', lambda N: mk_sup_near(N, 0.10)),
        ('SUP-HOLD  지지선 터치 후 방어 1회+', lambda N: mk_sup_hold(N)),
        ('RES-BLOCK 저항선까지 0~3% 배제', lambda N: mk_res_block(N, 0.03)),
        ('RES-BREAK N일 신고가 돌파만', lambda N: mk_res_break(N)),
        ('POS-HI    채널위치 >= 0.75', lambda N: mk_pos_hi(N)),
        ('POS-LO    채널위치 <= 0.25', lambda N: mk_pos_lo(N)),
    ]

    print('\n[표 1] 룩백 구간 스윕 — KODEX200 대비 일평균 초과수익 % (괄호 = baseline 대비 순증%p)')
    hdr = f"{'룰':34s}" + ''.join(f'{LB_LABEL[N]:>18s}' for N in LOOKBACKS)
    print(hdr)
    print('-' * len(hdr))
    store = {}
    for label, mk in families:
        cells = []
        for N in LOOKBACKS:
            r = run(C, codes, dates, mk(N))
            store[(label, N)] = r
            s = st(r)
            cells.append(f"{s['bm']:>10.4f}({s['bm']-b_all['bm']:+.3f})")
        print(f'{label:34s}' + ''.join(c.rjust(18) for c in cells))
    print(f"{'baseline':34s}" + f"{b_all['bm']:>10.4f}".rjust(18))

    print('\n[표 2] 발동일수 (369일 중 게이트가 픽을 바꾼 날)')
    hdr2 = f"{'룰':34s}" + ''.join(f'{LB_LABEL[N]:>10s}' for N in LOOKBACKS)
    print(hdr2)
    print('-' * len(hdr2))
    for label, mk in families:
        print(f'{label:34s}' + ''.join(f"{store[(label,N)]['fired']:>10d}" for N in LOOKBACKS))

    print('\n[표 3] 가드 통과 후보 — full·train·test 3분할 전부 baseline 초과 + 발동>=20일')
    print(f"{'룰 / 룩백':44s}{'초과%':>9s}{'순증%p':>9s}{'train':>9s}{'test':>9s}"
          f"{'발동':>6s}{'t':>7s}{'p':>8s}")
    print('-' * 101)
    winners = []
    for label, mk in families:
        for N in LOOKBACKS:
            r = store[(label, N)]
            s, tr, te = st(r), st(r, 0, half), st(r, half, None)
            if not (s and tr and te):
                continue
            ok = (s['bm'] > b_all['bm'] and tr['bm'] > b_tr['bm']
                  and te['bm'] > b_te['bm'] and r['fired'] >= 20)
            if ok:
                m, t, p = paired_t(r['bm'], base['bm'])
                winners.append((label, N, s, tr, te, r['fired'], t, p))
                print(f"{label.split()[0] + ' / ' + LB_LABEL[N]:44s}{s['bm']:>9.4f}"
                      f"{s['bm']-b_all['bm']:>9.4f}{tr['bm']:>9.4f}{te['bm']:>9.4f}"
                      f"{r['fired']:>6d}{t:>7.2f}{p:>8.3f}")
    if not winners:
        print('  (없음 — 3분할 가드를 통과한 조합이 하나도 없다)')

    print(f'\n총 시험 조합 {len(families)*len(LOOKBACKS)}개 → 다중검정 보정 임계 p < '
          f'{0.05/(len(families)*len(LOOKBACKS)):.4f} (Bonferroni)')


if __name__ == '__main__':
    main()
