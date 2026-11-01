# -*- coding: utf-8 -*-
"""15섹터 대표 ETF + 벤치마크 장기 OHLC 수집 (키움 ka10081, 1콜당 600거래일)."""
import csv, os, sys, time
sys.path.insert(0, '/sessions/wizardly-exciting-wozniak/mnt/loop')
import kiwoom_api as k

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ohlc_sector15.csv')

TARGETS = [
    ('반도체',   '091160', 'KODEX 반도체'),
    ('자동차',   '466930', 'SOL 자동차TOP3플러스'),
    ('증권',     '102970', 'KODEX 증권'),
    ('은행금융', '091170', 'KODEX 은행'),
    ('방산',     '463250', 'TIGER K방산&우주'),
    ('조선',     '466920', 'SOL 조선TOP3플러스'),
    ('2차전지',  '305720', 'KODEX 2차전지산업'),
    ('바이오',   '462900', 'KoAct 바이오헬스케어액티브'),
    ('원자력',   '434730', 'HANARO 원자력iSelect'),
    ('AI전력',   '487240', 'KODEX AI전력핵심설비'),
    ('화장품',   '228790', 'TIGER 화장품'),
    ('로봇',     '445290', 'KODEX 로봇액티브'),
    ('태양광',   '457990', 'PLUS 태양광&ESS'),
    ('건설',     '117700', 'KODEX 건설'),
    ('금귀금속', '411060', 'ACE KRX금현물'),
    ('BM_KODEX200', '069500', 'KODEX 200'),
]

rows = []
for sector, code, name in TARGETS:
    try:
        r = k.get_daily_chart(code, '00000000')
        arr = r.get('stk_dt_pole_chart_qry') or []
        n = 0
        for d in arr:
            try:
                rows.append({
                    'sector': sector, 'code': code, 'name': name, 'date': d['dt'],
                    'open': abs(float(d['open_pric'])), 'high': abs(float(d['high_pric'])),
                    'low': abs(float(d['low_pric'])), 'close': abs(float(d['cur_prc'])),
                    'volume': float(d.get('trde_qty') or 0),
                    'value': float(d.get('trde_prica') or 0),
                })
                n += 1
            except Exception:
                pass
        dates = sorted(d['dt'] for d in arr) if arr else []
        print(f"{sector:10s} {code} {name[:24]:26s} n={n:4d} {dates[0] if dates else '-'}~{dates[-1] if dates else '-'}", flush=True)
    except Exception as e:
        print(f"{sector:10s} {code} FAIL {e}", flush=True)
    time.sleep(0.35)

with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['sector','code','name','date','open','high','low','close','volume','value'])
    w.writeheader(); w.writerows(rows)
print('saved', OUT, len(rows))
