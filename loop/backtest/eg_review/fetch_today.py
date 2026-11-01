#!/usr/bin/env python3
"""9/3 확정 일봉을 유니버스 187종에 대해 별도 파일로 받는다(공용 패널은 건드리지 않음, 조회 전용, 재개 가능)."""
import csv,os,sys,time,pickle
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0,LOOP); sys.path.insert(0,os.path.join(LOOP,'references','scripts'))
import kiwoom_api as k
from ensure_data import settled
OUT=os.path.join(HERE,'_ohlc_recent.csv'); FIELDS=['code','name','date','open','high','low','close','volume']
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
uni=[(c,d['names'][c]) for c in d['codes']]
done=set()
if os.path.exists(OUT) and os.path.getsize(OUT)>10:
    done={r['code'] for r in csv.DictReader(open(OUT,encoding='utf-8'))}
todo=[(c,n) for c,n in uni if c not in done]
print('전체',len(uni),'완료',len(done),'남은',len(todo))
t0=time.time(); rows=[]
for c,name in todo:
    if time.time()-t0>float(sys.argv[1] if len(sys.argv)>1 else 40): break
    try:
        resp=None
        for att in range(4):
            try:
                time.sleep(0.2); resp=k.get_daily_chart(c); break
            except Exception as e:
                if '429' in str(e) and att<3: time.sleep(1+att); continue
                raise
        n=0
        for x in (resp or {}).get('stk_dt_pole_chart_qry') or []:
            dt=str(x['dt'])
            if dt<'20260825' or not settled(dt): continue
            f=lambda s: abs(float(str(s).replace('+','').replace('-','')))
            o,h,lo,cl=f(x['open_pric']),f(x['high_pric']),f(x['low_pric']),f(x['cur_prc']); v=float(x.get('trde_qty') or 0)
            if min(o,h,lo,cl)<=0 or h<lo: continue
            rows.append(dict(code=c,name=name,date=dt,open=o,high=h,low=lo,close=cl,volume=v)); n+=1
        if n==0: print('  [행없음]',c)
    except Exception as e: print('  [실패]',c,e)
if rows:
    new=not (os.path.exists(OUT) and os.path.getsize(OUT)>10)
    with open(OUT,'a',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        if new: w.writeheader()
        w.writerows(rows)
print('이번 실행 코드', len({r['code'] for r in rows}), f'{time.time()-t0:.0f}s')
