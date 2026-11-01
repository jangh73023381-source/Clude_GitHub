# -*- coding: utf-8 -*-
"""majorstock.json — 종목별 대량보유 상황보고 상세(보유비율·증감·보고사유). 멱등·재개형."""
import json, os, sys, time, urllib.request
LOOP = os.path.expanduser('~/mnt/loop')
K = open(os.path.join(LOOP, 'dart_apikey.txt')).read().strip()
fx = json.load(open('_fx.json', encoding='utf-8'))
corps = sorted({(r['corp_code'], r['corp_name'], r['stock_code']) for r in fx})
OUT = 'major.jsonl'
done = set()
if os.path.exists(OUT):
    for L in open(OUT, encoding='utf-8'):
        try: done.add(json.loads(L)['corp_code'])
        except: pass
budget = int(sys.argv[1]) if len(sys.argv) > 1 else 60
f = open(OUT, 'a', encoding='utf-8'); used = 0
for cc, nm, sc in corps:
    if cc in done: continue
    if used >= budget: break
    try:
        d = json.load(urllib.request.urlopen(
            f"https://opendart.fss.or.kr/api/majorstock.json?crtfc_key={K}&corp_code={cc}", timeout=30))
    except Exception as e:
        print('ERR', nm, e); break
    used += 1
    f.write(json.dumps({'corp_code': cc, 'corp_name': nm, 'stock_code': sc,
                        'status': d.get('status'), 'list': d.get('list', [])}, ensure_ascii=False) + '\n')
    time.sleep(0.1)
f.close()
print(f"조회 {used} · 완료 {len(done)+used}/{len(corps)}")
