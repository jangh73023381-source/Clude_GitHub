#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_sector_breadth_20260819.py — Rule SBD(업종별 breadth) 축 백테스트.

검증관이 2026-08-08·08-13·08-14·08-18 네 회차 연속 이월한 (a) '업종별 breadth' 축이다.
2026-08-18 에 업종 매핑 2종(yfinance sector · DART induty_code)을 수집 완료해
이번 회차(D=20260818, iteration 1)에서 처음 실행 가능해졌다.

2026-08-18 의 Rule BRD 는 **시장 전체·시총군·시장구분** 세 절단만 썼고 전부 기각됐다.
이번 축은 그것과 구별된다 — 절단 기준이 **업종**이고, 지표가 수준(level)이 아니라
**업종 간 분산·참여폭·집중도**다.

데이터
  backtest/krx_stock_panel.csv    — KRX 개별종목 일별매매 114일(20260303~20260814)
  backtest/stock_sector_yf.csv    — yfinance sector 11종 (2,279종 확보)
  backtest/stock_sector_dart.csv  — DART induty_code (2,650종 확보) → **2자리 절단**
  backtest/panel_close_0818.csv   — ETF 종가 패널, 유니버스 187종
  BENCH = KODEX200(069500), COST = 0 (v2.8)

★ 실전 조달 가능성 (CLAUDE.md §4-5)
  KRX OPEN API 는 D 일자를 D+1 장중에 공개한다. 선정 시각 T 06:00 에 쓸 수 있는 것은
  **[D-1] breadth 뿐**이므로 이 스크립트는 lag=1 만 돌린다. [D] 변형은 아예 만들지 않는다.

★ R3(정의 교체 재현) 내장
  같은 개념을 yfinance sector 와 DART 2자리 두 분류로 각각 계산한다.
  **한쪽에서만 통과하는 변형은 채택하지 않는다.**

한계
  · 업종 매핑 커버리지가 소스마다 다르다(YF 82.5% · DART 95.9%). breadth 는 종목 수
    비율이므로 **커버 집합 안에서만** 비율을 내고, 5종목 미만 업종은 버린다.
  · 표본 약 110일로 짧다. 통과해도 즉시 승격하지 않고 장기 패널 재검정을 요구한다.
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import eligible                      # noqa: E402

KRX = os.environ.get('SBD_KRX') or os.path.join(HERE, 'krx_stock_panel.csv')
ETF_OVERRIDE = os.environ.get('SBD_ETF')
YF = os.path.join(HERE, 'stock_sector_yf.csv')
DART = os.path.join(HERE, 'stock_sector_dart.csv')
BENCH = '069500'
NPICK, MOM = 5, 20
COST = 0.0
MIN_SEC = 5                       # 업종당 최소 종목 수


def newest_etf_panel():
    if ETF_OVERRIDE:
        return ETF_OVERRIDE
    c = sorted(f for f in os.listdir(HERE)
               if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(HERE, c[-1])


def tail_test(s, base):
    """R5 꼬리 기여도 — 상위 k일 제거 평균·중앙값 (CLAUDE.md §4-4 R5)."""
    bmap = dict(base['res'])
    diff = sorted((v - bmap[d] for d, v in s['res'] if d in bmap), reverse=True)
    n = len(diff)
    out = {'mean': sum(diff) / n, 'median': statistics.median(diff)}
    for k in (1, 3, 5, 10):
        out[f'ex{k}'] = sum(diff[k:]) / (n - k) if n > k else 0.0
    return out


# ─────────────────────────────────────────────── 데이터

def load_etf(path):
    px, names = defaultdict(dict), {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except (TypeError, ValueError):
            continue
        names[r['code']] = r['name']
    return px, names


def load_sector_maps():
    yf = {}
    for r in csv.DictReader(open(YF, encoding='utf-8')):
        s = (r.get('sector') or '').strip()
        if s:
            yf[r['code']] = s
    dart = {}
    for r in csv.DictReader(open(DART, encoding='utf-8')):
        c = (r.get('induty_code') or '').strip()
        if len(c) >= 2:
            dart[r['code']] = c[:2]          # 2자리 절단 (2026-08-18 로그 지시)
    return {'YF': yf, 'DART': dart}


def load_sector_breadth(smap):
    """일자 → {업종: (상승비율, 종목수)} + 파생 지표."""
    day = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(KRX, encoding='utf-8')):
        s = smap.get(r['code'])
        if not s:
            continue
        try:
            day[r['date']][s].append(float(r['chg_pct']))
        except (TypeError, ValueError):
            continue

    out = {}
    for d, secs in day.items():
        rows = [(s, sum(1 for c in v if c > 0) / len(v), len(v))
                for s, v in secs.items() if len(v) >= MIN_SEC]
        if len(rows) < 5:
            continue
        br = [b for _, b, _ in rows]
        ups = {s: b * n for s, b, n in rows}                 # 업종별 상승 종목 수
        tot = sum(ups.values()) or 1.0
        hhi = sum((u / tot) ** 2 for u in ups.values())      # 상승종목의 업종 집중도
        lead = max(rows, key=lambda x: x[1])[0]
        out[d] = {
            'disp': statistics.pstdev(br),                   # 업종 간 breadth 분산
            'part': sum(1 for b in br if b > 0.5) / len(br),  # 참여 업종 비율
            'hhi': hhi * len(rows),                          # 업종 수로 정규화된 집중도
            'lead': lead,
            'nsec': len(rows),
        }
    return out


# ─────────────────────────────────────────────── 채점 틀 (bt_breadth_20260818 과 동일)

def mom(px, code, d, dates, k=MOM):
    i = dates.index(d)
    if i < k:
        return None
    a, b = px[code].get(dates[i - k]), px[code].get(d)
    return None if not (a and b) else (b / a - 1) * 100


def rule_h(px, code, d, dates):
    i = dates.index(d)
    if i < 3:
        return False
    c0, c1, c3 = px[code].get(d), px[code].get(dates[i - 1]), px[code].get(dates[i - 3])
    if not (c0 and c1 and c3):
        return False
    return (c0 / c1 - 1) * 100 > 10 or (c0 / c3 - 1) * 100 > 20


def ranked(px, names, d, dates):
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


def run(select, px, names, dates, sb, sb_dates):
    res = []
    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        bm = fwd(px, BENCH, d, nxt)
        if bm is None:
            continue
        cands = ranked(px, names, d, dates)
        if len(cands) < NPICK:
            continue
        picks = select(cands, d, sb, sb_dates)
        rs = [x for x in (fwd(px, c, d, nxt) for c in picks) if x is not None]
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
    k = n // 3
    f1 = sum(v[:k]) / k if k else 0.0
    f2 = sum(v[k:2 * k]) / k if k else 0.0
    f3 = sum(v[2 * k:]) / (n - 2 * k) if n - 2 * k else 0.0
    h = n // 2
    tr = sum(v[:h]) / h if h else 0.0
    te = sum(v[h:]) / (n - h) if n - h else 0.0
    win = sum(1 for x in v if x > 0) / n * 100
    jk = min((sum(v) - x) / (n - 1) for x in v) if n > 2 else m
    return {'label': label, 'n': n, 'mean': m, 't': t, 'train': tr, 'test': te,
            'f1': f1, 'f2': f2, 'f3': f3, 'win': win, 'jk': jk, 'v': v, 'res': res}


def show(s, base=None):
    if not s:
        print('  (표본 없음)')
        return
    d = '' if base is None else f'  Δ{s["mean"] - base["mean"]:+.4f}'
    print(f'  {s["label"]:44s} n={s["n"]:3d} full{s["mean"]:+.4f} '
          f'f1{s["f1"]:+.3f} f2{s["f2"]:+.3f} f3{s["f3"]:+.3f} '
          f'승률{s["win"]:4.1f}% jk{s["jk"]:+.4f} t{s["t"]:+.2f}{d}')


# ─────────────────────────────────────────────── 변형 (lag=1 고정)

def lagged(d, sb_dates):
    """[D-1] — KRX D+1 지연을 반영한다. D 당일 breadth 는 선정 시각에 존재하지 않는다."""
    ds = [x for x in sb_dates if x <= d]
    if len(ds) < 2:
        return None
    return ds[-2]


def sel_base(cands, d, sb, sb_dates):
    return [c for _, c in cands[:NPICK]]


def _gate(fn):
    def f(cands, d, sb, sb_dates):
        p = lagged(d, sb_dates)
        b = sb.get(p) if p else None
        if b is None:
            return sel_base(cands, d, sb, sb_dates)
        return ([c for _, c in cands[-NPICK:]] if fn(b, p, sb, sb_dates)
                else [c for _, c in cands[:NPICK]])
    return f


def sbd1(thr):    # 업종 간 breadth 분산이 낮다 = 업종 구분 없이 동조 → 모멘텀 무력
    return _gate(lambda b, p, sb, ds: b['disp'] < thr)


def sbd2(thr):    # 참여 업종 비율이 낮다 = 좁은 장세
    return _gate(lambda b, p, sb, ds: b['part'] < thr)


def sbd3(thr):    # 상승종목의 업종 집중도가 낮다 = 리더십 부재
    return _gate(lambda b, p, sb, ds: b['hhi'] < thr)


def sbd4():       # 선도 업종이 이틀 연속 같지 않다 = 회전이 불안정
    def fn(b, p, sb, ds):
        i = ds.index(p)
        if i < 1:
            return False
        prev = sb.get(ds[i - 1])
        return prev is not None and prev['lead'] != b['lead']
    return _gate(fn)


def main():
    etf_path = newest_etf_panel()
    px, names = load_etf(etf_path)
    maps = load_sector_maps()
    dates_all = sorted({d for c in px for d in px[c]})

    print(f'ETF 패널 {os.path.basename(etf_path)} · {len(dates_all)}일 '
          f'{dates_all[0]}~{dates_all[-1]} · 유니버스 {len(px)}종')
    print(f'업종 매핑 — YF {len(maps["YF"])}종 / DART(2자리) {len(maps["DART"])}종')
    print('★ lag=1 고정 — KRX D+1 지연으로 [D-1] 만 실전 조달 가능 (CLAUDE.md §4-5)\n')

    results = {}
    for tag, smap in maps.items():
        sb = load_sector_breadth(smap)
        sb_dates = sorted(sb)
        nsec = statistics.median([v['nsec'] for v in sb.values()])
        dates = [d for d in dates_all if d >= sb_dates[1]]
        print(f'=== 분류 {tag} — breadth {len(sb_dates)}일 {sb_dates[0]}~{sb_dates[-1]} '
              f'· 업종 수(중앙) {nsec:.0f} ===')
        base = stat(run(sel_base, px, names, dates, sb, sb_dates), 'BASE mom20+RuleH')
        show(base)

        dsp = sorted(v['disp'] for v in sb.values())
        prt = sorted(v['part'] for v in sb.values())
        hhi = sorted(v['hhi'] for v in sb.values())
        q = lambda a, p: a[int(len(a) * p)]

        variants = []
        for p in (0.3, 0.4, 0.5, 0.6):
            variants.append((f'SBD1 업종분산<q{int(p*100)}({q(dsp,p):.3f}) 역전', sbd1(q(dsp, p))))
        for p in (0.3, 0.4, 0.5, 0.6):
            variants.append((f'SBD2 참여업종<q{int(p*100)}({q(prt,p):.3f}) 역전', sbd2(q(prt, p))))
        for p in (0.3, 0.4, 0.5, 0.6):
            variants.append((f'SBD3 상승집중도<q{int(p*100)}({q(hhi,p):.3f}) 역전', sbd3(q(hhi, p))))
        variants.append(('SBD4 선도업종 교체일 역전', sbd4()))

        rows = []
        for label, f in variants:
            s = stat(run(f, px, names, dates, sb, sb_dates), label)
            show(s, base)
            if s:
                s['tag'] = tag
                rows.append(s)
        results[tag] = (base, rows)
        print()

    print('--- 관문 R2(3분할 전부 baseline 초과) + 잭나이프(jk>0) ---')
    passed = {}
    for tag, (base, rows) in results.items():
        ok = [s for s in rows
              if s['mean'] > base['mean'] and s['f1'] > base['f1']
              and s['f2'] > base['f2'] and s['f3'] > base['f3'] and s['jk'] > 0]
        passed[tag] = {s['label'].split(' 역전')[0].split('<')[0].strip(): s for s in ok}
        print(f'  [{tag}] 통과 {len(ok)}건')
        for s in ok:
            show(s, base)
            if len(s['v']) >= 200:            # R5 는 대표본에서 필수
                r5 = tail_test(s, base)
                print(f'      R5 꼬리 — 평균차{r5["mean"]:+.4f} 중앙값차{r5["median"]:+.4f} '
                      f'상위1제거{r5["ex1"]:+.4f} 상위3제거{r5["ex3"]:+.4f} '
                      f'상위5제거{r5["ex5"]:+.4f} 상위10제거{r5["ex10"]:+.4f}'
                      + ('  → 상위3 제거 부호반전 = 기각' if r5['ex3'] <= 0 else ''))

    print('\n--- 관문 R3(정의 교체 재현 — YF·DART 양쪽에서 같은 축이 통과) ---')
    both = set(passed.get('YF', {})) & set(passed.get('DART', {}))
    if both:
        print(f'  양쪽 통과 축: {sorted(both)}')
    else:
        print('  없음 — 한쪽에서만 통과한 변형은 채택하지 않는다(R3 미통과).')
        print('  → Rule SBD 기각.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
