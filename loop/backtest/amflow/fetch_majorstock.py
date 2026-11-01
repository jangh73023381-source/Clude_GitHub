# -*- coding: utf-8 -*-
"""majorstock.json — 대상 corp_code 의 대량보유 상황보고 이력(보유비율·증감) 수집. 멱등."""
import os,sys,json,csv,time,threading,queue,urllib.request
import pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.dirname(os.path.dirname(HERE))
KEY=open(os.path.join(LOOP,'dart_apikey.txt'),encoding='utf-8').read().strip()
OUT=os.path.join(HERE,'_majorstock.csv')
fx=pd.read_csv(os.path.join(HERE,'_dart_fx.csv'),dtype=str)
codes=sorted(fx.corp_code.dropna().unique())
have=set()
if os.path.exists(OUT):
    have={r['corp_code'] for r in csv.DictReader(open(OUT,encoding='utf-8'))}
todo=[c for c in codes if c not in have]
print(f'대상 {len(codes)}개 중 {len(todo)}개 미수집')
if not todo: sys.exit(0)
COLS=['corp_code','rcept_no','rcept_dt','corp_name','repror','stkqy','stkqy_irds','stkrt','stkrt_irds','report_tp']
new=not os.path.exists(OUT)
fp=open(OUT,'a',newline='',encoding='utf-8'); w=csv.DictWriter(fp,fieldnames=COLS,extrasaction='ignore')
if new: w.writeheader()
q=queue.Queue(); [q.put(c) for c in todo]
lock=threading.Lock(); t0=time.time(); cnt=[0,0]
def work():
    while True:
        try: c=q.get_nowait()
        except queue.Empty: return
        if time.time()-t0>110: return
        u=f"https://opendart.fss.or.kr/api/majorstock.json?crtfc_key={KEY}&corp_code={c}"
        try:
            with urllib.request.urlopen(u,timeout=20) as r: d=json.load(r)
        except Exception: continue
        rows=d.get('list') or []
        with lock:
            for r in rows: r['corp_code']=c; w.writerow(r)
            if d.get('status') in ('000','013'):
                if not rows: w.writerow({'corp_code':c,'rcept_no':'','rcept_dt':''})
            fp.flush(); cnt[0]+=1; cnt[1]+=len(rows)
ths=[threading.Thread(target=work,daemon=True) for _ in range(6)]
[t.start() for t in ths]; [t.join() for t in ths]
fp.close()
print(f'{cnt[0]}개 회사 {cnt[1]:,}행 {time.time()-t0:.0f}s')
sys.exit(3 if cnt[0]<len(todo) else 0)
