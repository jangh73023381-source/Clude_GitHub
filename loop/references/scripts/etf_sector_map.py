#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""etf_sector_map.py — ETF 이름 → 섹터 분류. **공용 상수 1곳**(§5 유니버스 필터와 같은 원칙).

용도: 트랙 D(Rule EG) 타점 목록에서 같은 섹터 신호가 여러 건일 때 대표 1종만 남기고
나머지를 비고로 넘기기 위한 것이다. **선정 로직(트랙 A~C)에는 쓰지 않는다.**

규칙은 **순서가 중요하다** — 위에서부터 처음 걸리는 키워드로 확정한다.
예: 'KODEX AI반도체핵심장비' 는 '반도체'가 'AI'보다 먼저 걸려야 한다.
분류를 바꿀 때는 이 파일만 고치고 `python3 etf_sector_map.py` 로 전수 확인할 것.
"""
import re

# (섹터, 정규식) — 위에서부터 먼저 매칭되는 것으로 확정
RULES = [
    ('귀금속',    r'금현물|골드|은선물'),
    ('원자력',    r'원자력|SMR'),
    ('방산우주',  r'방산|우주'),
    ('조선',      r'조선'),
    ('건설',      r'건설'),
    ('화장품',    r'화장품'),
    ('리츠부동산', r'리츠|부동산'),
    ('태양광신재생', r'태양광|신재생|ESS'),
    ('2차전지',   r'2차전지|전고체|배터리|전기&수소차|전기차'),
    ('로봇',      r'로봇|휴머노이드|피지컬AI'),
    ('바이오',    r'바이오|헬스케어'),
    ('증권',      r'증권'),
    ('은행금융',  r'은행|금융지주|금융고배당'),
    ('자동차',    r'자동차|현대차'),
    ('양자컴퓨팅', r'양자'),
    ('중국',      r'차이나'),
    ('채권',      r'국채|회사채|채권혼합|미국채'),
    ('반도체',    r'반도체|HBM|비메모리|전공정|후공정|소부장|엔비디아|하이닉스|메모리'),
    ('AI전력인프라', r'전력|광통신|네트워크인프라'),
    ('미국지수',  r'미국|나스닥|S&P|빅테크|테슬라|다우존스'),
    ('IT테크',    r'IT|테크|전략산업|CAPEX|설비투자'),
    ('AI',        r'AI|인공지능'),
    ('배당',      r'고배당|배당|커버드콜'),
    ('국내지수',  r'200|코스피|코스닥|밸류업|MSCI|Top5|코리아TOP10|지주회사|그룹|ESG|Korea'),
]


def sector(name: str) -> str:
    for sec, pat in RULES:
        if re.search(pat, name, re.IGNORECASE):
            return sec
    return '기타'


if __name__ == '__main__':
    import collections
    import os
    import sys
    import pandas as pd
    HERE = os.path.dirname(os.path.abspath(__file__))
    LOOP = os.path.dirname(os.path.dirname(HERE))
    sys.path.insert(0, HERE)
    import universe_filters as uf
    lg = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_long.csv'), dtype={'code': str})
    t2 = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv'), dtype={'code': str})
    p = pd.concat([lg, t2[t2.date > lg.date.max()][lg.columns]], ignore_index=True)
    p = p.drop_duplicates(['code', 'date'])
    p = p[~p.name.map(lambda n: uf.is_deriv(n) or uf.is_cash(n))]
    nm = p.drop_duplicates('code')[['code', 'name']]
    nm['sec'] = nm.name.map(sector)
    c = collections.Counter(nm.sec)
    print(f'전체 {len(nm)}종 · {len(c)}개 섹터')
    for s, n in c.most_common():
        print(f'  {s:12s} {n:3d}종  ' + ', '.join(nm[nm.sec == s].name.head(4)))
    if c.get('기타'):
        print('\n[미분류]', list(nm[nm.sec == '기타'].name))
