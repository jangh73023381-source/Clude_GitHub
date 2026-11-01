# -*- coding: utf-8 -*-
"""야후 일봉 수집 (.KS → 없으면 .KQ). UA 헤더 필수. 멱등."""
import json, os, sys, time, urllib.request, datetime
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
P1, P2 = 1725148800, 1788912000   # 2024-09-01 ~ 2026-09-09
cands=json.load(open('_cands.json',encoding='utf-8'))
OUT='px.jsonl'
done=set()
if os.path.exists(OUT):
    for L in open(OUT,encoding='utf-8'):
        try: done.add(json.loads(L)['code'])
        except: pass
def fetch(sym):
    u=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={P1}&period2={P2}&interval=1d"
    d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=25))
    r=d['chart']['result'][0]
    ts=r['timestamp']; cl=r['indicators']['quote'][0]['close']
    pair=[(datetime.datetime.utcfromtimestamp(t).strftime('%Y-%m-%d'),c) for t,c in zip(ts,cl) if c is not None]
    return pair
budget=int(sys.argv[1]) if len(sys.argv)>1 else 40
f=open(OUT,'a',encoding='utf-8'); used=0
for c in cands:
    if c['code'] in done: continue
    if used>=budget: break
    got=None; sym=None
    for suf in ('.KS','.KQ'):
        try:
            p=fetch(c['code']+suf)
            if len(p)>100: got=p; sym=c['code']+suf; break
        except Exception: pass
    used+=1
    f.write(json.dumps({'code':c['code'],'sym':sym,'px':got or []},ensure_ascii=False)+'\n')
    time.sleep(0.05)
f.close()
print(f"조회 {used} · 완료 {len(done)+used}/{len(cands)}")
