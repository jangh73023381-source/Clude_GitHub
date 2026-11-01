# -*- coding: utf-8 -*-
"""데일리 브리핑 [1-4] 테마별 자금 흐름 — 생성 조각 (2026-10-06 신설, fable/CLAUDE.md 27번).

성격: **참고 정보 전용 — 선정 로직 반영 금지.** 어제 돈이 어느 테마로 몰리고 빠졌는지만 보여준다.
1절 네 번째 소제목으로 넣는다(새 절을 만들면 2절 이하 번호가 밀린다 — 19번 (a)와 같은 취지).

그림 3장(사용자 확정 2026-10-06):
  A  어제 하루 — 테마별 거래대금 ÷ 직전 40거래일 평균 (막대, 옆에 거래대금·점유·등락률)
  B  40일 흐름 히트맵 — 테마 × 최근 40거래일, 칸 색 = 그날 거래대금 ÷ 그날 직전 40일 평균
  C  테마별 40일 미니차트 — 일별 거래대금 막대 + 40일 평균선(점선), 마지막 막대 = 어제

생성기에서:
    import json, subprocess, sys
    blk = json.loads(subprocess.run([sys.executable, 'sector_flow_ref.py', '--json'],
                     capture_output=True, text=True, cwd=FABLE).stdout)
    add_sector_flow(blk, subsection, note, doc)
"""
import os
import math

RED, BLUE, MID = (0.890, 0.286, 0.282), (0.165, 0.471, 0.839), (0.941, 0.937, 0.925)
INK, MUTED, GRID = '#3d3d3a', '#898781', '#e1e0d9'
NAVY = '#1F3864'
WIDTH_IN = 7.0
CLIP = 2.0      # 그림 A 막대 길이 상한(log2) — 25% ~ 400%


def _부록(key):
    import sys, importlib
    d = os.path.dirname(os.path.abspath(__file__))
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        return importlib.import_module('_각주_부록').short(key)
    except Exception:
        return ''


def _font():
    """한글 글꼴 — 맑은 고딕(윈도) 우선, 없으면 Noto Sans CJK(.ttc 는 'JP' 이름으로 등록돼도 한글 글리프가 있다)."""
    import glob, matplotlib
    from matplotlib import font_manager as fm
    for f in glob.glob('/usr/share/fonts/**/NotoSansCJK-Regular.ttc', recursive=True):
        try:
            fm.fontManager.addfont(f)
        except Exception:
            pass
    have = {x.name for x in fm.fontManager.ttflist}
    for f in ('Malgun Gothic', 'Noto Sans CJK KR', 'Noto Sans CJK JP', 'NanumGothic'):
        if f in have:
            matplotlib.rcParams['font.family'] = f
            break
    matplotlib.rcParams['axes.unicode_minus'] = False


def _col(r):
    """비율 → 색. log2 대칭: 50% 이하 = 진한 파랑, 100% = 회색, 200% 이상 = 진한 빨강."""
    if r is None or r <= 0:
        return MID
    t = max(-1.0, min(1.0, math.log2(r)))
    tgt = RED if t > 0 else BLUE
    return tuple(m + (g - m) * abs(t) for m, g in zip(MID, tgt))


def _fmt_v(v):
    return f'{v:.1f}조' if v >= 1 else f'{v * 10000:,.0f}억'


def _md(d):
    return f'{int(d[4:6])}/{int(d[6:])}'


def _pct(p):
    if p is None:
        return ''
    return f"{'▲' if p > 0 else '▼' if p < 0 else ''}{abs(p):.1f}%"


def _clean(ax, left=True):
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    if not left:
        ax.spines['left'].set_visible(False)


def draw(blk, out_dir):
    """PNG 3장을 그리고 경로를 돌려준다."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, MaxNLocator
    _font()
    S, dates = blk['sectors'], blk['dates']
    n = len(S)
    paths = {}

    # ---------------------------------------------------------------- A 어제 하루
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 0.23 * n + 0.75))
    y = list(range(n))[::-1]
    lv = [math.log2(s['ratio'][-1]) if s['ratio'][-1] else 0 for s in S]
    ax.barh(y, [max(-CLIP, min(CLIP, v)) for v in lv], color=[_col(s['ratio'][-1]) for s in S], height=0.7)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_xlim(-CLIP - 0.15, CLIP + 0.15)
    ticks = [-2, -1, 0, 1, 2]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.set_xticklabels([f'{2 ** t * 100:.0f}%' for t in ticks], fontsize=7.5, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([s['name'] for s in S], fontsize=8, color=INK)
    ax.tick_params(length=0)
    for yy, s, v in zip(y, S, lv):
        r = s['ratio'][-1]
        # 막대 끝에 비율(%) — 상한을 넘으면 실제 값을 굵게
        xe = max(-CLIP, min(CLIP, v))
        if abs(v) > CLIP:   # 상한을 넘은 막대 — 막대 안쪽 끝에 실제 값을 흰 글씨로
            ax.text(xe - 0.05 if v > 0 else xe + 0.05, yy, f'{r * 100:.0f}% ▶' if v > 0 else f'◀ {r * 100:.0f}%',
                    va='center', ha='right' if v > 0 else 'left', fontsize=7, color='white', fontweight='bold')
        else:
            ax.text(xe + (0.05 if v >= 0 else -0.05), yy, f'{r * 100:.0f}%', va='center',
                    ha='left' if v >= 0 else 'right', fontsize=7, color=INK)
        ax.text(1.02, yy, f"{_fmt_v(s['value_jo'][-1])} · {s['share']:.1f}%  {_pct(s['pct'])}",
                transform=ax.get_yaxis_transform(), va='center', fontsize=7.3, color=INK)
    ax.text(1.02, n - 0.2, '거래대금 · 점유  등락', transform=ax.get_yaxis_transform(), fontsize=7, color=MUTED)
    ax.set_xlabel('직전 40거래일 평균 대비 (가운데 100% = 평균, 눈금은 2배 간격)', fontsize=7.5, color=MUTED)
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    _clean(ax, left=False)
    fig.tight_layout(rect=(0, 0, 0.80, 1))
    paths['A'] = os.path.join(out_dir, f"_flow_A_{blk['date']}.png")
    fig.savefig(paths['A'], dpi=200)
    plt.close(fig)

    # ---------------------------------------------------------------- B 40일 히트맵
    m = len(dates)
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 0.21 * (n + 1) + 1.0))
    rows = [blk['market']['ratio_series']] + [s['ratio'] for s in S]
    labs = ['시장 전체'] + [s['name'] for s in S]
    for i, rr in enumerate(rows):
        top = n - i
        for j, r in enumerate(rr):
            ax.add_patch(plt.Rectangle((j, top + 0.06), 0.92, 0.88, color=_col(r), lw=0))
        last = rr[-1]
        ax.text(m + 0.4, top + 0.5, f'{last * 100:.0f}%' if last else '—', va='center', fontsize=7,
                color=NAVY if i == 0 else INK, fontweight='bold' if i == 0 else 'normal')
    ax.add_patch(plt.Rectangle((m - 1 - 0.04, 0), 1.0, n + 1, fill=False, ec=INK, lw=0.8))
    ax.set_xlim(0, m + 3.2)
    ax.set_ylim(0, n + 1)
    ax.set_yticks([n - i + 0.5 for i in range(n + 1)])
    ax.set_yticklabels(labs, fontsize=7.5, color=INK)
    ax.get_yticklabels()[0].set_fontweight('bold')
    xt = sorted(set([j for j in range(0, m, 5)] + [m - 1]))
    if m - 1 - xt[-2] < 3:
        xt.pop(-2)
    ax.set_xticks([j + 0.46 for j in xt])
    ax.set_xticklabels([_md(dates[j]) for j in xt], fontsize=7, color=MUTED)
    ax.text(m + 0.4, n + 1.25, '어제', fontsize=7, color=MUTED)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    # 범례
    lg = [0.5, 0.71, 1.0, 1.41, 2.0]
    for k, r in enumerate(lg):
        ax.add_patch(plt.Rectangle((k * 3.2, -1.55), 2.9, 0.65, color=_col(r), clip_on=False, lw=0))
        ax.text(k * 3.2 + 1.45, -2.25, ('≤' if k == 0 else '≥' if k == 4 else '') + f'{r * 100:.0f}%',
                ha='center', fontsize=6.5, color=INK, clip_on=False)
    ax.text(16.6, -1.25, '그날 거래대금 ÷ 그날 직전 40거래일 평균 (빨강 = 평소보다 돈이 많이 들어옴)',
            fontsize=6.5, color=MUTED, va='center', clip_on=False)
    fig.tight_layout()
    paths['B'] = os.path.join(out_dir, f"_flow_B_{blk['date']}.png")
    fig.savefig(paths['B'], dpi=200)
    plt.close(fig)

    # ---------------------------------------------------------------- C 테마별 40일
    cols = 4
    nr = math.ceil(n / cols)
    fig, axs = plt.subplots(nr, cols, figsize=(WIDTH_IN, 1.0 * nr + 0.2))
    for k, ax in enumerate(axs.flat):
        if k >= n:
            ax.axis('off')
            continue
        s = S[k]
        v = s['value_jo']
        r = s['ratio'][-1] or 1
        ax.bar(range(len(v)), v, width=0.8, color=['#b4b2a9'] * (len(v) - 1) + [RED if r >= 1 else BLUE])
        ax.plot(range(len(v)), s['avg40_jo'], color='#444441', lw=0.9, ls=(0, (3, 2)))
        ax.set_title(f"{s['name']}  {r * 100:.0f}%", fontsize=7.3, loc='left', pad=2, color=INK)
        ax.set_xticks([0, len(v) - 1])
        ax.set_xticklabels([_md(dates[0]), _md(dates[-1])], fontsize=6, color=MUTED)
        ax.tick_params(axis='y', labelsize=6, colors=MUTED, length=0)
        ax.tick_params(axis='x', length=0)
        ax.yaxis.set_major_locator(MaxNLocator(3))
        ax.set_ylim(0, max(max(v), max(s['avg40_jo'])) * 1.08 or 1)
        _clean(ax)
        ax.spines['left'].set_color('#c3c2b7')
        ax.spines['bottom'].set_color('#c3c2b7')
    fig.tight_layout(h_pad=0.5, w_pad=0.6)
    paths['C'] = os.path.join(out_dir, f"_flow_C_{blk['date']}.png")
    fig.savefig(paths['C'], dpi=200)
    plt.close(fig)
    return paths


def _big(blk):
    return [s for s in blk['sectors'] if s['name'] != '기타(미분류)']


def summary(blk):
    """본문 첫 줄·카톡 한 줄 공용. 수기 작성 금지."""
    m = blk['market']
    big = _big(blk)
    up = [s for s in big if s['ratio'][-1] >= 1.2][:3]
    dn = [s for s in big[::-1] if s['ratio'][-1] <= 0.8][:3]
    f = lambda s: f"{s['name']} {s['ratio'][-1] * 100:.0f}%"
    t = f"{_md(blk['date'])} 시장 거래대금 {m['value_jo']:.1f}조 — 40일 평균의 {m['ratio'] * 100:.0f}%."
    if up:
        t += " 평균보다 몰린 곳: " + ', '.join(f(s) for s in up) + '.'
    if dn:
        t += " 빠진 곳: " + ', '.join(f(s) for s in dn) + '.'
    return t


def leaders_lines(blk, k=5):
    """돈이 몰린 테마(평균의 120% 이상) 상위 k개의 주도 종목 — 그림 A 아래 한 줄씩."""
    out = []
    for s in [x for x in _big(blk) if x['ratio'][-1] >= 1.2][:k]:
        ld = ' · '.join(f"{l['name']} {l['value_eok']:,}억 {_pct(l['chg'])}" for l in s['leaders'])
        out.append(f"{s['name']}({s['ratio'][-1] * 100:.0f}%) — {ld}")
    return out


def add_sector_flow(blk, subsection, note, doc, out_dir='.'):
    from docx.shared import Inches
    head = '[1-4] 테마별 자금 흐름 — 거래대금 ÷ 직전 40거래일 평균'
    if not blk.get('sectors'):
        subsection(head)
        note(f"※ 산출 실패 — {blk.get('error', '데이터 없음')}. 10절 검증표에 결손을 적습니다.", size=9)
        return
    if blk.get('stale'):
        head += ' ※캐시(갱신 실패)'
    subsection(head + ' (참고 전용, 종목 선정 미적용)')
    note('※ ' + summary(blk), size=9.5)
    p = draw(blk, out_dir)
    note('A. 어제 하루 — 가운데 100%가 평소(직전 40거래일 평균). 빨강 = 평소보다 돈이 더 들어옴, 파랑 = 덜 들어옴. '
         '오른쪽 = 어제 거래대금 · 시장 점유 · 테마 등락률(거래대금 가중).', size=8.5)
    doc.add_picture(p['A'], width=Inches(WIDTH_IN))
    ll = leaders_lines(blk)
    if ll:
        note('돈이 몰린 테마의 주도 종목(거래대금 상위 3) — ' + ' / '.join(ll), size=8.5)
    note('B. 40일 흐름 — 한 칸 = 그날 거래대금 ÷ 그날 직전 40거래일 평균. 가로로 읽으면 그 테마에 돈이 들어오는 중인지 '
         '빠지는 중인지, 세로로 읽으면 그날 돈이 어디서 어디로 옮겨갔는지가 보입니다. 맨 오른쪽 테두리 칸이 어제입니다.', size=8.5)
    doc.add_picture(p['B'], width=Inches(WIDTH_IN))
    note('C. 테마별 40일 — 막대 = 일별 거래대금(조), 점선 = 직전 40거래일 평균, 마지막 막대 = 어제(빨강 평균 이상 / 파랑 미만). '
         '테마마다 세로축 크기가 다릅니다.', size=8.5)
    doc.add_picture(p['C'], width=Inches(WIDTH_IN))
    if blk.get('source_D') == 'kiwoom':
        note(f"※ 어제({_md(blk['date'])}) 값은 키움 거래대금 순위(ka10032) 스냅샷이고, 그 이전은 KRX 전종목 일별 확정치입니다.", size=8.5)
    note(_부록('flow'), size=9)
    for w in blk.get('warn', []):
        note('※ ' + w, size=8.5)


def kakao_line(blk):
    return ('자금흐름 ' + summary(blk) + ' ※참고 전용') if blk.get('sectors') else ''
