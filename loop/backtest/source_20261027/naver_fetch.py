"""네이버 증권 종목분석 리포트(증권사) 수집 — 목록(page) → 상세(투자의견·목표가·직전 목표가). 조회 전용, 4병렬, 재시도·이어받기."""
import json, time, urllib.request, os, sys, concurrent.futures as cf
H = {'User-Agent': 'Mozilla/5.0'}
def get(u, tries=3):
    for k in range(tries):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20).read().decode('utf-8', 'ignore'))
        except Exception as e:
            if '404' in str(e): return None
            time.sleep(1 + k)
    return None
LIST = 'list.jsonl'
if not os.path.exists(LIST + '.done'):
    seen = set(); out = open(LIST, 'w')
    for pg in range(1, 900):
        r = get(f'https://m.stock.naver.com/api/research/company?pageSize=100&page={pg}')
        if not r: break
        for x in r:
            if x['researchId'] not in seen: seen.add(x['researchId']); out.write(json.dumps(x, ensure_ascii=False) + '\n')
        if r[-1]['writeDate'] < '2018-11-01': break
        time.sleep(0.15)
    out.close(); open(LIST + '.done', 'w').write('ok'); print('list', len(seen), flush=True)
items = [json.loads(l) for l in open(LIST)]
items = [x for x in items if x['writeDate'] >= '2018-11-01']
DET = 'detail.jsonl'
have = set()
if os.path.exists(DET):
    for l in open(DET):
        try: have.add(json.loads(l)['researchId'])
        except: pass
todo = [x['researchId'] for x in items if x['researchId'] not in have]
print('todo', len(todo), flush=True)
def one(i):
    r = get(f'https://m.stock.naver.com/api/research/company/{i}')
    time.sleep(0.05)
    if not r: return None
    c = r.get('researchContent', {}); c.pop('content', None); c.pop('attachUrl', None)
    return c
with open(DET, 'a') as f, cf.ThreadPoolExecutor(4) as ex:
    for n, c in enumerate(ex.map(one, todo)):
        if c: f.write(json.dumps(c, ensure_ascii=False) + '\n')
        if n % 2000 == 0: f.flush(); print(n, time.strftime('%H:%M:%S'), flush=True)
print('DONE', flush=True)
