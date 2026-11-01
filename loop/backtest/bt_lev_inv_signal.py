# -*- coding: utf-8 -*-
"""검토2 — 인버스·레버리지 ETF 지표로 한국증시 방향을 예측할 수 있는가.

사용자 가설: "레버리지 청산이 하락 원인이었다면 인버스·레버리지 보유량으로 증시를 예측할 수 있지 않나."

한계 먼저: **보유량(설정좌수·순자산) 시계열은 확보 불가**다. 키움 REST는 일봉·수급만 주고
(오늘은 주말 시스템점검으로 접속 불가), yfinance 도 ETF 상장좌수를 주지 않는다.
따라서 **거래대금 기반 프록시**로 대체한다 — 실제 보유량이 아니라 '그날 누가 얼마나 세게
베팅했나'의 대리 지표다. 이 차이를 결과 해석에 반드시 반영할 것.

신호(전부 D 종가까지 정보):
  IL  = 인버스계 거래대금 / (인버스계 + 레버리지계 거래대금)   … 비관 베팅 비중
  ILZ = IL 의 20일 z-score                                  … 비관 극단 여부
  LEVZ= 레버리지 거래대금의 20일 z-score                      … 투기 과열
피예측: KODEX200 의 D+1 · D+5 · D+20 수익률.
"""
import csv
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_lev_inv.csv')

LEV = ['122630', '233740']            # 레버리지(코스피200·코스닥150)
INV = ['114800', '252670', '251340']  # 인버스·인버스2X
BENCH = '069500'


def load():
    amt, px = defaultdict(dict), defaultdict(dict)
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                c, v = float(r['close']), float(r['volume'])
            except ValueError:
                continue
            if c <= 0:
                continue
            amt[r['code']][r['date']] = c * v
            px[r['code']][r['date']] = c
    dates = sorted(px[BENCH])
    return amt, px, dates


def zscore(series, i, k=20):
    if i < k:
        return None
    w = [x for x in series[i - k:i] if x is not None]
    if len(w) < k:
        return None
    m = sum(w) / k
    sd = math.sqrt(sum((x - m) ** 2 for x in w) / (k - 1))
    if sd <= 0 or series[i] is None:
        return None
    return (series[i] - m) / sd


def build_signals(amt, dates):
    il, lev = [], []
    for d in dates:
        a_lev = sum(amt[c].get(d, 0.0) for c in LEV)
        a_inv = sum(amt[c].get(d, 0.0) for c in INV)
        tot = a_lev + a_inv
        il.append(a_inv / tot if tot > 0 else None)
        lev.append(a_lev if a_lev > 0 else None)
    ilz = [zscore(il, i) for i in range(len(dates))]
    levz = [zscore(lev, i) for i in range(len(dates))]
    return il, ilz, levz


def fwd(px, dates, i, h):
    if i + h >= len(dates):
        return None
    a, b = px[BENCH].get(dates[i]), px[BENCH].get(dates[i + h])
    return (b / a - 1.0) if (a and b) else None


def corr(xs, ys):
    n = len(xs)
    if n < 10:
        return 0.0, 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx <= 0 or sy <= 0:
        return 0.0, 0.0
    r = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / (sx * sy)
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    return r, t


def quintiles(sig, ret, dates, label):
    pair = [(sig[i], ret[i], dates[i]) for i in range(len(sig))
            if sig[i] is not None and ret[i] is not None]
    if len(pair) < 50:
        print(f'  {label}: 관측 부족({len(pair)})')
        return
    pair.sort()
    n = len(pair)
    print(f'  {label} (n={n})')
    print(f'    {"5분위":<8}{"신호 구간":>20}{"평균 다음수익%":>14}{"승률%":>8}{"관측":>6}')
    for q in range(5):
        seg = pair[n * q // 5:n * (q + 1) // 5]
        v = [x[1] for x in seg]
        m = sum(v) / len(v) * 100
        w = sum(1 for x in v if x > 0) / len(v) * 100
        print(f'    Q{q+1:<7}{seg[0][0]:>9.3f}~{seg[-1][0]:>9.3f}'
              f'{m:>14.3f}{w:>8.1f}{len(seg):>6}')
    lo = [x[1] for x in pair[:n // 5]]
    hi = [x[1] for x in pair[-(n // 5):]]
    d = (sum(hi) / len(hi) - sum(lo) / len(lo)) * 100
    print(f'    Q5-Q1 스프레드 {d:+.3f}%p')


def main():
    amt, px, dates = load()
    il, ilz, levz = build_signals(amt, dates)
    print(f'패널 {len(dates)}거래일 {dates[0]}~{dates[-1]}')
    print(f'레버리지 {LEV} · 인버스 {INV} · 벤치 {BENCH}\n')

    print('■ 상관 (신호 D → KODEX200 미래수익)')
    print(f'  {"신호":<28}{"D+1 r":>9}{"t":>7}{"D+5 r":>9}{"t":>7}{"D+20 r":>9}{"t":>7}')
    print('  ' + '-' * 76)
    for lbl, s in [('IL 인버스 거래대금 비중', il),
                   ('ILZ 비중 20일 z', ilz),
                   ('LEVZ 레버리지금액 20일 z', levz)]:
        row = f'  {lbl:<28}'
        for h in (1, 5, 20):
            r_ = [fwd(px, dates, i, h) for i in range(len(dates))]
            xs = [s[i] for i in range(len(dates)) if s[i] is not None and r_[i] is not None]
            ys = [r_[i] for i in range(len(dates)) if s[i] is not None and r_[i] is not None]
            c, t = corr(xs, ys)
            row += f'{c:>9.3f}{t:>7.2f}'
        print(row)

    for h in (1, 5, 20):
        print(f'\n■ 5분위 — D+{h} KODEX200 수익률')
        r_ = [fwd(px, dates, i, h) for i in range(len(dates))]
        quintiles(il, r_, dates, 'IL 인버스 거래대금 비중')
        quintiles(ilz, r_, dates, 'ILZ 20일 z-score')

    print('\n■ 극단 신호일 확인 (ILZ 상·하위 8일)')
    pair = sorted([(ilz[i], dates[i], fwd(px, dates, i, 5))
                   for i in range(len(dates)) if ilz[i] is not None])
    for tag, seg in [('비관 극단(ILZ 최고)', pair[-8:]), ('낙관 극단(ILZ 최저)', pair[:8])]:
        print(f'  {tag}')
        for z, d, f5 in seg:
            print(f'    {d}  ILZ {z:+.2f}  → 5일후 {f5*100 if f5 is not None else float("nan"):+.2f}%')

    print('\n■ 최근 10거래일 신호값')
    print(f'  {"일자":<10}{"IL":>8}{"ILZ":>8}{"LEVZ":>8}{"KODEX200 등락%":>16}')
    for i in range(len(dates) - 10, len(dates)):
        d = dates[i]
        r1 = fwd(px, dates, i - 1, 1)
        print(f'  {d:<10}{il[i] if il[i] else float("nan"):>8.3f}'
              f'{ilz[i] if ilz[i] is not None else float("nan"):>8.2f}'
              f'{levz[i] if levz[i] is not None else float("nan"):>8.2f}'
              f'{(r1*100 if r1 is not None else float("nan")):>16.2f}')


if __name__ == '__main__':
    main()
