"""생존편의 없는 개별주 일별 패널 — KRX Open API 일별 전종목 스냅샷(그날 상장 종목 전부, 이후 상폐·합병 포함).
연도별 파일 YYYY.csv 에 날짜 단위로 추가, done.txt 로 멱등 재개. 조회 전용. 사용: python3 collect.py 20120101 20261022 [threads]"""
import os,sys,csv,datetime as dt,threading
from concurrent.futures import ThreadPoolExecutor
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.dirname(os.path.dirname(HERE)))
import krx_api as K
F=['date','code','name','market','open','high','low','close','chg_pct','volume','value','mktcap','shares']
DONE=os.path.join(HERE,'done.txt'); lock=threading.Lock()
done=set(open(DONE).read().split()) if os.path.exists(DONE) else set()
a,b=sys.argv[1],sys.argv[2]; nt=int(sys.argv[3]) if len(sys.argv)>3 else 4
d0=dt.date(int(a[:4]),int(a[4:6]),int(a[6:])); d1=dt.date(int(b[:4]),int(b[4:6]),int(b[6:]))
days=[(d0+dt.timedelta(n)).strftime('%Y%m%d') for n in range((d1-d0).days+1)]
days=[d for d in days if dt.date(int(d[:4]),int(d[4:6]),int(d[6:])).weekday()<5 and d not in done]
def one(d):
    out=[]
    for path in ('sto/stk_bydd_trd','sto/ksq_bydd_trd'):
        for att in range(3):
            st,data=K.call(path,basDd=d)
            if st=='ok': break
        if st!='ok': return d,None
        for r in K.rows(data):
            out.append([d,r.get('ISU_CD'),r.get('ISU_NM'),r.get('MKT_NM'),r.get('TDD_OPNPRC'),r.get('TDD_HGPRC'),r.get('TDD_LWPRC'),
                        r.get('TDD_CLSPRC'),r.get('FLUC_RT'),r.get('ACC_TRDVOL'),r.get('ACC_TRDVAL'),r.get('MKTCAP'),r.get('LIST_SHRS')])
    return d,out
import time
T0=time.time(); BUDGET=float(os.environ.get('BUDGET','150'))
n=0;fail=0
def batches():
    for i in range(0,len(days),nt*8):
        if time.time()-T0>BUDGET: print('예산 소진 — 다음 실행에서 이어받음',flush=True); return
        yield days[i:i+nt*8]
with ThreadPoolExecutor(nt) as ex:
  for bt in batches():
    for d,out in ex.map(one,bt):
        if out is None: fail+=1; continue
        if out:
            p=os.path.join(HERE,d[:4]+'.csv'); new=not os.path.exists(p)
            with open(p,'a',newline='',encoding='utf-8') as f:
                w=csv.writer(f)
                if new: w.writerow(F)
                w.writerows(out)
        with open(DONE,'a') as f: f.write(d+'\n')
        n+=1
print('이번 실행',n,'일 · 실패',fail,' 남은',len(days)-n-fail,flush=True)
