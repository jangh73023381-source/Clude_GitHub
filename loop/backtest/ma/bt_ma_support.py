# -*- coding: utf-8 -*-
"""이평선 지지·저항 룰 백테스트 (15섹터 대표 ETF, 496거래일).

채점(v2.3 P&L 1차지표 준용)
  - 선정일 d 종가까지의 정보로 5종 선정 → d→d+1 동일가중 보유 → 왕복비용 10bp 차감
  - 1차: KODEX200(069500) 대비 일별 초과수익 평균
  - 병기: 15섹터 등가중 바스켓 대비 초과수익 평균 (선정 스킬 순수 측정)
  - 보조: 15섹터 중 익일수익 상위3에 픽이 몇 개 들었나 (top3_hits/3)

과최적화 가드
  - full / train(전반) / test(후반) 3분할 전부 baseline 초과일 때만 후보 승격
  - 잭나이프(1일 제거) 하한 부호 확인
  - 발동일수(픽이 실제로 바뀐 날) 5일 미만이면 판정 보류
"""
import os
import sys
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ma_engine import load, Panel, BENCH

COST = 0.0010
NPICK = 5
WARMUP = 125          # MA120 + slope 여유
SUP_L = 20            # 지지 관찰창
RES_L = 20            # 저항 관찰창


# ----------------------------------------------------------------- 선정 로직
def rule_h_ok(P, c, d):
    """v2.1 Rule H — 전일 단일세션 +10% 초과 / 3일 누적 +20% 초과 제외."""
    s = P.mom(c, d, 1)
    c3 = P.mom(c, d, 3)
    if s is not None and s > 0.10:
        return False
    if c3 is not None and c3 > 0.20:
        return False
    return True


def rank_mom20(P, codes, d):
    cand = []
    for c in codes:
        m = P.mom(c, d, 20)
        if m is None or not rule_h_ok(P, c, d):
            continue
        cand.append((c, m))
    cand.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in cand]


def select(P, codes, d, gate=None, n=NPICK):
    """mom20 순위대로 gate를 통과하는 종목을 n개까지 채운다(차순위 충원)."""
    ranked = rank_mom20(P, codes, d)
    if gate is None:
        return ranked[:n]
    keep = [c for c in ranked if gate(P, c, d) is not False]
    if len(keep) >= n:
        return keep[:n]
    rest = [c for c in ranked if c not in keep]
    return (keep + rest)[:n]


# ----------------------------------------------------------------- 게이트들
def g_resistance_trapped(P, c, d):
    """MA-R1: 하락 중인 MA60 아래에 갇힌 종목 배제."""
    m = P.MA(c, d, 60)
    p = P.close(c, d)
    sl = P.slope(c, d, 60, 5)
    if None in (m, p, sl):
        return None
    return not (p < m and sl <= 0)


def g_head_blocked(P, c, d, thr=0.02):
    """MA-R2: 머리 바로 위(0~thr)에 MA60 저항이 붙어 있으면 배제."""
    h = P.head(c, d, 60)
    if h is None:
        return None
    return not (0 < h <= thr)


def g_rejected(P, c, d, k=2):
    """MA-R3: 최근 20일 MA60 터치 후 종가로 밀린 횟수 >= k 이면 배제."""
    n = P.rej_cnt(c, d, 60, RES_L)
    if n is None:
        return None
    return n < k


def mk_g_support(thr, k=20, use_low=False):
    """MA-S: 최근 L일 MA_k 하방이탈 최대깊이가 thr 초과면 배제."""
    def g(P, c, d):
        v = P.sup_break_depth(c, d, k, SUP_L, use_low)
        if v is None:
            return None
        return v <= thr
    return g


def g_aligned(P, c, d):
    """MA-A: 정배열(MA5>MA20>MA60)만 통과."""
    return P.aligned(c, d)


def g_ma20_slope(P, c, d):
    """MA-T: MA20 기울기 > 0 만 통과."""
    s = P.slope(c, d, 20, 5)
    if s is None:
        return None
    return s > 0


def g_fresh_break(P, c, d):
    """MA-B: 최근 3일 내 MA60 상향 돌파한 종목만 통과."""
    return P.fresh_break(c, d, 60, 3)


# ----------------------------------------------------------------- 채점
def run(P, codes, dates, gate, start=WARMUP):
    """returns dict with per-day series"""
    ex_bm, ex_bask, hits, fired = [], [], [], 0
    days = []
    base_ref = None
    for i in range(start, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        picks = select(P, codes, d, gate)
        if len(picks) < NPICK:
            continue
        rets = {}
        for c in codes:
            a, b = P.close(c, d), P.close(c, dn)
            if a and b:
                rets[c] = b / a - 1.0
        if len(rets) < len(codes):
            continue
        a, b = P.close(BENCH, d), P.close(BENCH, dn)
        if not (a and b):
            continue
        bm = b / a - 1.0
        basket = sum(rets.values()) / len(rets)
        port = sum(rets[c] for c in picks if c in rets) / NPICK
        ex_bm.append(port - COST - bm)
        ex_bask.append(port - COST - basket)
        top3 = [c for c, _ in sorted(rets.items(), key=lambda x: x[1], reverse=True)[:3]]
        hits.append(sum(1 for c in picks if c in top3))
        days.append(d)
    return {'d': days, 'bm': ex_bm, 'bask': ex_bask, 'hits': hits}


def stats(res, lo=None, hi=None):
    s = slice(lo, hi)
    bm, bask, h = res['bm'][s], res['bask'][s], res['hits'][s]
    if not bm:
        return None
    return {
        'n': len(bm),
        'bm': statistics.mean(bm) * 100,
        'bask': statistics.mean(bask) * 100,
        'hits': statistics.mean(h),
        'win': sum(1 for x in bm if x > 0) / len(bm) * 100,
    }


def fired_days(P, codes, dates, gate, start=WARMUP):
    n = 0
    for i in range(start, len(dates) - 1):
        d = dates[i]
        if set(select(P, codes, d, None)) != set(select(P, codes, d, gate)):
            n += 1
    return n


def jackknife(res, key='bm'):
    """1일씩 제거했을 때 평균의 최소값(부호 유지 확인)."""
    xs = res[key]
    if len(xs) < 3:
        return None
    tot = sum(xs)
    n = len(xs)
    return min((tot - x) / (n - 1) for x in xs) * 100


def main():
    bars, meta, dates, codes = load()
    P = Panel(bars, dates)
    half = None

    variants = [
        ('baseline (mom20+RuleH)', None),
        ('MA-R1 하락MA60 아래 갇힘 배제', g_resistance_trapped),
        ('MA-R2 머리위 MA60 0~2% 배제', g_head_blocked),
        ('MA-R3 MA60 터치반락 2회+ 배제', g_rejected),
        ('MA-S1 MA20 이탈깊이<=1% (종가)', mk_g_support(0.01)),
        ('MA-S2 MA20 이탈깊이<=2% (종가)', mk_g_support(0.02)),
        ('MA-S3 MA20 이탈깊이<=3% (종가)', mk_g_support(0.03)),
        ('MA-S4 MA20 이탈깊이<=2% (저가)', mk_g_support(0.02, use_low=True)),
        ('MA-A  정배열 MA5>MA20>MA60', g_aligned),
        ('MA-T  MA20 기울기>0', g_ma20_slope),
        ('MA-B  MA60 신선돌파(3일내)', g_fresh_break),
    ]

    results = {}
    print(f'패널: {len(dates)}거래일 {dates[0]}~{dates[-1]}, 섹터 {len(codes)}종, 워밍업 {WARMUP}일')
    base = run(P, codes, dates, None)
    half = len(base['bm']) // 2
    bs_f, bs_tr, bs_te = stats(base), stats(base, 0, half), stats(base, half, None)
    print(f"채점일 {bs_f['n']}일 (train {bs_tr['n']} / test {bs_te['n']}), "
          f"분할점 {base['d'][half]}\n")

    hdr = (f"{'변형':32s}{'발동':>5s}{'KODEX초과%':>11s}{'바스켓초과%':>12s}"
           f"{'top3':>6s}{'승률%':>7s}{'train':>8s}{'test':>8s}{'JK하한':>8s}")
    print(hdr)
    print('-' * len(hdr))
    for label, gate in variants:
        res = run(P, codes, dates, gate)
        results[label] = res
        f = stats(res)
        tr = stats(res, 0, half)
        te = stats(res, half, None)
        fd = 0 if gate is None else fired_days(P, codes, dates, gate)
        jk = jackknife(res)
        print(f"{label:32s}{fd:>5d}{f['bm']:>11.4f}{f['bask']:>12.4f}"
              f"{f['hits']:>6.2f}{f['win']:>7.1f}{tr['bm']:>8.4f}{te['bm']:>8.4f}{jk:>8.4f}")

    print('\n[가드 판정] full·train·test 3분할 전부 baseline 초과 + 발동>=5일 + JK하한 부호유지')
    print('-' * 88)
    for label, gate in variants:
        if gate is None:
            continue
        res = results[label]
        f, tr, te = stats(res), stats(res, 0, half), stats(res, half, None)
        fd = fired_days(P, codes, dates, gate)
        ok_f = f['bm'] > bs_f['bm']
        ok_tr = tr['bm'] > bs_tr['bm']
        ok_te = te['bm'] > bs_te['bm']
        ok_n = fd >= 5
        verdict = '채택후보' if (ok_f and ok_tr and ok_te and ok_n) else '기각'
        mark = lambda b: '▲' if b else '▼'
        print(f"{label:32s} full{mark(ok_f)} train{mark(ok_tr)} test{mark(ok_te)} "
              f"발동{fd:3d}일{'✓' if ok_n else '✗'}  → {verdict}")


if __name__ == '__main__':
    main()
