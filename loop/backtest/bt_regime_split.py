# -*- coding: utf-8 -*-
"""국면(상승·보합·하락)별로 선정 조건을 달리해야 하는가 — 실증 분해.

국면 판정(룩어헤드 금지, KODEX200 D종가까지 정보만):
  MA20, MA60 계산 후
    BULL(상승) : close > MA60 and MA20 > MA60
    BEAR(하락) : close < MA60 and MA20 < MA60
    SIDE(보합) : 그 외
보조 정의(민감도): 60일 수익률 r60 > +3% / < -3% / 그 사이.

주의 — 이 분석 자체가 다중검정 위험을 키운다. 표본을 3분할하면 각 국면 표본은 1/3로 줄고
시행 횟수는 3배가 된다. 따라서 "국면별로 부호가 뒤집히는가"라는 정성적 질문에 답하는 용도로만
쓰고, 국면별 파라미터를 따로 최적화하지는 않는다.
"""
import sys, os, math
from collections import defaultdict
os.environ.setdefault('PANEL_FILE', 'panel_ohlc_long.csv')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, mk_rank, eligible, rule_h_ok, BENCH, COST, NPICK)
from fib_engine import date_clustered_t

WARM = 300


def regimes(cache, dates, mode='ma'):
    """date -> 'BULL'|'SIDE'|'BEAR'. D종가까지만 사용."""
    be = cache[BENCH]; px = be['px']; idx = be['idx']
    out = {}
    for d in dates:
        i = idx.get(d)
        if i is None or i < 60:
            continue
        if mode == 'ma':
            ma20 = sum(px[i - 19:i + 1]) / 20
            ma60 = sum(px[i - 59:i + 1]) / 60
            if px[i] > ma60 and ma20 > ma60:
                out[d] = 'BULL'
            elif px[i] < ma60 and ma20 < ma60:
                out[d] = 'BEAR'
            else:
                out[d] = 'SIDE'
        else:
            r60 = px[i] / px[i - 60] - 1
            out[d] = 'BULL' if r60 > 0.03 else ('BEAR' if r60 < -0.03 else 'SIDE')
    return out


def add_mom(cache, lb):
    key = f'mom{lb}'
    for code, e in cache.items():
        if key in e:
            continue
        p = e['px']; a = [None] * len(p)
        for i in range(lb, len(p)):
            if p[i - lb]:
                a[i] = p[i] / p[i - lb] - 1.0
        e[key] = a


def evaluate(cache, name, dates, picker, reg, H=1, warm=WARM):
    """국면별 초과수익 리스트 반환. H=1은 매일, H=20은 겹침 허용(기술통계용)."""
    be = cache[BENCH]
    out = defaultdict(list)
    for k in range(warm, len(dates) - H):
        d = dates[k]; dn = dates[k + H]
        r = reg.get(d)
        if r is None:
            continue
        bi = be['idx'].get(d); bj = be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        univ = eligible(cache, name, d)
        picks = picker(cache, name, d, univ) if picker else []
        rets = []
        for c in picks:
            e = cache[c]; i = e['idx'][d]; j = e['idx'].get(dn)
            if j is not None:
                rets.append(e['px'][j] / e['px'][i] - 1.0)
        port = (sum(rets) / len(rets) - COST) if rets else 0.0   # picker=None → 전량 현금
        out[r].append(port - bench)
    return out


def line(lbl, res, order=('BULL', 'SIDE', 'BEAR')):
    cells = []
    for r in order:
        xs = res.get(r) or []
        if not xs:
            cells.append(f'{"-":>18}'); continue
        m, t, n = date_clustered_t(xs)
        cells.append(f'{m*100:>9.3f}({t if t else 0:>5.2f})' if m is not None
                     else f'{"-":>18}')
    print(f'{lbl:<30}' + ''.join(cells))


def main():
    cache, name, dates = build()
    for lb in (120, 150):
        add_mom(cache, lb)
    for mode in ('ma', 'r60'):
        reg = regimes(cache, dates, mode)
        cnt = defaultdict(int)
        for d in dates[WARM:]:
            if d in reg:
                cnt[reg[d]] += 1
        print(f'\n\n############ 국면 정의 = {mode} ############')
        print(f'거래일 분포: BULL {cnt["BULL"]} · SIDE {cnt["SIDE"]} · BEAR {cnt["BEAR"]}')

        for H in (1, 20):
            print(f'\n--- 보유 {H}일 · 평균 초과수익 %(괄호=일자클러스터 t) ---')
            print(f'{"전략":<30}{"BULL 상승":>18}{"SIDE 보합":>18}{"BEAR 하락":>18}')
            strat = [
                ('mom20 상위 (현행 단기)', mk_rank('mom20', True)),
                ('mom150 상위 (중기 후보)', mk_rank('mom150', True)),
                ('mom5 상위', mk_rank('mom5', True)),
                ('RSI14 과매도 (평균회귀)', mk_rank('rsi14', False)),
                ('%B 하단 (평균회귀)', mk_rank('pctb', False)),
                ('채널저점권 POS-LO', mk_rank('chpos60', False)),
                ('%B 상단', mk_rank('pctb', True)),
                ('전량 현금(관망)', None),
            ]
            for lbl, p in strat:
                line(lbl, evaluate(cache, name, dates, p, reg, H=H))
            if H == 20:
                print('  ※ H=20은 관측이 20배 겹쳐 t가 부풀려진다 — 부호·크기 비교용 기술통계')


if __name__ == '__main__':
    main()
