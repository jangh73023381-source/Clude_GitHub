#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""단기 ETF 선정 신규 가설 3종 백테스트 (2026-08-08, 사용자 지시).

가설 (기각 목록과 구별되는 신규 축, N 대장 +3 예정):
  ON  — 오버나이트 모멘텀: 최근 20세션 ln(open_t / close_{t-1}) 합 상위 5종
  ID  — 장중 모멘텀:       최근 20세션 ln(close_t / open_t) 합 상위 5종
  CH  — 채널위치 필터:     mom20 순위에서 6M 채널위치 0.40~0.60(최약 구간) 제외 후 상위 5종

기준선 BASE — 현행 확정방법: mom20 상위 5종 (+ Rule H 이중 과열필터, v2.1).
Rule H 는 모든 변형에 동일 적용(공정 비교).

채점(v2.3): 픽5 동일가중 · D→D+1 종가수익률 · 왕복 10bp 차감 · KODEX200(069500) 대비 초과.
사전 스크리닝: 신호 vs 익일수익률 일별 Spearman 랭크 IC.
in-sample 전수 검정이므로 결과 해석 시 --trials 누적 N 을 함께 볼 것.
"""
import numpy as np
import pandas as pd
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
import universe_filters as uf

LOOKBACK_CH = 126   # 6M 채널
MOM = 20
COST = 0.0010       # 왕복 10bp
BENCH = '069500'

df = pd.read_csv(os.path.join(HERE, 'panel_ohlc_2y.csv'), dtype={'code': str})
df = df.sort_values(['code', 'date'])

# 유니버스: 파생·현금성 제외 (선정·채점 동일 — v2.7 정합 원칙)
names = df.groupby('code')['name'].last()
excl = {c for c, n in names.items() if uf.is_deriv(n) or uf.is_cash(n)}
keep = sorted(set(names.index) - excl)

close = df.pivot_table(index='date', columns='code', values='close')
open_ = df.pivot_table(index='date', columns='code', values='open')
dates = close.index.tolist()

C = close[keep]
O = open_[keep]
bench_ret = close[BENCH].pct_change()

# ---- 신호 (전일까지 정보만: D 종가 기준 신호 → D+1 수익률로 채점) ----
ret1 = C.pct_change()                          # 당일 수익률 (Rule H r1)
ret3 = C.pct_change(3)                         # 3일 누적 (Rule H r3)
mom20 = C.pct_change(MOM)
on = np.log(O / C.shift(1))                    # 오버나이트
iday = np.log(C / O)                           # 장중
on20 = on.rolling(MOM).sum()
id20 = iday.rolling(MOM).sum()
hi126 = C.rolling(LOOKBACK_CH).max()
lo126 = C.rolling(LOOKBACK_CH).min()
ch = (C - lo126) / (hi126 - lo126)

fwd = C.pct_change().shift(-1)                 # D+1 수익률
fwd_b = bench_ret.shift(-1)

ruleH_ok = ~((ret1 > 0.10) | (ret3 > 0.20))    # 과열 제외


def pick5(sig_row, ok_row, ch_row=None, ch_filter=False):
    s = sig_row[ok_row & sig_row.notna()]
    if ch_filter and ch_row is not None:
        weak = (ch_row >= 0.40) & (ch_row <= 0.60)
        s = s[~weak.reindex(s.index).fillna(False)]
    return s.nlargest(5).index.tolist() if len(s) >= 5 else []


def run_variant(sig, ch_filter=False):
    rows = []
    for i, d in enumerate(dates[:-1]):
        if pd.isna(fwd_b.loc[d]):
            continue
        srow = sig.loc[d]
        if srow.notna().sum() < 30:
            continue
        p = pick5(srow, ruleH_ok.loc[d], ch.loc[d], ch_filter)
        if not p:
            continue
        r = fwd.loc[d, p].mean() - COST - fwd_b.loc[d]
        if pd.notna(r):
            rows.append((d, r * 100))
    return pd.DataFrame(rows, columns=['date', 'excess'])


def stats(t):
    x = t['excess'].values
    n = len(x)
    m = x.mean(); sd = x.std(ddof=1)
    tstat = m / (sd / np.sqrt(n)) if sd > 0 else np.nan
    # 잭나이프 하한 = leave-one-out 평균의 최솟값
    jk = min((x.sum() - x[i]) / (n - 1) for i in range(n))
    half = n // 2
    return dict(n=n, mean=m, t=tstat, win=(x > 0).mean() * 100, jk=jk,
                train=x[:half].mean(), test=x[half:].mean(), cum=x.sum())


def rank_ic(sig):
    ics = []
    for d in dates[:-1]:
        s = sig.loc[d]; f = fwd.loc[d]
        ok = s.notna() & f.notna() & ruleH_ok.loc[d]
        if ok.sum() < 50:
            continue
        ics.append(s[ok].rank().corr(f[ok].rank()))
    ics = np.array(ics)
    return dict(n=len(ics), ic=ics.mean(),
                t=ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics))))


variants = [('BASE mom20+RuleH (기준선)', mom20, False),
            ('ON   오버나이트20',          on20,  False),
            ('ID   장중20',               id20,  False),
            ('CH   mom20+채널0.4-0.6제외', mom20, True)]

print('=== 사전 스크리닝: 랭크 IC (신호 vs 익일수익률, 일별 Spearman) ===')
for nm, sig, _ in variants[:3]:
    r = rank_ic(sig)
    print(f'  {nm:28s} IC {r["ic"]:+.4f}  t={r["t"]:+.2f}  (n={r["n"]})')

print()
print('=== 픽5 채점: v2.3 손익 (동일가중·1일 회전·10bp·KODEX200 대비, %p/일) ===')
print(f'{"변형":30s} {"n":>4s} {"평균":>8s} {"t":>6s} {"승률":>6s} {"잭나이프하한":>10s} {"train":>8s} {"test":>8s} {"누적":>8s}')
res = {}
for nm, sig, chf in variants:
    t = run_variant(sig, chf)
    s = stats(t)
    res[nm] = (t, s)
    print(f'{nm:30s} {s["n"]:4d} {s["mean"]:+8.4f} {s["t"]:+6.2f} {s["win"]:5.1f}% '
          f'{s["jk"]:+10.4f} {s["train"]:+8.4f} {s["test"]:+8.4f} {s["cum"]:+8.2f}')

base = res['BASE mom20+RuleH (기준선)'][0].set_index('date')['excess']
print()
print('=== 기준선 대비 페어 차이 (같은 날짜만, %p/일) ===')
for nm in list(res)[1:]:
    v = res[nm][0].set_index('date')['excess']
    d = (v - base).dropna()
    n = len(d); m = d.mean(); sd = d.std(ddof=1)
    tt = m / (sd / np.sqrt(n)) if sd > 0 else np.nan
    print(f'  {nm:28s} n={n:4d}  Δ평균 {m:+.4f}  t={tt:+.2f}  Δ누적 {d.sum():+.2f}')
