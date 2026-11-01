#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_breadth_20260818.py — Rule BRD(시장 breadth) 축 백테스트.

검증관이 2026-08-08·08-13·08-14 세 회차 연속 이월한 (a) breadth 축이다.
2026-08-18 KRX OPEN API 서비스 승인(7/8)으로 처음 실행 가능해졌다.

데이터
  backtest/krx_stock_panel.csv  — KRX 개별종목 일별매매 113일(20260303~20260813),
                                  코스피+코스닥 전종목 약 2,760종/일. **가격 파생이 아닌 첫 외부 데이터.**
  backtest/panel_close_0814.csv — ETF 종가 패널 114일(20260303~20260814), 유니버스 187종.
  backtest/kospi_close.csv      — 벤치(코스피). KODEX200(069500)은 ETF 패널에서 읽는다.

주의 — 룩어헤드 금지
  선정일 D 의 픽은 **D 종가까지의 정보만** 쓴다. breadth 도 D 일자 행까지만 사용한다.
  채점은 D→D+1 ETF 종가 수익률, 벤치는 KODEX200 동일구간(v2.3 1차 지표, 비용 0 — v2.8).

한계(보고서에 반드시 명시할 것)
  · KRX `IDX_IND_NM`(업종) 필드가 **전 행 공란**이라 업종별 breadth 는 만들 수 없다.
    유가증권 종목기본정보(`sto/stk_isu_base_info`)가 아직 미승인이라 업종 매핑도 불가.
    따라서 이번 회차의 breadth 는 **시장 전체·시총군·시장구분** 세 절단만 쓴다.
  · KRX 일별매매는 **D+1 지연**이 있다(8/14·8/17·8/18 조회 시 0행, 최신 8/13).
    실전 적용 시 D 종가 시점에 D breadth 를 못 받는다 — 승격하려면 D-1 breadth 로
    재검정하거나 지연을 감안한 래그 변형을 써야 한다. 이 스크립트는 두 경우를 모두 돌린다.
"""
import csv, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import eligible             # noqa: E402  공용 상수 1곳

KRX = os.path.join(HERE, 'krx_stock_panel.csv')
ETF = os.path.join(HERE, 'panel_close_0814.csv')
BENCH = '069500'                                  # KODEX 200
NPICK, MOM = 5, 20
COST = 0.0                                        # v2.8 무비용 (2026-08-14 사용자 지시)


# ─────────────────────────────────────────────── 데이터

def load_etf():
    px, names = defaultdict(dict), {}
    for r in csv.DictReader(open(ETF, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except (TypeError, ValueError):
            continue
        names[r['code']] = r['name']
    return px, names


def load_breadth():
    """일자별 breadth 지표. KRX 개별종목 전체에서 직접 산출."""
    day = defaultdict(list)
    for r in csv.DictReader(open(KRX, encoding='utf-8')):
        try:
            chg = float(r['chg_pct']); cap = float(r['mktcap'] or 0)
        except (TypeError, ValueError):
            continue
        day[r['date']].append((chg, cap, r['market']))
    out = {}
    for d, v in day.items():
        n = len(v)
        up = sum(1 for c, _, _ in v if c > 0)
        big = sorted(v, key=lambda x: -x[1])[:100]          # 시총 상위 100
        sml = sorted(v, key=lambda x: -x[1])[100:]
        ks = [x for x in v if x[2] == 'KOSPI']
        kq = [x for x in v if x[2] == 'KOSDAQ']
        f = lambda z: (sum(1 for c, _, _ in z if c > 0) / len(z)) if z else 0.0
        out[d] = {
            'b': up / n,                                    # 전체 등락 breadth
            'big': f(big), 'sml': f(sml),
            'ks': f(ks), 'kq': f(kq),
            'med': statistics.median([c for c, _, _ in v]),  # 중위 종목 등락률
        }
    return out


# ─────────────────────────────────────────────── 채점 틀

def mom(px, code, d, dates, k=MOM):
    i = dates.index(d)
    if i < k:
        return None
    a, b = px[code].get(dates[i - k]), px[code].get(d)
    if not a or not b:
        return None
    return (b / a - 1) * 100


def rule_h(px, code, d, dates):
    """v2.1 이중 과열필터 — 전일 +10% 초과 또는 3일 누적 +20% 초과 제외."""
    i = dates.index(d)
    if i < 3:
        return False
    c0, c1, c3 = px[code].get(d), px[code].get(dates[i - 1]), px[code].get(dates[i - 3])
    if not (c0 and c1 and c3):
        return False
    return (c0 / c1 - 1) * 100 > 10 or (c0 / c3 - 1) * 100 > 20


def ranked(px, names, d, dates):
    """D 종가 기준 mom20 내림차순 후보(Rule H·파생·현금성 제외)."""
    out = []
    for code in px:
        if not eligible(names.get(code, '')):
            continue
        m = mom(px, code, d, dates)
        if m is None or rule_h(px, code, d, dates):
            continue
        out.append((m, code))
    out.sort(reverse=True)
    return out


def fwd(px, code, d, nxt):
    a, b = px[code].get(d), px[code].get(nxt)
    return None if not (a and b) else (b / a - 1) * 100


def run(select, px, names, dates, brd):
    """select(cands, d, brd) -> 코드 5종. 반환: 일별 (날짜, 벤치대비 %p)."""
    res = []
    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        bm = fwd(px, BENCH, d, nxt)
        if bm is None:
            continue
        cands = ranked(px, names, d, dates)
        if len(cands) < NPICK:
            continue
        picks = select(cands, d, brd)
        rs = [fwd(px, c, d, nxt) for c in picks]
        rs = [x for x in rs if x is not None]
        if len(rs) < NPICK:
            continue
        res.append((d, sum(rs) / len(rs) - COST - bm))
    return res


def stat(res, label):
    v = [x for _, x in res]
    if not v:
        return None
    n = len(v)
    m = sum(v) / n
    sd = statistics.stdev(v) if n > 1 else 0.0
    t = m / (sd / n ** 0.5) if sd else 0.0
    h = n // 2
    tr = sum(x for _, x in res[:h]) / h if h else 0.0
    te = sum(x for _, x in res[h:]) / (n - h) if n - h else 0.0
    win = sum(1 for x in v if x > 0) / n * 100
    # 잭나이프: 1개씩 빼고 재계산한 평균들의 최솟값
    jk = min((sum(v) - x) / (n - 1) for x in v) if n > 2 else m
    return {'label': label, 'n': n, 'mean': m, 't': t, 'train': tr, 'test': te,
            'win': win, 'jk': jk}


def show(s, base=None):
    if not s:
        print(f'  {"?":40s} 표본 없음'); return
    d = '' if base is None else f'  Δ{s["mean"] - base["mean"]:+.4f}'
    print(f'  {s["label"]:40s} n={s["n"]:3d} full{s["mean"]:+.4f} '
          f'train{s["train"]:+.4f} test{s["test"]:+.4f} 승률{s["win"]:4.1f}% '
          f'jk{s["jk"]:+.4f} t{s["t"]:+.2f}{d}')


# ─────────────────────────────────────────────── 변형

def sel_base(cands, d, brd):
    return [c for _, c in cands[:NPICK]]


def make_gate(key, thr, lag, low_is_reversal=True):
    """BRD1 레짐 게이트 — breadth 가 임계 미만인 날은 mom20 하위(역모멘텀)로 전환."""
    def f(cands, d, brd):
        b = brd.get(lagged(d, lag))
        if b is None:
            return sel_base(cands, d, brd)
        narrow = b[key] < thr
        if narrow and low_is_reversal:
            return [c for _, c in cands[-NPICK:]]
        return [c for _, c in cands[:NPICK]]
    return f


def make_spread(key_a, key_b, thr, lag):
    """BRD3/4 스프레드 게이트 — (대형−소형) 또는 (코스피−코스닥) breadth 우위 시 역전."""
    def f(cands, d, brd):
        b = brd.get(lagged(d, lag))
        if b is None:
            return sel_base(cands, d, brd)
        if (b[key_a] - b[key_b]) > thr:
            return [c for _, c in cands[-NPICK:]]
        return [c for _, c in cands[:NPICK]]
    return f


def make_trend(win, thr, lag):
    """BRD2 breadth 추세 — 최근 win 일 평균 breadth 가 thr 미만이면 역전."""
    def f(cands, d, brd):
        ds = [x for x in BRD_DATES if x <= lagged(d, lag)][-win:]
        if len(ds) < win:
            return sel_base(cands, d, brd)
        avg = sum(brd[x]['b'] for x in ds) / win
        if avg < thr:
            return [c for _, c in cands[-NPICK:]]
        return [c for _, c in cands[:NPICK]]
    return f


def make_narrow_rally(thr, lag):
    """BRD5 좁은 랠리 — 지수는 올랐는데(중위종목 등락률<0) breadth 가 낮으면 역전."""
    def f(cands, d, brd):
        b = brd.get(lagged(d, lag))
        if b is None:
            return sel_base(cands, d, brd)
        if b['b'] < thr and b['med'] < 0:
            return [c for _, c in cands[-NPICK:]]
        return [c for _, c in cands[:NPICK]]
    return f


BRD_DATES = []


def lagged(d, lag):
    """lag=0 → D 당일 breadth, lag=1 → D-1 breadth(KRX D+1 지연 반영)."""
    ds = [x for x in BRD_DATES if x <= d]
    if not ds:
        return d
    i = len(ds) - 1 - lag
    return ds[max(i, 0)]


def main():
    px, names = load_etf()
    brd = load_breadth()
    global BRD_DATES
    BRD_DATES = sorted(brd)
    dates = sorted({d for c in px for d in px[c]})
    dates = [d for d in dates if d >= BRD_DATES[0]]
    print(f'ETF 패널 {len(dates)}일 {dates[0]}~{dates[-1]} · 유니버스 {len(px)}종')
    print(f'KRX breadth {len(BRD_DATES)}일 {BRD_DATES[0]}~{BRD_DATES[-1]} '
          f'(평균 등락비율 {sum(v["b"] for v in brd.values())/len(brd):.3f})\n')

    base = stat(run(sel_base, px, names, dates, brd), 'BASE mom20+RuleH')
    show(base)
    print()

    variants = []
    for lag in (0, 1):
        tag = 'D' if lag == 0 else 'D-1'
        for thr in (0.35, 0.40, 0.45, 0.50):
            variants.append((f'BRD1 전체breadth<{thr} 역전 [{tag}]',
                             make_gate('b', thr, lag)))
        for thr in (0.40, 0.45):
            variants.append((f'BRD2 5일평균breadth<{thr} 역전 [{tag}]',
                             make_trend(5, thr, lag)))
        for thr in (0.05, 0.10):
            variants.append((f'BRD3 (대형-소형)breadth>{thr} 역전 [{tag}]',
                             make_spread('big', 'sml', thr, lag)))
        for thr in (0.03, 0.08):
            variants.append((f'BRD4 (코스피-코스닥)breadth>{thr} 역전 [{tag}]',
                             make_spread('ks', 'kq', thr, lag)))
        variants.append((f'BRD5 좁은랠리(b<0.45 & 중위<0) 역전 [{tag}]',
                         make_narrow_rally(0.45, lag)))

    rows = []
    for label, f in variants:
        s = stat(run(f, px, names, dates, brd), label)
        show(s, base)
        if s:
            rows.append(s)

    print('\n--- 3분할+잭나이프 가드 (full·train·test 전부 baseline 초과 AND jk>0) ---')
    ok = [s for s in rows
          if s['mean'] > base['mean'] and s['train'] > base['train']
          and s['test'] > base['test'] and s['jk'] > 0]
    if ok:
        for s in ok:
            show(s, base)
        print('\n※ 통과 변형이 있으나 113일 소표본이다. 8/13 절차에 따라 더 긴 별도 패널에서')
        print('  재검정하기 전에는 승격하지 않는다(8/14 EWM 이 정확히 이 관문에서 걸렸다).')
    else:
        print('  통과 0건 — Rule BRD 기각.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
