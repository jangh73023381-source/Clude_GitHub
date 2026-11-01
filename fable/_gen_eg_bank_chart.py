# -*- coding: utf-8 -*-
"""Rule EG v1.2 은행 ETF 1년 캔들차트 — 매수(빨간 화살표)·매도(파란 화살표)"""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib import font_manager as fm

LOOP = os.path.expanduser('~/mnt/loop')
for f in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
    if os.path.exists(f):
        fm.fontManager.addfont(f)
plt.rcParams['font.family'] = 'Noto Sans CJK JP'
plt.rcParams['axes.unicode_minus'] = False

PULL_WIN = 10          # v1.2
HOLD = 20

lg = pd.read_csv(os.path.join(LOOP,'backtest','panel_ohlc_long.csv'), dtype={'code':str})
t2 = pd.read_csv(os.path.join(LOOP,'backtest','panel_ohlc_2y.csv'), dtype={'code':str})
p = pd.concat([lg, t2[t2.date > lg.date.max()][lg.columns]], ignore_index=True)
p = p.drop_duplicates(['code','date']).sort_values(['code','date'])

def signals(d, pull_win):
    H,L,C,O,V = d.high,d.low,d.close,d.open,d.volume
    M  = C.rolling(20).mean(); M1 = M.shift(1)
    M6 = C.rolling(60).mean(); VA = V.rolling(20).mean()
    core = (C>=M) & (M>M1) & (C>M6) & (M6>=M6.shift(5))
    pull = L.rolling(pull_win).min() <= M*1.02
    eg = (core & pull & (C>=O.shift(1)) & (C>O) & (C.shift(1)<O.shift(1))
          & (C>=L+(H-L)*0.6) & (V>=VA*1.3)).fillna(False)
    return eg, M, M6

def draw(ax, axv, d, code, name, eg, M, M6, start_idx):
    dd = d.iloc[start_idx:].reset_index(drop=True)
    m20 = M.iloc[start_idx:].reset_index(drop=True)
    m60 = M6.iloc[start_idx:].reset_index(drop=True)
    n = len(dd)
    UP, DN = '#D9333F', '#2E6FD9'
    for i in range(n):
        o,h,l,c = dd.open[i], dd.high[i], dd.low[i], dd.close[i]
        col = UP if c >= o else DN
        ax.vlines(i, l, h, color=col, linewidth=0.8, alpha=.85)
        lo, hi = min(o,c), max(o,c)
        ax.add_patch(Rectangle((i-0.32, lo), 0.64, max(hi-lo, (dd.high.max()-dd.low.min())*0.0012),
                               facecolor=col if c>=o else 'none',
                               edgecolor=col, linewidth=0.8, alpha=.9))
        axv.bar(i, dd.volume[i], width=0.64, color=col, alpha=.45, linewidth=0)
    ax.plot(range(n), m20, color='#E08A00', lw=1.1, label='MA20')
    ax.plot(range(n), m60, color='#7B61A8', lw=1.1, label='MA60')

    rng = dd.high.max() - dd.low.min()
    trades = []
    sig_local = [i for i in range(n) if bool(eg.iloc[start_idx+i])]
    placed_b, placed_s = [], []
    for i in sig_local:
        j = i + HOLD
        buy = dd.close[i]
        yb = dd.low[i]-rng*0.085
        while any(abs(px-i) < 16 and abs(py-yb) < rng*0.105 for px, py in placed_b):
            yb -= rng*0.105
        placed_b.append((i, yb))
        ax.annotate('', xy=(i, dd.low[i]-rng*0.015), xytext=(i, yb),
                    arrowprops=dict(arrowstyle='-|>,head_width=0.32,head_length=0.6',
                                    color='#D9333F', lw=2.2))
        ax.text(i, yb-rng*0.012, f'매수\n{buy:,.0f}', ha='center', va='top',
                fontsize=6.6, color='#B01F29', linespacing=1.15)
        if j < n:
            sell = dd.close[j]
            pnl = (sell/buy-1)*100
            trades.append((dd.date[i], dd.date[j], buy, sell, pnl))
            ys = dd.high[j]+rng*0.085
            while any(abs(px-j) < 16 and abs(py-ys) < rng*0.135 for px, py in placed_s):
                ys += rng*0.135
            placed_s.append((j, ys))
            ax.annotate('', xy=(j, dd.high[j]+rng*0.015), xytext=(j, ys),
                        arrowprops=dict(arrowstyle='-|>,head_width=0.32,head_length=0.6',
                                        color='#2E6FD9', lw=2.2))
            ax.text(j, ys+rng*0.012, f'매도\n{sell:,.0f}\n{pnl:+.1f}%', ha='center', va='bottom',
                    fontsize=6.6, color='#1B4FA0', linespacing=1.15)
            ax.plot([i,j],[buy,sell], color='#888', lw=0.8, ls=':', zorder=1)
        else:
            trades.append((dd.date[i], None, buy, dd.close.iloc[-1], (dd.close.iloc[-1]/buy-1)*100))
            ax.axvspan(i, n-1, color='#D9333F', alpha=.05)

    ticks = [i for i in range(n) if i>0 and str(dd.date[i])[:6] != str(dd.date[i-1])[:6]]
    lab = [f"{str(dd.date[i])[2:4]}.{str(dd.date[i])[4:6]}" for i in ticks]
    ax.set_xticks(ticks); ax.tick_params(axis='x', labelbottom=False)
    axv.set_xticks(ticks); axv.set_xticklabels(lab, fontsize=7.5)
    ax.set_xlim(-2, n+1); axv.set_xlim(-2, n+1)
    ax.set_ylim(min(dd.low.min()-rng*0.30, min([y for _,y in placed_b], default=1e18)-rng*0.10),
                max(dd.high.max()+rng*0.34, max([y for _,y in placed_s], default=-1e18)+rng*0.16))
    ax.grid(axis='y', color='#E6E6E6', lw=.6); ax.set_axisbelow(True)
    axv.grid(axis='y', color='#EEEEEE', lw=.5); axv.set_axisbelow(True)
    axv.set_yticks([]); axv.set_ylabel('거래량', fontsize=7.5, color='#666')
    ax.set_ylabel('종가(원)', fontsize=8.5)
    ax.legend(loc='upper left', fontsize=7.5, frameon=False)
    ax.set_title(f'{name} ({code}) — Rule EG v1.2 매수·매도 타점 · 최근 1년',
                 fontsize=12, fontweight='bold', pad=8, loc='left')
    for s in ('top','right'):
        ax.spines[s].set_visible(False); axv.spines[s].set_visible(False)
    return trades

CODES = [('466940','TIGER 은행고배당플러스TOP10'), ('091170','KODEX 은행')]
END = 20260903
allt = {}
for code, _nm in CODES:
    d = p[p.code==code].reset_index(drop=True)
    eg, M, M6 = signals(d, PULL_WIN)
    idx = d.index[d.date<=END][-1]
    start_idx = max(0, idx-246)
    name = d.name.iloc[0]
    fig = plt.figure(figsize=(15, 8.2), dpi=170)
    gs = fig.add_gridspec(2, 1, height_ratios=[3.4, 1.0], hspace=0.06)
    ax = fig.add_subplot(gs[0]); axv = fig.add_subplot(gs[1], sharex=ax)
    tr = draw(ax, axv, d, code, name, eg, M, M6, start_idx)
    allt[code] = (name, tr)
    win = [t for t in tr if t[1] is not None]
    s = (f"신호 {len(tr)}건 · 청산완료 {len(win)}건 · 평균 {np.mean([t[4] for t in win]):+.2f}% · "
         f"승률 {100*np.mean([t[4]>0 for t in win]):.0f}%") if win else "청산 완료 거래 없음"
    fig.text(0.012, 0.012, f"규칙: C≥MA20 · MA20↑ · C>MA60 · MA60↑(5일) · lowest(L,10)≤MA20×1.02 · C≥O(1) · C>O · C(1)<O(1) · "
                           f"C≥L+(H−L)×0.6 · V≥avg(V,20)×1.3  →  매수(종가), 20거래일 뒤 종가 매도\n"
                           f"{s}   |   빨간 화살표=매수 · 파란 화살표=매도 · 수급 게이트/5슬롯 미적용(수식 단독)",
             fontsize=7.4, color='#555', va='bottom')
    fig.subplots_adjust(left=0.055, right=0.985, top=0.945, bottom=0.105)
    out = os.path.expanduser(f'~/mnt/fable/트랙D_RuleEG_v1.2_{code}_1년캔들_2026-09-03.png')
    fig.savefig(out, facecolor='white'); plt.close(fig)
    print('saved', out)

for c,(nm,tr) in allt.items():
    print('\n==', c, nm)
    for t in tr:
        print(f"  {t[0]} 매수 {t[2]:,.0f} → {t[1] or '보유중'} 매도 {t[3]:,.0f}  {t[4]:+.2f}%")
