#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""유니버스 제외 필터 공용 상수 (2026-08-… 정렬 작업으로 신설, 사용자 지시 2026-07-30).

종전에는 `morning_run.py`(선정)·`dual_score.py`(채점)·`rank_etf.py`(백테스트)가 제외 키워드를
**각자 다르게** 갖고 있었다. 선정과 채점의 유니버스가 어긋나면 "선정이 고를 수 없는 종목이
채점의 상위10% 슬롯을 차지"하는 v2.7 결함이 재발하므로, 목록을 이 파일 한 곳으로 통일한다.

정렬 전 실측 차이(2026-07-30):
  - morning_run 에만 있던 키워드: SOFR, 현금
  - dual_score  에만 있던 키워드: 금리플러스, 금리투자
  - rank_etf   : '숏'만 제외 — 레버리지·인버스·현금성이 전부 유니버스에 남아 있었다
  ※ 해당 종목 수는 양쪽 모두 0종이라 실제 채점 결과 차이는 없었다(잠재 결함).

최소가격 필터는 2026-07-30 사용자 지시로 폐지됐다 — 이 파일에 가격 조건은 두지 않는다.
"""

# 레버리지·인버스 등 파생 추종 (확정 규칙 v1.2 — 추천·채점 모두 제외)
DERIV = ['인버스', '곱버스', '레버리지', '2X', '2배', '숏']

# 현금성 (확정 규칙 v2.7 — 하락일 상위10% 슬롯을 잠식하던 문제로 제외)
CASH = ['머니마켓', 'MMF', 'CD1년', 'CD금리', '초단기', 'KOFR', 'SOFR',
        '국고채', '통안', '금리액티브', '금리플러스', '금리투자', '현금']


def _norm(name):
    return (name or '').replace(' ', '')


def is_deriv(name):
    return any(k in _norm(name) for k in DERIV)


def is_cash(name):
    return any(k in _norm(name) for k in CASH)


def is_spot(name):
    """파생 추종이 아니면 True (기존 dual_score.is_spot 과 동일 의미)."""
    return not is_deriv(name)


def eligible(name):
    """단기 ETF 후보·채점 유니버스에 남길지 여부. 가격 조건은 보지 않는다."""
    return not is_deriv(name) and not is_cash(name)
