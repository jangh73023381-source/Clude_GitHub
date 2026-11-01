# -*- coding: utf-8 -*-
"""krx_etf_panel.csv 기간 연장 (멱등·재개). 조회 전용.
사용: python3 collect_etf_extend.py <YYYYMMDD> <YYYYMMDD> [budget_sec]
기존 수집기(collect_krx_etf_idx_20260818.py)는 stock_panel 날짜에만 의존해 114일에 묶여 있었다.
이 스크립트는 날짜를 직접 생성해 같은 파일에 append 한다. 이미 있는 날짜는 건너뛴다."""
import csv, os, sys, time, datetime as dt, threading, queue
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE); LOOP=os.path.dirname(BT)
sys.path.insert(0, LOOP)
import krx_api as K
OUT=os.path.join(BT,'krx_etf_panel.csv')
COLS=['date','code','name','close','chg_pct','nav','value','volume','mktcap','netasset','list_shrs','base_idx']
def f(x): return (x or '').replace(',','').strip()
def have():
    if not os.path.exists(OUT): return set()
    return {r['date'] for r in csv.DictReader(open(OUT,encoding='utf-8'))}
def fetch(d):
    try: st,data=K.call('etp/etf_bydd_trd', basDd=d)
    except Exception: return d,None
    if st!='ok': return d,None
    rs=K.rows(data)
    if not rs: return d,[]
    out=[]
    for r in rs:
        out.append({'date':d,'code':f(r.get('ISU_CD')),'name':f(r.get('ISU_NM')),
            'close':f(r.get('TDD_CLSPRC')),'chg_pct':f(r.get('FLUC_RT')),'nav':f(r.get('NAV')),
            'value':f(r.get('ACC_TRDVAL')),'volume':f(r.get('ACC_TRDVOL')),'mktcap':f(r.get('MKTCAP')),
            'netasset':f(r.get('INVSTASST_NETASST_TOTAMT')),'list_shrs':f(r.get('LIST_SHRS')),
            'base_idx':f(r.get('IDX_IND_NM'))})
    return d,out
def main():
    a,b=sys.argv[1],sys.argv[2]; budget=float(sys.argv[3]) if len(sys.argv)>3 else 130
    d0=dt.datetime.strptime(a,'%Y%m%d').date(); d1=dt.datetime.strptime(b,'%Y%m%d').date()
    hv=have(); todo=[]
    d=d0
    while d<=d1:
        s=d.strftime('%Y%m%d')
        if d.weekday()<5 and s not in hv: todo.append(s)
        d+=dt.timedelta(days=1)
    print(f'대상 {len(todo)}일 (보유 {len(hv)}일)')
    if not todo: print('추가할 날짜 없음'); return
    new=not os.path.exists(OUT)
    fp=open(OUT,'a',newline='',encoding='utf-8'); w=csv.DictWriter(fp,fieldnames=COLS)
    if new: w.writeheader()
    t0=time.time(); q=queue.Queue(); res={}
    for s in todo: q.put(s)
    def worker():
        while True:
            try: s=q.get_nowait()
            except queue.Empty: return
            if time.time()-t0>budget: q.task_done(); continue
            res[s]=fetch(s)[1]; q.task_done()
    ths=[threading.Thread(target=worker,daemon=True) for _ in range(6)]
    [t.start() for t in ths]; [t.join() for t in ths]
    n=0; got=0
    for s in sorted(res):
        rows=res[s]
        if rows is None: continue
        if rows==[]: got+=1; continue          # 휴장일 — 정상
        for r in rows: w.writerow(r)
        n+=len(rows); got+=1
    fp.close()
    left=len([s for s in todo if s not in res or res[s] is None])
    print(f'{got}일 처리 {n:,}행 추가 · 남은 {left}일 · {time.time()-t0:.0f}s')
    sys.exit(3 if left else 0)
main()
