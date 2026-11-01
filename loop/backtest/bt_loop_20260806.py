# -*- coding: utf-8 -*-
"""2026-08-06 루프 3~5단계 — distinct 5축.

동기: 2026-08-05 채점(D=20260805)에서 트랙 A는 P&L 코스피 대비 **-2.582%p**·KODEX200 대비
**-2.776%p**, 보조 이진 **0/5**(순위 185·134·149·159·181/187)였다. 그날 상위10%
(19위 컷 **+6.02%**)는 코스피 +3.76%·KODEX200 +3.96%의 **강한 반등일**에 고베타 국내
테마(로봇·태양광·건설·조선)가 독식했고, 픽5는 미국물(S&P500·빅테크)·방어(은행)·
바이오·화장품으로 **반등에 구조적으로 참여하지 못했다**. 8/4·8/5 연속 같은 실패 유형이다.

2026-08-05 검증관이 지정한 다음 회차 우선 시도축을 그대로 검정한다.

 · iteration 1 Rule HS — **Rule H 소프트화(제외 → 연속 페널티)**. 검증관 지정 (a)+(c).
   지금까지 Rule H는 이진 제외였고, 8/4 회차에서 상위군과 제외군이 정면 충돌했다.
   제외 대신 mom20에서 런업폭에 비례한 감점을 주고 순위를 매긴다.
 · iteration 2 Rule HC — **Rule H 조건부화(레짐 게이팅)**. 검증관 지정 (a).
   벤치가 급락 직후 반등 국면일 때만 Rule H를 해제한다(과열필터가 반등 참여를 막는 구간).
 · iteration 3 Rule RE — **레짐 조건부 EM(초과모멘텀)**. 검증관 지정 (b).
   8/5 회차에서 EM k20 은 baseline과 t=0.00 완전 동일(횡단면 상수)이었다. 그래서 이번엔
   랭킹축이 아니라 **국내/해외 계열 선택 게이트**로 쓴다 — 리스크온이면 해외물을 배제.
 · iteration 4 Rule BR — **시장 폭(breadth) 반등 게이트**. 전일 상승종목 비율이 임계 이상인
   반등 국면에서 저모멘텀(낙폭과대) 쪽으로 틸트. 폭 축은 기존 기각목록에 없다.
 · iteration 5 Rule DM — **국내물 우선 틸트(도메스틱)**. 8/4·8/5 패인이 공통적으로
   "미국물·환헤지물이 국내 반등을 못 따라감"이었다. 명시적 국내/해외 분리 축.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과일 때만 후보 승격 + 잭나이프 하한 > baseline.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용. 조회 전용.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0805.csv')
B.MINP = 0

# 해외/환헤지 계열 판별 키워드 (국내물과 구분)
FOREIGN_KW = ('미국', '나스닥', 'S&P', 'SP500', '차이나', '중국', '일본', '인도',
              '베트남', '글로벌', '선진국', '신흥국', '유럽', '대만', '아시아',
              'TOP7', '빅테크', '필라델피아', '항셍', '니케이')


def is_foreign(nm):
    n = (nm or '').replace(' ', '').upper()
    return any(k.upper() in n for k in FOREIGN_KW)


def build_cand_noh(px, name, d, di, dates):
    """Rule H를 적용하지 않은 후보군 — HS·HC 축 전용.

    B.build_cand 는 Rule H를 하드필터로 걸어버려서 '소프트화·조건부화'를 검정할 수 없다.
    파생·현금성·최소가격 등 나머지 유니버스 조건은 동일하게 유지한다.
    """
    out = []
    for c in px:
        pc = px[c].get(d)
        if (not pc or pc < B.MINP or not B.is_spot(name.get(c, ''))
                or B.is_cash(name.get(c, ''))):
            continue
        m = B.mom(px, c, d, di, dates, 20)
        if m is None:
            continue
        out.append({'code': c, 'mom': m, 'name': name.get(c, ''),
                    'r1': B.mom(px, c, d, di, dates, 1),
                    'r3': B.mom(px, c, d, di, dates, 3)})
    return out


def bench_ret(px, d, di, dates, k):
    i = di[d]
    if i < k:
        return None
    a, b = px[B.BENCH].get(dates[i - k]), px[B.BENCH].get(d)
    return (b / a - 1.0) if (a and b) else None


# ---------------------------------------------------------------- iteration 1
def hs_sel(cand, px=None, d=None, di=None, dates=None, lam=1.0, **_):
    """Rule HS — Rule H 이진 제외 대신 런업폭 연속 페널티.

    score = mom20 - lam * max(0, r1-10%) - lam * max(0, r3-20%)
    lam=0 이면 필터 전무(Rule H 무력화), lam이 크면 사실상 제외에 수렴한다.
    """
    full = build_cand_noh(px, name_tbl, d, di, dates)
    sc = []
    for x in full:
        pen = 0.0
        if x['r1'] is not None and x['r1'] > 0.10:
            pen += lam * (x['r1'] - 0.10)
        if x['r3'] is not None and x['r3'] > 0.20:
            pen += lam * (x['r3'] - 0.20)
        sc.append((x['mom'] - pen, x['code']))
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


# ---------------------------------------------------------------- iteration 2
def hc_sel(cand, px=None, d=None, di=None, dates=None, thr=-0.03, look=3, **_):
    """Rule HC — Rule H 조건부 해제(급락 직후 반등 국면에서만).

    직전 look일 벤치 수익률이 thr 이하(=급락 국면)면 과열필터를 풀어 반등 주도군을
    후보에 남긴다. 그 외에는 확정 Rule H를 그대로 적용한다.
    """
    br = bench_ret(px, d, di, dates, look)
    if br is not None and br <= thr:
        full = build_cand_noh(px, name_tbl, d, di, dates)
        if len(full) >= 5:
            return [x['code'] for x in sorted(full, key=lambda x: -x['mom'])[:5]]
    return B.base_sel(cand)


# ---------------------------------------------------------------- iteration 3
def re_sel(cand, px=None, d=None, di=None, dates=None, thr=0.02, look=3, **_):
    """Rule RE — 레짐 조건부 해외물 배제.

    직전 look일 벤치가 thr 이상 오른 리스크온·반등 국면에서는 해외/환헤지 계열을 빼고
    국내물만 남긴다(8/4·8/5 패인 = 국내 반등에 미국물이 못 따라감).
    """
    br = bench_ret(px, d, di, dates, look)
    if br is None or br < thr:
        return B.base_sel(cand)
    keep = [x for x in cand if not is_foreign(x['name'])]
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 4
def br_sel(cand, px=None, d=None, di=None, dates=None, thr=0.60, pool=20, **_):
    """Rule BR — 시장 폭(breadth) 반등 게이트.

    당일 상승종목 비율이 thr 이상이면 광범위 반등으로 보고, mom20 상위 pool 안에서
    오히려 **모멘텀 하위** 5종(낙폭과대 순환매)을 고른다. 미만이면 baseline.
    """
    i = di[d]
    if i < 1:
        return B.base_sel(cand)
    prev = dates[i - 1]
    up = tot = 0
    for x in cand:
        a, b = px[x['code']].get(prev), px[x['code']].get(d)
        if a and b:
            tot += 1
            if b > a:
                up += 1
    if tot < 20 or (up / tot) < thr:
        return B.base_sel(cand)
    top = sorted(cand, key=lambda x: -x['mom'])[:pool]
    return [x['code'] for x in sorted(top, key=lambda x: x['mom'])[:5]]


# ---------------------------------------------------------------- iteration 5
def dm_sel(cand, px=None, d=None, di=None, dates=None, mode='filter', **_):
    """Rule DM — 국내물 우선(상시). mode='filter' 해외 배제 / 'tilt' 국내 가점."""
    if mode == 'filter':
        keep = [x for x in cand if not is_foreign(x['name'])]
        if len(keep) < 5:
            keep = cand
        return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]
    sc = [(x['mom'] + (0.02 if not is_foreign(x['name']) else 0.0), x['code'])
          for x in cand]
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


AXES = {
    'HS': ('iteration 1 · Rule HS Rule H 소프트화(연속 페널티)', [
        ('HS lam0.5', hs_sel, {'lam': 0.5}),
        ('HS lam1.0', hs_sel, {'lam': 1.0}),
        ('HS lam2.0', hs_sel, {'lam': 2.0}),
        ('HS lam5.0 (제외 근사)', hs_sel, {'lam': 5.0}),
    ]),
    'HC': ('iteration 2 · Rule HC Rule H 조건부 해제(급락후 반등)', [
        ('HC thr-3% look3', hc_sel, {'thr': -0.03, 'look': 3}),
        ('HC thr-5% look3', hc_sel, {'thr': -0.05, 'look': 3}),
        ('HC thr-5% look5', hc_sel, {'thr': -0.05, 'look': 5}),
    ]),
    'RE': ('iteration 3 · Rule RE 레짐 조건부 해외물 배제', [
        ('RE thr+2% look3', re_sel, {'thr': 0.02, 'look': 3}),
        ('RE thr+3% look3', re_sel, {'thr': 0.03, 'look': 3}),
        ('RE thr+1% look1', re_sel, {'thr': 0.01, 'look': 1}),
    ]),
    'BR': ('iteration 4 · Rule BR 시장 폭 반등 게이트', [
        ('BR thr60% pool20', br_sel, {'thr': 0.60, 'pool': 20}),
        ('BR thr70% pool20', br_sel, {'thr': 0.70, 'pool': 20}),
        ('BR thr70% pool30', br_sel, {'thr': 0.70, 'pool': 30}),
    ]),
    'DM': ('iteration 5 · Rule DM 국내물 우선 틸트', [
        ('DM filter (해외 배제)', dm_sel, {'mode': 'filter'}),
        ('DM tilt +2%p', dm_sel, {'mode': 'tilt'}),
    ]),
}


def jackknife(recs, folds=5):
    n = len(recs)
    if n < folds * 3:
        return None
    out, w = [], n // folds
    for f in range(folds):
        rest = recs[:f * w] + recs[(f + 1) * w if f < folds - 1 else n:]
        if rest:
            out.append(statistics.mean(rest))
    return min(out) if out else None


def tstat(a, b):
    d = [x - y for x, y in zip(a, b)]
    if len(d) < 3:
        return None
    sd = statistics.stdev(d)
    return (statistics.mean(d) / (sd / len(d) ** 0.5)) if sd else None


name_tbl = {}


def main():
    global name_tbl
    px, name, dates = B.load_panel()
    name_tbl = name
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · 코드 {len(px)}종')

    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'\n[baseline] mom20+RuleH  n={len(base)}일  '
          f'full {bfull:+.4f} · train {btr:+.4f} · test {bte:+.4f}  (%p/일, vs KODEX200)')

    for key in (sys.argv[1:] or list(AXES)):
        title, variants = AXES[key]
        print(f'\n=== {title} ===')
        print(f"{'변형':32s} {'전체':>9s} {'train':>9s} {'test':>9s} "
              f"{'잭나이프':>9s} {'t':>6s}  판정")
        print('-' * 96)
        for label, fn, kw in variants:
            r = B.run(fn, px, name, dates, di, fo, ins, **kw)
            if not r or len(r) != len(base):
                print(f'{label:32s} — 표본 불일치 {len(r)} vs {len(base)}')
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
            print(f'{label:32s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} '
                  f'{js} {ts}  {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
