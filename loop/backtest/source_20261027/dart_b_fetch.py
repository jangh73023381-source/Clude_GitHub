# DART 주요사항보고서(pblntf_ty=B) 목록 수집 — 조회 전용, 멱등·이어받기. 키는 loop/dart_apikey.txt 에서 읽고 출력하지 않는다.
import json, os, sys, time, csv, urllib.request, urllib.parse
from datetime import date, timedelta
LOOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY = open(os.path.join(LOOP, 'dart_apikey.txt'), encoding='utf-8-sig').read().strip()
OUT = 'dart_B.csv'; DONE = 'dart_B_done.txt'
done = set(open(DONE).read().split()) if os.path.exists(DONE) else set()
t0 = time.time(); new = not os.path.exists(OUT)
f = open(OUT, 'a', newline='', encoding='utf-8'); w = csv.writer(f)
if new: w.writerow(['rcept_dt', 'rcept_no', 'corp_code', 'corp_name', 'stock_code', 'corp_cls', 'report_nm', 'rm'])
d = date(2018, 11, 1)
while d < date(2026, 10, 27):
    e = min(d + timedelta(days=80), date(2026, 10, 26)); tag = d.strftime('%Y%m%d')
    if tag in done: d = e + timedelta(days=1); continue
    pg = 1; rows = []
    while True:
        if time.time() - t0 > float(os.environ.get("BUDGET", "150")): f.close(); print('budget stop at', tag); sys.exit(0)
        q = urllib.parse.urlencode(dict(crtfc_key=KEY, bgn_de=tag, end_de=e.strftime('%Y%m%d'), pblntf_ty='B', page_no=pg, page_count=100))
        try: r = json.load(urllib.request.urlopen('https://opendart.fss.or.kr/api/list.json?' + q, timeout=30))
        except Exception as ex: print('err', type(ex).__name__); time.sleep(2); continue
        if r.get('status') not in ('000', '013'): print('status', r.get('status'), r.get('message')); f.close(); sys.exit(1)
        for x in r.get('list', []):
            rows.append([x['rcept_dt'], x['rcept_no'], x['corp_code'], x['corp_name'], x.get('stock_code', ''), x.get('corp_cls', ''), x['report_nm'], x.get('rm', '')])
        if pg >= int(r.get('total_page', 1) or 1): break
        pg += 1; time.sleep(0.12)
    w.writerows(rows); f.flush(); open(DONE, 'a').write(tag + '\n'); print(tag, len(rows))
    d = e + timedelta(days=1)
f.close(); print('ALL DONE')
