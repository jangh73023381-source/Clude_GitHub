# 변동성 돌파 독립 검증용 KRX ETF OHLC 수집(조회 전용, 멱등). 대상: 검증 ETF 목록만 저장.
import sys, os, csv, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import krx_api as K
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_vb_krx_etf_ohlc.csv')
have = set()
if os.path.exists(OUT):
    have = {r['date'] for r in csv.DictReader(open(OUT, encoding='utf-8'))}
d = datetime.strptime(sys.argv[1], '%Y%m%d'); end = datetime.strptime(sys.argv[2], '%Y%m%d'); t0 = time.time()
new = not os.path.exists(OUT)
with open(OUT, 'a', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    if new: w.writerow(['date', 'code', 'open', 'high', 'low', 'close', 'value'])
    while d <= end and time.time() - t0 < 150:
        ds = d.strftime('%Y%m%d'); d += timedelta(days=1)
        if d.weekday() == 0 and False: pass
        if datetime.strptime(ds, '%Y%m%d').weekday() >= 5 or ds in have: continue
        st, data = K.call('etp/etf_bydd_trd', basDd=ds)
        if st != 'ok': print('stop', ds, st); break
        for r in K.rows(data):
            w.writerow([ds, r.get('ISU_CD'), r.get('TDD_OPNPRC'), r.get('TDD_HGPRC'), r.get('TDD_LWPRC'), r.get('TDD_CLSPRC'), r.get('ACC_TRDVAL')])
        f.flush()
print('last', ds)
