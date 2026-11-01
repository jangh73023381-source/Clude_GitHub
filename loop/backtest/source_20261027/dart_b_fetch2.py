# DART 주요사항보고서(B) 목록 — 창(80일)별 페이지를 6병렬로 수집. 조회 전용·멱등. 키 출력 금지.
import json, os, sys, time, csv, urllib.request, urllib.parse, concurrent.futures as cf
from datetime import date, timedelta
LOOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY = open(os.path.join(LOOP, 'dart_apikey.txt'), encoding='utf-8-sig').read().strip()
OUT = 'dart_B.csv'; DONE = 'dart_B_done.txt'
done = set(open(DONE).read().split()) if os.path.exists(DONE) else set()
def call(b, e, pg):
    for k in range(4):
        try:
            q = urllib.parse.urlencode(dict(crtfc_key=KEY, bgn_de=b, end_de=e, pblntf_ty='B', page_no=pg, page_count=100))
            return json.load(urllib.request.urlopen('https://opendart.fss.or.kr/api/list.json?' + q, timeout=40))
        except Exception: time.sleep(2)
    return {}
t0 = time.time(); wins = []
d = date(2018, 11, 1)
while d < date(2026, 10, 27):
    e = min(d + timedelta(days=80), date(2026, 10, 26)); wins.append((d.strftime('%Y%m%d'), e.strftime('%Y%m%d'))); d = e + timedelta(days=1)
f = open(OUT, 'a', newline='', encoding='utf-8'); w = csv.writer(f)
with cf.ThreadPoolExecutor(6) as ex:
    for b, e in wins:
        if b in done: continue
        if time.time() - t0 > 140: print('budget stop', b); break
        r1 = call(b, e, 1); tp = int(r1.get('total_page', 1) or 1)
        res = [r1] + list(ex.map(lambda p: call(b, e, p), range(2, tp + 1)))
        if any(not r or r.get('status') not in ('000', '013') for r in res): print('fail', b); break
        rows = [[x['rcept_dt'], x['rcept_no'], x['corp_code'], x['corp_name'], x.get('stock_code', ''), x.get('corp_cls', ''), x['report_nm'], x.get('rm', '')] for r in res for x in r.get('list', [])]
        w.writerows(rows); f.flush(); open(DONE, 'a').write(b + '\n'); print(b, len(rows), tp, round(time.time() - t0))
f.close()
