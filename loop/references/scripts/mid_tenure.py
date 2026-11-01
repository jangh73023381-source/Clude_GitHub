# -*- coding: utf-8 -*-
"""[6-2] 중기 ETF 픽의 '연속 추천일수'를 계산한다 (2026-08-03 사용자 요청).

배경: 사용자 질문 — "추천에서 빠져도 20일 들고 있는 게 유리하다면 며칠 들고 있었는지도
표시해 달라". 2026-08-03 검정 결과 20일 고정 보유는 탈락청산보다 열위였으므로(B-A
-0.0410%p/일, 잭나이프 구간 전부 음수) 20일은 청산 트리거가 아니다. 다만 연속 추천일수
자체는 유용한 정보다 — 완결 스펠 중앙값이 3거래일뿐이라 오래 살아남은 픽은 드문 신호이고,
슬롯 점유 시간의 60.7%를 20일 이상 스펠이 차지한다.

조회 전용. mom150 랭킹을 과거로 거슬러 재계산해 해당 코드가 상위 5에 연속으로
들어 있던 거래일 수와 최초 진입일을 돌려준다.
"""
import collections
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
PANEL = os.path.join(LOOP, 'backtest', 'panel_full.csv')
K = 150
MAXBACK = 260      # 되짚어 볼 최대 거래일(약 1년). 그 이상은 '260일+'로 표기.

import sys
sys.path.insert(0, HERE)
from universe_filters import eligible  # noqa: E402


def _load():
    px, nm = collections.defaultdict(dict), {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                px[r['code']][r['date']] = float(r['close'])
            except (ValueError, KeyError):
                continue
            nm[r['code']] = r['name']
    return px, nm, sorted({d for c in px for d in px[c]})


def tenures(D=None, n=5):
    """D 종가 기준 mom150 상위 n종의 {code, name, days, since, capped} 목록."""
    px, nm, ds = _load()
    di = {d: i for i, d in enumerate(ds)}
    if D is None:
        D = ds[-1]
    if D not in di or di[D] < K:
        return []

    cache = {}

    def top(d):
        if d not in cache:
            i = di[d]
            out = []
            for c in px:
                if not eligible(nm.get(c, '')):
                    continue
                a, b = px[c].get(ds[i - K]), px[c].get(d)
                if a and b:
                    out.append((b / a - 1.0, c))
            out.sort(reverse=True)
            cache[d] = {c for _, c in out[:n]}
        return cache[d]

    out = []
    for c in sorted(top(D), key=lambda x: x):
        days, i = 0, di[D]
        while i - K >= 0 and days < MAXBACK and c in top(ds[i]):
            days += 1
            i -= 1
        out.append({'code': c, 'name': nm.get(c, ''), 'days': days,
                    'since': ds[di[D] - days + 1], 'capped': days >= MAXBACK})
    out.sort(key=lambda x: -x['days'])
    return out


def label(t):
    """브리핑 표에 넣을 문자열."""
    d = f"{t['days']}거래일+" if t['capped'] else f"{t['days']}거래일"
    return f"{d} (최초 {t['since'][4:6]}/{t['since'][6:]})"


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', help='기준일 YYYYMMDD (기본: 패널 최종일)')
    a = ap.parse_args()
    rows = tenures(a.date)
    if not rows:
        raise SystemExit('산출 불가 — 패널 또는 날짜 확인')
    print(f"[중기 ETF 연속 추천일수] 기준일 {a.date or '패널 최종일'}")
    for t in rows:
        print(f"  {t['code']:8s} {t['name'][:26]:26s} {label(t)}")
    print('\n※ 완결 스펠 중앙값은 3거래일이다. 20일 이상 유지되는 픽은 스펠 수로는 10.3%뿐이지만')
    print('  슬롯 점유 시간의 60.7%를 차지한다 — 오래 남은 픽일수록 드물고 비중이 크다.')
    print('※ 연속 추천일수는 청산 트리거가 아니다(2026-08-03 검정: 20일 고정 보유가 탈락청산 대비')
    print('  -0.0410%p/일 열위). 청산은 상위 5에서 빠진 첫날 종가에 한다.')
