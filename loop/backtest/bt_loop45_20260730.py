# -*- coding: utf-8 -*-
"""2026-07-30 루프 iteration 4·5.

iteration 4 — **ST3 × X2 결합**(근소 미달 두 축의 교집합/합집합, 미시도 조합):
  UX1 : 고착(ST3) 제외 **또는** 외국인 비중감소(X2) 제외 — 합집합(더 공격적 배제)
  UX2 : 고착 **그리고** 외국인 비중감소인 종목만 제외 — 교집합(더 보수적)

iteration 5 — **Rule TD(테마 집중도 제한)**, 신규 distinct 축:
  같은 테마(종목명 키워드) 종목을 최대 M개까지만 담고 나머지는 차순위로 충원.
  현재 픽5가 은행·고배당 한 테마에 5/5 몰려 있어 사실상 1종목 베팅이 된 상태를
  겨냥한다. 종전 기각축(가격·수급·유동성·변동성)과 달리 '픽 간 상관'을 쓴다.

가드는 동일 — full·train·test 3개 모두 baseline 초과 시에만 3분할·잭나이프.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402
from bt_loop_20260730 import daily, deep, report  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0729.csv')

THEMES = [
    ('은행금융', ['은행', '금융', '고배당', '배당', '증권', '보험']),
    ('반도체', ['반도체', 'HBM', 'D램', '메모리', '소부장']),
    ('2차전지', ['2차전지', '배터리', '에너지솔루션', '리튬']),
    ('원자력', ['원자력', '원전', 'SMR']),
    ('방산우주', ['방산', '우주', '항공']),
    ('조선', ['조선']),
    ('건설', ['건설', '인프라']),
    ('바이오', ['바이오', '헬스', '제약', '의료']),
    ('AI전력', ['AI전력', '전력', '전선', '변압기']),
    ('자동차', ['자동차', '모빌리티']),
    ('금귀금속', ['금현물', '골드', '은현물', '실버', '귀금속']),
    ('인터넷', ['인터넷', '게임', '소프트웨어', '플랫폼']),
    ('지수', ['200', '코스피', '코스닥', 'MSCI', 'TOP', '대표']),
]


def theme_of(nm):
    n = (nm or '').replace(' ', '')
    for t, kws in THEMES:
        if any(k in n for k in kws):
            return t
    return '기타'


def run(px, name, dates, di, fo, mode, m=2, k=3):
    hist, out = [], []
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

        def drop_x2(c):
            s = B.flow_score(fo, c, d, di, dates, 5, 'level')
            return s is not None and s < 0

        if mode == 'UX1':
            keep = [x for x in ranked
                    if x['code'] not in stale and not drop_x2(x['code'])]
        elif mode == 'UX2':
            keep = [x for x in ranked
                    if not (x['code'] in stale and drop_x2(x['code']))]
        else:                                   # TD — 테마당 최대 m종
            keep, cnt = [], {}
            for x in ranked:
                t = theme_of(x['name'])
                if cnt.get(t, 0) >= m:
                    continue
                cnt[t] = cnt.get(t, 0) + 1
                keep.append(x)
        if len(keep) < 5:
            keep = ranked
        b, v = daily(px, base5, d, nxt), daily(px, [x['code'] for x in keep[:5]], d, nxt)
        hist.append(base5)
        if b is None or v is None:
            continue
        out.append((d, b, v))
    return out


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, _ = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · {dates[0]}~{dates[-1]} ({len(dates)}일)\n')

    print('[iteration 4] ST3 × X2 결합')
    good = []
    for tag in ('UX1', 'UX2'):
        ok, s = report(tag, run(px, name, dates, di, fo, tag))
        if ok:
            good.append((tag, s))

    print('\n[iteration 5] Rule TD — 테마 집중도 제한 (신규 distinct 축)')
    for m in (1, 2, 3):
        ok, s = report(f'TD{m}', run(px, name, dates, di, fo, 'TD', m=m))
        if ok:
            good.append((f'TD{m}', s))
    for tag, s in good:
        deep(tag, s)


if __name__ == '__main__':
    main()
