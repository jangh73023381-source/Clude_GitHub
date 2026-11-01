import csv, os, sys, json, threading, urllib.request, datetime as dt
from concurrent.futures import ThreadPoolExecutor
OUT="_px_weekly_2019_2026.csv"
LIMIT=int(sys.argv[1]) if len(sys.argv)>1 else 400
uni=[(r["code"],r["name"]) for r in csv.DictReader(open("_uni_2026.csv",encoding="utf-8"))]
done=set()
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT,encoding="utf-8")): done.add(r["code"])
if os.path.exists(OUT+".fail"):
    done|=set(open(OUT+".fail",encoding="utf-8").read().split())
todo=[x for x in uni if x[0] not in done][:LIMIT]
fo=open(OUT,"a",newline="",encoding="utf-8"); w=csv.writer(fo); lk=threading.Lock()
if fo.tell()==0: w.writerow(["code","date","close","volume","frgn"])
def job(cn):
    code,name=cn
    u=(f"https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1"
       f"&startTime=20190101&endTime=20260828&timeframe=day")
    try:
        req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Referer":"https://finance.naver.com/"})
        txt=urllib.request.urlopen(req,timeout=25).read().decode("utf-8")
        arr=json.loads(txt.replace("'",'"'))
    except Exception as e:
        with lk: open(OUT+".fail","a").write(code+"\n")
        return f"FAIL {code} {e}"
    rows=[]; keep=[]
    for x in arr[1:]:
        try: rows.append((x[0], float(x[4]), float(x[5]), float(x[6]) if x[6] not in (None,"") else 0.0))
        except Exception: pass
    # 주단위 마지막 거래일 + 월말 샘플링
    lastwk=None; lastmo=None; buf={}
    for d,c,v,f in rows:
        dd=dt.date(int(d[:4]),int(d[4:6]),int(d[6:8]))
        wk=dd.isocalendar()[:2]; mo=d[:6]
        buf[(wk,mo)]=(d,c,v,f)
    seen=set()
    for (wk,mo),val in buf.items():
        if val[0] in seen: continue
        seen.add(val[0]); keep.append([code]+list(val))
    keep.sort(key=lambda r:r[1])
    with lk:
        w.writerows(keep); fo.flush()
    return f"OK {code} {len(keep)}"
with ThreadPoolExecutor(max_workers=6) as ex:
    r=list(ex.map(job,todo))
fo.close()
print(f"처리 {len(todo)} 실패 {sum(1 for x in r if x.startswith('FAIL'))} 남은 {len([x for x in uni if x[0] not in done])-len(todo)}")
