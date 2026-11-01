# -*- coding: utf-8 -*-
"""업로드 문서(주식매매기법_2026 / 최근_1년_주식매매기법_조사보고서_2026) 기법 검정용 엔진.

문서의 서술형 기법을 숫자 조건으로 바꾼 신호만 담는다. 평가(오프셋·통계)는
mid_engine 의 run_h/stat/show 를 그대로 쓴다 — 기존 백테스트와 같은 잣대로 비교하기 위함.

모든 지표는 인덱스 i 에서 dates[0..i] 만 사용한다(룩어헤드 없음).
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')
FLOW = os.path.join(HERE, 'flow_2y.csv')

import sys
sys.path.insert(0, os.path.join(HERE, '..', 'references', 'scripts'))
from universe_filters import eligible as _univ_ok  # noqa: E402

BENCH = '069500'
NPICK = 5
COST = 0.0010


def _rsi(px, n=14):
    out = [None] * len(px)
    if len(px) <= n:
        return out

    def _r(ag, al):
        if al == 0:
            return 100.0 if ag > 0 else 50.0
        return 100 - 100 / (1 + ag / al)
    g = l = 0.0
    for i in range(1, n + 1):
        ch = px[i] - px[i - 1]
        g += max(ch, 0.0)
        l += max(-ch, 0.0)
    ag, al = g / n, l / n
    out[n] = _r(ag, al)
    for i in range(n + 1, len(px)):
        ch = px[i] - px[i - 1]
        ag = (ag * (n - 1) + max(ch, 0.0)) / n
        al = (al * (n - 1) + max(-ch, 0.0)) / n
        out[i] = _r(ag, al)
    return out


def _sma(px, k):
    n = len(px)
    out = [None] * n
    s = 0.0
    for i, v in enumerate(px):
        s += v
        if i >= k:
            s -= px[i - k]
        if i >= k - 1:
            out[i] = s / k
    return out


def build():
    """code -> 지표 dict. 반환 (cache, name, all_dates)."""
    raw = defaultdict(dict)
    name = {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                raw[r['code']][r['date']] = (
                    float(r['open']), float(r['high']), float(r['low']),
                    float(r['close']), float(r['volume']))
            except Exception:
                continue
            name[r['code']] = r['name']

    flow = defaultdict(dict)
    if os.path.exists(FLOW):
        with open(FLOW, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                try:
                    flow[r['code']][r['date']] = (
                        float(r['for_net']), float(r['orgn_net']))
                except Exception:
                    continue

    all_dates = sorted({d for c in raw for d in raw[c]})
    cache = {}
    for code, s in raw.items():
        ds = sorted(s)
        op = [s[d][0] for d in ds]
        hi = [s[d][1] for d in ds]
        lo = [s[d][2] for d in ds]
        px = [s[d][3] for d in ds]
        vol = [s[d][4] for d in ds]
        n = len(px)
        e = {'dates': ds, 'idx': {d: i for i, d in enumerate(ds)},
             'op': op, 'hi': hi, 'lo': lo, 'px': px, 'vol': vol}

        for k in (5, 20, 60, 150):
            e[f'ma{k}'] = _sma(px, k)
            a = [None] * n
            for i in range(k, n):
                if px[i - k]:
                    a[i] = px[i] / px[i - k] - 1.0
            e[f'mom{k}'] = a
        e['rsi14'] = _rsi(px, 14)

        # 갭 / 양봉
        gap = [None] * n
        for i in range(1, n):
            if px[i - 1]:
                gap[i] = op[i] / px[i - 1] - 1.0
        e['gap'] = gap
        e['bull'] = [px[i] >= op[i] for i in range(n)]

        # 거래량 급증 (전일까지 20일 평균 대비 당일)
        vs = [None] * n
        for i in range(20, n):
            m = sum(vol[i - 20:i]) / 20
            if m > 0:
                vs[i] = vol[i] / m
        e['volsurge'] = vs

        # 거래대금 급증(20일)
        amt = [px[i] * vol[i] for i in range(n)]
        asf = [None] * n
        for i in range(20, n):
            m = sum(amt[i - 20:i]) / 20
            if m > 0:
                asf[i] = amt[i] / m
        e['amtsurge'] = asf

        # 직전 N일 종가 최고 (당일 제외) — 돌파 판정용
        for k in (20, 60):
            a = [None] * n
            for i in range(k, n):
                a[i] = max(px[i - k:i])
            e[f'prevhi{k}'] = a

        # 60일 채널 위치
        cp = [None] * n
        for i in range(59, n):
            H = max(hi[i - 59:i + 1])
            L = min(lo[i - 59:i + 1])
            if H > L:
                cp[i] = (px[i] - L) / (H - L)
        e['chpos60'] = cp

        # 수급 누적 (외국인/기관 순매수, 5·20일)
        fw = flow.get(code, {})
        fn = [fw.get(d, (0.0, 0.0))[0] for d in ds]
        on = [fw.get(d, (0.0, 0.0))[1] for d in ds]
        has = [d in fw for d in ds]
        for k in (5, 20):
            fa = [None] * n
            oa = [None] * n
            for i in range(k - 1, n):
                if all(has[i - k + 1:i + 1]):
                    fa[i] = sum(fn[i - k + 1:i + 1])
                    oa[i] = sum(on[i - k + 1:i + 1])
            e[f'for{k}'] = fa
            e[f'org{k}'] = oa
        cache[code] = e
    return cache, name, all_dates


def eligible(cache, name, d):
    """파생·현금성 제외. 최소가격 필터는 2026-07-30 지시로 폐지."""
    out = []
    for code, e in cache.items():
        if not _univ_ok(name[code]):
            continue
        i = e['idx'].get(d)
        if i is None:
            continue
        out.append((code, i))
    return out


def rule_h_ok(e, i):
    """v2.1 이중 과열필터: 전일 +10% 초과 또는 3일 +20% 초과 제외."""
    if i < 3:
        return True
    p0, p1, p3 = e['px'][i], e['px'][i - 1], e['px'][i - 3]
    if p1 and p0 / p1 - 1.0 > 0.10:
        return False
    if p3 and p0 / p3 - 1.0 > 0.20:
        return False
    return True


def topn(scored, n=NPICK):
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:n]]
