# -*- coding: utf-8 -*-
"""통과 변형 유의성 검정 · 조합 · 플라시보(부호 반전) 확인.

1) 대응표본 t검정 : 일별 (변형초과 - baseline초과) 의 평균이 0과 유의하게 다른가
2) 조합 게이트     : 통과 변형들을 AND 로 묶었을 때
3) 플라시보        : 게이트를 반전(저항에 갇힌 종목만 선호)했을 때 반대 부호가 나오는가
                     -> 반대 부호가 나와야 '메커니즘이 실재'한다는 증거
"""
import os
import sys
import math
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ma_engine import load, Panel
import bt_ma_support as B


def paired_t(a, b):
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    m = statistics.mean(d)
    sd = statistics.stdev(d)
    if sd == 0:
        return m, float('nan'), float('nan')
    t = m / (sd / math.sqrt(n))
    # 양측 p 근사 (정규근사, n=369 이면 충분)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return m * 100, t, p


def invert(gate):
    def g(P, c, d):
        v = gate(P, c, d)
        return None if v is None else (not v)
    return g


def combine(*gates):
    def g(P, c, d):
        vals = [gt(P, c, d) for gt in gates]
        if all(v is None for v in vals):
            return None
        return all(v is not False for v in vals)
    return g


def main():
    bars, meta, dates, codes = load()
    P = Panel(bars, dates)
    base = B.run(P, codes, dates, None)
    half = len(base['bm']) // 2

    passers = [
        ('MA-R2 머리위 MA60 0~2% 배제', B.g_head_blocked),
        ('MA-R3 MA60 터치반락 2회+ 배제', B.g_rejected),
        ('MA-S1 MA20 이탈깊이<=1%', B.mk_g_support(0.01)),
        ('MA-A  정배열', B.g_aligned),
        ('MA-T  MA20 기울기>0', B.g_ma20_slope),
    ]

    print('=' * 92)
    print('1) 대응표본 t검정 — 일별 초과수익 차이(변형 - baseline), n=%d' % len(base['bm']))
    print('=' * 92)
    print(f"{'변형':32s}{'평균차%p':>10s}{'t':>8s}{'p':>9s}{'유의':>6s}")
    print('-' * 92)
    for label, gate in passers:
        res = B.run(P, codes, dates, gate)
        m, t, p = paired_t(res['bm'], base['bm'])
        sig = '***' if p < 0.01 else '**' if p < 0.05 else '*' if p < 0.10 else ''
        print(f"{label:32s}{m:>10.4f}{t:>8.2f}{p:>9.3f}{sig:>6s}")

    print()
    print('=' * 92)
    print('2) 조합 게이트 (AND)')
    print('=' * 92)
    combos = [
        ('R2+R3 (저항 축만)', combine(B.g_head_blocked, B.g_rejected)),
        ('R3+T  (저항+기울기)', combine(B.g_rejected, B.g_ma20_slope)),
        ('R2+R3+T', combine(B.g_head_blocked, B.g_rejected, B.g_ma20_slope)),
        ('R2+R3+T+A', combine(B.g_head_blocked, B.g_rejected, B.g_ma20_slope, B.g_aligned)),
        ('전체 5종 AND', combine(B.g_head_blocked, B.g_rejected,
                                B.mk_g_support(0.01), B.g_aligned, B.g_ma20_slope)),
    ]
    bs_f = B.stats(base)
    bs_tr = B.stats(base, 0, half)
    bs_te = B.stats(base, half, None)
    print(f"{'조합':24s}{'발동':>5s}{'KODEX초과%':>11s}{'바스켓초과%':>12s}"
          f"{'train':>9s}{'test':>9s}{'t':>7s}{'판정':>10s}")
    print('-' * 92)
    print(f"{'baseline':24s}{0:>5d}{bs_f['bm']:>11.4f}{bs_f['bask']:>12.4f}"
          f"{bs_tr['bm']:>9.4f}{bs_te['bm']:>9.4f}{'-':>7s}{'-':>10s}")
    for label, gate in combos:
        res = B.run(P, codes, dates, gate)
        f, tr, te = B.stats(res), B.stats(res, 0, half), B.stats(res, half, None)
        fd = B.fired_days(P, codes, dates, gate)
        m, t, p = paired_t(res['bm'], base['bm'])
        ok = (f['bm'] > bs_f['bm']) and (tr['bm'] > bs_tr['bm']) and (te['bm'] > bs_te['bm']) and fd >= 5
        print(f"{label:24s}{fd:>5d}{f['bm']:>11.4f}{f['bask']:>12.4f}"
              f"{tr['bm']:>9.4f}{te['bm']:>9.4f}{t:>7.2f}{'채택후보' if ok else '기각':>10s}")

    print()
    print('=' * 92)
    print('3) 플라시보 — 게이트 반전(지지 깨진/저항 갇힌 종목을 오히려 선호)')
    print('   메커니즘이 실재하면 반전 시 baseline보다 뚜렷하게 나빠져야 한다.')
    print('=' * 92)
    print(f"{'반전 변형':32s}{'KODEX초과%':>11s}{'vs baseline':>13s}{'해석':>12s}")
    print('-' * 92)
    for label, gate in passers:
        res = B.run(P, codes, dates, invert(gate))
        f = B.stats(res)
        diff = f['bm'] - bs_f['bm']
        verdict = '대칭(신뢰)' if diff < -0.005 else '비대칭(의심)'
        print(f"{('~' + label):32s}{f['bm']:>11.4f}{diff:>13.4f}{verdict:>12s}")

    print()
    print('=' * 92)
    print('4) 기준선 비교 — 그냥 들고만 있었으면?')
    print('=' * 92)
    n = len(base['bm'])
    # 15섹터 등가중 vs KODEX200
    diffs = []
    for i in range(B.WARMUP, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        rets = []
        for c in codes:
            a, b = P.close(c, d), P.close(c, dn)
            if a and b:
                rets.append(b / a - 1.0)
        a, b = P.close('069500', d), P.close('069500', dn)
        if len(rets) == len(codes) and a and b:
            diffs.append(sum(rets) / len(rets) - (b / a - 1.0))
    print(f"15섹터 등가중 바스켓 vs KODEX200 : 일평균 {statistics.mean(diffs)*100:+.4f}%p "
          f"(누적 {(math.prod(1+x for x in diffs)-1)*100:+.1f}%, {len(diffs)}일)")
    print(f"baseline(mom20 top5)  vs KODEX200 : 일평균 {bs_f['bm']:+.4f}%p")
    print(f"baseline(mom20 top5)  vs 15섹터바스켓: 일평균 {bs_f['bask']:+.4f}%p")


if __name__ == '__main__':
    main()
