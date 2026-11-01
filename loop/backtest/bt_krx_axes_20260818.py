#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_krx_axes_20260818.py — KRX 신규 데이터 축 iteration 2~5.

iteration 1(Rule BRD, 등락 breadth)이 22변형 전량 기각된 뒤 이어지는 4개 distinct 축.
전부 `krx_stock_panel.csv`(코스피+코스닥 전종목 일별매매)에서만 나오는 정보이며
ETF 가격 시계열에서는 만들 수 없다 — 2026-08-14 검증관이 "가격 시계열 축은 소진됐다"고
판정한 뒤 처음 열린 외부 데이터축이다.

  iteration 2  Rule TVC  거래대금 집중도 — 상위 20종목이 전체 거래대금에서 차지하는 비중.
                         '소수 대형주로 자금이 몰리는 날' 다음날 테마 ETF 모멘텀이 깨지는가.
  iteration 3  Rule TAL  극단 등락 꼬리 — |등락률|>5% 종목 비율(위험선호 프록시).
  iteration 4  Rule CWS  시총가중 − 동일가중 시장수익률 스프레드(대형주 프리미엄).
  iteration 5  Rule BTL  breadth 틸트 — 게이트(전량 역전)가 아니라 **픽 구성**을 바꾼다.
                         좁은 장세에서 mom20 상위 5종 대신 상위 15종의 중위 5종을 잡는다.

가드는 iteration 1 과 동일: full·train·test 3분할 전부 baseline 초과 AND 잭나이프 하한 > 0.
통과해도 113일 소표본이므로 더 긴 별도 패널 재검정 전에는 승격하지 않는다(8/13 절차).
"""
import csv, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_breadth_20260818 as B                     # noqa: E402  채점 틀 재사용

KRX = os.path.join(HERE, 'krx_stock_panel.csv')


def load_krx_axes():
    day = defaultdict(list)
    for r in csv.DictReader(open(KRX, encoding='utf-8')):
        try:
            chg = float(r['chg_pct'])
            cap = float(r['mktcap'] or 0)
            val = float(r['value'] or 0)
        except (TypeError, ValueError):
            continue
        day[r['date']].append((chg, cap, val))
    out = {}
    for d, v in day.items():
        tot = sum(x[2] for x in v) or 1.0
        top = sorted(v, key=lambda x: -x[2])[:20]
        capsum = sum(x[1] for x in v) or 1.0
        out[d] = {
            'tvc': sum(x[2] for x in top) / tot,                       # 거래대금 집중도
            'tal': sum(1 for c, _, _ in v if abs(c) > 5) / len(v),     # 극단 꼬리 비율
            'cws': (sum(c * cp for c, cp, _ in v) / capsum
                    - sum(c for c, _, _ in v) / len(v)),               # 대형주 프리미엄 %p
        }
    return out


AX = {}


def _at(d, lag):
    ds = [x for x in B.BRD_DATES if x <= d]
    return ds[max(len(ds) - 1 - lag, 0)] if ds else d


def gate(key, thr, lag, above=True):
    """임계 초과(또는 미만)면 mom20 하위 5종으로 역전."""
    def f(cands, d, brd):
        a = AX.get(_at(d, lag))
        if a is None:
            return B.sel_base(cands, d, brd)
        hit = (a[key] > thr) if above else (a[key] < thr)
        return [c for _, c in (cands[-B.NPICK:] if hit else cands[:B.NPICK])]
    return f


def tilt(thr, lag, pool=15):
    """Rule BTL — 좁은 장세면 상위 pool 종 중 '중위' 5종. 전량 역전보다 완만한 개입."""
    def f(cands, d, brd):
        b = brd.get(_at(d, lag))
        if b is None or b['b'] >= thr:
            return [c for _, c in cands[:B.NPICK]]
        mid = cands[:pool]
        s = (len(mid) - B.NPICK) // 2
        return [c for _, c in mid[s:s + B.NPICK]]
    return f


def main():
    px, names = B.load_etf()
    brd = B.load_breadth()
    B.BRD_DATES = sorted(brd)
    global AX
    AX = load_krx_axes()
    dates = sorted({d for c in px for d in px[c]})
    dates = [d for d in dates if d >= B.BRD_DATES[0]]

    base = B.stat(B.run(B.sel_base, px, names, dates, brd), 'BASE mom20+RuleH')
    B.show(base)
    print()

    variants = []
    for lag in (0, 1):
        tag = 'D' if lag == 0 else 'D-1'
        for thr in (0.30, 0.35, 0.40):
            variants.append((f'TVC 거래대금집중도>{thr} 역전 [{tag}]', gate('tvc', thr, lag)))
        for thr in (0.06, 0.10, 0.15):
            variants.append((f'TAL 극단꼬리비율>{thr} 역전 [{tag}]', gate('tal', thr, lag)))
        for thr in (0.3, 0.8):
            variants.append((f'CWS 대형주프리미엄>{thr}%p 역전 [{tag}]', gate('cws', thr, lag)))
        for thr in (0.35, 0.42):
            variants.append((f'BTL breadth<{thr} 중위틸트 [{tag}]', tilt(thr, lag)))

    rows = []
    for label, f in variants:
        s = B.stat(B.run(f, px, names, dates, brd), label)
        B.show(s, base)
        if s:
            rows.append(s)

    print('\n--- 3분할+잭나이프 가드 ---')
    ok = [s for s in rows
          if s['mean'] > base['mean'] and s['train'] > base['train']
          and s['test'] > base['test'] and s['jk'] > 0]
    if ok:
        for s in ok:
            B.show(s, base)
        print('\n※ 113일 소표본 통과 — 더 긴 별도 패널 재검정 전 승격 금지(8/13 절차).')
    else:
        print('  통과 0건 — iteration 2~5 전량 기각.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
