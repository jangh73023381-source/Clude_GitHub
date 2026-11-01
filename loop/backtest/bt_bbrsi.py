# -*- coding: utf-8 -*-
"""트랙1(볼린저·RSI 단독 선정) / 트랙2(mom20 선정 + 볼린저·RSI 집행필터) 백테스트.

채점: v2.3 손익 1차 지표 — 픽 동일가중·1일 회전·왕복 10bp 차감 후 KODEX200 대비 초과수익.
룩어헤드 금지: 선정은 D종가까지, 채점은 D+1 종가.
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbrsi_engine import build_cache, is_excluded, is_cashlike, BENCH
from fib_engine import date_clustered_t, jackknife_low

MINP = 10000
NPICK = 5
COST = 0.0010
WARM = 140


def eligible(cache, name, d):
    out = []
    for code, e in cache.items():
        nm = name[code]
        if is_excluded(nm) or is_cashlike(nm):
            continue
        i = e['idx'].get(d)
        if i is None or e['px'][i] < MINP:
            continue
        out.append((code, i))
    return out


def rule_h_ok(e, i):
    if i < 3:
        return True
    p0, p1, p3 = e['px'][i], e['px'][i - 1], e['px'][i - 3]
    if p1 and p0 / p1 - 1.0 > 0.10:
        return False
    if p3 and p0 / p3 - 1.0 > 0.20:
        return False
    return True


# ---------------- 선정기 ----------------
def mk_mom20(filt=None):
    def f(cache, name, d, univ):
        sc = []
        for code, i in univ:
            e = cache[code]
            m = e['mom20'][i]
            if m is None or not rule_h_ok(e, i):
                continue
            if filt and not filt(e, i):
                continue
            sc.append((m, code))
        sc.sort(reverse=True)
        return [c for _, c in sc[:NPICK]]
    return f


def mk_rank(key, reverse, cond=None, ruleh=True):
    """key 기준 정렬 상위 5종. reverse=True면 큰 값 우선."""
    def f(cache, name, d, univ):
        sc = []
        for code, i in univ:
            e = cache[code]
            v = e[key][i]
            if v is None:
                continue
            if ruleh and not rule_h_ok(e, i):
                continue
            if cond and not cond(e, i):
                continue
            sc.append((v, code))
        sc.sort(reverse=reverse)
        return [c for _, c in sc[:NPICK]]
    return f


def mk_target(key, target, cond=None):
    def f(cache, name, d, univ):
        sc = []
        for code, i in univ:
            e = cache[code]
            v = e[key][i]
            if v is None or not rule_h_ok(e, i):
                continue
            if cond and not cond(e, i):
                continue
            sc.append((abs(v - target), code))
        sc.sort()
        return [c for _, c in sc[:NPICK]]
    return f


# ---------------- 실행 ----------------
def run(cache, name, dates, picker, label):
    be = cache[BENCH]
    daily = []
    for k in range(WARM, len(dates) - 1):
        d = dates[k]; dn = dates[k + 1]
        bi = be['idx'].get(d); bj = be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        univ = eligible(cache, name, d)
        picks = picker(cache, name, d, univ)
        rets = []
        for code in picks:
            e = cache[code]
            i = e['idx'][d]; j = e['idx'].get(dn)
            if j is None:
                continue
            rets.append(e['px'][j] / e['px'][i] - 1.0)
        if not rets:
            daily.append((d, 0.0, bench, 0, 0)); continue
        port = sum(rets) / len(rets) - COST
        u = []
        for code, i in univ:
            e = cache[code]; j = e['idx'].get(dn)
            if j is not None:
                u.append((e['px'][j] / e['px'][i] - 1.0, code))
        u.sort(reverse=True)
        cut = max(1, math.ceil(len(u) * 0.10))
        top = {c for _, c in u[:cut]}
        hit = sum(1 for c in picks if c in top)
        daily.append((d, port, bench, len(picks), hit))
    return label, daily


def summarize(label, daily):
    ex = [p - b for _, p, b, n, h in daily]
    cp = 1.0
    for _, p, b, n, h in daily:
        cp *= (1 + p)
    m, t, nd = date_clustered_t(ex)
    jk = jackknife_low(ex)
    k = len(ex) // 2
    m1, t1, _ = date_clustered_t(ex[:k]); m2, t2, _ = date_clustered_t(ex[k:])
    hits = [h for _, _, _, n, h in daily if n > 0]
    return {'label': label, 'days': nd, 'cum': (cp - 1) * 100, 'mean': m * 100,
            't': t, 'jk': jk * 100 if jk is not None else 0,
            'win': sum(1 for x in ex if x > 0) / len(ex) * 100,
            'train': m1 * 100, 'test': m2 * 100,
            'nbuy': sum(n for _, _, _, n, _ in daily) / len(daily),
            'hit': sum(hits) / len(hits) if hits else 0}


def show(rows):
    print(f'\n{"전략":<38}{"일수":>5}{"누적%":>9}{"평균초과%":>10}{"t":>7}'
          f'{"잭나이프%":>10}{"승률%":>7}{"train%":>8}{"test%":>8}{"매수수":>7}{"적중":>6}')
    print('-' * 125)
    for r in rows:
        print(f'{r["label"]:<38}{r["days"]:>5}{r["cum"]:>9.2f}{r["mean"]:>10.4f}'
              f'{(r["t"] or 0):>7.2f}{r["jk"]:>10.4f}{r["win"]:>7.1f}{r["train"]:>8.4f}'
              f'{r["test"]:>8.4f}{r["nbuy"]:>7.2f}{r["hit"]:>6.2f}')


def main(which='all'):
    cache, name, dates = build_cache()
    print(f'채점 {dates[WARM]}~{dates[-1]} · {len(dates)-WARM-1}일')
    rows = [summarize(*run(cache, name, dates, mk_mom20(), 'BASE mom20+RuleH'))]

    T1 = []
    if which in ('all', 't1'):
        for n in (9, 14, 25):
            T1.append((mk_rank(f'rsi{n}', False), f'T1 RSI{n} 과매도 랭킹(오름)'))
            T1.append((mk_rank(f'rsi{n}', True), f'T1 RSI{n} 과매수 랭킹(내림)'))
        T1.append((mk_target('rsi14', 30), 'T1 RSI14 30 근접'))
        T1.append((mk_target('rsi14', 75), 'T1 RSI14 75 근접'))
        for k in (1.5, 2.0, 2.5):
            T1.append((mk_rank(f'pctb{k}', False), f'T1 %B(k={k}) 하단 랭킹'))
            T1.append((mk_rank(f'pctb{k}', True), f'T1 %B(k={k}) 상단 랭킹'))
        T1.append((mk_rank('pctb2.0', True,
                           cond=lambda e, i: (e['bwpct'][i] is not None and e['bwpct'][i] < 0.2)),
                   'T1 스퀴즈(bw<20%)+%B상단'))
        T1.append((mk_rank('bwpct', False,
                           cond=lambda e, i: (e['mom20'][i] or -1) > 0),
                   'T1 스퀴즈 랭킹(mom20>0)'))
        T1.append((mk_rank('rsi14', False,
                           cond=lambda e, i: (e['pctb2.0'][i] is not None and e['pctb2.0'][i] < 0.1)),
                   'T1 고전 평균회귀 %B<0.1+RSI낮은순'))
        T1.append((mk_rank('pctb2.0', True,
                           cond=lambda e, i: (e['rsi14'][i] or 0) > 70),
                   'T1 모멘텀 RSI>70+%B상단'))
        T1.append((mk_rank('mom20', True,
                           cond=lambda e, i: (e['pctb2.0'][i] or -9) > 1.0),
                   'T1 %B>1 돌파 중 mom20 상위'))
        T1.append((mk_rank('mom20', True,
                           cond=lambda e, i: 70 <= (e['rsi14'][i] or 0) <= 85),
                   'T1 RSI14 70~85 중 mom20 상위'))
        for picker, lbl in T1:
            rows.append(summarize(*run(cache, name, dates, picker, lbl)))
        show(rows)

    if which in ('all', 't2'):
        rows2 = [rows[0]]
        F = [
            (lambda e, i: (e['rsi14'][i] or 0) < 70, 'T2 RSI14<70 제외필터'),
            (lambda e, i: (e['rsi14'][i] or 0) < 80, 'T2 RSI14<80'),
            (lambda e, i: (e['rsi14'][i] or 0) < 90, 'T2 RSI14<90 (극단과열만 배제)'),
            (lambda e, i: (e['rsi9'][i] or 0) < 90, 'T2 RSI9<90'),
            (lambda e, i: (e['rsi14'][i] or 0) > 50, 'T2 RSI14>50'),
            (lambda e, i: 50 <= (e['rsi14'][i] or 0) < 85, 'T2 RSI14 50~85'),
            (lambda e, i: (e['pctb2.0'][i] if e['pctb2.0'][i] is not None else 0) < 1.0,
             'T2 %B<1.0 (상단이탈 배제)'),
            (lambda e, i: (e['pctb2.0'][i] if e['pctb2.0'][i] is not None else 0) > 0.8,
             'T2 %B>0.8'),
            (lambda e, i: not (e['bwpct'][i] is not None and e['bwpct'][i] < 0.2
                               and (e['pctb2.0'][i] or 1) < 0.2),
             'T2 스퀴즈+%B<0.2 배제'),
            (lambda e, i: (e['bwpct'][i] is None or e['bwpct'][i] > 0.4),
             'T2 밴드폭 상위60%만'),
        ]
        for filt, lbl in F:
            rows2.append(summarize(*run(cache, name, dates, mk_mom20(filt), lbl)))
        show(rows2)
        rows += rows2[1:]

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f'bbrsi_results_{which}.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'all')
