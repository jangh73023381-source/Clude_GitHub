# -*- coding: utf-8 -*-
"""DART 지분공시(pblntf_ty=D) 전수 수집 — 멱등·재개. 조회 전용.
사용: python3 collect_dart_holders.py <YYYYMMDD> <YYYYMMDD> [budget_sec]
월 단위로 끊어 수집하고 _dart_disc.csv 에 append, 완료 월은 _dart_done.txt 에 기록해 건너뛴다."""
import sys, os, json, time, csv, urllib.request
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.dirname(os.path.dirname(HERE))
KEY=open(os.path.join(LOOP,'dart_apikey.txt'),encoding='utf-8').read().strip()
OUT=os.path.join(HERE,'_dart_disc.csv'); DONE=os.path.join(HERE,'_dart_done.txt')
COLS=['rcept_no','rcept_dt','corp_code','corp_name','stock_code','report_nm','flr_nm']

def months(a,b):
    y,m=int(a[:4]),int(a[4:6]); ey,em=int(b[:4]),int(b[4:6]); out=[]
    while (y,m)<=(ey,em):
        import calendar
        last=calendar.monthrange(y,m)[1]
        out.append((f'{y}{m:02d}01',f'{y}{m:02d}{last:02d}'))
        m+=1
        if m>12: m=1;y+=1
    return out

def fetch(b,e,pg,tries=3):
    u=(f"https://opendart.fss.or.kr/api/list.json?crtfc_key={KEY}&bgn_de={b}&end_de={e}"
       f"&pblntf_ty=D&page_count=100&page_no={pg}")
    for i in range(tries):
        try:
            with urllib.request.urlopen(u,timeout=25) as r: return json.load(r)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.5)

def main():
    a,b=sys.argv[1],sys.argv[2]; budget=float(sys.argv[3]) if len(sys.argv)>3 else 130
    done=set(open(DONE).read().split()) if os.path.exists(DONE) else set()
    new=not os.path.exists(OUT)
    f=open(OUT,'a',newline='',encoding='utf-8'); w=csv.DictWriter(f,fieldnames=COLS,extrasaction='ignore')
    if new: w.writeheader()
    t0=time.time(); n=0; mm=0
    for mb,me in months(a,b):
        key=mb[:6]
        if key in done: continue
        if time.time()-t0>budget:
            print(f'예산 소진 — {key} 부터 남음 (rc=3)'); f.close(); sys.exit(3)
        try:
            d=fetch(mb,me,1)
        except Exception as ex:
            print(f'{key} 실패 {ex}'); continue
        if d.get('status')=='013':   # 조회 결과 없음
            open(DONE,'a').write(key+'\n'); continue
        if d.get('status')!='000':
            print(f'{key} status={d.get("status")} {d.get("message")}'); continue
        tp=d.get('total_page',1); rows=d.get('list',[])
        ok=True
        for p in range(2,tp+1):
            if time.time()-t0>budget+25: ok=False; break
            try: rows+=fetch(mb,me,p).get('list',[])
            except Exception: ok=False; break
        for r in rows: w.writerow(r)
        f.flush(); n+=len(rows); mm+=1
        if ok: open(DONE,'a').write(key+'\n')
        print(f'  {key}: {len(rows)}건 (page {tp})')
    f.close()
    print(f'완료 {mm}개월 {n}건 {time.time()-t0:.0f}s')
main()
