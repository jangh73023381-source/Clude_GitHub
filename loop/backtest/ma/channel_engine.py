# -*- coding: utf-8 -*-
"""가격채널(N일 저점·고점) 지지·저항 지표 엔진.

사용자 가설
  지지선 = 최근 N개월 저점 구간   /   저항선 = 최근 N개월 고점 구간
  N(룩백)은 임의값(6·12개월)이 아니라 스윕으로 최적 구간을 찾는다.

지표 (전부 D일 종가까지의 정보만 사용 — 룩어헤드 없음)
  lo_N(c,d)   = min(저가) over [d-N+1, d]        지지선
  hi_N(c,d)   = max(고가) over [d-N+1, d]        저항선
  pos_N(c,d)  = (종가 - lo_N) / (hi_N - lo_N)    채널 내 위치 0~1
  sup_N(c,d)  = 종가 / lo_N - 1                  지지선 대비 이격(클수록 지지선에서 멀다)
  res_N(c,d)  = hi_N / 종가 - 1                  저항선까지 거리(0에 가까울수록 머리 위 저항)
  break_N     = 종가 >= hi_N                     N일 신고가 돌파
  hold_N(c,d,L) = 최근 L일 중 저가가 lo_N 근접(1% 이내)했으나 종가는 그 위에서 마감한 횟수
                  = "지지선을 지켜준" 횟수

롤링 min/max는 단조 덱(monotonic deque)으로 O(n) 계산.
"""
import csv
import os
from collections import defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = '069500'

# 거래일 기준 룩백 (약 1·3·6·12·24개월)
LOOKBACKS = [20, 60, 120, 250, 500]
LB_LABEL = {20: '1개월', 60: '3개월', 120: '6개월', 250: '12개월', 500: '24개월'}


def load(path):
    bars = defaultdict(dict)
    meta = {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        try:
            bars[r['code']][r['date']] = {
                'o': float(r['open']), 'h': float(r['high']),
                'l': float(r['low']), 'c': float(r['close']),
                'v': float(r['volume']),
            }
        except Exception:
            continue
        meta[r['code']] = (r['sector'], r['name'])
    names = [c for c in bars if not meta[c][0].startswith('BM_')]
    common = None
    for c in names + [BENCH]:
        s = set(bars[c].keys())
        common = s if common is None else (common & s)
    return bars, meta, sorted(common), names


def _roll_min(vals, N):
    """vals[i] 기준 [i-N+1, i] 최소. 앞부분은 None."""
    out = [None] * len(vals)
    dq = deque()
    for i, v in enumerate(vals):
        while dq and vals[dq[-1]] >= v:
            dq.pop()
        dq.append(i)
        while dq[0] <= i - N:
            dq.popleft()
        if i >= N - 1:
            out[i] = vals[dq[0]]
    return out


def _roll_max(vals, N):
    out = [None] * len(vals)
    dq = deque()
    for i, v in enumerate(vals):
        while dq and vals[dq[-1]] <= v:
            dq.pop()
        dq.append(i)
        while dq[0] <= i - N:
            dq.popleft()
        if i >= N - 1:
            out[i] = vals[dq[0]]
    return out


class Channel:
    def __init__(self, bars, dates, codes, lookbacks=LOOKBACKS, ma_windows=(20, 60)):
        self.bars = bars
        self.dates = dates
        self.codes = codes
        self.idx = {d: i for i, d in enumerate(dates)}
        self.lo = {N: {} for N in lookbacks}
        self.hi = {N: {} for N in lookbacks}
        self.ma = {k: {} for k in ma_windows}
        for c in list(bars):
            lows = [bars[c][d]['l'] for d in dates if d in bars[c]]
            highs = [bars[c][d]['h'] for d in dates if d in bars[c]]
            closes = [bars[c][d]['c'] for d in dates if d in bars[c]]
            if len(lows) != len(dates):
                continue
            for N in lookbacks:
                self.lo[N][c] = _roll_min(lows, N)
                self.hi[N][c] = _roll_max(highs, N)
            for k in ma_windows:
                acc = [None] * len(closes)
                s = 0.0
                for i, v in enumerate(closes):
                    s += v
                    if i >= k:
                        s -= closes[i - k]
                    if i >= k - 1:
                        acc[i] = s / k
                self.ma[k][c] = acc

    # ---------- 기본 ----------
    def close(self, c, d):
        b = self.bars[c].get(d)
        return b['c'] if b else None

    def mom(self, c, d, k):
        i = self.idx[d]
        if i < k:
            return None
        a = self.close(c, self.dates[i - k])
        b = self.close(c, d)
        return (b / a - 1.0) if (a and b) else None

    def MA(self, c, d, k):
        arr = self.ma[k].get(c)
        return arr[self.idx[d]] if arr else None

    # ---------- 채널 ----------
    def LO(self, c, d, N):
        arr = self.lo[N].get(c)
        return arr[self.idx[d]] if arr else None

    def HI(self, c, d, N):
        arr = self.hi[N].get(c)
        return arr[self.idx[d]] if arr else None

    def pos(self, c, d, N):
        lo, hi, p = self.LO(c, d, N), self.HI(c, d, N), self.close(c, d)
        if None in (lo, hi, p) or hi <= lo:
            return None
        return (p - lo) / (hi - lo)

    def sup(self, c, d, N):
        """지지선(N일 저점) 대비 이격."""
        lo, p = self.LO(c, d, N), self.close(c, d)
        return (p / lo - 1.0) if (lo and p) else None

    def res(self, c, d, N):
        """저항선(N일 고점)까지 거리. 0이면 신고가."""
        hi, p = self.HI(c, d, N), self.close(c, d)
        return (hi / p - 1.0) if (hi and p) else None

    def is_break(self, c, d, N):
        hi, p = self.HI(c, d, N), self.close(c, d)
        if hi is None or p is None:
            return None
        return p >= hi - 1e-9

    def hold_cnt(self, c, d, N, L=20, eps=0.01):
        """최근 L일 중 저가가 N일 저점 1% 이내 접근했으나 종가는 그 위에서 마감한 횟수."""
        i = self.idx[d]
        if i < max(N, L):
            return None
        n = 0
        for j in range(i - L + 1, i + 1):
            dd = self.dates[j]
            lo = self.LO(c, dd, N)
            b = self.bars[c].get(dd)
            if lo is None or b is None:
                continue
            if b['l'] <= lo * (1 + eps) and b['c'] > lo * (1 + eps):
                n += 1
        return n


if __name__ == '__main__':
    path = os.path.join(HERE, 'ohlc_stock15.csv')
    bars, meta, dates, codes = load(path)
    C = Channel(bars, dates, codes)
    print(f'공통 거래일 {len(dates)}일  {dates[0]}~{dates[-1]}  종목 {len(codes)}종')
    d = dates[-1]
    print(f'\n[{d}] 섹터 대표주 채널 위치 (pos = 0 저점 / 1 고점)')
    print(f"{'섹터':11s}{'종목':14s}" + ''.join(f'{LB_LABEL[N]:>9s}' for N in LOOKBACKS))
    for c in codes:
        s, n = meta[c]
        cells = ''.join(('%9.2f' % C.pos(c, d, N)) if C.pos(c, d, N) is not None else '        -'
                        for N in LOOKBACKS)
        print(f'{s:11s}{n[:13]:14s}{cells}')
