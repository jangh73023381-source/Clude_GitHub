# -*- coding: utf-8 -*-
"""2026-08-11 루프 3~5단계 — distinct 5축.

동기: 2026-08-10 채점(D=20260810)에서 트랙 A 보조 이진 **0/5**(순위 53·26·179·38·51/187,
컷오프 상위19위 +6.72%). 1차 P&L 은 코스피 대비 +2.413%p·KODEX200 대비 +2.888%p 로 크게
이겼으나 이진 목표(5/5)는 전패다. 그날 상위 10% 슬롯을 **미국 우주항공·우주테크 ETF**가
독식(+10~12%대)했고, 그 종목들은 전부 Rule H(전일 +10% 초과 / 3일 +20% 초과)로 후보에서
제외돼 있었다 — 즉 이진 실패의 직접 원인은 "Rule H 가 그날의 승자군을 통째로 잘랐다"이다.
다만 Rule H 제외군 재편입 계열은 8/6·8/10 두 회차에서 네 경로 전부 유의하게 유해함이
확인됐고 **재시도 금지** 상태다(loop-log 2026-08-10). 따라서 이번 회차는 검증관이 지정한
세 축을 그대로 검정하고, 남은 두 iteration 을 미시도 축으로 채운다.

 · iteration 1 Rule AGL — **AG 의 패널 의존성 제거**. 검증관 지정 (a).
   8/10 에 가드를 통과한 유일 후보 AG(상장 730일↑)는 연령을 `panel_ohlc_2y.csv`(2년)에서
   재므로 730일 임계가 패널 시작일(20240219)과 겹쳐 "패널 개시 시점에 이미 있었는가"라는
   이분 변수에 가까웠다. 이번엔 `panel_ohlc_long.csv`(20190401~, 1800거래일)로 상장연령을
   다시 산출해 임계가 재현되는지 확인하고, **발동일(제외가 실제 픽을 바꾼 날) 수와 그날
   한정 승률**을 함께 출력한다. 축은 같아도 측정 기반이 바뀌므로 재검정 대상이다.
 · iteration 2 Rule WT — **슬롯 금액 가중 축**. 검증관 지정 (b).
   선정 규칙은 그대로 두고 5슬롯의 **금액 가중**만 mom20 랭크·연령으로 차등한다.
   기각된 W1~W3 는 전부 변동성 기반(역변동성·역베타·목표변동성)이므로 distinct.
 · iteration 3 Rule EX — **집행 시점 축**. 검증관 지정 (c).
   같은 픽을 (i) 종가→익일종가(현행) (ii) 종가→익일시가(오버나이트만) (iii) 익일시가→
   익일종가(장중만)로 나눠 벤치마크도 같은 규약으로 맞춰 비교한다. 2026-08-08 의 ONM·IDM
   기각은 '오버나이트/장중 수익률을 **선정 신호**로 쓰는' 축이었고, 여기서는 선정을 건드리지
   않고 **집행 구간**만 바꾸므로 구별된다.
 · iteration 4 Rule TA — **다기간 추세 일치 게이트**. mom20 상위 풀에서 장기 추세가 함께
   살아 있는 종목만 남긴다(mom60>0 · mom120>0 · 종가>MA150). 기각된 MB 는 랭킹 계산식을
   다기간 랭크로 **합성**하는 축이었고, TA 는 랭킹은 mom20 그대로 두고 **필터**로만 쓴다.
 · iteration 5 Rule RV — **횡단면 랭크 속도**. mom20 순위 자체의 최근 k일 변화(올라오는
   중인가)를 우대한다. AC(가격 가속도)는 수익률의 2차 차분이고 RV 는 **횡단면 순위**의
   차분이라 스케일 불변이라는 점에서 구별된다.

1차 지표 = v2.3 P&L (픽5 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과 + 잭나이프 하한 > baseline 일 때만 후보 승격.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용. 조회 전용.
"""
import csv
import os
import statistics
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402
from bt_loop_20260806 import jackknife, tstat  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0810.csv')
B.MINP = 0

FIRST_LONG = {}
OPEN = defaultdict(dict)


# ---------------------------------------------------------------- 공통
def _dt(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def load_first_long():
    """코드별 최초 관측일 — 장기 OHLC 패널(2019-04-01~)에서 읽는다."""
    p = os.path.join(HERE, 'panel_ohlc_long.csv')
    out = {}
    for r in csv.DictReader(open(p, encoding='utf-8')):
        c, d = r['code'], r['date']
        if c not in out or d < out[c]:
            out[c] = d
    return out


def load_open():
    p = os.path.join(HERE, 'panel_open.csv')
    out = defaultdict(dict)
    for r in csv.DictReader(open(p, encoding='utf-8')):
        try:
            out[r['code']][r['date']] = float(r['open'])
        except (ValueError, KeyError):
            continue
    return out


def age_long(code, d):
    f = FIRST_LONG.get(code)
    if not f:
        return -1                      # 장기 패널에 없음 = 연령 미상
    return (_dt(d) - _dt(f)).days


def ma(px, c, d, di, dates, k):
    i = di[d]
    if i < k:
        return None
    vals = [px[c].get(dates[j]) for j in range(i - k + 1, i + 1)]
    vals = [v for v in vals if v]
    return sum(vals) / len(vals) if len(vals) == k else None


# ---------------------------------------------------------------- iteration 1
def agl_sel(cand, px=None, d=None, di=None, dates=None, minage=365,
            unknown_ok=True, **_):
    """Rule AGL — 장기 패널 기준 상장연령 게이트."""
    keep = []
    for x in cand:
        a = age_long(x['code'], d)
        if a < 0:
            if unknown_ok:
                keep.append(x)
            continue
        if a >= minage:
            keep.append(x)
    if len(keep) < 5:
        return B.base_sel(cand)
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 2
def wt_rank(n=5, mode='lin', **_):
    """랭크 기반 슬롯 가중치(합=1)."""
    if mode == 'eq':
        return [1.0 / n] * n
    if mode == 'lin':                    # 5:4:3:2:1
        w = [n - i for i in range(n)]
    elif mode == 'lin2':                 # 3:2.5:2:1.5:1 (완만)
        w = [(n - i) + n for i in range(n)]
    elif mode == 'exp':                  # 기하 0.7
        w = [0.7 ** i for i in range(n)]
    elif mode == 'top':                  # 상위 2종만
        w = [1.0, 1.0, 0.0, 0.0, 0.0]
    else:
        w = [1.0] * n
    s = sum(w)
    return [x / s for x in w]


def wt_age(codes, d, **_):
    """연령 기반 가중 — 오래된 종목에 더 큰 비중(신규 상장 수급 왜곡 회피)."""
    ages = [max(age_long(c, d), 0) for c in codes]
    w = [min(a, 1095) + 180 for a in ages]      # 3년 상한, 하한 보정
    s = sum(w)
    return [x / s for x in w] if s else [1.0 / len(codes)] * len(codes)


def run_weighted(selfn, px, name, dates, di, fo, ins, wmode='eq', **kw):
    """B.run 과 동일하되 슬롯 금액 가중을 적용한다."""
    recs = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        picks = selfn(cand, px=px, d=d, di=di, dates=dates, fo=fo, ins=ins, **kw)
        pr = [(c, px[c][nxt] / px[c][d] - 1.0) for c in picks
              if px[c].get(d) and px[c].get(nxt)]
        if not pr:
            continue
        codes = [c for c, _ in pr]
        if wmode == 'age':
            w = wt_age(codes, d)
        else:
            w = wt_rank(len(pr), wmode)
        s = sum(w)
        w = [x / s for x in w]
        port = sum(wi * ri for wi, (_, ri) in zip(w, pr))
        ba, bb = px[B.BENCH].get(d), px[B.BENCH].get(nxt)
        if not (ba and bb):
            continue
        recs.append(100 * ((port - B.COST) - (bb / ba - 1.0)))
    return recs


# ---------------------------------------------------------------- iteration 3
def run_exec(px, name, dates, di, fo, ins, span='cc'):
    """집행 구간별 성과 — 벤치마크도 같은 구간으로 맞춘다.

    cc = D종가→D+1종가(현행) · on = D종가→D+1시가 · id = D+1시가→D+1종가
    """
    recs = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        picks = B.base_sel(cand)

        def leg(c):
            if span == 'cc':
                a, b = px[c].get(d), px[c].get(nxt)
            elif span == 'on':
                a, b = px[c].get(d), OPEN[c].get(nxt)
            else:
                a, b = OPEN[c].get(nxt), px[c].get(nxt)
            return (b / a - 1.0) if (a and b) else None

        rets = [r for r in (leg(c) for c in picks) if r is not None]
        if len(rets) < 5:
            continue
        br = leg(B.BENCH)
        if br is None:
            continue
        recs.append(100 * ((sum(rets) / len(rets) - B.COST) - br))
    return recs


# ---------------------------------------------------------------- iteration 4
def ta_sel(cand, px=None, d=None, di=None, dates=None, mode='m60', **_):
    """Rule TA — 다기간 추세 일치 게이트(필터 전용, 랭킹은 mom20 그대로)."""
    keep = []
    for x in cand:
        c = x['code']
        ok = True
        if mode in ('m60', 'both'):
            m = B.mom(px, c, d, di, dates, 60)
            ok = ok and (m is not None and m > 0)
        if mode in ('m120', 'both'):
            m = B.mom(px, c, d, di, dates, 120)
            ok = ok and (m is not None and m > 0)
        if mode == 'ma150':
            m = ma(px, c, d, di, dates, 150)
            ok = m is not None and px[c][d] > m
        if ok:
            keep.append(x)
    if len(keep) < 5:
        return B.base_sel(cand)
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 5
def rv_sel(cand, px=None, d=None, di=None, dates=None, k=5, w=0.3, **_):
    """Rule RV — 횡단면 mom20 랭크의 k일 변화(올라오는 중인 종목 우대)."""
    i = di[d]
    if i < 20 + k:
        return B.base_sel(cand)
    d0 = dates[i - k]
    prev = []
    for x in cand:
        m0 = B.mom(px, x['code'], d0, di, dates, 20)
        if m0 is not None:
            prev.append((x['code'], m0))
    if len(prev) < 10:
        return B.base_sel(cand)
    r0 = {c: n for n, (c, _) in enumerate(sorted(prev, key=lambda t: -t[1]))}
    now = sorted(cand, key=lambda x: -x['mom'])
    r1 = {x['code']: n for n, x in enumerate(now)}
    N = len(now)
    scored = []
    for x in now:
        c = x['code']
        if c not in r0:
            continue
        # 랭크 상승폭을 [-1,1] 로 정규화해 mom20 z 대용 점수에 가산
        vel = (r0[c] - r1[c]) / max(N, 1)
        scored.append((c, -r1[c] / max(N, 1) + w * vel))
    if len(scored) < 5:
        return B.base_sel(cand)
    return [c for c, _ in sorted(scored, key=lambda t: -t[1])[:5]]


AXES = {
    'AGL': ('iteration 1 · Rule AGL 장기패널 상장연령 게이트 (검증관 지정 a)', [
        ('AGL 180일↑', agl_sel, {'minage': 180}),
        ('AGL 365일↑', agl_sel, {'minage': 365}),
        ('AGL 730일↑', agl_sel, {'minage': 730}),
        ('AGL 1095일↑', agl_sel, {'minage': 1095}),
        ('AGL 730일↑ (미상 제외)', agl_sel, {'minage': 730, 'unknown_ok': False}),
    ]),
    'TA': ('iteration 4 · Rule TA 다기간 추세 일치 게이트', [
        ('TA mom60>0', ta_sel, {'mode': 'm60'}),
        ('TA mom120>0', ta_sel, {'mode': 'm120'}),
        ('TA mom60&120>0', ta_sel, {'mode': 'both'}),
        ('TA 종가>MA150', ta_sel, {'mode': 'ma150'}),
    ]),
    'RV': ('iteration 5 · Rule RV 횡단면 랭크 속도', [
        ('RV k5 w0.3', rv_sel, {'k': 5, 'w': 0.3}),
        ('RV k5 w0.6', rv_sel, {'k': 5, 'w': 0.6}),
        ('RV k10 w0.3', rv_sel, {'k': 10, 'w': 0.3}),
        ('RV k10 w0.6', rv_sel, {'k': 10, 'w': 0.6}),
        ('RV k20 w0.3', rv_sel, {'k': 20, 'w': 0.3}),
    ]),
}


def report_axis(key, px, name, dates, di, fo, ins, base, bfull, btr, bte):
    title, variants = AXES[key]
    print(f'\n=== {title} ===')
    print(f"{'변형':28s} {'전체':>9s} {'train':>9s} {'test':>9s} "
          f"{'잭나이프':>9s} {'t':>6s}  판정")
    print('-' * 92)
    for label, fn, kw in variants:
        r = B.run(fn, px, name, dates, di, fo, ins, **kw)
        if not r or len(r) != len(base):
            print(f'{label:28s} — 표본 불일치 {len(r)} vs {len(base)}')
            continue
        h = len(r) // 2
        full, tr, te = statistics.mean(r), statistics.mean(r[:h]), statistics.mean(r[h:])
        ok = full > bfull and tr > btr and te > bte
        jk = jackknife(r) if ok else None
        t = tstat(r, base)
        js = f'{jk:+9.4f}' if jk is not None else f'{"—":>9s}'
        ts = f'{t:+6.2f}' if t is not None else f'{"—":>6s}'
        verdict = ('기각(3분할 미통과)' if not ok else
                   ('후보승격' if (jk is not None and jk > bfull)
                    else '가드통과·잭나이프미달'))
        print(f'{label:28s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} {js} {ts}  {verdict}')


def agl_trigger_stats(px, name, dates, di, fo, ins, minage=730):
    """AGL 발동일(제외가 실제 픽을 바꾼 날) 수·그날 한정 승률."""
    nchg, win, diffs = 0, 0, []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        b = B.base_sel(cand)
        a = agl_sel(cand, px=px, d=d, di=di, dates=dates, minage=minage)
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
        if pa > pb:
            win += 1
    m = statistics.mean(diffs) if diffs else 0.0
    print(f'\n[AGL {minage}일 발동 통계] 픽 변경일 {nchg}일 · 우위 {win}일 '
          f'({100 * win / nchg if nchg else 0:.1f}%) · 발동일 평균 차 {m:+.4f}%p')


def main():
    global FIRST_LONG, OPEN
    px, name, dates = B.load_panel()
    import bt_loop_20260806 as L
    L.name_tbl = name
    FIRST_LONG = load_first_long()
    OPEN = load_open()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · 코드 {len(px)}종 · '
          f'장기패널 상장일 {len(FIRST_LONG)}종 · 시가패널 {len(OPEN)}종')

    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'\n[baseline] mom20+RuleH  n={len(base)}일  '
          f'full {bfull:+.4f} · train {btr:+.4f} · test {bte:+.4f}  (%p/일, vs KODEX200)')

    want = sys.argv[1:] or ['AGL', 'WT', 'EX', 'TA', 'RV']

    for key in ('AGL', 'TA', 'RV'):
        if key in want:
            report_axis(key, px, name, dates, di, fo, ins, base, bfull, btr, bte)
    if 'AGL' in want:
        for a in (365, 730, 1095):
            agl_trigger_stats(px, name, dates, di, fo, ins, minage=a)

    # ---- iteration 2 · Rule WT (슬롯 금액 가중)
    if 'WT' in want:
        print('\n=== iteration 2 · Rule WT 슬롯 금액 가중 축 (검증관 지정 b) ===')
        print(f"{'변형':28s} {'전체':>9s} {'train':>9s} {'test':>9s} "
              f"{'잭나이프':>9s} {'t':>6s}  판정")
        print('-' * 92)
        for label, mode in [('WT 동일가중(재현)', 'eq'), ('WT 선형 5:4:3:2:1', 'lin'),
                            ('WT 완만 선형', 'lin2'), ('WT 기하 0.7', 'exp'),
                            ('WT 상위2 집중', 'top'), ('WT 연령 비례', 'age')]:
            r = run_weighted(B.base_sel, px, name, dates, di, fo, ins, wmode=mode)
            if len(r) != len(base):
                print(f'{label:28s} — 표본 불일치 {len(r)} vs {len(base)}')
                continue
            hh = len(r) // 2
            full, tr, te = (statistics.mean(r), statistics.mean(r[:hh]),
                            statistics.mean(r[hh:]))
            ok = full > bfull and tr > btr and te > bte
            jk = jackknife(r) if ok else None
            t = tstat(r, base)
            js = f'{jk:+9.4f}' if jk is not None else f'{"—":>9s}'
            ts = f'{t:+6.2f}' if t is not None else f'{"—":>6s}'
            verdict = ('기각(3분할 미통과)' if not ok else
                       ('후보승격' if (jk is not None and jk > bfull)
                        else '가드통과·잭나이프미달'))
            print(f'{label:28s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} {js} {ts}  {verdict}')

    # ---- iteration 3 · Rule EX (집행 시점)
    if 'EX' in want:
        print('\n=== iteration 3 · Rule EX 집행 시점 축 (검증관 지정 c) ===')
        print('※ 시가 패널은 20240213~20260731 구간만 존재 — 표본이 짧다.')
        res = {}
        for span, lab in [('cc', 'EX 종가→익일종가(현행)'),
                          ('on', 'EX 종가→익일시가(오버나이트)'),
                          ('id', 'EX 익일시가→익일종가(장중)')]:
            r = run_exec(px, name, dates, di, fo, ins, span=span)
            res[span] = r
            if not r:
                print(f'{lab:28s} — 표본 없음')
                continue
            hh = len(r) // 2
            full, tr, te = (statistics.mean(r), statistics.mean(r[:hh]),
                            statistics.mean(r[hh:]))
            print(f'{lab:28s} n={len(r):3d}  full {full:+8.4f} · '
                  f'train {tr:+8.4f} · test {te:+8.4f}')
        if res.get('on') and res.get('id') and res.get('cc'):
            n = min(len(res['on']), len(res['id']), len(res['cc']))
            print(f"\n  분해 합계 확인(n={n}): 오버나이트 "
                  f"{statistics.mean(res['on'][:n]):+.4f} + 장중 "
                  f"{statistics.mean(res['id'][:n]):+.4f} ≈ 종가-종가 "
                  f"{statistics.mean(res['cc'][:n]):+.4f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
