# -*- coding: utf-8 -*-
"""2026-07-30 루프 iteration 3 — 신규 distinct 축 **Rule ST(픽 고착 해제)**.

동기(loop-log 2026-07-29 실증 한계): 7/20 이후 은행·고배당 5종이 8거래일 연속
고착됐다. mom20 순위가 저베타 방어 노출로 굳으면 '새 모멘텀 발굴'이 멈추고
급락일에 벌고 반등일에 잃는 패턴이 반복된다. 종전 기각축(유동성·상대강도·수급·
변동성 가중)과 달리 이 축은 **가격도 수급도 아닌 '픽의 시간적 지속성'** 을 쓴다.

  ST(K) : 직전 K거래일 연속으로 상위5에 있던 종목을 제외하고 차순위로 충원
  STR(K): 반대로 K일 연속 상위5인 종목만 남긴다(지속성 선호 — 부호 반대 대조군)

부호 반대 대조군을 함께 돌리는 이유: ST가 개선되면 그것이 '고착 해제'의 효과인지
단순히 픽을 흔든 잡음인지 구분하기 위해서다. 둘 다 개선되면 잡음이다.

1차 지표 = v2.3 P&L. 가드: full·train·test 3개 모두 baseline 초과 → 3분할·잭나이프.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402
from bt_loop_20260730 import daily, deep, report  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0729.csv')


def run_st(px, name, dates, di, k, invert=False):
    """직전 k일 연속 상위5 종목을 제외(invert=True면 그 종목만 유지)."""
    hist = []                       # 각 날짜의 baseline 상위5
    out = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        ranked = sorted(cand, key=lambda x: -x['mom'])
        base5 = [x['code'] for x in ranked[:5]]
        stale = set()
        if len(hist) >= k:
            stale = set(hist[-1])
            for h in hist[-k:]:
                stale &= set(h)
        if invert:
            keep = [x for x in ranked if x['code'] in stale] or ranked
        else:
            keep = [x for x in ranked if x['code'] not in stale]
            if len(keep) < 5:
                keep = ranked
        var5 = [x['code'] for x in keep[:5]]
        b, v = daily(px, base5, d, nxt), daily(px, var5, d, nxt)
        hist.append(base5)
        if b is None or v is None:
            continue
        out.append((d, b, v))
    return out


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    print(f'패널 {os.path.basename(B.PANEL)} · {dates[0]}~{dates[-1]} ({len(dates)}일)\n')
    print('[iteration 3] Rule ST — 픽 고착 해제 (신규 distinct 축)')
    cands = []
    for k in (3, 5, 8):
        ok, s = report(f'ST{k}', run_st(px, name, dates, di, k))
        if ok:
            cands.append((f'ST{k}', s))
    print('  (부호 반대 대조군 — 지속성 선호)')
    for k in (3, 5):
        report(f'STR{k}', run_st(px, name, dates, di, k, invert=True))
    for tag, s in cands:
        deep(tag, s)


if __name__ == '__main__':
    main()
