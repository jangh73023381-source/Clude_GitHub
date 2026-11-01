#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_sbr_20260818.py — Rule SBR: 업종별 breadth(업종 내 상승종목 비율) 축.

검증관이 2026-08-08·13·14·18 **네 회차 연속 이월**한 (a) 업종축이다. KRX OPEN API 에
업종 분류가 없다는 사실이 2026-08-18 확인되어, 외부 소스 2종으로 매핑을 확보한 뒤 처음 실행한다.
**다음 채점 대상일의 iteration 1 로 사전 등록(pre-register)** 하고 여기서 미리 돌린다 —
오늘 대상일(D=20260814)은 상한 10회를 소진했다(CLAUDE.md §3-5).

SRV(2026-08-18 iteration 9, 기각)와 무엇이 다른가
  SRV 는 업종지수의 **수익률**(집계 성과)을 썼다. SBR 은 업종 내 **참여율**(상승종목 비율)을
  쓴다. "업종이 얼마나 올랐나"와 "그 업종이 얼마나 고르게 오르나"는 다른 정보다.

ETF → 업종 매핑을 손으로 하지 않는다 (SRV 와 결정적으로 다른 점)
  SRV 는 ETF 종목명 토큰으로 업종을 붙였고 커버리지가 93/201종이었다. R3(정의 교체 재현)에서
  깨진 것이 신호 부재 때문인지 매핑 품질 때문인지 가릴 수 없었다.
  SBR 은 **각 ETF 의 일간 수익률과 각 업종 등가중 수익률의 상관을 60일 롤링으로 재어
  argmax 업종에 배정**한다. 손 개입이 없고 커버리지 100%이며, 상관 계산에 쓰는 창은
  선정일 이전 구간뿐이라 룩어헤드가 없다.

분류 2종 (같은 축을 두 정의로 — R3 를 처음부터 내장한다)
  dart2 : DART induty_code 앞 2자리(KSIC 중분류). **자릿수가 3·4·5로 섞여 있어 원본으로
          묶으면 528그룹 중 216개가 1종목이라 breadth 산출이 불가하다 — 2자리 절단 필수.**
  yf    : yfinance sector 11종.

실전 조달(§4-5): KRX 개별종목 일별매매는 **D+1 공개**다. **[D-1] 만 실전 가능**하며
  [D] 는 참고치일 뿐 승격 후보가 아니다.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_breadth_20260818 as B                      # noqa: E402

STK = os.path.join(HERE, 'krx_stock_panel.csv')
MAP_DART = os.path.join(HERE, 'stock_sector_dart.csv')
MAP_YF = os.path.join(HERE, 'stock_sector_yf.csv')
CORR_WIN = 60                                        # 업종 배정용 롤링 상관 창
MIN_MEMBERS = 5                                      # 이보다 작은 업종은 쓰지 않는다


# ─────────────────────────────────────────── 매핑

def load_maps():
    dart, yf = {}, {}
    for r in csv.DictReader(open(MAP_DART, encoding='utf-8')):
        ic = (r['induty_code'] or '').strip()
        if len(ic) >= 2:
            dart[r['code']] = 'D' + ic[:2]           # ★ 2자리 절단
    for r in csv.DictReader(open(MAP_YF, encoding='utf-8')):
        s = (r['sector'] or '').strip()
        if s:
            yf[r['code']] = 'Y' + s
    return {'dart2': dart, 'yf': yf}


# ─────────────────────────────────────────── 업종 시계열

def sector_series(smap):
    """업종별 (등가중 수익률, 상승종목 비율)을 일자별로 만든다."""
    day = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(STK, encoding='utf-8')):
        s = smap.get(r['code'])
        if not s:
            continue
        try:
            day[r['date']][s].append(float(r['chg_pct']))
        except (TypeError, ValueError):
            continue
    dates = sorted(day)
    secs = sorted({s for d in day for s in day[d]
                   if len(day[d][s]) >= MIN_MEMBERS})
    ret = np.full((len(dates), len(secs)), np.nan)
    brd = np.full((len(dates), len(secs)), np.nan)
    for i, d in enumerate(dates):
        for j, s in enumerate(secs):
            v = day[d].get(s)
            if v and len(v) >= MIN_MEMBERS:
                ret[i, j] = sum(v) / len(v)
                brd[i, j] = sum(1 for x in v if x > 0) / len(v)
    return dates, secs, ret, brd


def etf_returns(px, codes, dates):
    R = np.full((len(dates), len(codes)), np.nan)
    for j, c in enumerate(codes):
        s = px[c]
        for i in range(1, len(dates)):
            a, b = s.get(dates[i - 1]), s.get(dates[i])
            if a and b:
                R[i, j] = (b / a - 1) * 100
    return R


def assign(R_etf, R_sec, end_idx, win=CORR_WIN):
    """end_idx(포함)까지의 win 일로 ETF↔업종 상관 → argmax 배정. 룩어헤드 없음.

    ★ 결함 수정(2026-08-18) — 처음에는 'ETF 한 종목이라도 NaN 인 행'을 통째로 버렸다.
    유니버스 201종에는 신규상장이 섞여 있어 전반부 행이 거의 전멸했고, **배정이 None 이 되어
    규칙이 train 구간에서 한 번도 발동하지 않았다**(전 변형의 train 이 baseline 과 소수점까지
    같아서 발각). 지금은 업종 쪽 결손 행만 버리고, ETF 는 **종목별로** 유효 표본을 세어
    20일 미만이면 그 종목만 미배정(-1)한다."""
    lo = max(1, end_idx - win + 1)
    A, Bm = R_etf[lo:end_idx + 1], R_sec[lo:end_idx + 1]
    ok = ~np.isnan(Bm).any(1)                         # 업종 결손 행만 제거
    A, Bm = A[ok], Bm[ok]
    if A.shape[0] < 20:
        return None
    valid = (~np.isnan(A)).sum(0)                     # 종목별 유효 일수
    mu = np.nanmean(np.where(np.isnan(A), np.nan, A), axis=0)
    sd = np.nanstd(np.where(np.isnan(A), np.nan, A), axis=0)
    Az = np.nan_to_num((A - mu) / (sd + 1e-9), nan=0.0)
    Bz = (Bm - Bm.mean(0)) / (Bm.std(0) + 1e-9)
    C = Az.T @ Bz / A.shape[0]                        # (netf × nsec)
    out = np.nanargmax(C, axis=1)
    out[valid < 20] = -1                              # 표본 부족 종목은 미배정
    return out


# ─────────────────────────────────────────── 변형

def make_rule(tag, dates_s, ret_s, brd_s, R_etf, codes, lag, direction, pool, mode):
    idx_etf = {c: j for j, c in enumerate(codes)}
    ds_pos = {d: i for i, d in enumerate(dates_s)}
    cache = {}

    def sec_of(d):
        """선정일 d 기준 배정(20일마다 갱신해 계산량을 줄인다)."""
        i = ds_pos.get(d)
        if i is None:
            return None
        key = i // 20
        if key not in cache:
            cache[key] = assign(R_etf, ret_s, min(i, len(dates_s) - 1))
        return cache[key]

    def f(cands, d, brd_ignored):
        i = ds_pos.get(d)
        if i is None or i - lag < 0:
            return B.sel_base(cands, d, None)
        a = sec_of(d)
        if a is None:
            return B.sel_base(cands, d, None)
        row = brd_s[i - lag]
        if mode == 'delta':
            lo = max(0, i - lag - 5)
            base = np.nanmean(brd_s[lo:i - lag], axis=0) if i - lag > lo else row
            row = row - base
        sc = []
        for _, c in cands[:pool]:
            j = idx_etf.get(c)
            if j is None:
                continue
            if a[j] < 0:                          # 미배정 종목은 건너뛴다
                continue
            v = row[a[j]]
            if not np.isnan(v):
                sc.append((v, c))
        if len(sc) < B.NPICK:
            return B.sel_base(cands, d, None)
        sc.sort(reverse=(direction == 'high'))
        return [c for _, c in sc[:B.NPICK]]
    return f


def main():
    px, names = B.load_etf()
    brd_dummy = B.load_breadth()
    B.BRD_DATES = sorted(brd_dummy)
    dates = sorted({d for c in px for d in px[c]})
    dates = [d for d in dates if d >= B.BRD_DATES[0]]
    codes = sorted(px)
    R_etf = etf_returns(px, codes, dates)

    maps = load_maps()
    built = {}
    for tag, smap in maps.items():
        ds, secs, ret, brd = sector_series(smap)
        ds_idx = [d for d in ds if d in set(dates)]
        keep = [i for i, d in enumerate(ds) if d in set(dates)]
        built[tag] = (ds_idx, secs, ret[keep], brd[keep])
        print(f'[{tag}] 업종 {len(secs)}개(구성 {MIN_MEMBERS}종목 이상) · 일자 {len(ds_idx)}일 · '
              f'매핑 종목 {len(smap)}종')

    # 배정 예시 — 매핑이 상식적인지 눈으로 확인
    for tag in ('dart2', 'yf'):
        ds_s, secs, ret_s, brd_s = built[tag]
        a = assign(R_etf, ret_s, len(ds_s) - 1)
        show = ['0148J0', '469070', '364970', '228790', '117700', '463250']
        print(f'  [{tag}] 배정 예시: ' + ' / '.join(
            f'{names.get(c, c)[:14]}→{secs[a[codes.index(c)]]}' for c in show if c in codes))
    print()

    base = B.stat(B.run(B.sel_base, px, names, dates, brd_dummy), 'BASE mom20+RuleH')
    B.show(base)

    variants = []
    for tag in ('dart2', 'yf'):
        ds_s, secs, ret_s, brd_s = built[tag]
        for lag in (0, 1):
            lt = 'D' if lag == 0 else 'D-1'
            for direction in ('high', 'low'):
                dt = '참여율상위' if direction == 'high' else '참여율하위'
                variants.append((f'SBR[{tag}] {dt}5 pool15 [{lt}]',
                                 make_rule(tag, ds_s, ret_s, brd_s, R_etf, codes,
                                           lag, direction, 15, 'level')))
        for direction in ('high', 'low'):
            dt = '참여율상위' if direction == 'high' else '참여율하위'
            variants.append((f'SBR[{tag}] {dt}5 pool10 [D-1]',
                             make_rule(tag, ds_s, ret_s, brd_s, R_etf, codes,
                                       1, direction, 10, 'level')))
            variants.append((f'SBR[{tag}] Δ5일 {dt}5 pool15 [D-1]',
                             make_rule(tag, ds_s, ret_s, brd_s, R_etf, codes,
                                       1, direction, 15, 'delta')))

    rows = []
    print(f'\n=== Rule SBR 업종별 breadth ({len(variants)}변형) ===')
    for label, f in variants:
        s = B.stat(B.run(f, px, names, dates, brd_dummy), label)
        B.show(s, base)
        if s:
            rows.append(s)

    print('\n--- 3분할+잭나이프 가드 ---')
    ok = [s for s in rows
          if s['mean'] > base['mean'] and s['train'] > base['train']
          and s['test'] > base['test'] and s['jk'] > 0]
    feas = [s for s in ok if '[D-1]' in s['label']]
    if ok:
        for s in ok:
            B.show(s, base)
        print(f'\n  통과 {len(ok)}건 · 그중 실전 가능([D-1]) {len(feas)}건')
        if not feas:
            print('  → 실전 가능한 통과 0건. [D] 는 KRX D+1 공개 지연으로 조달 불가(§4-5).')
    else:
        print('  통과 0건 — Rule SBR 기각.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
