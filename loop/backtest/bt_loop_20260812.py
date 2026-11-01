# -*- coding: utf-8 -*-
"""2026-08-12 루프 3~5단계 — distinct 5축.

동기: 2026-08-12 채점(D=20260811)에서 트랙 A 는 **1차 P&L -0.816%p(코스피 대비)**,
보조 이진 **1/5**(순위 81·145·112·2·160/187, 컷오프 상위19위 +1.36%). 8/10 회차와 달리
컷오프는 평범했는데도(+1.36%) 4종이 컷 아래였고 포트가 코스피에 졌다.

검증관(2026-08-11)이 지정한 다음 회차 우선 시도축 (a)(b)를 iteration 1~2 로 그대로 검정하고,
남은 3축은 미시도 축으로 채운다.

 · iteration 1 Rule KD — **코스닥/코스피 괴리 국면 슬롯 확보**. 검증관 지정 (a).
   7/29 기각된 Rule RS 는 "주도시장 계열만 남긴다"는 **필터**였고, KD 는 괴리가 임계를 넘은
   날에 한해 **코스닥 계열 1슬롯을 강제 확보**하는 슬롯 할당이다(나머지 4슬롯은 mom20 그대로).
   RS 는 후보를 잘라내고 KD 는 후보를 밀어넣으므로 구별된다.
 · iteration 2 Rule TAL — **장기 추세 게이트 재검정**. 검증관 지정 (b).
   8/11 의 TA 는 110거래일 패널에서 mom120·MA150 계산이 불가해 전량 baseline 폴백했다.
   이번엔 `panel_ohlc_long.csv`(20190401~20260729) 종가에 현행 패널을 이어붙인 **장기 종가
   시계열**로 다시 산출한다. 축은 같아도 이전 회차는 '검정 불가'였으므로 결론이 없다.
 · iteration 3 Rule DSC — **횡단면 분산 조건부 룩백 전환**. 승자 독식일(횡단면 수익률 분산이
   큰 날)에는 20일 모멘텀이 이미 식은 테마를 가리킬 수 있다. 분산이 상위 분위인 날만
   mom5/mom10 으로 룩백을 바꾼다. 7/23 기각된 PN1(mom5 **상시**)·PN3(가중 합성)과 달리
   **국면 조건부 전환**이라 구별된다.
 · iteration 4 Rule RC — **베타조정 잔차 모멘텀**. mom20 에서 벤치 베타×벤치 mom20 을 뺀
   잔차로 랭킹한다. 8/5 기각된 EM(지수 초과 모멘텀)은 벤치 mom 이 횡단면 상수라 랭킹이
   불변이었으나, 베타가 종목마다 다르므로 RC 는 실제로 순위를 바꾼다. 7/26 기각된 W2(역베타)는
   **비중 배분** 축이고 RC 는 **랭킹** 축이다.
 · iteration 5 Rule HD — **단기 트랙 보유기간(회전) 축**. 지금까지 보유기간 검정은 중기 트랙
   (H=5/10/20/40)에서만 했고 단기 트랙은 1일 회전을 한 번도 흔들지 않았다. 탈락청산 규약으로
   H=1/2/3/5 를 비교한다(집행 축 관측 — 선정 규칙은 불변).

1차 지표 = v2.3 P&L (픽5 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과 + 잭나이프 하한 > baseline 일 때만 후보 승격.
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

B.PANEL = os.path.join(HERE, 'panel_close_0811.csv')
B.MINP = 0

LPX = defaultdict(dict)      # 장기 종가 시계열 (long + 현행 패널 스티칭)
LDATES = []
LDI = {}
XSD = {}                     # 날짜 → 횡단면 일간수익률 표준편차
XSD_SORTED = []


# ---------------------------------------------------------------- 공통 준비
def build_long(px, dates):
    """장기 패널(20190401~20260729) 종가에 현행 패널을 이어붙인다."""
    p = os.path.join(HERE, 'panel_ohlc_long.csv')
    out = defaultdict(dict)
    ds = set()
    for r in csv.DictReader(open(p, encoding='utf-8')):
        try:
            out[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError):
            continue
        ds.add(r['date'])
    for c in px:
        for d, v in px[c].items():
            out[c][d] = v          # 겹치는 구간은 현행 패널 값으로 덮어쓴다
            ds.add(d)
    dl = sorted(ds)
    return out, dl, {d: i for i, d in enumerate(dl)}


def lmom(c, d, k):
    i = LDI.get(d)
    if i is None or i < k:
        return None
    a, b = LPX[c].get(LDATES[i - k]), LPX[c].get(d)
    return (b / a - 1.0) if (a and b) else None


def lma(c, d, k):
    i = LDI.get(d)
    if i is None or i < k:
        return None
    vals = [LPX[c].get(LDATES[j]) for j in range(i - k + 1, i + 1)]
    vals = [v for v in vals if v]
    return sum(vals) / len(vals) if len(vals) >= int(k * 0.9) else None


def build_xsd(px, name, dates, di):
    """날짜별 횡단면 일간수익률 표준편차 — 컷오프 높이의 프록시."""
    out = {}
    for i in range(1, len(dates)):
        d, prv = dates[i], dates[i - 1]
        rs = []
        for c in px:
            a, b = px[c].get(prv), px[c].get(d)
            if a and b and B.is_spot(name.get(c, '')) and not B.is_cash(name.get(c, '')):
                rs.append(b / a - 1.0)
        if len(rs) >= 30:
            out[d] = statistics.stdev(rs)
    return out


def xsd_pctl(d, p):
    """D 시점까지의 **과거** 분산만 써서 분위 임계를 구한다(룩어헤드 금지)."""
    hist = [XSD[x] for x in XSD_SORTED if x <= d]
    if len(hist) < 30 or d not in XSD:
        return False
    hist = sorted(hist)
    thr = hist[int(len(hist) * p / 100.0)]
    return XSD[d] >= thr


# ---------------------------------------------------------------- iteration 1
def kd_sel(cand, px=None, d=None, di=None, dates=None, k=10, thr=2.0, **_):
    """Rule KD — 코스닥/코스피 괴리 국면에서 코스닥 계열 1슬롯 강제 확보."""
    base = B.base_sel(cand)
    i = di[d]
    if i < k:
        return base
    pa, pb = px[B.BENCH].get(dates[i - k]), px[B.BENCH].get(d)
    qa, qb = px[B.KQ].get(dates[i - k]), px[B.KQ].get(d)
    if not (pa and pb and qa and qb):
        return base
    spread = 100 * ((qb / qa - 1.0) - (pb / pa - 1.0))
    if spread < thr:
        return base
    kq = [x for x in cand if '코스닥' in x['name']]
    if not kq:
        return base
    if any(c in [x['code'] for x in kq] for c in base):
        return base
    top = max(kq, key=lambda x: x['mom'])
    return base[:4] + [top['code']]


# ---------------------------------------------------------------- iteration 2
def tal_sel(cand, px=None, d=None, di=None, dates=None, mode='m120', **_):
    """Rule TAL — 장기 종가 시계열 기반 다기간 추세 일치 게이트(필터 전용)."""
    keep = []
    for x in cand:
        c = x['code']
        if mode == 'm120':
            v = lmom(c, d, 120)
            ok = v is not None and v > 0
        elif mode == 'm250':
            v = lmom(c, d, 250)
            ok = v is not None and v > 0
        elif mode == 'ma150':
            m = lma(c, d, 150)
            ok = m is not None and LPX[c].get(d) is not None and LPX[c][d] > m
        elif mode == 'ma200':
            m = lma(c, d, 200)
            ok = m is not None and LPX[c].get(d) is not None and LPX[c][d] > m
        else:                                            # both
            a, b = lmom(c, d, 60), lmom(c, d, 120)
            ok = (a is not None and a > 0) and (b is not None and b > 0)
        if ok:
            keep.append(x)
    if len(keep) < 5:
        return B.base_sel(cand)
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 3
def dsc_sel(cand, px=None, d=None, di=None, dates=None, p=80, k=5, **_):
    """Rule DSC — 횡단면 분산 상위 분위 국면에서만 단기 룩백으로 전환."""
    if not xsd_pctl(d, p):
        return B.base_sel(cand)
    scored = []
    for x in cand:
        m = B.mom(px, x['code'], d, di, dates, k)
        if m is not None:
            scored.append((x['code'], m))
    if len(scored) < 5:
        return B.base_sel(cand)
    return [c for c, _ in sorted(scored, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 4
def _beta(px, c, d, di, dates, w):
    i = di[d]
    if i < w:
        return None
    xs, ys = [], []
    for j in range(i - w + 1, i + 1):
        a, b = px[c].get(dates[j - 1]), px[c].get(dates[j])
        p, q = px[B.BENCH].get(dates[j - 1]), px[B.BENCH].get(dates[j])
        if a and b and p and q:
            ys.append(b / a - 1.0)
            xs.append(q / p - 1.0)
    if len(xs) < w * 0.8:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def rc_sel(cand, px=None, d=None, di=None, dates=None, w=60, lam=1.0, **_):
    """Rule RC — 벤치 베타를 제거한 잔차 모멘텀으로 랭킹한다."""
    bm = B.mom(px, B.BENCH, d, di, dates, 20)
    if bm is None:
        return B.base_sel(cand)
    scored = []
    for x in cand:
        bt = _beta(px, x['code'], d, di, dates, w)
        if bt is None:
            scored.append((x['code'], x['mom']))
        else:
            scored.append((x['code'], x['mom'] - lam * bt * bm))
    return [c for c, _ in sorted(scored, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 5
def run_hold(px, name, dates, di, H=1):
    """Rule HD — 보유기간 H(탈락청산). 매일 재선정하고 보유집합 = 최근 H회 픽의 합집합."""
    recs, book = [], []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        book.append(B.base_sel(cand))
        book = book[-H:]
        hold = []
        for p in book:
            for c in p:
                if c not in hold:
                    hold.append(c)
        rets = [px[c][nxt] / px[c][d] - 1.0 for c in hold
                if px[c].get(d) and px[c].get(nxt)]
        if not rets:
            continue
        ba, bb = px[B.BENCH].get(d), px[B.BENCH].get(nxt)
        if not (ba and bb):
            continue
        # 회전분에만 비용 — 신규 편입 비율 × 왕복 10bp
        new = sum(1 for c in book[-1] if c not in
                  [x for p in book[:-1] for x in p]) if len(book) > 1 else len(book[-1])
        cost = B.COST * (new / max(len(hold), 1))
        recs.append(100 * ((sum(rets) / len(rets) - cost) - (bb / ba - 1.0)))
    return recs


# ---------------------------------------------------------------- 리포트
AXES = {
    'KD': ('iteration 1 · Rule KD 코스닥 괴리 슬롯 확보 (검증관 지정 a)', [
        ('KD k5 thr+2%', kd_sel, {'k': 5, 'thr': 2.0}),
        ('KD k10 thr+2%', kd_sel, {'k': 10, 'thr': 2.0}),
        ('KD k10 thr+4%', kd_sel, {'k': 10, 'thr': 4.0}),
        ('KD k20 thr+4%', kd_sel, {'k': 20, 'thr': 4.0}),
        ('KD 상시(thr=-99)', kd_sel, {'k': 10, 'thr': -99.0}),
    ]),
    'TAL': ('iteration 2 · Rule TAL 장기 추세 게이트 재검정 (검증관 지정 b)', [
        ('TAL mom120>0', tal_sel, {'mode': 'm120'}),
        ('TAL mom250>0', tal_sel, {'mode': 'm250'}),
        ('TAL 종가>MA150', tal_sel, {'mode': 'ma150'}),
        ('TAL 종가>MA200', tal_sel, {'mode': 'ma200'}),
        ('TAL mom60&120>0', tal_sel, {'mode': 'both'}),
    ]),
    'DSC': ('iteration 3 · Rule DSC 횡단면 분산 조건부 룩백 전환', [
        ('DSC p70 → mom5', dsc_sel, {'p': 70, 'k': 5}),
        ('DSC p80 → mom5', dsc_sel, {'p': 80, 'k': 5}),
        ('DSC p90 → mom5', dsc_sel, {'p': 90, 'k': 5}),
        ('DSC p80 → mom10', dsc_sel, {'p': 80, 'k': 10}),
    ]),
    'RC': ('iteration 4 · Rule RC 베타조정 잔차 모멘텀', [
        ('RC w40 λ1.0', rc_sel, {'w': 40, 'lam': 1.0}),
        ('RC w60 λ1.0', rc_sel, {'w': 60, 'lam': 1.0}),
        ('RC w60 λ0.5', rc_sel, {'w': 60, 'lam': 0.5}),
        ('RC w60 λ2.0', rc_sel, {'w': 60, 'lam': 2.0}),
        ('RC w90 λ1.0', rc_sel, {'w': 90, 'lam': 1.0}),
    ]),
}


def report_axis(key, px, name, dates, di, fo, ins, base, bfull, btr, bte):
    title, variants = AXES[key]
    print(f'\n=== {title} ===')
    print(f"{'변형':24s} {'전체':>9s} {'train':>9s} {'test':>9s} "
          f"{'잭나이프':>9s} {'t':>6s}  판정")
    print('-' * 88)
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
        verdict = ('기각(3분할 미통과)' if not ok else
                   ('후보승격' if (jk is not None and jk > bfull)
                    else '가드통과·잭나이프미달'))
        print(f'{label:24s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} {js} {ts}  {verdict}')


def trigger_stats(fn, kw, px, name, dates, di, label):
    """발동일(픽이 실제로 바뀐 날) 수·그날 한정 승률."""
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
        if pa > pb:
            win += 1
    m = statistics.mean(diffs) if diffs else 0.0
    print(f'[{label} 발동] 픽 변경일 {nchg}일 · 우위 {win}일 '
          f'({100 * win / nchg if nchg else 0:.1f}%) · 발동일 평균 차 {m:+.4f}%p')


def main():
    global LPX, LDATES, LDI, XSD, XSD_SORTED
    px, name, dates = B.load_panel()
    import bt_loop_20260806 as L
    L.name_tbl = name
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    LPX, LDATES, LDI = build_long(px, dates)
    XSD = build_xsd(px, name, dates, di)
    XSD_SORTED = sorted(XSD)
    print(f'패널 {os.path.basename(B.PANEL)} · {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · 코드 {len(px)}종')
    print(f'장기 종가 시계열 {len(LDATES)}일 ({LDATES[0]}~{LDATES[-1]}) · '
          f'횡단면 분산 표본 {len(XSD)}일')

    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'\n[baseline] mom20+RuleH  n={len(base)}일  '
          f'full {bfull:+.4f} · train {btr:+.4f} · test {bte:+.4f}  (%p/일, vs KODEX200)')

    want = sys.argv[1:] or ['KD', 'TAL', 'DSC', 'RC', 'HD']

    for key in ('KD', 'TAL', 'DSC', 'RC'):
        if key in want:
            report_axis(key, px, name, dates, di, fo, ins, base, bfull, btr, bte)
            print()
            if key == 'KD':
                for kw in ({'k': 10, 'thr': 2.0}, {'k': 10, 'thr': 4.0}):
                    trigger_stats(kd_sel, kw, px, name, dates, di,
                                  f"KD k{kw['k']} thr{kw['thr']:+.0f}%")
            if key == 'TAL':
                for m in ('m120', 'ma150', 'ma200'):
                    trigger_stats(tal_sel, {'mode': m}, px, name, dates, di,
                                  f'TAL {m}')
            if key == 'DSC':
                trigger_stats(dsc_sel, {'p': 80, 'k': 5}, px, name, dates, di,
                              'DSC p80 mom5')

    if 'HD' in want:
        print('\n=== iteration 5 · Rule HD 단기 트랙 보유기간(회전) 축 ===')
        print('※ 탈락청산 규약 — 보유집합 = 최근 H회 픽의 합집합, 비용은 회전분에만.')
        print(f"{'변형':24s} {'전체':>9s} {'train':>9s} {'test':>9s} "
              f"{'잭나이프':>9s} {'t':>6s}  판정")
        print('-' * 88)
        for H in (1, 2, 3, 5):
            r = run_hold(px, name, dates, di, H=H)
            if len(r) != len(base):
                print(f'HD H={H}일 — 표본 불일치 {len(r)} vs {len(base)}')
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
            print(f'{"HD H=" + str(H) + "일":24s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} '
                  f'{js} {ts}  {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
