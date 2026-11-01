# -*- coding: utf-8 -*-
"""2026-07-28 루프 iteration 1 — Rule XC (교차상관 중복 픽 제거) 검증.

가설: 2026-07-27 픽 5종(498410 금융고배당커버드콜 / 484880 금융지주고배당 / 091170 은행 /
279530 고배당주 / 466940 은행고배당TOP10)은 '섹터 라벨'이 서로 다르지만 실현수익률로 보면
사실상 하나의 베팅(은행·고배당)이다. 그래서 반도체·코스닥150이 주도한 반등일(7/27)에
5종이 통째로 소외돼 0/5가 났다.

기존 Rule Q(섹터 라벨 기준 분산 상한, 2026-07-09 기각)와 구별되는 점:
  Rule Q  = 사전 정의된 '섹터 taxonomy' 라벨이 겹치면 배제 → 위 5종은 라벨이 전부 달라 무력.
  Rule XC = 최근 60거래일 '실현 일간수익률 상관계수'가 임계 이상이면 배제 → 라벨과 무관하게
            실제로 같이 움직이는 픽을 잡아낸다. 룩어헤드 없음(D 시점까지의 과거 수익률만 사용).

1차 지표 = 일별 초과수익(픽5 동일가중 1일보유 -10bp - KODEX200 당일수익) 평균 (v2.3)
보조 지표 = 상위10% 적중 종목수 평균 (이진)
과최적화 가드: 변형 채택은 full·train·test 모두 baseline 초과일 때만.
"""
import csv
import os
import math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def newest_panel():
    c = sorted(f for f in os.listdir(HERE)
               if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(HERE, c[-1])


PANEL = newest_panel()
BENCH = '069500'
COST = 0.0010
CASH_KW = ['머니마켓', 'CD금리', '초단기채', 'KOFR', '국고채', '통안']


def load():
    px = defaultdict(dict)
    name = {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except Exception:
            pass
        name[r['code']] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, name, dates


def is_spot(nm):
    n = (nm or '').replace(' ', '')
    return not ('인버스' in n or '곱버스' in n or '레버리지' in n
                or '2X' in n.upper() or '2배' in n or '숏' in n)


def mom(px, c, d, dates, k):
    i = dates.index(d)
    if i < k:
        return None
    a = px[c].get(dates[i - k])
    b = px[c].get(d)
    return (b / a - 1.0) if (a and b) else None


def rule_h_ok(px, c, d, dates):
    s = mom(px, c, d, dates, 1)
    c3 = mom(px, c, d, dates, 3)
    if s is not None and s > 0.10:
        return False
    if c3 is not None and c3 > 0.20:
        return False
    return True


def rank_candidates(px, name, d, dates, window=20, minp=10000):
    cand = []
    for c in px:
        pc = px[c].get(d)
        if not pc or pc < minp or not is_spot(name.get(c, '')):
            continue
        m = mom(px, c, d, dates, window)
        if m is None or not rule_h_ok(px, c, d, dates):
            continue
        cand.append((c, m))
    cand.sort(key=lambda x: -x[1])
    return [c for c, _ in cand]


def sel_baseline(px, name, d, dates, n=5):
    return rank_candidates(px, name, d, dates)[:n]


# ---------------------------------------------------------------- Rule XC
def _rets(px, c, d, dates, look=60):
    """D 시점까지의 최근 look 거래일 일간수익률(룩어헤드 없음)."""
    i = dates.index(d)
    s = dates[max(0, i - look):i + 1]
    out = []
    for a, b in zip(s, s[1:]):
        x, y = px[c].get(a), px[c].get(b)
        out.append((y / x - 1.0) if (x and y) else None)
    return out


def _corr(a, b):
    p = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(p) < 20:
        return 0.0
    n = len(p)
    ma = sum(x for x, _ in p) / n
    mb = sum(y for _, y in p) / n
    va = sum((x - ma) ** 2 for x, _ in p)
    vb = sum((y - mb) ** 2 for _, y in p)
    if va <= 0 or vb <= 0:
        return 0.0
    cov = sum((x - ma) * (y - mb) for x, y in p)
    return cov / math.sqrt(va * vb)


def make_xc(rho, look=60):
    def sel(px, name, d, dates, n=5):
        order = rank_candidates(px, name, d, dates)
        cache = {}
        picks = []
        for c in order:
            if len(picks) >= n:
                break
            if c not in cache:
                cache[c] = _rets(px, c, d, dates, look)
            if any(_corr(cache[c], cache[p]) >= rho for p in picks):
                continue
            picks.append(c)
        if len(picks) < n:  # 임계가 너무 빡세면 차순위로 채운다
            for c in order:
                if c not in picks:
                    picks.append(c)
                if len(picks) >= n:
                    break
        return picks[:n]
    return sel


# ---------------------------------------------------------------- 채점
def day_excess(px, picks, d, dn):
    rs = []
    for c in picks:
        a, b = px[c].get(d), px[c].get(dn)
        if a and b:
            rs.append(b / a - 1.0)
    if not rs:
        return None
    ba, bb = px[BENCH].get(d), px[BENCH].get(dn)
    if not (ba and bb):
        return None
    return (sum(rs) / len(rs) - COST - (bb / ba - 1.0)) * 100


def day_hits(px, name, picks, d, dn, minp=10000, toppct=10.0):
    uni = []
    for c in px:
        a, b = px[c].get(d), px[c].get(dn)
        if not a or not b or a < minp or not is_spot(name.get(c, '')):
            continue
        if any(k in (name.get(c, '')).replace(' ', '') for k in CASH_KW):
            continue
        uni.append((c, b / a - 1.0))
    if len(uni) < 20:
        return None
    uni.sort(key=lambda x: -x[1])
    cut = max(1, round(len(uni) * toppct / 100.0))
    win = {c for c, _ in uni[:cut]}
    return sum(1 for c in picks if c in win)


def track(px, name, dates, fn, start=20):
    ex, hi = [], []
    for i in range(start, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        picks = fn(px, name, d, dates)
        e = day_excess(px, picks, d, dn)
        h = day_hits(px, name, picks, d, dn)
        if e is not None:
            ex.append((d, e))
        if h is not None:
            hi.append((d, h))
    return ex, hi


def avg(v):
    return sum(v) / len(v) if v else float('nan')


def main():
    px, name, dates = load()
    print(f'패널 {os.path.basename(PANEL)} · 거래일 {len(dates)} '
          f'({dates[0]}~{dates[-1]}) · 종목 {len(px)}')
    variants = [('baseline mom20+RuleH', sel_baseline)]
    for rho in (0.85, 0.90, 0.95):
        variants.append((f'Rule XC rho={rho}', make_xc(rho)))

    res = {}
    for lbl, fn in variants:
        ex, hi = track(px, name, dates, fn)
        half = len(ex) // 2
        tr = [v for _, v in ex[:half]]
        te = [v for _, v in ex[half:]]
        hh = len(hi) // 2
        res[lbl] = {
            'full': avg([v for _, v in ex]), 'train': avg(tr), 'test': avg(te),
            'win': sum(1 for _, v in ex if v > 0), 'n': len(ex),
            'bfull': avg([v for _, v in hi]),
            'btrain': avg([v for _, v in hi[:hh]]),
            'btest': avg([v for _, v in hi[hh:]]),
        }
        r = res[lbl]
        print('%-22s [P&L] 평균 %+.3f%%p | train %+.3f%%p test %+.3f%%p | 지수이김 %d/%d'
              '  [이진] 평균 %.3f종 (tr %.3f/te %.3f)'
              % (lbl, r['full'], r['train'], r['test'], r['win'], r['n'],
                 r['bfull'], r['btrain'], r['btest']))

    print('\n=== 과최적화 가드 (채택 = 1차지표 full·train·test 모두 baseline 초과) ===')
    b = res['baseline mom20+RuleH']
    for lbl in res:
        if lbl.startswith('baseline'):
            continue
        r = res[lbl]
        m = lambda k: '▲' if r[k] > b[k] else '▼'  # noqa: E731
        ok = all(r[k] > b[k] for k in ('full', 'train', 'test'))
        print('%-22s full %s train %s test %s | 이진 full %.3f -> %.3f | %s'
              % (lbl, m('full'), m('train'), m('test'), b['bfull'], r['bfull'],
                 '통과' if ok else '미통과'))


if __name__ == '__main__':
    main()
