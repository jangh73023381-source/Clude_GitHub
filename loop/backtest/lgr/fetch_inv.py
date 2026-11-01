# -*- coding: utf-8 -*-
"""이가람식 검정용 — 종목별 투자자주체 순매수(금액, 백만원) 패널 수집 (ka10059).
1회 호출 = dt 기준 과거 100거래일. 유량 5/s. 거래대금 top150 등장일을 100일 창으로 greedy 커버.
재개 가능: done.txt 에 완료 task 기록. 출력 inv_parts/<code>_<dt>.csv (task 단위 파일 → 덮어쓰기 소실 없음).
"""
import os, sys, time, csv, json
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.abspath(os.path.join(HERE,'..','..'))
sys.path.insert(0,LOOP); import kiwoom_api as k
S=os.path.join(LOOP,'backtest','sjh')
OUT=os.path.join(HERE,'inv_parts'); os.makedirs(OUT,exist_ok=True)
DONE=os.path.join(HERE,'done.txt'); TASKS=os.path.join(HERE,'tasks.json')
FIELDS=['ind_invsr','frgnr_invsr','orgn','fnnc_invt','insrnc','invtrt','etc_fnnc','bank','penfnd_etc','samo_fund','natn','etc_corp','natfor','acc_trde_prica','cur_prc']
def build_tasks(K=150):
    dates=np.load(S+'/dates.npy'); codes=np.load(S+'/codes.npy',allow_pickle=True)
    C=np.load(S+'/C.npy').astype(float); V=np.load(S+'/V.npy').astype(float); TO=C*V; T=len(dates)
    need={}
    for t in range(T):
        row=np.nan_to_num(TO[t],nan=-1); idx=np.argpartition(-row,K)[:K]
        for i in idx: need.setdefault(int(i),[]).append(t)
    tasks=[]
    for i,ts in need.items():
        ts=sorted(ts); j=0
        while j<len(ts):
            end=min(ts[j]+99,T-1); tasks.append((str(codes[i]),str(dates[end])))
            while j<len(ts) and ts[j]<=end: j+=1
    tasks.sort(); json.dump(tasks,open(TASKS,'w')); return tasks
def num(s):
    try: return float(str(s).replace('+','').replace(',',''))
    except: return None
def fetch(code,dt):
    body={"dt":dt,"stk_cd":code,"amt_qty_tp":"1","trde_tp":"0","unit_tp":"1"}
    for a in range(6):
        try:
            r=k._call("/api/dostk/stkinfo","ka10059",body); break
        except Exception as e:
            if '429' in str(e): time.sleep(0.6*(a+1)); continue
            raise
    else: raise RuntimeError('429 persist')
    arr=[v for v in r.values() if isinstance(v,list)]
    return arr[0] if arr else []
def main(budget=165):
    t0=time.time()
    tasks=json.load(open(TASKS)) if os.path.exists(TASKS) else build_tasks()
    done=set(open(DONE).read().split()) if os.path.exists(DONE) else set()
    todo=[t for t in tasks if f'{t[0]}_{t[1]}' not in done]
    print('tasks',len(tasks),'todo',len(todo),flush=True)
    n=0; fails=0
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock=threading.Lock()
    def work(task):
        nonlocal n,fails
        code,dt=task
        if time.time()-t0>budget: return
        key=f'{code}_{dt}'
        try: arr=fetch(code,dt)
        except Exception as e:
            with lock: fails+=1
            print('fail',key,str(e)[:100],flush=True); return
        with open(os.path.join(OUT,key+'.csv'),'w',newline='') as f:
            w=csv.writer(f); w.writerow(['dt','code']+FIELDS)
            for x in arr: w.writerow([x.get('dt'),code]+[num(x.get(c)) for c in FIELDS])
        with lock:
            df.write(key+'\n'); df.flush(); n+=1
        time.sleep(0.45)
    with open(DONE,'a') as df:
        with ThreadPoolExecutor(3) as ex: list(ex.map(work,todo))
    print('done',n,'fails',fails,'remain',len(todo)-n,'elapsed',round(time.time()-t0),flush=True)
if __name__=='__main__': main(int(sys.argv[1]) if len(sys.argv)>1 else 165)
