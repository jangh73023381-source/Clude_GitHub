# -*- coding: utf-8 -*-
"""이평선 지지·저항 지표 엔진 (15섹터 대표 ETF, OHLC 기반).

정의
----
MA_k(c, d)            : 종가 k일 단순이동평균
slope_k(c, d, s)      : MA_k(d) / MA_k(d-s) - 1        (기울기, 기본 s=5)
disp_k(c, d)          : close/MA_k - 1                  (이격도)

지지강도(support break depth, 낮을수록 지지 잘 지킴)
    sup_close(c,d,k,L) = max_{t in [d-L+1, d]} max(0, 1 - close_t / MA_k(t))
    sup_low(c,d,k,L)   = max_{t in [d-L+1, d]} max(0, 1 - low_t   / MA_k(t))
    → 0 이면 관찰창 L일 동안 한 번도 MA_k 아래로 안 내려간 것 = 완전 방어

저항압력(resistance overhead, 작은 양수일수록 머리 위 저항 근접)
    head(c,d,k)        = MA_k(d)/close_d - 1            (양수면 가격이 MA 아래 = 저항 존재)
    rej_cnt(c,d,k,L)   = #{t in [d-L+1,d] : high_t >= MA_k(t) and close_t < MA_k(t)}
                         (장중 이평선 터치 후 종가로 밀린 횟수 = 저항 확인 횟수)

신선 돌파
    fresh_break(c,d,k,B) = True  if close_d > MA_k(d) and
                                    exists t in [d-B, d-1] with close_t <= MA_k(t)

모든 지표는 d 시점 종가까지의 정보만 사용 → 룩어헤드 없음.
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OHLC = os.path.join(HERE, 'ohlc_sector15.csv')
BENCH = '069500'


def load(path=OHLC):
    """returns bars[code][date] = dict(o,h,l,c,v), meta[code]=(sector,name), dates=sorted list"""
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
    # 공통 거래일: 벤치마크 + 모든 섹터가 값을 가진 날짜만 사용
    sectors = [c for c in bars if not meta[c][0].startswith('BM_')]
    common = None
    for c in sectors + [BENCH]:
        s = set(bars[c].keys())
        common = s if common is None else (common & s)
    dates = sorted(common)
    return bars, meta, dates, sectors


class Panel:
    """이평선·지지/저항 지표를 사전 계산해 캐시한다."""

    def __init__(self, bars, dates, ma_windows=(5, 20, 60, 120)):
        self.bars = bars
        self.dates = dates
        self.idx = {d: i for i, d in enumerate(dates)}
        self.ma = {k: defaultdict(dict) for k in ma_windows}
        for k in ma_windows:
            for c in bars:
                closes = [bars[c][d]['c'] if d in bars[c] else None for d in dates]
                run = 0.0
                buf = []
                for i, v in enumerate(closes):
                    if v is None:
                        buf.append(None)
                        continue
                    buf.append(v)
                    run += v
                    if len(buf) > k:
                        old = buf[-k - 1]
                        if old is not None:
                            run -= old
                    if i >= k - 1 and all(x is not None for x in buf[-k:]):
                        self.ma[k][c][dates[i]] = run / k

    # ---- 기본 조회 -------------------------------------------------
    def close(self, c, d):
        b = self.bars[c].get(d)
        return b['c'] if b else None

    def MA(self, c, d, k):
        return self.ma[k][c].get(d)

    def mom(self, c, d, k):
        i = self.idx[d]
        if i < k:
            return None
        a = self.close(c, self.dates[i - k])
        b = self.close(c, d)
        return (b / a - 1.0) if (a and b) else None

    def slope(self, c, d, k, s=5):
        i = self.idx[d]
        if i < s:
            return None
        a = self.MA(c, self.dates[i - s], k)
        b = self.MA(c, d, k)
        return (b / a - 1.0) if (a and b) else None

    def disp(self, c, d, k):
        m = self.MA(c, d, k)
        p = self.close(c, d)
        return (p / m - 1.0) if (m and p) else None

    # ---- 지지 -----------------------------------------------------
    def sup_break_depth(self, c, d, k=20, L=20, use_low=False):
        """관찰창 L일 중 MA_k 아래로 내려간 최대 깊이. 0 = 완전 방어."""
        i = self.idx[d]
        if i < L - 1:
            return None
        worst = 0.0
        seen = 0
        for j in range(i - L + 1, i + 1):
            dd = self.dates[j]
            m = self.MA(c, dd, k)
            b = self.bars[c].get(dd)
            if not m or not b:
                continue
            px = b['l'] if use_low else b['c']
            worst = max(worst, max(0.0, 1.0 - px / m))
            seen += 1
        return worst if seen >= L * 0.8 else None

    # ---- 저항 -----------------------------------------------------
    def head(self, c, d, k=60):
        """MA_k가 현재가보다 위에 있으면 양수(=머리 위 저항까지의 거리)."""
        m = self.MA(c, d, k)
        p = self.close(c, d)
        return (m / p - 1.0) if (m and p) else None

    def rej_cnt(self, c, d, k=60, L=20):
        """장중 MA_k 터치했으나 종가는 아래로 밀린 횟수 = 저항 확인 횟수."""
        i = self.idx[d]
        if i < L - 1:
            return None
        n = 0
        for j in range(i - L + 1, i + 1):
            dd = self.dates[j]
            m = self.MA(c, dd, k)
            b = self.bars[c].get(dd)
            if not m or not b:
                continue
            if b['h'] >= m and b['c'] < m:
                n += 1
        return n

    def fresh_break(self, c, d, k=60, B=3):
        """최근 B일 내 MA_k를 아래→위로 갓 돌파했는가."""
        i = self.idx[d]
        if i < B:
            return None
        m = self.MA(c, d, k)
        p = self.close(c, d)
        if not m or not p or p <= m:
            return False
        for j in range(i - B, i):
            dd = self.dates[j]
            mm = self.MA(c, dd, k)
            pp = self.close(c, dd)
            if mm and pp and pp <= mm:
                return True
        return False

    def aligned(self, c, d):
        """정배열: MA5 > MA20 > MA60"""
        a, b, e = self.MA(c, d, 5), self.MA(c, d, 20), self.MA(c, d, 60)
        if None in (a, b, e):
            return None
        return a > b > e


if __name__ == '__main__':
    bars, meta, dates, sectors = load()
    P = Panel(bars, dates)
    print(f'거래일 {len(dates)}일  {dates[0]}~{dates[-1]}   섹터 {len(sectors)}종')
    d = dates[-1]
    print(f'\n[{d}] 섹터별 지지·저항 스냅샷')
    print(f"{'섹터':10s}{'이격MA20':>9s}{'MA20기울기':>11s}{'지지이탈깊이':>13s}{'저항까지':>9s}{'저항확인':>8s}{'정배열':>7s}")
    for c in sectors:
        s, n = meta[c]
        f = lambda v, p=2: ('%.2f%%' % (v * 100)) if isinstance(v, float) else ('-' if v is None else str(v))
        print(f"{s:10s}{f(P.disp(c,d,20)):>9s}{f(P.slope(c,d,20)):>11s}"
              f"{f(P.sup_break_depth(c,d,20,20)):>13s}{f(P.head(c,d,60)):>9s}"
              f"{str(P.rej_cnt(c,d,60,20)):>8s}{str(P.aligned(c,d)):>7s}")
