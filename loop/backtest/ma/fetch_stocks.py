# -*- coding: utf-8 -*-
"""15섹터 대표 개별종목 장기 OHLC 수집 (키움 ka10081, base_dt 페이지네이션).

대표 선정 원칙
  - 각 섹터 ETF의 최상위 비중 후보군 중 키움 API 실측 시가총액 최대인 순수주(pure-play)
  - 섹터 간 중복 배제 (POSCO홀딩스는 2차전지에 두고 금속은 고려아연)
  - 반도체는 삼성전자 대신 SK하이닉스 사용 — 삼성전자는 KOSPI200 비중이 압도적이라
    KODEX200 대비 초과수익 측정이 기계적으로 희석되고, KRX Semicon 계열 반도체 ETF는
    삼성전자 편입이 제한되는 경우가 있다. (한계로 보고서에 명시)
  - 금현물(ACE KRX금현물)은 대응 개별종목이 없어 금속·귀금속 제련주 고려아연으로 대체
"""
import csv
import os
import sys
import time

sys.path.insert(0, '/sessions/wizardly-exciting-wozniak/mnt/loop')
import kiwoom_api as k

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ohlc_stock15.csv')
PAGES = 3          # 600 * 3 = 최대 1800거래일 (약 7년)

TARGETS = [
    ('반도체',     '000660', 'SK하이닉스'),
    ('자동차',     '005380', '현대차'),
    ('증권',       '006800', '미래에셋증권'),
    ('은행금융',   '105560', 'KB금융'),
    ('방산',       '012450', '한화에어로스페이스'),
    ('조선',       '329180', 'HD현대중공업'),
    ('2차전지',    '373220', 'LG에너지솔루션'),
    ('바이오',     '207940', '삼성바이오로직스'),
    ('원자력',     '034020', '두산에너빌리티'),
    ('AI전력',     '010120', 'LS ELECTRIC'),
    ('화장품',     '090430', '아모레퍼시픽'),
    ('로봇',       '277810', '레인보우로보틱스'),
    ('태양광',     '009830', '한화솔루션'),
    ('건설',       '047040', '대우건설'),
    ('금속귀금속', '010130', '고려아연'),
    ('BM_KODEX200', '069500', 'KODEX 200'),
]


def fetch_all(code, pages=PAGES):
    """base_dt를 가장 오래된 날짜로 옮겨가며 반복 호출."""
    seen = {}
    base = '00000000'
    for _ in range(pages):
        try:
            r = k.get_daily_chart(code, base)
        except Exception:
            break
        arr = r.get('stk_dt_pole_chart_qry') or []
        if not arr:
            break
        new = 0
        for d in arr:
            dt = d.get('dt')
            if dt and dt not in seen:
                seen[dt] = d
                new += 1
        oldest = min(x['dt'] for x in arr if x.get('dt'))
        if new == 0 or oldest == base:
            break
        base = oldest
        time.sleep(0.35)
    return seen


rows = []
for sector, code, name in TARGETS:
    bars = fetch_all(code)
    n = 0
    for dt, d in bars.items():
        try:
            rows.append({
                'sector': sector, 'code': code, 'name': name, 'date': dt,
                'open': abs(float(d['open_pric'])), 'high': abs(float(d['high_pric'])),
                'low': abs(float(d['low_pric'])), 'close': abs(float(d['cur_prc'])),
                'volume': float(d.get('trde_qty') or 0),
                'value': float(d.get('trde_prica') or 0),
            })
            n += 1
        except Exception:
            pass
    ds = sorted(bars)
    print(f"{sector:11s} {code} {name:20s} n={n:5d} {ds[0] if ds else '-'}~{ds[-1] if ds else '-'}", flush=True)
    time.sleep(0.3)

with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['sector', 'code', 'name', 'date',
                                      'open', 'high', 'low', 'close', 'volume', 'value'])
    w.writeheader()
    w.writerows(rows)
print('saved', OUT, len(rows))
