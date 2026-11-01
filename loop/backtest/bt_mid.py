# -*- coding: utf-8 -*-
"""(a) 중기 트랙 — 보유 20일 지평에서 기존 지표 전면 재검증.

1~3일 지평에서 기각된 축(과매도·되돌림·채널저점)이 중기에서 살아나는지 확인한다.
평가는 겹치지 않는 20개 오프셋 방식(mid_engine.run_h).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, run_h, stat, show, mk_rank, rule_h_ok, NPICK)


def main():
    cache, name, dates = build()
    H = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f'보유 {H}일 · 유니버스 {len(cache)}종 · 거래일 {len(dates)} '
          f'({dates[0]}~{dates[-1]}) · 오프셋 {H}개 독립평가')

    strat = [
        (mk_rank('mom20', True), 'BASE mom20+RuleH'),
        (mk_rank('mom5', True), 'mom5 상위'),
        (mk_rank('mom60', True), 'mom60 상위 (중기 모멘텀)'),
        (mk_rank('mom120', True), 'mom120 상위'),
        (mk_rank('mom20', False), '역모멘텀 mom20 하위 (평균회귀)'),
        (mk_rank('mom60', False), '역모멘텀 mom60 하위'),
        (mk_rank('rsi14', False), 'RSI14 과매도 랭킹'),
        (mk_rank('rsi14', True), 'RSI14 과매수 랭킹'),
        (mk_rank('pctb', False), '%B 하단 랭킹'),
        (mk_rank('pctb', True), '%B 상단 랭킹'),
        (mk_rank('retr60', True), '피보나치 깊은되돌림 (retr 큰순)'),
        (mk_rank('retr60', False), '피보나치 얕은되돌림 (retr 작은순)'),
        (mk_rank('chpos60', False), '채널위치 저점권 (POS-LO)'),
        (mk_rank('chpos60', True), '채널위치 고점권 (POS-HI)'),
        (mk_rank('mom20', True,
                 cond=lambda e, i: (e['rsi14'][i] or 0) < 90),
         'mom20 + RSI<90'),
    ]
    rows = []
    for picker, lbl in strat:
        _, per, allobs = run_h(cache, name, dates, picker, lbl, H=H)
        rows.append((lbl, stat(per, allobs)))
    show(rows)

    base = rows[0][1]
    print(f'\n기준선 대비 우위 & 오프셋 양수 {H//2}개 이상인 전략:')
    for lbl, s in rows[1:]:
        if s['mean'] > base['mean'] and s['npos'] >= H // 2:
            print(f'  ★ {lbl:<34} {s["mean"]:+.3f}%  (기준선 {base["mean"]:+.3f}%) '
                  f't={s["t"]:.2f} 오프셋양수 {s["npos"]}/{s["noff"]}')


if __name__ == '__main__':
    main()
