# -*- coding: utf-8 -*-
"""2026-08-05 루프 3~5단계 — distinct 5축.

동기: 2026-08-04 채점(D=20260804)에서 트랙 A는 P&L 코스피 대비 -0.321%p·KODEX200 대비
+0.065%p 로 사실상 벤치 동률, **보조 이진 0/5**(순위 143·180·37·183·167/187)였다.
전일(8/3)의 '상위군 미도달'과 달리 이번엔 상승일(코스피 +1.62%)에 픽이 벤치를 겨우 따라간
형태다. 2026-08-04 검증관이 지정한 다음 회차 우선 시도축을 그대로 검정한다.

 · iteration 1 Rule WD — DV(하방편차)의 **윈저화 + 랭크블렌드**. 어제 DV k60 이 잭나이프는
   통과했으나 일별 우위 21.7%(극단일 의존)였다. 극단값을 자르고 mom 랭크와 섞어 의존을 낮춘다.
 · iteration 2 Rule BT — **이진 목표 전용 서브랭킹(2트랙)**. 픽5 중 일부를 '과거 상위10%
   진입 빈도'로 채운다. P&L 축과 분리해 상위군 도달만 노리는 구조.
 · iteration 3 Rule DP — **Omega 비(상방합/하방합)**. DV(mom/하방편차)와 달리 분자가 mom이
   아니라 실현 상방합이다 — 크기가 아니라 상·하방 비대칭 자체를 본다.
 · iteration 4 Rule GA — **갭 성향**(시가-전일종가) k일 평균. HL(종가위치)과 같은 OHLC
   패널을 쓰지만 장중이 아니라 **개장 갭** 축이라 distinct.
 · iteration 5 Rule EM — **지수 초과 모멘텀**(ETF mom20 − 벤치 mom20) 랭킹. CR(실현상관
   분산, 기각)과 달리 상관이 아니라 초과폭 자체를 랭킹축으로 쓴다.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과일 때만 후보 승격 + 잭나이프 하한 > baseline.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용. 조회 전용.
"""
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0804.csv')
B.MINP = 0

OHLC = os.path.join(HERE, 'panel_ohlc_2y.csv')
_gap = {}


def load_gap():
    """코드별 {date: (시가/전일종가 - 1)} — 개장 갭."""
    if _gap:
        return _gap
    rows = {}
    for r in csv.DictReader(open(OHLC, encoding='utf-8')):
        try:
            rows.setdefault(r['code'], {})[r['date']] = (float(r['open']),
                                                         float(r['close']))
        except (KeyError, ValueError):
            continue
    for c, t in rows.items():
        ds = sorted(t)
        out = {}
        for i in range(1, len(ds)):
            pc = t[ds[i - 1]][1]
            if pc > 0:
                out[ds[i]] = t[ds[i]][0] / pc - 1.0
        _gap[c] = out
    return _gap


def rets(px, c, d, di, dates, k):
    i = di[d]
    if i < k:
        return []
    out = []
    for j in range(i - k + 1, i + 1):
        a, b = px[c].get(dates[j - 1]), px[c].get(dates[j])
        if a and b:
            out.append(b / a - 1.0)
    return out


def _ranks(pairs):
    """[(값, key)] → {key: 랭크(1=최고)}"""
    pairs = sorted(pairs, key=lambda t: -t[0])
    return {k: i + 1 for i, (_, k) in enumerate(pairs)}


# ---------------------------------------------------------------- iteration 1
def wd_sel(cand, px=None, d=None, di=None, dates=None, k=60, wq=0.05,
           blend=0.5, **_):
    """Rule WD — 윈저화 하방편차 정규화 + mom 랭크 블렌드."""
    dv = []
    for x in cand:
        rr = rets(px, x['code'], d, di, dates, k)
        if len(rr) < k // 2:
            continue
        rr = sorted(rr)
        cut = max(1, int(len(rr) * wq))
        lo_v, hi_v = rr[cut - 1], rr[-cut]
        rw = [min(max(r, lo_v), hi_v) for r in rr]
        neg = [r for r in rw if r < 0]
        dd = (sum(r * r for r in neg) / len(rw)) ** 0.5 if neg else 0.0
        dv.append((x['mom'] / max(dd, 0.004), x['code']))
    if len(dv) < 5:
        return B.base_sel(cand)
    rd = _ranks(dv)
    rm = _ranks([(x['mom'], x['code']) for x in cand])
    sc = [(blend * rd[c] + (1 - blend) * rm.get(c, len(rm)), c) for _, c in dv]
    sc.sort(key=lambda t: t[0])
    return [c for _, c in sc[:5]]


# ---------------------------------------------------------------- iteration 2
def bt_sel(cand, px=None, d=None, di=None, dates=None, k=60, n_bin=2, **_):
    """Rule BT — mom20 상위 (5-n_bin)종 + '과거 상위10% 진입 빈도' 상위 n_bin종."""
    i = di[d]
    win = dates[max(1, i - k + 1):i + 1]
    codes = [x['code'] for x in cand]
    freq = {c: 0 for c in codes}
    for j, dt in enumerate(win):
        prev = dates[di[dt] - 1]
        day = []
        for c in codes:
            a, b = px[c].get(prev), px[c].get(dt)
            if a and b:
                day.append((b / a - 1.0, c))
        if len(day) < 20:
            continue
        day.sort(key=lambda t: -t[0])
        top = max(1, len(day) // 10)
        for _, c in day[:top]:
            freq[c] += 1
    base = [x['code'] for x in sorted(cand, key=lambda x: -x['mom'])]
    out = base[:5 - n_bin]
    for c in sorted(codes, key=lambda c: -freq[c]):
        if len(out) >= 5:
            break
        if c not in out:
            out.append(c)
    return out[:5]


# ---------------------------------------------------------------- iteration 3
def dp_sel(cand, px=None, d=None, di=None, dates=None, k=20, **_):
    """Rule DP — Omega 비 = 양수수익 합 / |음수수익 합|."""
    sc = []
    for x in cand:
        rr = rets(px, x['code'], d, di, dates, k)
        if len(rr) < k // 2:
            continue
        up = sum(r for r in rr if r > 0)
        dn = -sum(r for r in rr if r < 0)
        sc.append((up / max(dn, 1e-4), x['code']))
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(key=lambda t: -t[0])
    return [c for _, c in sc[:5]]


# ---------------------------------------------------------------- iteration 4
def ga_sel(cand, px=None, d=None, di=None, dates=None, k=20, mode='filter',
           sign=1, **_):
    """Rule GA — 개장 갭 k일 평균. sign=+1 갭 강한 쪽, -1 갭 약한 쪽."""
    tbl = load_gap()
    i = di[d]
    win = dates[max(0, i - k + 1):i + 1]
    sc = []
    for x in cand:
        t = tbl.get(x['code'])
        if not t:
            continue
        v = [t[dt] for dt in win if dt in t]
        if len(v) < k // 2:
            continue
        sc.append((sign * sum(v) / len(v), x))
    if len(sc) < 10:
        return B.base_sel(cand)
    sc.sort(key=lambda t: -t[0])
    if mode == 'rank':
        return [x['code'] for _, x in sc[:5]]
    keep = [x for _, x in sc[:max(5, len(sc) // 2)]]
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 5
def em_sel(cand, px=None, d=None, di=None, dates=None, k=20, **_):
    """Rule EM — 지수 초과 모멘텀 (ETF mom_k − 벤치 mom_k)."""
    bm = B.mom(px, B.BENCH, d, di, dates, k)
    if bm is None:
        return B.base_sel(cand)
    sc = []
    for x in cand:
        m = B.mom(px, x['code'], d, di, dates, k)
        if m is None:
            continue
        sc.append((m - bm, x['code']))
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(key=lambda t: -t[0])
    return [c for _, c in sc[:5]]


AXES = {
    'WD': ('iteration 1 · Rule WD 윈저화 하방편차 + 랭크블렌드', [
        ('WD k60 wq5% blend0.5', wd_sel, {'k': 60, 'wq': 0.05, 'blend': 0.5}),
        ('WD k60 wq10% blend0.5', wd_sel, {'k': 60, 'wq': 0.10, 'blend': 0.5}),
        ('WD k60 wq5% blend1.0 (순수 윈저DV)', wd_sel,
         {'k': 60, 'wq': 0.05, 'blend': 1.0}),
        ('WD k20 wq5% blend0.5', wd_sel, {'k': 20, 'wq': 0.05, 'blend': 0.5}),
    ]),
    'BT': ('iteration 2 · Rule BT 이진 전용 서브랭킹(2트랙)', [
        ('BT k60 n2 (mom3 + 빈도2)', bt_sel, {'k': 60, 'n_bin': 2}),
        ('BT k60 n1', bt_sel, {'k': 60, 'n_bin': 1}),
        ('BT k20 n2', bt_sel, {'k': 20, 'n_bin': 2}),
    ]),
    'DP': ('iteration 3 · Rule DP Omega 비(상방합/하방합)', [
        ('DP k20', dp_sel, {'k': 20}),
        ('DP k60', dp_sel, {'k': 60}),
    ]),
    'GA': ('iteration 4 · Rule GA 개장 갭 성향', [
        ('GA k20 filter (+)', ga_sel, {'k': 20, 'mode': 'filter', 'sign': 1}),
        ('GA k20 filter (-)', ga_sel, {'k': 20, 'mode': 'filter', 'sign': -1}),
        ('GA k20 rank (+)', ga_sel, {'k': 20, 'mode': 'rank', 'sign': 1}),
        ('GA k60 filter (+)', ga_sel, {'k': 60, 'mode': 'filter', 'sign': 1}),
    ]),
    'EM': ('iteration 5 · Rule EM 지수 초과 모멘텀', [
        ('EM k20', em_sel, {'k': 20}),
        ('EM k60', em_sel, {'k': 60}),
    ]),
}


def jackknife(recs, folds=5):
    n = len(recs)
    if n < folds * 3:
        return None
    out = []
    w = n // folds
    for f in range(folds):
        rest = recs[:f * w] + recs[(f + 1) * w if f < folds - 1 else n:]
        if rest:
            out.append(statistics.mean(rest))
    return min(out) if out else None


def tstat(a, b):
    """페어 차이 t값."""
    d = [x - y for x, y in zip(a, b)]
    if len(d) < 3:
        return None
    sd = statistics.stdev(d)
    if sd == 0:
        return None
    return statistics.mean(d) / (sd / len(d) ** 0.5)


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · 코드 {len(px)}종')

    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'\n[baseline] mom20+RuleH  n={len(base)}일  '
          f'full {bfull:+.4f} · train {btr:+.4f} · test {bte:+.4f}  (%p/일, vs KODEX200)')

    want = sys.argv[1:] or list(AXES)
    for key in want:
        title, variants = AXES[key]
        print(f'\n=== {title} ===')
        print(f"{'변형':32s} {'전체':>9s} {'train':>9s} {'test':>9s} "
              f"{'잭나이프':>9s} {'t':>6s}  판정")
        print('-' * 96)
        for label, fn, kw in variants:
            r = B.run(fn, px, name, dates, di, fo, ins, **kw)
            if not r or len(r) != len(base):
                print(f'{label:32s} — 표본 불일치 {len(r)} vs {len(base)}')
                continue
            hh = len(r) // 2
            full, tr, te = (statistics.mean(r), statistics.mean(r[:hh]),
                            statistics.mean(r[hh:]))
            ok = full > bfull and tr > btr and te > bte
            jk = jackknife(r) if ok else None
            t = tstat(r, base)
            js = f'{jk:+9.4f}' if jk is not None else f'{"—":>9s}'
            ts = f'{t:+6.2f}' if t is not None else f'{"—":>6s}'
            if ok:
                verdict = ('후보승격' if (jk is not None and jk > bfull)
                           else '가드통과·잭나이프미달')
            else:
                verdict = '기각(3분할 미통과)'
            print(f'{label:32s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} '
                  f'{js} {ts}  {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
