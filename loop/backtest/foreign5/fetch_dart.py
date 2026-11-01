# -*- coding: utf-8 -*-
"""DART 주식등의대량보유상황보고서(5% 룰) 수집 — 조회 전용·멱등·재개형.
pblntf_detail_ty=D001 단독 사용(pblntf_ty 와 함께 주면 필터가 무시된다 — 2026-09-08 실측).
"""
import json, os, sys, time, urllib.request
LOOP = os.path.expanduser('~/mnt/loop')
K = open(os.path.join(LOOP, 'dart_apikey.txt')).read().strip()
BGN, END = '20250908', '20260908'
OUT, ST = 'd001.jsonl', '_st.json'

def page(n):
    u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={K}"
         f"&bgn_de={BGN}&end_de={END}&pblntf_detail_ty=D001&page_no={n}&page_count=100")
    return json.load(urllib.request.urlopen(u, timeout=30))

def main():
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    st = json.load(open(ST)) if os.path.exists(ST) else {'p': 1, 'tp': None}
    seen = set()
    if os.path.exists(OUT):
        for L in open(OUT, encoding='utf-8'):
            try: seen.add(json.loads(L)['rcept_no'])
            except: pass
    f = open(OUT, 'a', encoding='utf-8'); used = 0
    while used < budget:
        if st['tp'] and st['p'] > st['tp']: break
        try: d = page(st['p'])
        except Exception as e:
            print('ERR', e); break
        used += 1
        if d.get('status') != '000':
            print('status', d.get('status'), d.get('message')); break
        st['tp'] = d.get('total_page')
        for x in d.get('list', []):
            if x['rcept_no'] in seen: continue
            seen.add(x['rcept_no'])
            f.write(json.dumps({k: x.get(k) for k in
                    ('rcept_no','corp_name','corp_code','stock_code','report_nm','flr_nm','rcept_dt')},
                    ensure_ascii=False) + '\n')
        st['p'] += 1
        json.dump(st, open(ST, 'w')); time.sleep(0.12)
    f.close()
    print(f"요청 {used} · 누적 {len(seen)} · 다음 페이지 {st['p']}/{st['tp']}")

if __name__ == '__main__':
    main()
