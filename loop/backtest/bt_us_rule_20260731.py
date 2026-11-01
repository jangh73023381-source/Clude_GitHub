# -*- coding: utf-8 -*-
"""2026-07-31 — Rule US(미국 섹터 전이)를 '선정 규칙'으로 백테스트.

`bt_us_kr_transfer.py` 에서 전이 자체는 강하게 확인됐다(M1 종가→종가 IC +0.141, t=+5.18).
문제는 그 전이가 **거의 전부 시가 갭에서 소화**된다는 것이다(M3 IC +0.219 / M2 +0.026).

그래서 같은 규칙을 두 가지 체결 가정으로 나란히 채점한다.
  (a) 종가→종가 : 저장소 표준 채점 관행. 신호를 알기 전 시점에 사는 것이므로 **과대평가**.
  (b) 시가→종가 : 신호를 보고 시초가에 사는 실제 집행. **유일하게 유효한 수치**.

두 값의 격차가 곧 '이 규칙을 표준 관행대로 채점하면 얼마나 속게 되는가'다.
룩어헤드 금지 — US 신호는 한국 거래일 D 보다 엄격히 이전인 미국 세션만 쓴다.
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))

import bt_us_kr_transfer as T  # noqa: E402
from universe_filters import is_cash, is_deriv  # noqa: E402

PANEL = os.path.join(HERE, 'panel_close_0731.csv')
OPENS = os.path.join(HERE, 'panel_open.csv')
THEMES = os.path.join(HERE, 'theme_map.csv')
BENCH, COST = '069500', 0.0010


def load():
    px, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError):
            continue
        nm[r['code']] = r.get('name', '')
    op = defaultdict(dict)
    for r in csv.DictReader(open(OPENS, encoding='utf-8')):
        op[r['code']][r['date']] = float(r['open'])
    th = {r['code']: r['theme'] for r in csv.DictReader(open(THEMES, encoding='utf-8'))
          if r['theme'] in T.MAP}
    return px, nm, op, th, sorted({d for v in px.values() for d in v})


def us_signal(dk):
    """한국 거래일 dk 직전 미국 세션의 테마별 시장초과 수익률."""
    us = T.load_us()
    days = sorted(us)
    prior = [d for d in days if d < dk]
    if len(prior) < 2:
        return {}
    du = prior[-1]
    ku = days[days.index(du) - 1]
    if T.BENCH_US not in us[du] or T.BENCH_US not in us[ku]:
        return {}
    mkt = us[du][T.BENCH_US] / us[ku][T.BENCH_US] - 1
    out = {}
    for th, t in T.MAP.items():
        if t in us[du] and t in us[ku]:
            out[th] = (us[du][t] / us[ku][t] - 1) - mkt
    return out


def mom(px, c, d, di, dates, k):
    i = di[d]
    if i < k:
        return None
    a, b = px[c].get(dates[i - k]), px[c].get(d)
    return (b / a - 1.0) if (a and b) else None


def ruleh_ok(px, c, d, di, dates):
    s, c3 = mom(px, c, d, di, dates, 1), mom(px, c, d, di, dates, 3)
    return not ((s is not None and s > 0.10) or (c3 is not None and c3 > 0.20))


def cand(px, nm, d, di, dates):
    out = []
    for c in px:
        if not px[c].get(d) or is_deriv(nm.get(c, '')) or is_cash(nm.get(c, '')):
            continue
        m = mom(px, c, d, di, dates, 20)
        if m is None or not ruleh_ok(px, c, d, di, dates):
            continue
        out.append({'code': c, 'mom': m})
    return out


def base_sel(cs, **_):
    return [x['code'] for x in sorted(cs, key=lambda x: -x['mom'])[:5]]


def us_sel(cs, sig=None, th=None, pool=15, **_):
    """U1/U2 — mom20 상위 pool 안에서 US 섹터 신호 상위 5."""
    top = sorted(cs, key=lambda x: -x['mom'])[:pool]
    sc = [(sig[th[x['code']]], x['code']) for x in top
          if x['code'] in th and th[x['code']] in sig]
    if len(sc) < 5:
        return base_sel(cs)
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


def us_pure(cs, sig=None, th=None, **_):
    """U3 — mom20 무시, 테마 보유 종목 중 US 신호 상위 5(테마당 mom20 최상위 1종)."""
    best = {}
    for x in sorted(cs, key=lambda x: -x['mom']):
        t = th.get(x['code'])
        if t in sig and t not in best:
            best[t] = x['code']
    if len(best) < 5:
        return base_sel(cs)
    order = sorted(best, key=lambda t: -sig[t])[:5]
    return [best[t] for t in order]


def run(fn, px, nm, op, th, dates, di, mode, **kw):
    """mode: 'cc' 종가→종가(과대평가) / 'oc' 시가→종가(매매 가능)."""
    out = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cs = cand(px, nm, d, di, dates)
        if len(cs) < 10:
            continue
        sig = us_signal(nxt)                 # nxt 장 시작 전에 확정되는 신호
        if not sig:
            continue
        picks = fn(cs, sig=sig, th=th, **kw)
        rets = []
        for c in picks:
            if mode == 'cc':
                a, b = px[c].get(d), px[c].get(nxt)
            else:
                a, b = op[c].get(nxt), px[c].get(nxt)
            if a and b:
                rets.append(b / a - 1.0)
        if mode == 'cc':
            ba, bb = px[BENCH].get(d), px[BENCH].get(nxt)
        else:
            ba, bb = op[BENCH].get(nxt), px[BENCH].get(nxt)
        if not rets or not (ba and bb):
            continue
        out.append((d, 100 * ((sum(rets) / len(rets) - COST) - (bb / ba - 1.0))))
    return out


def folds(v, k=3):
    n = len(v)
    return [v[i * n // k:(i + 1) * n // k] for i in range(k)]


def main():
    px, nm, op, th, dates = load()
    di = {d: i for i, d in enumerate(dates)}
    variants = [
        ('baseline mom20+RuleH', base_sel, {}),
        ('U1 mom20 top15 → US신호 top5', us_sel, {'pool': 15}),
        ('U2 mom20 top30 → US신호 top5', us_sel, {'pool': 30}),
        ('U3 US신호 top5 (mom20 무시)', us_pure, {}),
    ]
    print(f'패널 {len(dates)}일 ({dates[0]}~{dates[-1]}) · 테마 라벨 {len(th)}종')
    print(f'\n{"변형":32s}{"(a)종가→종가":>14s}{"(b)시가→종가":>14s}{"괴리":>10s}')
    print('-' * 72)
    store = {}
    for label, fn, kw in variants:
        cc = run(fn, px, nm, op, th, dates, di, 'cc', **kw)
        oc = run(fn, px, nm, op, th, dates, di, 'oc', **kw)
        mcc, moc = statistics.fmean([x[1] for x in cc]), statistics.fmean([x[1] for x in oc])
        store[label] = (cc, oc)
        print(f'{label:32s}{mcc:+14.4f}{moc:+14.4f}{mcc - moc:+10.4f}')
    print(f'\n표본 {len(store["baseline mom20+RuleH"][0])}일 · 단위 %p/일 (벤치 대비 초과, 왕복 10bp 차감)')

    print('\n=== 3분할 가드 — (b) 시가→종가 기준(유효 수치) ===')
    b = [x[1] for x in store['baseline mom20+RuleH'][1]]
    for label, _, _ in variants[1:]:
        v = [x[1] for x in store[label][1]]
        ok = all(statistics.fmean(y) > statistics.fmean(x)
                 for x, y in zip(folds(b), folds(v)))
        diff = [q - p for p, q in zip(b, v)]
        jk = [statistics.fmean(diff[:i] + diff[i + 1:]) for i in range(len(diff))]
        print(f'{label:32s} full {statistics.fmean(v):+.4f} vs base {statistics.fmean(b):+.4f}'
              f' · 3분할 {"통과" if ok else "미통과"} · 잭나이프하한 {min(jk):+.4f}')


if __name__ == '__main__':
    main()
