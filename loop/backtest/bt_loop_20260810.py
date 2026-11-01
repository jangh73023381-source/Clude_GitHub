# -*- coding: utf-8 -*-
"""2026-08-10 루프 3~5단계 — distinct 3축.

동기: 2026-08-07 채점(D=20260807)에서 트랙 A 보조 이진 **1/5**(순위 174·182·6·163·88/187,
컷오프 상위19위 +2.61%). 1차 P&L 은 코스피 대비 +0.094%p·KODEX200 대비 +0.316%p 로 근소
승리였으나 이진 목표(5/5)는 미달이다. 그날 상위군은 **2차전지 1~4위 독식**(+6.12/+5.90/
+5.74/+4.50%)과 우주항공·방산이었고, 픽5 중 **3종이 로봇·휴머노이드 단일 테마**
(469070 -1.89% 174위 / 0177X0 -2.65% 182위 / 0148J0 -1.28% 163위)로 하위권에 몰렸다.

2026-08-06 검증관이 지정한 '다음 회차 우선 시도축' 3개를 그대로 검정한다.

 · iteration 1 Rule RS — **국내/해외 상대강도 스프레드 게이트**. 검증관 지정 (a).
   8/6 회차의 RE·DM 은 발동 임계가 '벤치 1일 수익률'이라 발동일이 적고 t가 작았다(t=+1.04/
   +0.75). 이번엔 국내(KODEX200) − 해외(미국물 바스켓) **상대강도 스프레드**로 발동을
   정의해 게이트를 정교화한다. RE/DM 과 발동 정의가 다르므로 distinct.
 · iteration 2 Rule HX — **Rule H 제외군 별도 슬롯(하이브리드)**. 검증관 지정 (b).
   8/6 검정에서 Rule H 전면해제는 t=-2.84 로 유의하게 해로웠고, 소프트화(HS)·조건부해제
   (HC)도 전부 기각됐다. 남은 미시도 형태는 **슬롯 수 제약** — 제외군 전체를 되살리지 않고
   제외군 최상위 k종(k=1,2)만 5슬롯 중 일부로 재편입한다. HS(연속 페널티)·HC(레짐 해제)와
   기전이 다르다.
 · iteration 3 Rule TP — **테마 지속성(theme persistence)**. 검증관 지정 (c).
   전일 상위10% 승자군에서 **최다 출현 테마**를 구해 그 테마 소속 종목을 우대한다.
   기각된 LAG1 은 '전일 상위10% 개별 ETF 편입'(종목 수준), TD 는 '테마 집중도 상한'
   (분산 강제)이었다. TP 는 반대로 **테마 수준의 집중을 승자 방향으로 허용**하는 축이라
   둘 다와 구별된다.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과 + 잭나이프 하한 > baseline 일 때만 후보 승격.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용. 조회 전용.
"""
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402
from bt_loop_20260806 import (  # noqa: E402
    build_cand_noh, is_foreign, jackknife, tstat,
)

B.PANEL = os.path.join(HERE, 'panel_close_0807.csv')
B.MINP = 0

name_tbl = {}
THEME = {}


def load_theme():
    p = os.path.join(HERE, 'theme_map.csv')
    out = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8')):
            out[r['code']] = r['theme']
    return out


# ---------------------------------------------------------------- iteration 1
def rs_sel(cand, px=None, d=None, di=None, dates=None, thr=0.005, look=5, **_):
    """Rule RS — 국내/해외 상대강도 스프레드 게이트.

    spread = (국내 벤치 look일 수익률) − (해외물 바스켓 look일 평균 수익률).
    spread >= thr 이면 국내 주도 국면으로 보고 해외/환헤지 계열을 후보에서 뺀다.
    RE(벤치 절대 수익률 임계)·DM(상시 배제)과 발동 정의가 다르다.
    """
    i = di[d]
    if i < look:
        return B.base_sel(cand)
    d0 = dates[i - look]
    a, b = px[B.BENCH].get(d0), px[B.BENCH].get(d)
    if not a or not b:
        return B.base_sel(cand)
    dom = b / a - 1.0
    frs = []
    for x in cand:
        if not is_foreign(x['name']):
            continue
        pa, pb = px[x['code']].get(d0), px[x['code']].get(d)
        if pa and pb:
            frs.append(pb / pa - 1.0)
    if len(frs) < 3:
        return B.base_sel(cand)
    if (dom - statistics.mean(frs)) < thr:
        return B.base_sel(cand)
    keep = [x for x in cand if not is_foreign(x['name'])]
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 2
def hx_sel(cand, px=None, d=None, di=None, dates=None, k=1, **_):
    """Rule HX — Rule H 제외군 별도 슬롯 k종만 재편입(하이브리드).

    baseline 픽5 중 하위 k종을 빼고, Rule H 로 제외된 종목 중 mom20 최상위 k종을 넣는다.
    제외군이 없으면 baseline 그대로. 전면 해제(t=-2.84 유해)와 달리 노출을 k종으로 묶는다.
    """
    base = B.base_sel(cand)
    keep_codes = {x['code'] for x in cand}
    full = build_cand_noh(px, name_tbl, d, di, dates)
    excl = [x for x in full if x['code'] not in keep_codes]
    if not excl:
        return base
    excl.sort(key=lambda x: -x['mom'])
    add = [x['code'] for x in excl[:k]]
    return base[:max(0, 5 - len(add))] + add[:5]


# ---------------------------------------------------------------- iteration 3
def tp_sel(cand, px=None, d=None, di=None, dates=None, bonus=0.03, topq=0.10, **_):
    """Rule TP — 전일 상위10% 최다 테마에 가점(테마 지속성).

    D-1→D 수익률 상위 topq 안에서 최빈 테마를 구해, 그 테마 소속 후보의 mom20 에
    bonus 를 더해 재랭킹한다. bonus=None 이면 필터(해당 테마만) 모드.
    """
    i = di[d]
    if i < 1:
        return B.base_sel(cand)
    prev = dates[i - 1]
    rs = []
    for x in cand:
        a, b = px[x['code']].get(prev), px[x['code']].get(d)
        if a and b:
            rs.append((b / a - 1.0, x['code']))
    if len(rs) < 20:
        return B.base_sel(cand)
    rs.sort(reverse=True)
    n = max(5, int(len(rs) * topq))
    cnt = {}
    for _, c in rs[:n]:
        t = THEME.get(c)
        if t:
            cnt[t] = cnt.get(t, 0) + 1
    if not cnt:
        return B.base_sel(cand)
    hot = max(cnt, key=lambda t: cnt[t])
    sc = [(x['mom'] + (bonus if THEME.get(x['code']) == hot else 0.0), x['code'])
          for x in cand]
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


def tp_filter_sel(cand, px=None, d=None, di=None, dates=None, topq=0.10, **_):
    """Rule TP-F — 최빈 테마 소속만 후보로 남기고, 5종 미만이면 baseline 보충."""
    i = di[d]
    if i < 1:
        return B.base_sel(cand)
    prev = dates[i - 1]
    rs = []
    for x in cand:
        a, b = px[x['code']].get(prev), px[x['code']].get(d)
        if a and b:
            rs.append((b / a - 1.0, x['code']))
    if len(rs) < 20:
        return B.base_sel(cand)
    rs.sort(reverse=True)
    n = max(5, int(len(rs) * topq))
    cnt = {}
    for _, c in rs[:n]:
        t = THEME.get(c)
        if t:
            cnt[t] = cnt.get(t, 0) + 1
    if not cnt:
        return B.base_sel(cand)
    hot = max(cnt, key=lambda t: cnt[t])
    keep = [x for x in cand if THEME.get(x['code']) == hot]
    keep.sort(key=lambda x: -x['mom'])
    out = [x['code'] for x in keep[:5]]
    if len(out) < 5:
        for c in B.base_sel(cand):
            if c not in out:
                out.append(c)
            if len(out) == 5:
                break
    return out[:5]


# ---------------------------------------------------------------- iteration 4
FIRST = {}


def load_first():
    """코드별 최초 관측일(=상장 시점 대리) — 2년 OHLC 패널에서 읽는다."""
    p = os.path.join(HERE, 'panel_ohlc_2y.csv')
    out = {}
    for r in csv.DictReader(open(p, encoding='utf-8')):
        c, d = r['code'], r['date']
        if c not in out or d < out[c]:
            out[c] = d
    return out


def _age_days(code, d):
    f = FIRST.get(code)
    if not f:
        return 9999
    from datetime import date
    a = date(int(f[:4]), int(f[4:6]), int(f[6:]))
    b = date(int(d[:4]), int(d[4:6]), int(d[6:]))
    return (b - a).days


def ag_sel(cand, px=None, d=None, di=None, dates=None, minage=180, **_):
    """Rule AG — 신규 상장 ETF 배제(상장 연령 게이트).

    8/7 하위권 픽 0177X0(20260407 상장)·0148J0 는 상장 4개월 미만이었고, 상위군
    305540·364980·305720 은 전부 구종목이었다. 신규 ETF 의 mom20 은 상장 초기 수급으로
    부풀려져 지속성이 낮다는 가설. 유동성(거래대금) 필터가 아니라 **연령** 축이다.
    """
    keep = [x for x in cand if _age_days(x['code'], d) >= minage]
    if len(keep) < 5:
        return B.base_sel(cand)
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 5
def th_sel(cand, px=None, d=None, di=None, dates=None, thr=0.15, look=20, **_):
    """Rule TH — 테마 단위 과열 필터(Rule H 의 집계 수준 확장).

    Rule H 는 종목 단위 급등을 본다. TH 는 같은 테마 구성원의 look일 평균 수익률이
    thr 이상이면 그 테마 전체를 후보에서 뺀다 — 8/7 로봇·휴머노이드처럼 테마가 이미
    올라 있어 개별 종목은 Rule H 에 걸리지 않는 경우를 겨냥한다.
    """
    i = di[d]
    if i < look:
        return B.base_sel(cand)
    d0 = dates[i - look]
    agg = {}
    for x in cand:
        t = THEME.get(x['code'])
        if not t:
            continue
        a, b = px[x['code']].get(d0), px[x['code']].get(d)
        if a and b:
            agg.setdefault(t, []).append(b / a - 1.0)
    hot = {t for t, v in agg.items() if statistics.mean(v) >= thr}
    keep = [x for x in cand if THEME.get(x['code']) not in hot]
    if len(keep) < 5:
        return B.base_sel(cand)
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


AXES = {
    'RS': ('iteration 1 · Rule RS 국내/해외 상대강도 스프레드 게이트', [
        ('RS thr+0.5%p look5', rs_sel, {'thr': 0.005, 'look': 5}),
        ('RS thr+1.0%p look5', rs_sel, {'thr': 0.010, 'look': 5}),
        ('RS thr+0.5%p look10', rs_sel, {'thr': 0.005, 'look': 10}),
        ('RS thr+2.0%p look10', rs_sel, {'thr': 0.020, 'look': 10}),
        ('RS thr 0%p look3', rs_sel, {'thr': 0.0, 'look': 3}),
    ]),
    'HX': ('iteration 2 · Rule HX Rule H 제외군 별도 슬롯', [
        ('HX k=1', hx_sel, {'k': 1}),
        ('HX k=2', hx_sel, {'k': 2}),
    ]),
    'TP': ('iteration 3 · Rule TP 테마 지속성', [
        ('TP bonus+3%p top10%', tp_sel, {'bonus': 0.03, 'topq': 0.10}),
        ('TP bonus+5%p top10%', tp_sel, {'bonus': 0.05, 'topq': 0.10}),
        ('TP bonus+3%p top20%', tp_sel, {'bonus': 0.03, 'topq': 0.20}),
        ('TP bonus+10%p top10%', tp_sel, {'bonus': 0.10, 'topq': 0.10}),
        ('TP-F 필터 top10%', tp_filter_sel, {'topq': 0.10}),
        ('TP-F 필터 top20%', tp_filter_sel, {'topq': 0.20}),
    ]),
    'AG': ('iteration 4 · Rule AG 신규 상장 ETF 배제(연령 게이트)', [
        ('AG 상장 90일↑', ag_sel, {'minage': 90}),
        ('AG 상장 180일↑', ag_sel, {'minage': 180}),
        ('AG 상장 365일↑', ag_sel, {'minage': 365}),
        ('AG 상장 730일↑', ag_sel, {'minage': 730}),
    ]),
    'TH': ('iteration 5 · Rule TH 테마 단위 과열 필터', [
        ('TH thr+10% look20', th_sel, {'thr': 0.10, 'look': 20}),
        ('TH thr+15% look20', th_sel, {'thr': 0.15, 'look': 20}),
        ('TH thr+20% look20', th_sel, {'thr': 0.20, 'look': 20}),
        ('TH thr+8% look10', th_sel, {'thr': 0.08, 'look': 10}),
        ('TH thr+25% look60', th_sel, {'thr': 0.25, 'look': 60}),
    ]),
}


def main():
    global name_tbl, THEME, FIRST
    px, name, dates = B.load_panel()
    name_tbl = name
    import bt_loop_20260806 as L
    L.name_tbl = name
    THEME = load_theme()
    FIRST = load_first()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · 코드 {len(px)}종 · 테마맵 {len(THEME)}종')

    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'\n[baseline] mom20+RuleH  n={len(base)}일  '
          f'full {bfull:+.4f} · train {btr:+.4f} · test {bte:+.4f}  (%p/일, vs KODEX200)')

    for key in (sys.argv[1:] or list(AXES)):
        title, variants = AXES[key]
        print(f'\n=== {title} ===')
        print(f"{'변형':30s} {'전체':>9s} {'train':>9s} {'test':>9s} "
              f"{'잭나이프':>9s} {'t':>6s}  판정")
        print('-' * 94)
        for label, fn, kw in variants:
            r = B.run(fn, px, name, dates, di, fo, ins, **kw)
            if not r or len(r) != len(base):
                print(f'{label:30s} — 표본 불일치 {len(r)} vs {len(base)}')
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
            print(f'{label:30s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} '
                  f'{js} {ts}  {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
