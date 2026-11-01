# -*- coding: utf-8 -*-
"""2026-08-03 — 집행 파라미터를 ATR14로 정규화하는 것이 고정%보다 나은가.

사용자 질문: "ATR14가 큰 종목일수록 많이 흔들리는데 매수상단·지정가·갭하락·손절을
             모든 종목에 동일한 %로 갖는 게 맞지 않아 보인다."

세 가지를 잰다.
  (1) 픽5의 ATR14% 분산이 실제로 얼마나 큰가 (문제 제기의 크기).
  (2) 매수상단(+0.6% 고정) → k×ATR 로 바꾸면 집행안 D 성과가 개선되는가.
  (3) 손절(-2.5% 고정) → m×ATR 로 바꾸면 개선되는가.
집행·청산 관행은 bt_execution.py 와 동일: 픽5 동일가중, D+1 매수, D+1 종가 청산,
왕복 10bp, 벤치 KODEX200 대비 초과수익(%p/일).
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import is_cash, is_deriv  # noqa: E402

PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')
BENCH, COST = '069500', 0.0010


def load():
    bar, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            o, h, l, c = (float(r['open']), float(r['high']),
                          float(r['low']), float(r['close']))
        except (ValueError, KeyError):
            continue
        if min(o, h, l, c) <= 0:
            continue
        nm[r['code']] = r['name']
        bar[r['code']][r['date']] = (o, h, l, c)
    bar = {c: v for c, v in bar.items() if not is_deriv(nm[c]) and not is_cash(nm[c])}
    return bar, nm, sorted({d for v in bar.values() for d in v})


def mom(bar, c, d, di, dates, k):
    i = di[d]
    if i < k:
        return None
    a, b = bar[c].get(dates[i - k]), bar[c].get(d)
    return (b[3] / a[3] - 1.0) if (a and b) else None


def atr_pct(bar, c, d, di, dates, n=14):
    """ATR14 / 종가. d 까지의 정보만 사용."""
    i = di[d]
    if i < n:
        return None
    trs = []
    for j in range(i - n + 1, i + 1):
        cur, prv = bar[c].get(dates[j]), bar[c].get(dates[j - 1])
        if not cur or not prv:
            return None
        h, l, pc = cur[1], cur[2], prv[3]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < n:
        return None
    return (sum(trs) / n) / bar[c][d][3]


def picks5(bar, nm, d, di, dates):
    cs = []
    for c, v in bar.items():
        if d not in v:
            continue
        m = mom(bar, c, d, di, dates, 20)
        r1 = mom(bar, c, d, di, dates, 1)
        r3 = mom(bar, c, d, di, dates, 3)
        if m is None or r1 is None or r3 is None:
            continue
        if r1 > 0.10 or r3 > 0.20:
            continue
        cs.append((m, c))
    cs.sort(reverse=True)
    return [c for _, c in cs[:5]]


def exec_ret(pc, o, h, l, cl, upper, stop=None):
    """집행안 D: 지정가(upper) 시도 → 미체결이면 시가 매수. stop 지정 시 장중 손절."""
    if o <= upper:
        entry = o
    elif l <= upper:
        entry = upper
    else:
        entry = o                       # 미체결 → 시가 대체매수 (케이스 ③)
    if stop is not None:
        sp = entry * (1 - stop)
        if l <= sp:                     # 진입 후 저가가 손절선 이탈 (보수적: 같은 날 저가 사용)
            return sp / entry - 1
    return cl / entry - 1


def run(bar, nm, dates, di, mode, k=None, stop_mode=None, m=None):
    out = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        p = picks5(bar, nm, d, di, dates)
        if len(p) < 5 or nxt not in bar[BENCH] or d not in bar[BENCH]:
            continue
        b_oc = bar[BENCH][nxt][3] / bar[BENCH][nxt][0] - 1
        rs = []
        for c in p:
            if d not in bar[c] or nxt not in bar[c]:
                continue
            pc = bar[c][d][3]
            o, h, l, cl = bar[c][nxt]
            a = atr_pct(bar, c, d, di, dates)
            if a is None:
                a = 0.025
            upper = pc * (1 + (0.006 if mode == 'fix' else k * a))
            if stop_mode is None:
                st = None
            elif stop_mode == 'fix':
                st = 0.025
            else:
                st = m * a
            rs.append(exec_ret(pc, o, h, l, cl, upper, st))
        if rs:
            out.append(100 * ((sum(rs) / len(rs) - COST) - b_oc))
    return out


def rep(lab, v):
    mu = statistics.fmean(v)
    sd = statistics.stdev(v)
    t = mu / (sd / len(v) ** 0.5)
    print(f'  {lab:34s}{mu:+9.4f}{sum(1 for x in v if x > 0) / len(v):8.1%}{t:8.2f}')


def main():
    bar, nm, dates = load()
    di = {d: i for i, d in enumerate(dates)}

    # (1) 픽5 ATR14% 분포
    av, per_day = [], []
    for i in range(21, len(dates) - 1):
        d = dates[i]
        p = picks5(bar, nm, d, di, dates)
        xs = [atr_pct(bar, c, d, di, dates) for c in p]
        xs = [x for x in xs if x]
        if len(xs) >= 2:
            av += xs
            per_day.append(max(xs) / min(xs))
    av.sort()
    print(f'[1] 픽5 종목의 ATR14%(=ATR/종가) 분포 — {len(av)}건')
    print(f'    중앙값 {statistics.median(av)*100:.2f}%  '
          f'하위10% {av[int(len(av)*.1)]*100:.2f}%  상위10% {av[int(len(av)*.9)]*100:.2f}%  '
          f'최대 {av[-1]*100:.2f}%')
    print(f'    같은 날 픽5 안에서 최대/최소 ATR 배수 중앙값 {statistics.median(per_day):.2f}배\n')

    print('[2] 매수상단: 고정 +0.6% vs k×ATR   (집행안 D, 손절 없음)')
    print(f'  {"방식":34s}{"평균초과":>9s}{"승률":>8s}{"t":>8s}')
    print('  ' + '-' * 58)
    base = run(bar, nm, dates, di, 'fix')
    rep('고정 +0.6% (현행)', base)
    for k in (0.15, 0.25, 0.35, 0.50, 0.75):
        rep(f'k={k:.2f} × ATR14', run(bar, nm, dates, di, 'atr', k=k))

    print('\n[3] 손절: 고정 -2.5% vs m×ATR   (매수상단은 현행 고정 +0.6%)')
    print(f'  {"방식":34s}{"평균초과":>9s}{"승률":>8s}{"t":>8s}')
    print('  ' + '-' * 58)
    rep('손절 없음 (종가청산)', base)
    rep('고정 -2.5% (현행)', run(bar, nm, dates, di, 'fix', stop_mode='fix'))
    for m in (1.0, 1.5, 2.0, 3.0):
        rep(f'{m:.1f} ATR 손절', run(bar, nm, dates, di, 'fix', stop_mode='atr', m=m))


if __name__ == '__main__':
    main()
