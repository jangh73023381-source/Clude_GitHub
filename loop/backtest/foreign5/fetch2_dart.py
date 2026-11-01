# -*- coding: utf-8 -*-
"""DART 주식등의대량보유상황보고서(5% 룰) 12개월 수집 — 조회 전용·멱등·재개형.
★ corp_code 없이 조회하면 **검색기간 3개월 제한** — 3개월 창으로 쪼갠다(2026-09-08 실측).
★ pblntf_detail_ty=D001 은 **단독**으로 줘야 한다(pblntf_ty 와 함께 주면 필터가 무시된다).
"""
import json, os, sys, time, urllib.request
LOOP = os.path.expanduser('~/mnt/loop')
K = open(os.path.join(LOOP, 'dart_apikey.txt')).read().strip()
WINDOWS = [('20250909','20251208'), ('20251209','20260308'),
           ('20260309','20260608'), ('20260609','20260908')]
OUT, ST = 'd001.jsonl', '_st2.json'

def page(b, e, n):
    u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={K}"
         f"&bgn_de={b}&end_de={e}&pblntf_detail_ty=D001&page_no={n}&page_count=100")
    return json.load(urllib.request.urlopen(u, timeout=30))

def main():
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    st = json.load(open(ST)) if os.path.exists(ST) else {'wi': 0, 'p': 1, 'tp': None}
    seen = set()
    if os.path.exists(OUT):
        for L in open(OUT, encoding='utf-8'):
            try: seen.add(json.loads(L)['rcept_no'])
            except: pass
    f = open(OUT, 'a', encoding='utf-8'); used = 0
    while used < budget and st['wi'] < len(WINDOWS):
        b, e = WINDOWS[st['wi']]
        try: d = page(b, e, st['p'])
        except Exception as ex:
            print('ERR', ex); break
        used += 1
        if d.get('status') != '000':
            print(b, e, 'status', d.get('status'), d.get('message'))
            st['wi'] += 1; st['p'] = 1; st['tp'] = None
            json.dump(st, open(ST, 'w')); continue
        st['tp'] = d.get('total_page')
        for x in d.get('list', []):
            if x['rcept_no'] in seen: continue
            seen.add(x['rcept_no'])
            f.write(json.dumps({k: x.get(k) for k in
                    ('rcept_no','corp_name','corp_code','stock_code','report_nm','flr_nm','rcept_dt')},
                    ensure_ascii=False) + '\n')
        if st['p'] >= (st['tp'] or 1):
            print(f"  {b}~{e} 완료 ({st['tp']}p, 누적 {len(seen)})")
            st['wi'] += 1; st['p'] = 1; st['tp'] = None
        else:
            st['p'] += 1
        json.dump(st, open(ST, 'w')); time.sleep(0.1)
    f.close()
    print(f"요청 {used} · 누적 {len(seen)} · 창 {st['wi']}/{len(WINDOWS)}")

if __name__ == '__main__':
    main()
