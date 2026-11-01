# -*- coding: utf-8 -*-
"""2026-08-14 루프 3~5단계 — distinct 5축.

동기: 2026-08-14 채점(D=20260813)에서 트랙 A 1차 P&L **+0.739%(비용후)** →
코스피 대비 **-2.822%p**, KODEX200 대비 **-3.154%p**. 보조 이진 **0/5**
(순위 141·187·124·104·91/187, 컷오프 상위19위 +4.57%).

**사흘 연속 같은 구조**다. 8/11·8/12에 이어 8/13도 시장이 크게 오르는 날(코스피 +3.56%)
우리 픽(화장품·바이오·로봇)만 제자리였다. mom20 상위군이 시장 상승분을 못 따라간다.

검증관(2026-08-13)이 지정한 다음 회차 우선 시도축은 (a) breadth(구성종목 폭) —
**ETF 구성종목 매핑 구축 선행 필요**, (b) 공매도·대차잔고 — **KRX 수집기 선행 필요**,
(c) Rule NL — 관측 전용(승격 근거 금지). (a)(b)는 이번 세션에서 신규 데이터 수집이
불가하므로, **가격 시계열 안에서 아직 열려 있는 형태축 5개**로 iteration 1~5를 채운다.
(a)(b)는 다음 회차 과제로 그대로 이월한다.

 · iteration 1 Rule CLV — **일중 마감 강도**(Close Location Value = (C-L)/(H-L))의 20일 평균.
   8/08 기각된 ONM/IDM 은 *오버나이트 vs 장중 수익률 분해*(수익률 크기)였고, 8/13 기각된 CST 는
   *일별 수익률의 부호 빈도*였다. CLV 는 **하루 안에서 종가가 고·저 범위 어디에 찍히는가**를
   쓴다 — 종가 대 종가 수익률에는 들어 있지 않은 **일중 범위 정보**라 미시도 축이다.
   OHLC 패널(`panel_ohlc_2y.csv`)이 있어야 계산된다.
 · iteration 2 Rule SKW — **20일 일별수익률 왜도**(복권성향 회피). 7/13 기각된 X/X2 는
   **2차 적률(변동성)로 나눈** 위험조정이었다. SKW 는 **3차 적률의 부호**를 쓴다 —
   같은 변동성이라도 '몇 번의 큰 점프로 만든 상승'과 '고르게 쌓은 상승'을 구분한다.
 · iteration 3 Rule JMC — **점프 집중도 조정 모멘텀**. mom20 에서 **기여가 가장 큰 1~2일을
   제거**한 뒤 랭킹. CST(부호 빈도)와 달리 **크기의 집중도**를 직접 깎는다.
   "하루짜리 뉴스로 만든 모멘텀은 반감기가 짧다"는 가설.
 · iteration 4 Rule EWM — **지수가중 모멘텀**(half-life 스윕). 7/15 EE·8/12 DSC·8/13 BWL 이
   기각한 것은 **국면 조건부 룩백 '전환'**(짧게/길게 스위칭)이었다. EWM 은 스위칭 없이
   **상시 가중함수 형태만** 바꾼다 — 조건부가 아니므로 그 축과 구분된다.
 · iteration 5 Rule THM — **테마 수준 모멘텀 집계 후 테마 내 상위 선택**(`theme_map.csv`).
   7/09 Q(섹터 분산 상한)·7/28 NMC(토큰 개수 상한)·8/13 XSN(토큰 내 z)은 전부 테마 쏠림을
   **완화**하는 제약이었고 셋 다 유해했다. THM 은 **반대 방향** — 테마 평균으로 잡음을 줄여
   가장 뜨거운 테마에 의도적으로 집중한다. 방향이 반대이므로 미시도 축이다.

1차 지표 = v2.3 P&L (픽5 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과 + 잭나이프 하한 > baseline 일 때만 후보 승격.
**8/13 절차 교훈 적용** — 후보 승격 전 반드시 `panel_ohlc_2y.csv`(2년) 별도 패널에서 재검정.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용. 조회 전용.
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402
from bt_loop_20260806 import jackknife, tstat  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0813.csv')
B.MINP = 0

OHLC_PATH = os.path.join(HERE, 'panel_ohlc_2y.csv')
THEME_PATH = os.path.join(HERE, 'theme_map.csv')

OHLC = {}      # code -> date -> (o,h,l,c)
THEME = {}     # code -> theme


def load_ohlc():
    out = defaultdict(dict)
    try:
        for r in csv.DictReader(open(OHLC_PATH, encoding='utf-8')):
            try:
                o, h, l, c = (float(r['open']), float(r['high']),
                              float(r['low']), float(r['close']))
            except (ValueError, KeyError, TypeError):
                continue
            if h <= 0 or l <= 0 or c <= 0:
                continue
            out[r['code']][r['date']] = (o, h, l, c)
    except OSError:
        pass
    return out


def load_theme():
    out = {}
    try:
        for r in csv.DictReader(open(THEME_PATH, encoding='utf-8')):
            t = (r.get('theme') or '').strip()
            if t:
                out[r['code']] = t
    except OSError:
        pass
    return out


# ---------------------------------------------------------------- iteration 1
def _clv(c, d, di, dates, k=20):
    """(C-L)/(H-L) 의 최근 k일 평균. 1에 가까울수록 매일 고가 근처에서 마감."""
    i = di.get(d)
    if i is None or i < k:
        return None
    vals = []
    for j in range(i - k + 1, i + 1):
        v = OHLC.get(c, {}).get(dates[j])
        if not v:
            continue
        _o, h, l, cl = v
        if h - l <= 0:
            continue
        vals.append((cl - l) / (h - l))
    return statistics.mean(vals) if len(vals) >= k * 0.8 else None


def clv_sel(cand, px=None, d=None, di=None, dates=None,
            mode='blend', wgt=0.5, k=20, **_):
    rows = []
    for x in cand:
        v = _clv(x['code'], d, di, dates, k)
        if v is not None:
            rows.append((x['code'], x['mom'], v))
    if len(rows) < 10:
        return B.base_sel(cand)
    if mode == 'filter':
        med = statistics.median(v for _, _, v in rows)
        keep = [(c, m) for c, m, v in rows if v >= med]
        if len(keep) < 5:
            return B.base_sel(cand)
        return [c for c, _ in sorted(keep, key=lambda t: -t[1])[:5]]
    if mode == 'only':                     # CLV 단독 랭킹(모멘텀 미사용)
        return [c for c, _, _ in sorted(rows, key=lambda t: -t[2])[:5]]
    ms = [m for _, m, _ in rows]
    vs = [v for _, _, v in rows]
    mm, sm = statistics.mean(ms), (statistics.stdev(ms) or 1.0)
    mv, sv = statistics.mean(vs), (statistics.stdev(vs) or 1.0)
    sc = [(c, (1 - wgt) * (m - mm) / sm + wgt * (v - mv) / sv) for c, m, v in rows]
    return [c for c, _ in sorted(sc, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 2
def _rets(px, c, d, di, dates, k=20):
    i = di[d]
    if i < k:
        return None
    out = []
    for j in range(i - k + 1, i + 1):
        a, b = px[c].get(dates[j - 1]), px[c].get(dates[j])
        if a and b:
            out.append(b / a - 1.0)
    return out if len(out) >= k * 0.8 else None


def _skew(rs):
    n = len(rs)
    if n < 8:
        return None
    mu = statistics.mean(rs)
    sd = statistics.pstdev(rs)
    if sd <= 0:
        return None
    return sum(((r - mu) / sd) ** 3 for r in rs) / n


def skw_sel(cand, px=None, d=None, di=None, dates=None,
            mode='blend', wgt=0.3, **_):
    """Rule SKW — 왜도가 낮을수록(고르게 쌓은 상승) 가점."""
    rows = []
    for x in cand:
        rs = _rets(px, x['code'], d, di, dates, 20)
        s = _skew(rs) if rs else None
        if s is not None:
            rows.append((x['code'], x['mom'], s))
    if len(rows) < 10:
        return B.base_sel(cand)
    if mode == 'filter':                  # 왜도 중앙값 이하만 남기고 mom20 랭킹
        med = statistics.median(s for _, _, s in rows)
        keep = [(c, m) for c, m, s in rows if s <= med]
        if len(keep) < 5:
            return B.base_sel(cand)
        return [c for c, _ in sorted(keep, key=lambda t: -t[1])[:5]]
    if mode == 'filter_hi':               # 반대 방향 대조군
        med = statistics.median(s for _, _, s in rows)
        keep = [(c, m) for c, m, s in rows if s >= med]
        if len(keep) < 5:
            return B.base_sel(cand)
        return [c for c, _ in sorted(keep, key=lambda t: -t[1])[:5]]
    ms = [m for _, m, _ in rows]
    ss = [s for _, _, s in rows]
    mm, sm = statistics.mean(ms), (statistics.stdev(ms) or 1.0)
    mv, sv = statistics.mean(ss), (statistics.stdev(ss) or 1.0)
    sc = [(c, (1 - wgt) * (m - mm) / sm - wgt * (s - mv) / sv) for c, m, s in rows]
    return [c for c, _ in sorted(sc, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 3
def jmc_sel(cand, px=None, d=None, di=None, dates=None, drop=1, **_):
    """Rule JMC — mom20 에서 기여 최대 drop 일을 제거한 누적수익으로 랭킹."""
    rows = []
    for x in cand:
        rs = _rets(px, x['code'], d, di, dates, 20)
        if not rs or len(rs) <= drop + 2:
            continue
        keep = sorted(rs, reverse=True)[drop:]
        acc = 1.0
        for r in keep:
            acc *= (1.0 + r)
        rows.append((x['code'], acc - 1.0))
    if len(rows) < 5:
        return B.base_sel(cand)
    return [c for c, _ in sorted(rows, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 4
def ewm_sel(cand, px=None, d=None, di=None, dates=None, hl=10, k=40, **_):
    """Rule EWM — 반감기 hl 의 지수가중 누적 로그수익(상시, 국면 무조건)."""
    import math
    lam = 0.5 ** (1.0 / hl)
    rows = []
    for x in cand:
        rs = _rets(px, x['code'], d, di, dates, k)
        if not rs:
            continue
        n = len(rs)
        s = w = 0.0
        for j, r in enumerate(rs):          # rs[-1] 이 가장 최근
            wt = lam ** (n - 1 - j)
            if r <= -0.99:
                continue
            s += wt * math.log(1.0 + r)
            w += wt
        if w > 0:
            rows.append((x['code'], s / w))
    if len(rows) < 5:
        return B.base_sel(cand)
    return [c for c, _ in sorted(rows, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 5
def thm_sel(cand, px=None, d=None, di=None, dates=None,
            minn=3, ntheme=1, **_):
    """Rule THM — 테마 평균 mom20 상위 ntheme 테마 안에서만 상위 5종."""
    grp = defaultdict(list)
    for x in cand:
        t = THEME.get(x['code'])
        if t:
            grp[t].append(x)
    ok = {t: xs for t, xs in grp.items() if len(xs) >= minn}
    if len(ok) < ntheme:
        return B.base_sel(cand)
    order = sorted(ok.items(), key=lambda kv: -statistics.mean(x['mom'] for x in kv[1]))
    pool = []
    for _t, xs in order[:ntheme]:
        pool += xs
    if len(pool) < 5:                       # 부족분은 전체 랭킹에서 보충
        rest = [x for x in cand if x not in pool]
        pool += sorted(rest, key=lambda x: -x['mom'])[:5 - len(pool)]
    return [x['code'] for x in sorted(pool, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- 실행
AXES = {
    'CLV': ('iteration 1 · Rule CLV — 일중 마감 강도(20일 평균)', [
        ('CLV 블렌드 w0.3', clv_sel, {'mode': 'blend', 'wgt': 0.3}),
        ('CLV 블렌드 w0.5', clv_sel, {'mode': 'blend', 'wgt': 0.5}),
        ('CLV 블렌드 w0.7', clv_sel, {'mode': 'blend', 'wgt': 0.7}),
        ('CLV 중앙값 필터', clv_sel, {'mode': 'filter'}),
        ('CLV 단독 랭킹', clv_sel, {'mode': 'only'}),
        ('CLV 블렌드 w0.5 k10', clv_sel, {'mode': 'blend', 'wgt': 0.5, 'k': 10}),
    ]),
    'SKW': ('iteration 2 · Rule SKW — 20일 수익률 왜도(복권성향 회피)', [
        ('SKW 블렌드 w0.2', skw_sel, {'mode': 'blend', 'wgt': 0.2}),
        ('SKW 블렌드 w0.3', skw_sel, {'mode': 'blend', 'wgt': 0.3}),
        ('SKW 블렌드 w0.5', skw_sel, {'mode': 'blend', 'wgt': 0.5}),
        ('SKW 저왜도 필터', skw_sel, {'mode': 'filter'}),
        ('SKW 고왜도 필터(대조)', skw_sel, {'mode': 'filter_hi'}),
    ]),
    'JMC': ('iteration 3 · Rule JMC — 점프 집중도 조정 모멘텀', [
        ('JMC drop1', jmc_sel, {'drop': 1}),
        ('JMC drop2', jmc_sel, {'drop': 2}),
        ('JMC drop3', jmc_sel, {'drop': 3}),
    ]),
    'EWM': ('iteration 4 · Rule EWM — 지수가중 모멘텀(반감기 스윕)', [
        ('EWM hl5 k40', ewm_sel, {'hl': 5, 'k': 40}),
        ('EWM hl10 k40', ewm_sel, {'hl': 10, 'k': 40}),
        ('EWM hl15 k40', ewm_sel, {'hl': 15, 'k': 40}),
        ('EWM hl20 k40', ewm_sel, {'hl': 20, 'k': 40}),
        ('EWM hl30 k60', ewm_sel, {'hl': 30, 'k': 60}),
    ]),
    'THM': ('iteration 5 · Rule THM — 테마 수준 모멘텀 집계 후 테마 내 상위', [
        ('THM 1테마 minn3', thm_sel, {'minn': 3, 'ntheme': 1}),
        ('THM 2테마 minn3', thm_sel, {'minn': 3, 'ntheme': 2}),
        ('THM 3테마 minn3', thm_sel, {'minn': 3, 'ntheme': 3}),
    ]),
}
ORDER = ['CLV', 'SKW', 'JMC', 'EWM', 'THM']


def report_axis(key, px, name, dates, di, fo, ins, base, bfull, btr, bte):
    title, variants = AXES[key]
    print(f'\n=== {title} ===')
    print(f"{'변형':24s} {'전체':>9s} {'train':>9s} {'test':>9s} "
          f"{'잭나이프':>9s} {'t':>6s}  판정")
    print('-' * 92)
    passers = []
    for label, fn, kw in variants:
        r = B.run(fn, px, name, dates, di, fo, ins, **kw)
        if not r or len(r) != len(base):
            print(f'{label:24s} — 표본 불일치 {len(r)} vs {len(base)}')
            continue
        h = len(r) // 2
        full, tr, te = statistics.mean(r), statistics.mean(r[:h]), statistics.mean(r[h:])
        ok = full > bfull and tr > btr and te > bte
        jk = jackknife(r) if ok else None
        t = tstat(r, base)
        js = f'{jk:+9.4f}' if jk is not None else f'{"—":>9s}'
        ts = f'{t:+6.2f}' if t is not None else f'{"—":>6s}'
        if not ok:
            verdict = '기각(3분할 미통과)'
        elif jk is not None and jk > bfull:
            verdict = '후보승격→2년재검정'
            passers.append((label, fn, kw))
        else:
            verdict = '가드통과·잭나이프미달'
        print(f'{label:24s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} {js} {ts}  {verdict}')
    return passers


def trigger_stats(fn, kw, px, name, dates, di, label):
    nchg, win, diffs = 0, 0, []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        b = B.base_sel(cand)
        a = fn(cand, px=px, d=d, di=di, dates=dates, **kw)
        if set(a) == set(b):
            continue

        def port(p):
            rs = [px[c][nxt] / px[c][d] - 1.0 for c in p
                  if px[c].get(d) and px[c].get(nxt)]
            return sum(rs) / len(rs) if rs else None
        pa, pb = port(a), port(b)
        if pa is None or pb is None:
            continue
        nchg += 1
        diffs.append(100 * (pa - pb))
        win += 1 if pa > pb else 0
    if not nchg:
        print(f'  [발동] {label}: 0일 — 발동 없음')
        return
    print(f'  [발동] {label}: {nchg}일 · 우위 {win}일({100*win/nchg:.1f}%) · '
          f'평균 차 {statistics.mean(diffs):+.4f}%p')


def confirm_2y(passers):
    """8/13 절차 교훈 — 후보는 반드시 더 긴 별도 패널에서 재검정한다."""
    if not passers:
        print('\n[2년 패널 재검정] 후보 없음 — 생략')
        return
    print('\n=== 2년 패널(panel_ohlc_2y.csv) 재검정 ===')
    px, name, dates = load_2y()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'[2y baseline] n={len(base)}일  full {bfull:+.4f} · '
          f'train {btr:+.4f} · test {bte:+.4f}')
    print(f"{'변형':24s} {'전체':>9s} {'train':>9s} {'test':>9s} "
          f"{'잭나이프':>9s} {'t':>6s}  판정")
    print('-' * 92)
    for label, fn, kw in passers:
        r = B.run(fn, px, name, dates, di, fo, ins, **kw)
        if not r or len(r) != len(base):
            print(f'{label:24s} — 표본 불일치 {len(r)} vs {len(base)}')
            continue
        hh = len(r) // 2
        full, tr, te = (statistics.mean(r), statistics.mean(r[:hh]),
                        statistics.mean(r[hh:]))
        ok = full > bfull and tr > btr and te > bte
        jk = jackknife(r) if ok else None
        t = tstat(r, base)
        js = f'{jk:+9.4f}' if jk is not None else f'{"—":>9s}'
        ts = f'{t:+6.2f}' if t is not None else f'{"—":>6s}'
        verdict = ('기각(2년 3분할 미통과)' if not ok else
                   ('2년 확인 통과' if (jk is not None and jk > bfull)
                    else '2년 잭나이프 미달'))
        print(f'{label:24s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} {js} {ts}  {verdict}')


def load_2y():
    px, name = defaultdict(dict), {}
    for c, dd in OHLC.items():
        for d, v in dd.items():
            px[c][d] = v[3]
    for r in csv.DictReader(open(OHLC_PATH, encoding='utf-8')):
        name[r['code']] = r['name']
    return px, name, sorted({d for c in px for d in px[c]})


def main():
    global OHLC, THEME
    OHLC = load_ohlc()
    THEME = load_theme()
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · 코드 {len(px)}종')
    print(f'OHLC 보조패널 {len(OHLC)}종 · 테마맵 {len(THEME)}종')

    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'\n[baseline] mom20+RuleH  n={len(base)}일  '
          f'full {bfull:+.4f} · train {btr:+.4f} · test {bte:+.4f}  (%p/일, vs KODEX200)')

    want = sys.argv[1:] or ORDER
    passers = []
    for key in ORDER:
        if key not in want:
            continue
        passers += report_axis(key, px, name, dates, di, fo, ins,
                               base, bfull, btr, bte)
        if key == 'CLV':
            trigger_stats(clv_sel, {'mode': 'filter'}, px, name, dates, di,
                          'CLV 중앙값 필터')
        if key == 'THM':
            trigger_stats(thm_sel, {'minn': 3, 'ntheme': 1}, px, name, dates, di,
                          'THM 1테마')
    confirm_2y(passers)
    return 0


if __name__ == '__main__':
    sys.exit(main())
