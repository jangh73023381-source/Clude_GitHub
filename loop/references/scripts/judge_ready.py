#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""judge_ready.py — shadow 판정 시점을 표본의 잡음으로 결정한다 (2026-07-31 신설).

배경: 종전에는 모든 shadow 규칙을 일률적으로 "20영업일"에 판정했다. 2026-07-31 검정
결과 **필요 기간은 규칙마다 2배 이상 차이**가 났다 — 신호 대비 잡음이 다르기 때문이다.

  N* = (1.28 × sd/|mean|)²        ← 부호 판정을 90% 신뢰로 하는 데 필요한 표본 수

부트스트랩 검증(2026-07-31, `backtest/bt_window_length.py`): 네 계열 전부에서 이 N* 의
실현 정확도가 **89.9~91.1%** 로 목표치와 일치했다.

  Rule CB           N*=11  (20일 규정은 과잉 — 이미 판정 가능했다)
  Rule CB 실매수일     N*=14
  트랙 B 조합제        N*=23  (20일 규정은 오히려 약간 부족)
  Rule RG 발동일       N*=24  → 발동 빈도 22% 라 달력으로는 약 109영업일

**핵심: 달력일이 아니라 '이벤트 일수'로 센다.** 게이트가 가끔만 발동하는 규칙을
달력일로 세면 유효표본이 5분의 1로 줄어드는 것을 못 본다.

**주의(2026-09-04 실측) — 이 스크립트는 트래커 파일을 통째로 읽으며 표본 분절을 모른다.**
`close_bet_band_tracker.csv` 는 `method` 열로 선정 레이어를 분절한다(현재 `mom150`, 그 앞은
`mom20+RuleH(in-sample)` 등 54행 중 25행). 파일 전체로 돌리면 매수일 30건·잭나이프 하한
+0.714 로 "승격 조건 충족"이 나오지만, **mom150 분절만 보면 매수일 12건·평균 +0.4233 ·
잭나이프 하한 -0.0109 · N\*=26 으로 아직 판정 시점도 아니다.** CLAUDE.md §5 Rule CB 는
"교체일부터 표본을 분절하고 OOS를 새로 센다"고 규정하므로 **CB 판정은 반드시 mom150 행만
걸러 계산한다.** 필터 옵션을 여기에 추가하지 않은 것은 외과적 수정 원칙(§8-1) 때문이며,
분절이 필요한 트래커는 호출부에서 걸러 넘길 것.

조회 전용 — 파일을 읽기만 한다.
"""
import argparse
import csv
import os
import statistics
import sys

LOOP = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
Z90 = 1.28
FLOOR = 8          # 최소 이벤트 일수 — 우연한 연승으로 조기 확정되는 것을 막는다
CAP = 60           # 이 이상은 기다리지 않고 '신뢰 낮음'으로 판정한다


def need(mean, sd):
    if not sd or not mean:
        return CAP
    return max(FLOOR, min(CAP, round((Z90 * sd / abs(mean)) ** 2)))


def jackknife_low(x):
    return min(statistics.fmean(x[:i] + x[i + 1:]) for i in range(len(x))) if len(x) > 1 else x[0]


def assess(x, label='규칙'):
    n = len(x)
    if n < 3:
        print(f'{label}: 표본 {n}일 — 평가 불가')
        return None
    m = statistics.fmean(x)
    sd = statistics.stdev(x)
    n_star = need(m, sd)
    jk = jackknife_low(x)
    ready = n >= n_star
    print(f'■ {label}')
    print(f'  이벤트 표본 {n}일 · 평균 {m:+.3f} · sd {sd:.3f} · sd/|평균| {sd / abs(m) if m else 0:.2f}')
    print(f'  필요 표본 N* = {n_star}일 (90% 신뢰) → {"판정 가능" if ready else f"{n_star - n}일 더 필요"}')
    if ready:
        print(f'  (a) 평균 > 0 : {m:+.3f} → {"충족" if m > 0 else "미달"}')
        print(f'  (b) 잭나이프 하한 > 0 : {jk:+.3f} → {"충족" if jk > 0 else "미달"}')
        print(f'  판정: {"승격 조건 충족" if (m > 0 and jk > 0) else "미달 — 유지 또는 기각"}')
    if n_star >= CAP:
        print(f'  ※ 잡음이 커서 N*가 상한({CAP})에 걸렸다 — 이 규칙은 이 지표로는 판정하기 어렵다.')
    return {'n': n, 'mean': m, 'sd': sd, 'n_star': n_star, 'ready': ready, 'jk': jk}


def read(path, value, event=None):
    p = path if os.path.isabs(path) else os.path.join(LOOP, path)
    out = []
    for r in csv.DictReader(open(p, encoding='utf-8')):
        if event:
            v = (r.get(event) or '').strip()
            if not v or v in ('0', '0.0', 'False', 'false'):
                continue
        try:
            out.append(float(r[value]))
        except (ValueError, KeyError, TypeError):
            continue
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='트래커 CSV 경로(loop 폴더 기준 상대경로 가능)')
    ap.add_argument('value', help='판정 대상 수치 컬럼')
    ap.add_argument('--event', help='이벤트 일만 세기 위한 컬럼(0/빈칸이면 제외)')
    ap.add_argument('--label', default=None)
    a = ap.parse_args()
    x = read(a.path, a.value, a.event)
    r = assess(x, a.label or os.path.basename(a.path))
    sys.exit(0 if r and r['ready'] else 3)
