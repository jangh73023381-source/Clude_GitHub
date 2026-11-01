# -*- coding: utf-8 -*-
"""2026-08-04 루프 3~5단계 — distinct 5축.

동기: 2026-08-03 채점에서 트랙 A는 P&L 1차지표로 크게 이겼으나(코스피 대비 +4.683%p,
KODEX200 대비 +8.486%p) **보조 이진은 0/5**(순위 39·54·56·64·92/187)였다. 즉 "지수보다
덜 빠졌지만 그날의 상위10% 승자군에는 못 들었다". 방어 고착 픽의 구조적 한계가 급락일에도
반복되는지, 다른 정보축으로 상위군을 잡을 수 있는지 검정한다.

 · iteration 1 Rule AC — 모멘텀 **가속도**(단기 mom이 장기 mom 대비 얼마나 빠른가).
   크기(mom20)·스킵(SK, 기각)과 달리 2차 미분 성격이라 distinct.
 · iteration 2 Rule TR — 20일 중 **상승일 비율**(추세 일관성). 크기가 아니라 빈도.
 · iteration 3 Rule DV — **하방편차 정규화**(Sortino식). 총변동성 정규화(VR, 기각)와 달리
   상방 변동은 벌하지 않는다.
 · iteration 4 Rule HL — **일중 종가위치** (close-low)/(high-low) 20일 평균. 종가 패널에는
   없는 OHLC 정보축(장중 매수강도).
 · iteration 5 Rule RO — **랭크 오프셋**(top5 대신 6~10위·11~15위). 픽 개수(PC, 기각)가
   아니라 '분위 위치'를 옮기는 축.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과일 때만 후보 승격.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용. 조회 전용.
"""
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0803.csv')
B.MINP = 0

OHLC = os.path.join(HERE, 'panel_ohlc_2y.csv')
_hl = {}


def load_hl():
    if _hl:
        return _hl
    for r in csv.DictReader(open(OHLC, encoding='utf-8')):
        try:
            h, lo, c = float(r['high']), float(r['low']), float(r['close'])
        except (KeyError, ValueError):
            continue
        if h <= lo:
            continue
        _hl.setdefault(r['code'], {})[r['date']] = (c - lo) / (h - lo)
    return _hl


def rets(px, c, d, di, dates, k):
    """D까지 최근 k거래일 일간수익률 리스트."""
    i = di[d]
    if i < k:
        return []
    out = []
    for j in range(i - k + 1, i + 1):
        a, b = px[c].get(dates[j - 1]), px[c].get(dates[j])
        if a and b:
            out.append(b / a - 1.0)
    return out


# ---------------------------------------------------------------- iteration 1
def ac_sel(cand, px=None, d=None, di=None, dates=None, short=5, w=1.0, **_):
    """Rule AC — 가속도 = mom(short) - short/20 * mom20. 양수면 최근 구간이 더 빠르다."""
    sc = []
    for x in cand:
        ms = B.mom(px, x['code'], d, di, dates, short)
        if ms is None:
            continue
        acc = ms - (short / 20.0) * x['mom']
        sc.append((x['mom'] + w * acc, x['code']))
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(key=lambda t: -t[0])
    return [c for _, c in sc[:5]]


# ---------------------------------------------------------------- iteration 2
def tr_sel(cand, px=None, d=None, di=None, dates=None, k=20, mode='rank', **_):
    """Rule TR — 20일 중 상승일 비율. mode=rank(단독 랭킹) / filter(비율 상위50%만)."""
    sc = []
    for x in cand:
        rr = rets(px, x['code'], d, di, dates, k)
        if len(rr) < k // 2:
            continue
        up = sum(1 for r in rr if r > 0) / len(rr)
        sc.append((up, x))
    if len(sc) < 10:
        return B.base_sel(cand)
    if mode == 'rank':
        sc.sort(key=lambda t: -t[0])
        return [x['code'] for _, x in sc[:5]]
    sc.sort(key=lambda t: -t[0])
    keep = [x for _, x in sc[:max(5, len(sc) // 2)]]
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 3
def dv_sel(cand, px=None, d=None, di=None, dates=None, k=20, floor=0.004, **_):
    """Rule DV — mom20 / 하방편차(음수 수익률만의 RMS). 상방 변동은 벌하지 않는다."""
    sc = []
    for x in cand:
        rr = rets(px, x['code'], d, di, dates, k)
        if len(rr) < k // 2:
            continue
        neg = [r for r in rr if r < 0]
        dd = (sum(r * r for r in neg) / len(rr)) ** 0.5 if neg else 0.0
        sc.append((x['mom'] / max(dd, floor), x['code']))
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(key=lambda t: -t[0])
    return [c for _, c in sc[:5]]


# ---------------------------------------------------------------- iteration 4
def hl_sel(cand, px=None, d=None, di=None, dates=None, k=20, mode='filter', **_):
    """Rule HL — 일중 종가위치 20일 평균. mode=rank / filter(상위50% 안에서 mom20)."""
    tbl = load_hl()
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
        sc.append((sum(v) / len(v), x))
    if len(sc) < 10:
        return B.base_sel(cand)
    sc.sort(key=lambda t: -t[0])
    if mode == 'rank':
        return [x['code'] for _, x in sc[:5]]
    keep = [x for _, x in sc[:max(5, len(sc) // 2)]]
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 5
def ro_sel(cand, off=5, **_):
    """Rule RO — mom20 랭크 오프셋. off=0이 baseline."""
    srt = sorted(cand, key=lambda x: -x['mom'])
    sl = srt[off:off + 5]
    if len(sl) < 5:
        sl = srt[:5]
    return [x['code'] for x in sl]


AXES = {
    'AC': ('iteration 1 · Rule AC 모멘텀 가속도', [
        ('AC s5 w1.0  (mom20 + 가속도)', ac_sel, {'short': 5, 'w': 1.0}),
        ('AC s5 w2.0', ac_sel, {'short': 5, 'w': 2.0}),
        ('AC s10 w1.0', ac_sel, {'short': 10, 'w': 1.0}),
        ('AC s10 w2.0', ac_sel, {'short': 10, 'w': 2.0}),
    ]),
    'TR': ('iteration 2 · Rule TR 상승일 비율', [
        ('TR k20 rank (비율 단독 랭킹)', tr_sel, {'k': 20, 'mode': 'rank'}),
        ('TR k20 filter (상위50% 안 mom20)', tr_sel, {'k': 20, 'mode': 'filter'}),
        ('TR k40 rank', tr_sel, {'k': 40, 'mode': 'rank'}),
        ('TR k40 filter', tr_sel, {'k': 40, 'mode': 'filter'}),
    ]),
    'DV': ('iteration 3 · Rule DV 하방편차 정규화', [
        ('DV k20', dv_sel, {'k': 20}),
        ('DV k40', dv_sel, {'k': 40}),
        ('DV k60', dv_sel, {'k': 60}),
    ]),
    'HL': ('iteration 4 · Rule HL 일중 종가위치', [
        ('HL k20 filter', hl_sel, {'k': 20, 'mode': 'filter'}),
        ('HL k20 rank', hl_sel, {'k': 20, 'mode': 'rank'}),
        ('HL k60 filter', hl_sel, {'k': 60, 'mode': 'filter'}),
        ('HL k60 rank', hl_sel, {'k': 60, 'mode': 'rank'}),
    ]),
    'RO': ('iteration 5 · Rule RO 랭크 오프셋', [
        ('RO off5  (6~10위)', ro_sel, {'off': 5}),
        ('RO off10 (11~15위)', ro_sel, {'off': 10}),
        ('RO off15 (16~20위)', ro_sel, {'off': 15}),
    ]),
}


def jackknife(recs, folds=5):
    """구간 잭나이프 — 1/folds 구간씩 빼고 평균. 하한이 양수여야 통과."""
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
    promoted = []
    for key in want:
        title, variants = AXES[key]
        print(f'\n=== {title} ===')
        print(f"{'변형':34s} {'전체':>9s} {'train':>9s} {'test':>9s} {'잭나이프하한':>11s}  판정")
        print('-' * 92)
        for label, fn, kw in variants:
            r = B.run(fn, px, name, dates, di, fo, ins, **kw)
            if not r:
                print(f'{label:34s} — 표본 없음')
                continue
            hh = len(r) // 2
            full, tr, te = (statistics.mean(r), statistics.mean(r[:hh]),
                            statistics.mean(r[hh:]))
            ok = full > bfull and tr > btr and te > bte
            jk = jackknife(r) if ok else None
            js = f'{jk:+11.4f}' if jk is not None else f'{"—":>11s}'
            if ok:
                verdict = '후보승격' if (jk is not None and jk > bfull) else '가드통과·잭나이프미달'
                if jk is not None and jk > bfull:
                    promoted.append((label, full, jk))
            else:
                verdict = '기각(3분할 미통과)'
            print(f'{label:34s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} {js}  {verdict}')

    print('\n' + '=' * 92)
    if promoted:
        for label, full, jk in promoted:
            print(f'  [후보승격] {label}  full {full:+.4f} · 잭나이프하한 {jk:+.4f}')
    else:
        print('  후보승격 0건 — 전 변형 기각. 확정방법 유지.')


if __name__ == '__main__':
    main()
