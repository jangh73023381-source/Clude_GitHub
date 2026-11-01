#!/usr/bin/env python3
"""보고서 차트 3종 (조회 전용). 팔레트: dataviz 기본 범주색 1~3(검증 통과, aqua 는 대비 경고 → 직접 라벨 병기)."""
import json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
fp = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
fm.fontManager.addfont(fp); plt.rcParams['font.family'] = fm.FontProperties(fname=fp).get_name()
plt.rcParams['axes.unicode_minus'] = False
BLUE, ORANGE, AQUA, INK, MUTED, GRID = '#2a78d6', '#eb6834', '#1baf7a', '#222222', '#6b6b66', '#e6e6e3'


def style(ax):
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color('#bdbdb8')
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis='y', color=GRID, lw=0.8); ax.set_axisbelow(True)


# 1) 신호 후 누적 초과수익 경로
P = json.load(open('finalists_path.json', encoding='utf-8'))['path']
fig, ax = plt.subplots(figsize=(7.2, 3.1), dpi=200)
spec = [('F14 역배열 진입', '역배열 진입(채택 후보)', BLUE, '-'), ('F3c 데드크로스 20/60', '데드크로스 20/60', ORANGE, '-'),
        ('F12 mom20 하위 10% 진입', 'mom20 하위 10%(순수 모멘텀 참조)', AQUA, '--')]
for k, lab, col, ls in spec:
    xs = [h for h, _ in P[k]]; ys = [v for _, v in P[k]]
    ax.plot(xs, ys, color=col, lw=2, ls=ls, marker='o', ms=3.5, label=lab)
    ax.annotate(f'{ys[-1]:+.2f}', (xs[-1], ys[-1]), xytext=(4, 0), textcoords='offset points', fontsize=7.5, color=INK, va='center')
ax.axhline(0, color='#9a9a95', lw=1)
ax.axvline(20, color='#9a9a95', lw=1, ls=':'); ax.text(20.6, 0.12, '금지 20거래일', fontsize=7.5, color=MUTED)
ax.set_xlabel('신호 후 거래일(브리핑일 종가 매수 기준)', fontsize=8, color=MUTED)
ax.set_ylabel('유니버스 대비 누적 초과(%p)', fontsize=8, color=MUTED)
ax.set_xlim(0, 66); style(ax)
ax.legend(fontsize=7.5, frameon=False, loc='lower left')
fig.tight_layout(); fig.savefig('chart_path.png', facecolor='white'); plt.close(fig)

# 2) V1 연도별 목록 일평균 초과(bp/일)
G = json.load(open('gates_v1.json', encoding='utf-8'))
ys = G['years']; xs = list(ys.keys()); vs = list(ys.values())
fig, ax = plt.subplots(figsize=(7.2, 2.6), dpi=200)
b = ax.bar(xs, vs, color=BLUE, width=0.6)
for x, v in zip(xs, vs):
    ax.annotate(f'{v:+.1f}', (x, v), xytext=(0, -9), textcoords='offset points', ha='center', fontsize=7.5, color=INK)
ax.axhline(0, color='#9a9a95', lw=1); ax.set_ylim(min(vs) * 1.15, 2)
ax.set_ylabel('bp/일', fontsize=8, color=MUTED); ax.set_xticks(xs); ax.set_xticklabels([f"{x}{'(~9/10)' if x == '2026' else ''}" for x in xs])
style(ax); fig.tight_layout(); fig.savefig('chart_years.png', facecolor='white'); plt.close(fig)

# 3) 목록 비중 구간별 — 샀다면 20거래일 초과
D = json.load(open('describe_v1.json', encoding='utf-8'))
cats = ['소(≤5.4%)', '중(5.4~17.2%)', '대(>17.2%)']
ban = [D[f'금지 목록 · 목록비중 {c}']['excess'] for c in cats]
non = [D[f'목록 밖 · 목록비중 {c}']['excess'] for c in cats]
fig, ax = plt.subplots(figsize=(7.2, 2.6), dpi=200)
import numpy as np
x = np.arange(3); w = 0.34
ax.bar(x - w / 2 - 0.01, ban, w, color=BLUE, label='금지 목록 종목')
ax.bar(x + w / 2 + 0.01, non, w, color=ORANGE, label='목록 밖 종목')
for xi, v in zip(x - w / 2, ban):
    ax.annotate(f'{v:+.2f}', (xi, v), xytext=(0, -9 if v < 0 else 3), textcoords='offset points', ha='center', fontsize=7.5, color=INK)
for xi, v in zip(x + w / 2, non):
    ax.annotate(f'{v:+.2f}', (xi, v), xytext=(0, 3), textcoords='offset points', ha='center', fontsize=7.5, color=INK)
ax.axhline(0, color='#9a9a95', lw=1)
ax.set_xticks(x); ax.set_xticklabels([f'목록 비중 {c}' for c in cats], fontsize=8)
ax.set_ylim(min(ban) * 1.2, max(non) + 0.35)
ax.set_ylabel('20거래일 초과(%p)', fontsize=8, color=MUTED); style(ax)
ax.legend(fontsize=7.5, frameon=False, loc='lower right')
fig.tight_layout(); fig.savefig('chart_size.png', facecolor='white'); plt.close(fig)
print('charts ok')
