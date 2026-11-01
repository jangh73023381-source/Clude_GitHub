# -*- coding: utf-8 -*-
"""피보나치 되돌림 엔진 — 룩어헤드 금지(선정은 D종가까지 정보만, 채점은 D+1).

정의
----
룩백 L거래일(D 포함) 구간에서
    H  = 구간 최고가(high), Lo = 구간 최저가(low)
    iH = H가 발생한 위치,   iLo = Lo가 발생한 위치
방향(regime):
    iH > iLo  → 상승 임펄스 후 되돌림 국면(UP).  retr = (H - C) / (H - Lo)
                retr=0 → 고점, retr=1 → 저점까지 전부 되돌림
    iLo > iH  → 하락 임펄스 후 반등 국면(DOWN).  retr = (C - Lo) / (H - Lo)
                retr=0 → 저점, retr=1 → 고점까지 전부 반등
채널위치(비교군): chpos = (C - Lo) / (H - Lo)  ← 방향 무시. 기존 2026-07-26 백테스트 지표.
"""
import csv, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')
BENCH = '069500'
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]


# ---------------- 데이터 ----------------
def load():
    o = defaultdict(dict); h = defaultdict(dict); l = defaultdict(dict)
    c = defaultdict(dict); v = defaultdict(dict); name = {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            k, d = r['code'], r['date']
            try:
                o[k][d] = float(r['open']); h[k][d] = float(r['high'])
                l[k][d] = float(r['low']);  c[k][d] = float(r['close'])
                v[k][d] = float(r['volume'])
            except Exception:
                continue
            name[k] = r['name']
    dates = sorted({d for k in c for d in c[k]})
    return {'o': o, 'h': h, 'l': l, 'c': c, 'v': v, 'name': name, 'dates': dates}


def is_excluded(nm):
    """레버리지·인버스·숏 제외 (v1.2 확정 규칙)."""
    n = nm.replace(' ', '').upper()
    return ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n
            or '2배' in n or '숏' in n)


def is_cashlike(nm):
    n = nm.replace(' ', '')
    for kw in ('머니마켓', 'CD금리', '초단기채', 'KOFR', '국고채', '통안', 'CP금리'):
        if kw in n:
            return True
    return False


# ---------------- 지표 ----------------
def series(P, code, upto_idx, L, key):
    """dates[upto_idx-L+1 : upto_idx+1] 구간의 key 값. 결측 있으면 None."""
    ds = P['dates']; src = P[key]; out = []
    for i in range(upto_idx - L + 1, upto_idx + 1):
        val = src[code].get(ds[i])
        if val is None:
            return None
        out.append(val)
    return out


def fib_state(P, code, i, L):
    """D=dates[i] 기준 되돌림 상태. 반환 (regime, retr, chpos, H, Lo, C, amp)."""
    hs = series(P, code, i, L, 'h')
    ls = series(P, code, i, L, 'l')
    if hs is None or ls is None:
        return None
    H = max(hs); Lo = min(ls)
    rng = H - Lo
    if rng <= 0:
        return None
    iH = 0; iL = 0
    for j in range(L):
        if hs[j] >= hs[iH]:
            iH = j          # 동률이면 가장 최근 위치를 채택
        if ls[j] <= ls[iL]:
            iL = j
    C = P['c'][code][P['dates'][i]]
    chpos = (C - Lo) / rng
    if iH > iL:
        regime = 'UP'; retr = (H - C) / rng
    else:
        regime = 'DOWN'; retr = (C - Lo) / rng
    amp = rng / Lo   # 스윙 진폭(변동성 정규화용)
    return regime, retr, chpos, H, Lo, C, amp


def nearest_fib(retr):
    """가장 가까운 피보나치 레벨과 거리."""
    best = min(FIB_LEVELS, key=lambda x: abs(x - retr))
    return best, abs(best - retr)


def mom(P, code, i, k=20):
    ds = P['dates']
    if i - k < 0:
        return None
    a = P['c'][code].get(ds[i - k]); b = P['c'][code].get(ds[i])
    if not a or not b:
        return None
    return b / a - 1.0


# ---------------- 통계 ----------------
def date_clustered_t(by_date):
    """일자별 평균값 리스트 → (평균, t통계량, 일수). 같은 날 종목 간 상관을 흡수."""
    xs = [v for v in by_date if v is not None]
    n = len(xs)
    if n < 3:
        return (None, None, n)
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return (m, (m / se if se > 0 else None), n)


def jackknife_low(by_date):
    """1일씩 제거한 평균들의 최솟값(하한)."""
    xs = [v for v in by_date if v is not None]
    n = len(xs)
    if n < 3:
        return None
    s = sum(xs)
    return min((s - x) / (n - 1) for x in xs)
