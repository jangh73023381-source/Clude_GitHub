# -*- coding: utf-8 -*-
"""볼린저 밴드 · RSI 지표 엔진 (전체 사전계산 캐시).

지표
----
RSI(n)  : Wilder 지수평활. n ∈ {9, 14, 25}
볼린저   : MA20 ± k·SD20 (표본표준편차, ddof=0). k ∈ {1.5, 2.0, 2.5}
  %B     = (종가 − 하단) / (상단 − 하단).  0=하단, 1=상단, <0=하단 이탈, >1=상단 이탈
  밴드폭  = (상단 − 하단) / MA20            → 스퀴즈 판정용
  bwpct  = 그 종목의 최근 120일 밴드폭 분포에서 현재 밴드폭의 백분위(0=최협착)

룩어헤드 금지: 인덱스 i의 값은 dates[0..i] 정보만으로 계산된다.
"""
import csv, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')
BENCH = '069500'
RSI_NS = (9, 14, 25)
BB_KS = (1.5, 2.0, 2.5)
BB_N = 20
BW_LOOK = 120


def load_panel():
    c = defaultdict(dict); name = {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                c[r['code']][r['date']] = float(r['close'])
            except Exception:
                continue
            name[r['code']] = r['name']
    dates = sorted({d for k in c for d in c[k]})
    return c, name, dates


def is_excluded(nm):
    n = nm.replace(' ', '').upper()
    return ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n
            or '2배' in n or '숏' in n)


def is_cashlike(nm):
    n = nm.replace(' ', '')
    return any(kw in n for kw in ('머니마켓', 'CD금리', '초단기채', 'KOFR',
                                 '국고채', '통안', 'CP금리'))


def rsi_series(px, n):
    """Wilder RSI. px는 연속 종가 리스트. 앞 n개는 None."""
    out = [None] * len(px)
    if len(px) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        ch = px[i] - px[i - 1]
        gains += max(ch, 0.0); losses += max(-ch, 0.0)
    def _rsi(ag, al):
        # 무변동 구간(ag=al=0)은 RSI 100이 아니라 중립 50. 거래 없는 ETF가
        # 과매수 극단으로 잘못 분류되는 것을 막는다.
        if al == 0:
            return 100.0 if ag > 0 else 50.0
        return 100 - 100 / (1 + ag / al)

    ag = gains / n; al = losses / n
    out[n] = _rsi(ag, al)
    for i in range(n + 1, len(px)):
        ch = px[i] - px[i - 1]
        ag = (ag * (n - 1) + max(ch, 0.0)) / n
        al = (al * (n - 1) + max(-ch, 0.0)) / n
        out[i] = _rsi(ag, al)
    return out


def build_cache():
    """code -> {'idx': {date: i}, 'px': [...], 'rsi9/14/25': [...],
                'pctb1.5/2.0/2.5': [...], 'bw': [...], 'bwpct': [...], 'mom20': [...]}"""
    c, name, dates = load_panel()
    cache = {}
    for code, series in c.items():
        ds = sorted(series)
        px = [series[d] for d in ds]
        e = {'dates': ds, 'idx': {d: i for i, d in enumerate(ds)}, 'px': px}
        for n in RSI_NS:
            e[f'rsi{n}'] = rsi_series(px, n)
        # 볼린저
        ma = [None] * len(px); sd = [None] * len(px)
        run_s = 0.0; run_s2 = 0.0
        for i, v in enumerate(px):
            run_s += v; run_s2 += v * v
            if i >= BB_N:
                old = px[i - BB_N]; run_s -= old; run_s2 -= old * old
            if i >= BB_N - 1:
                m = run_s / BB_N
                var = max(run_s2 / BB_N - m * m, 0.0)
                ma[i] = m; sd[i] = var ** 0.5
        for k in BB_KS:
            key = f'pctb{k}'
            arr = [None] * len(px)
            for i in range(len(px)):
                if ma[i] is None or sd[i] is None or sd[i] <= 0:
                    continue
                up = ma[i] + k * sd[i]; lo = ma[i] - k * sd[i]
                arr[i] = (px[i] - lo) / (up - lo)
            e[key] = arr
        bw = [None] * len(px)
        for i in range(len(px)):
            if ma[i] and sd[i] is not None and ma[i] > 0:
                bw[i] = 2 * 2.0 * sd[i] / ma[i]      # k=2.0 기준 밴드폭
        e['bw'] = bw
        bwp = [None] * len(px)
        for i in range(len(px)):
            if bw[i] is None or i < BW_LOOK:
                continue
            win = [x for x in bw[i - BW_LOOK + 1:i + 1] if x is not None]
            if len(win) < BW_LOOK // 2:
                continue
            bwp[i] = sum(1 for x in win if x < bw[i]) / len(win)
        e['bwpct'] = bwp
        m20 = [None] * len(px)
        for i in range(20, len(px)):
            if px[i - 20]:
                m20[i] = px[i] / px[i - 20] - 1.0
        e['mom20'] = m20
        cache[code] = e
    return cache, name, dates


def get(cache, code, d, key):
    e = cache.get(code)
    if not e:
        return None
    i = e['idx'].get(d)
    if i is None:
        return None
    return e[key][i]
