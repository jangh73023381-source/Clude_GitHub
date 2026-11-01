# -*- coding: utf-8 -*-
"""개별종목 → 투자테마 섹터 매핑 (2026-09-08).
1순위 yfinance industry(`backtest/stock_sector_yf.csv`) → 2순위 DART KSIC 2~5자리
(`stock_sector_dart.csv`) → 3순위 명시 override.

★ KSIC 함정: **지주회사가 '64 금융업'으로 분류된다**(SK스퀘어·LX홀딩스·에코프로·유수홀딩스).
   KSIC 2자리만 쓰면 반도체 지주가 은행과 같은 칸에 들어가므로 override 로 교정한다.
   [[loop-sector-mapping]] 이 경고한 '2자리 절단' 한계의 실사례다.
"""
import csv, os
BT = os.path.expanduser('~/mnt/loop/backtest')

IND2SEC = {   # yfinance industry → 투자테마
    'Semiconductors': '반도체', 'Semiconductor Equipment & Materials': '반도체',
    'Chemicals': '화학·소재', 'Specialty Chemicals': '화학·소재',
    'Drug Manufacturers - Specialty & Generic': '제약·바이오', 'Biotechnology': '제약·바이오',
    'Banks - Regional': '은행·금융', 'Financial Conglomerates': '은행·금융',
    'Capital Markets': '증권·자산운용', 'Asset Management': '증권·자산운용',
    'Credit Services': '은행·금융', 'Insurance - Property & Casualty': '보험',
    'Aerospace & Defense': '방산·항공우주',
    'Auto Parts': '자동차·부품',
    'Marine Shipping': '해운·운송', 'Integrated Freight & Logistics': '해운·운송',
    'Railroads': '기계·중공업', 'Airports & Air Services': '해운·운송',
    'Engineering & Construction': '건설', 'Building Products & Equipment': '건설',
    'Internet Content & Information': '인터넷·플랫폼',
    'Information Technology Services': 'IT서비스·SW',
    'Entertainment': '엔터·미디어',
    'Household & Personal Products': '화장품·생활소비재',
    'Apparel Manufacturing': '의류·패션', 'Confectioners': '음식료',
    'Security & Protection Services': '보안·안전',
    'Steel': '철강·소재', 'Specialty Industrial Machinery': '기계·중공업',
    'Farm & Heavy Construction Machinery': '기계·중공업',
    'Electrical Equipment & Parts': '전력·전기설비',
    'Telecom Services': '통신', 'Packaging & Containers': '포장·소재',
    'Oil & Gas Refining & Marketing': '정유·화학',
    'Conglomerates': '지주·복합',
    'Staffing & Employment Services': '인터넷·플랫폼',
    'Electronic Components': '전자부품',
}
KSIC2SEC = {  # KSIC 앞자리 → 테마 (yfinance 미확보분 폴백)
    '4659': '반도체', '465': '반도체', '29271': '반도체', '261': '반도체',
    '2049': '반도체', '20423': '화장품·생활소비재',
    '27219': '기계·중공업', '27199': '의료기기',
    '58222': 'IT서비스·SW', '58221': 'IT서비스·SW', '5821': '엔터·미디어',
    '582': 'IT서비스·SW', '63112': '인터넷·플랫폼',
}
OVERRIDE = {  # KSIC 지주회사 오분류 등 규칙이 틀리는 경우만 명시 교정
    '402340': '지주·복합',    # SK스퀘어  — KSIC 64(금융)이나 반도체 지주
    '383800': '지주·복합',    # LX홀딩스  — KSIC 64
    '086520': '2차전지',      # 에코프로   — KSIC 64, 실제는 2차전지 지주
    '000700': '지주·복합',    # 유수홀딩스 — KSIC 71
    '032190': '지주·복합',    # 다우데이타 — KSIC 46
    '067160': '인터넷·플랫폼',  # SOOP     — KSIC 582 이나 인터넷 방송
    '071200': '의료기기',      # 인피니트헬스케어 — 의료영상 SW
    '490470': '반도체',        # 세미파이브 — KSIC 72(연구개발)
    '196170': '제약·바이오',    # 알테오젠  — KSIC 70
    '011930': '태양광·신재생',  # 신성이엔지 — KSIC 26 이나 태양광
}

def load():
    yf, dt = {}, {}
    for r in csv.DictReader(open(f'{BT}/stock_sector_yf.csv', encoding='utf-8')):
        if r.get('industry'): yf[r['code']] = r['industry']
    for r in csv.DictReader(open(f'{BT}/stock_sector_dart.csv', encoding='utf-8')):
        if r.get('induty_code'): dt[r['code']] = r['induty_code']
    return yf, dt

_YF, _DT = load()

def sector(code):
    if code in OVERRIDE: return OVERRIDE[code], 'override'
    ind = _YF.get(code)
    if ind and ind in IND2SEC: return IND2SEC[ind], 'yfinance'
    k = _DT.get(code, '')
    for n in (5, 4, 3, 2):
        if k[:n] in KSIC2SEC: return KSIC2SEC[k[:n]], 'KSIC'
    return (ind or f'미분류(KSIC {k})'), '미매핑'
