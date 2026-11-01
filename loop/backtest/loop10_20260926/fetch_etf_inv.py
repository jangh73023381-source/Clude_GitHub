# -*- coding: utf-8 -*-
"""loop10 iteration 10 — ETF 투자자주체 순매수(금액·백만원) 패널 수집 (키움 ka10059, 조회 전용).
대상: panel_ohlc_long.csv 의 전 ETF(201종). 종목별 상장 이후 100거래일 창을 겹침 없이 커버.
재개 가능(done.txt). 출력 parts/<code>_<dt>.csv. 주문 기능 호출 없음.
"""
import os, sys, time, csv, json
from concurrent.futures import ThreadPoolExecutor
import threading
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.abspath(os.path.join(HERE,'..','..'))
sys.path.insert(0,LOOP); import kiwoom_api as k
sys.path.insert(0,os.path.join(LOOP,'backtest','lgr')); from fetch_inv import fetch, FIELDS
OUT=os.path.join(HERE,'parts'); os.makedirs(OUT,exist_ok=True)
DONE=os.path.join(HERE,'done.txt'); TASKS=os.path.join(HERE,'tasks.json')
def build():
    first={}; dates=set()
    with open(os.path.join(LOOP,'backtest','panel_ohlc_long.csv'),encoding='utf-8') as f:
        r=csv.reader(f); h=next(r); ic,idt=h.index('code'),h.index('date')
        per={}
        for row in r:
            per.setdefault(row[ic],[]).append(row[idt]); dates.add(row[idt])
    D=sorted(dates); pos={d:i for i,d in enumerate(D)}; tasks=[]
    for c,ds in per.items():
        s=pos[min(ds)]; e=pos[max(ds)]
        t=e
        while t>=s:
            tasks.append((c,D[t])); t-=100
    tasks.sort(); json.dump(tasks,open(TASKS,'w')); return tasks
def main(budget=100):
    t0=time.time()
    tasks=json.load(open(TASKS)) if os.path.exists(TASKS) else build()
    done=set(open(DONE).read().split()) if os.path.exists(DONE) else set()
    todo=[t for t in tasks if f'{t[0]}_{t[1]}' not in done]
    print('tasks',len(tasks),'todo',len(todo),flush=True)
    lock=threading.Lock(); st={'n':0,'f':0}
    def work(task):
        if time.time()-t0>budget: return
        code,dt=task; key=f'{code}_{dt}'
        try: arr=fetch(code,dt)
        except Exception as e:
            with lock: st['f']+=1
            print('fail',key,str(e)[:120],flush=True); return
        with open(os.path.join(OUT,key+'.csv'),'w',newline='') as f:
            w=csv.writer(f); w.writerow(['dt','code']+FIELDS)
            for x in arr:
                w.writerow([x.get('dt'),code]+[x.get(c) for c in FIELDS])
        with lock:
            df.write(key+'\n'); df.flush(); st['n']+=1
        time.sleep(0.45)
    with open(DONE,'a') as df:
        with ThreadPoolExecutor(3) as ex: list(ex.map(work,todo))
    print('done',st,'remain',len(todo)-st['n'],'elapsed',round(time.time()-t0),flush=True)
if __name__=='__main__': main(int(sys.argv[1]) if len(sys.argv)>1 else 100)
