import urllib.request, json, csv, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
KEY=open("../dart_apikey.txt",encoding="utf-8").read().strip()
OUT="_dart_fin_2019_2026.csv"
WANT={"자산총계","부채총계","자본총계","매출액","영업이익","당기순이익(손실)"}
REPRT=["11013","11012","11014","11011"]   # 1Q, 반기, 3Q, 사업
YEARS=[str(y) for y in range(2019,2027)]
m={r['stock_code'].strip():r['corp_code'] for r in csv.DictReader(open('_dart_corpcode.csv',encoding='utf-8')) if r.get('stock_code','').strip()}
uni=[r['code'] for r in csv.DictReader(open('_uni_2026.csv',encoding='utf-8'))]
codes=[(c,m[c]) for c in uni if c in m]
CH=60
batches=[codes[i:i+CH] for i in range(0,len(codes),CH)]
jobs=[(y,rp,bi) for y in YEARS for rp in REPRT for bi in range(len(batches))]
done=set()
if os.path.exists(OUT+".done"):
    done=set(open(OUT+".done",encoding="utf-8").read().split())
todo=[j for j in jobs if f"{j[0]}_{j[1]}_{j[2]}" not in done][:int(sys.argv[1]) if len(sys.argv)>1 else 40]
fo=open(OUT,"a",newline="",encoding="utf-8"); w=csv.writer(fo)
dn=open(OUT+".done","a",encoding="utf-8"); lk=threading.Lock()
if fo.tell()==0: w.writerow(["code","year","reprt","fs","account","amt","addamt"])
rev={v:k for k,v in m.items()}
def num(s):
    s=(s or "").replace(",","").strip()
    if s in ("","-"): return ""
    try: return int(s)
    except ValueError: return ""
def job(j):
    y,rp,bi=j; b=batches[bi]
    u=(f"https://opendart.fss.or.kr/api/fnlttMultiAcnt.json?crtfc_key={KEY}"
       f"&corp_code={','.join(x[1] for x in b)}&bsns_year={y}&reprt_code={rp}")
    for att in range(4):
        try:
            d=json.load(urllib.request.urlopen(u,timeout=40)); break
        except Exception as e:
            if att==3: return f"FAIL {j} {e}"
            time.sleep(1.5*(att+1))
    out=[]
    for x in d.get("list",[]):
        if x.get("account_nm") not in WANT: continue
        sc=rev.get(x["corp_code"])
        if not sc: continue
        out.append([sc,y,rp,x.get("fs_div"),x["account_nm"],num(x.get("thstrm_amount")),num(x.get("thstrm_add_amount"))])
    with lk:
        w.writerows(out); fo.flush(); dn.write(f"{y}_{rp}_{bi}\n"); dn.flush()
    return f"OK {y}/{rp}/{bi} {len(out)}"
with ThreadPoolExecutor(max_workers=20) as ex:
    r=list(ex.map(job,todo))
print(f"처리 {len(todo)} 실패 {sum(1 for x in r if x.startswith('FAIL'))} 남은 {len(jobs)-len(done)-len(todo)}")
