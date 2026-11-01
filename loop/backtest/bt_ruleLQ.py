# -*- coding: utf-8 -*-
"""Rule LQ — 유동성(거래대금) '수준' 축 백테스트. iteration 1 / 2026-07-29.

기각된 Rule AA(거래량 '급증' 비율)와 구별되는 축:
  AA = D일거래량 / 20일평균거래량  (변화율)
  LQ = 20일평균 거래대금(close*volume)의 절대 수준 (횡단면 백분위)

1차 지표 = v2.3 P&L: 픽5 동일가중 1일보유(-10bp) - KODEX200 당일수익, 평균 %p/일.
과최적화 가드: full / train / test 3개 모두 baseline 초과일 때만 후보 승격.
룩어헤드 금지 — 선정은 D 종가·D까지 거래량 정보만 사용.
"""
import csv
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_vol.csv')
BENCH = '069500'
COST = 0.0010
MINP = 10000

CASH_KW = ['머니마켓', 'CD금리', 'CD1년', '초단기채', 'KOFR', '국고채', '통안',
           '금리액티브', '금리플러스', '금리투자']


def load():
    px, vol, name = defaultdict(dict), defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        c = r['code']
        try:
            px[c][r['date']] = float(r['close'])
            vol[c][r['date']] = float(r['volume'])
        except (ValueError, KeyError):
            continue
        name[c] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, vol, name, dates


def is_spot(nm):
    n = (nm or '').replace(' ', '')
    return not ('인버스' in n or '곱버스' in n or '레버리지' in n
                or '2X' in n.upper() or '2배' in n or '숏' in n)


def is_cash(nm):
    n = (nm or '').replace(' ', '')
    return any(k in n for k in CASH_KW)


def mom(px, c, d, dates, k):
    i = dates.index(d)
    if i < k:
        return None
    a, b = px[c].get(dates[i - k]), px[c].get(d)
    return (b / a - 1.0) if (a and b) else None


def rule_h_ok(px, c, d, dates):
    s, c3 = mom(px, c, d, dates, 1), mom(px, c, d, dates, 3)
    if s is not None and s > 0.10:
        return False
    if c3 is not None and c3 > 0.20:
        return False
    return True


def avg_value(px, vol, c, d, dates, k=20):
    """D일까지 k일 평균 거래대금(원). 룩어헤드 없음."""
    i = dates.index(d)
    if i < k - 1:
        return None
    vals = []
    for j in range(i - k + 1, i + 1):
        dd = dates[j]
        p, v = px[c].get(dd), vol[c].get(dd)
        if p is None or v is None:
            return None
        vals.append(p * v)
    return sum(vals) / len(vals)


def candidates(px, vol, name, d, dates):
    out = []
    for c in px:
        pc = px[c].get(d)
        if not pc or pc < MINP or not is_spot(name.get(c, '')) or is_cash(name.get(c, '')):
            continue
        m = mom(px, c, d, dates, 20)
        if m is None or not rule_h_ok(px, c, d, dates):
            continue
        av = avg_value(px, vol, c, d, dates, 20)
        out.append({'code': c, 'mom': m, 'av': av})
    return out


def sel_baseline(cand):
    return [x['code'] for x in sorted(cand, key=lambda x: -x['mom'])[:5]]


def sel_lq_floor(cand, pct):
    """LQ1 — 거래대금 하위 pct 백분위 사전제외 후 mom20 상위5."""
    have = [x for x in cand if x['av'] is not None]
    if len(have) < 20:
        return sel_baseline(cand)
    vals = sorted(x['av'] for x in have)
    thr = vals[int(len(vals) * pct)]
    keep = [x for x in have if x['av'] >= thr]
    if len(keep) < 5:
        keep = have
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def sel_lq_blend(cand, w):
    """LQ2 — mom20 백분위와 거래대금 백분위를 w:(1-w) 블렌드."""
    have = [x for x in cand if x['av'] is not None]
    if len(have) < 20:
        return sel_baseline(cand)
    n = len(have)
    mr = {x['code']: i for i, x in enumerate(sorted(have, key=lambda x: x['mom']))}
    lr = {x['code']: i for i, x in enumerate(sorted(have, key=lambda x: x['av']))}
    sc = [(w * mr[x['code']] / n + (1 - w) * lr[x['code']] / n, x['code']) for x in have]
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


def sel_lq_top(cand, k):
    """LQ3 — mom20 상위 k풀 안에서 거래대금 상위5(유동성 우선)."""
    pool = sorted(cand, key=lambda x: -x['mom'])[:k]
    have = [x for x in pool if x['av'] is not None]
    if len(have) < 5:
        return sel_baseline(cand)
    return [x['code'] for x in sorted(have, key=lambda x: -x['av'])[:5]]


def run(strategy, px, vol, name, dates, warm=21):
    px_, recs = px, []
    for i in range(warm, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = candidates(px_, vol, name, d, dates)
        if len(cand) < 10:
            continue
        picks = strategy(cand)
        rets = []
        for c in picks:
            a, b = px_[c].get(d), px_[c].get(nxt)
            if a and b:
                rets.append(b / a - 1.0)
        if not rets:
            continue
        port = sum(rets) / len(rets) - COST
        ba, bb = px_[BENCH].get(d), px_[BENCH].get(nxt)
        if not (ba and bb):
            continue
        recs.append((d, 100 * (port - (bb / ba - 1.0))))
    return recs


def summarize(recs):
    v = [x[1] for x in recs]
    return {'n': len(v), 'mean': statistics.mean(v) if v else 0.0}


def main():
    px, vol, name, dates = load()
    print(f'패널 {len(dates)}일 ({dates[0]}~{dates[-1]}) · {len(px)}종')
    variants = [
        ('baseline (mom20+RuleH)', sel_baseline),
        ('LQ1 거래대금 하위20% 제외', lambda c: sel_lq_floor(c, 0.20)),
        ('LQ1b 거래대금 하위40% 제외', lambda c: sel_lq_floor(c, 0.40)),
        ('LQ2 mom:유동성 70:30 블렌드', lambda c: sel_lq_blend(c, 0.70)),
        ('LQ2b mom:유동성 50:50 블렌드', lambda c: sel_lq_blend(c, 0.50)),
        ('LQ3 mom20 상위15풀 → 유동성 상위5', lambda c: sel_lq_top(c, 15)),
    ]
    base = None
    print(f"\n{'변형':32s} {'전체':>9s} {'train':>9s} {'test':>9s}  판정")
    print('-' * 74)
    for label, fn in variants:
        recs = run(fn, px, vol, name, dates)
        half = len(recs) // 2
        full = summarize(recs)['mean']
        tr = summarize(recs[:half])['mean']
        te = summarize(recs[half:])['mean']
        if base is None:
            base = (full, tr, te)
            verdict = f'기준선 (n={len(recs)}일)'
        else:
            ok = full > base[0] and tr > base[1] and te > base[2]
            verdict = '후보승격' if ok else '기각(가드 미통과)'
        print(f'{label:32s} {full:+9.4f} {tr:+9.4f} {te:+9.4f}  {verdict}')


if __name__ == '__main__':
    main()
