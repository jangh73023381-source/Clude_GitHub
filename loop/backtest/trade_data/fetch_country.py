import sys, os, csv, time, urllib.request, xml.etree.ElementTree as ET
KEY=open(os.path.expanduser('~/mnt/loop/customs_apikey_encoded.txt')).read().strip()
NAT="https://apis.data.go.kr/1220000/nationtrade/getNationtradeList"
NIT="https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
HSG={'반도체':'8542','자동차':'8703','이차전지':'8507','화장품':'3304','의약품':'3004','커피':'0901'}

def get(url, retries=3):
    for a in range(retries):
        try:
            root=ET.fromstring(urllib.request.urlopen(url,timeout=40).read())
            if root.findtext('.//resultCode')!='00': raise RuntimeError(root.findtext('.//resultMsg'))
            return root
        except Exception:
            if a==retries-1: raise
            time.sleep(2)

def run_nat(months):
    out='country_monthly.csv'; seen=set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out,encoding='utf-8')): seen.add(r['yyyymm'])
    new=not os.path.exists(out)
    with open(out,'a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        if new: w.writerow(['yyyymm','cntyCd','cntyKor','expDlr','impDlr'])
        for ym in months:
            if ym in seen: continue
            root=get(f"{NAT}?serviceKey={KEY}&strtYymm={ym}&endYymm={ym}&cntyCd=&numOfRows=1000&pageNo=1")
            n=0
            for it in root.findall('.//item'):
                if (it.findtext('year') or '')=='총계': continue
                w.writerow([ym,it.findtext('statCd'),it.findtext('statCdCntnKor1'),
                            int(it.findtext('expDlr') or 0),int(it.findtext('impDlr') or 0)]); n+=1
            f.flush(); print(f"nat {ym} {n}")

def run_nit(months):
    out='item_country_monthly.csv'; seen=set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out,encoding='utf-8')): seen.add((r['yyyymm'],r['item']))
    new=not os.path.exists(out)
    with open(out,'a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        if new: w.writerow(['yyyymm','item','cntyCd','cntyKor','expDlr','impDlr'])
        for ym in months:
            for nm,hs in HSG.items():
                if (ym,nm) in seen: continue
                root=get(f"{NIT}?serviceKey={KEY}&strtYymm={ym}&endYymm={ym}&hsSgn={hs}&cntyCd=&numOfRows=5000&pageNo=1")
                agg={}
                for it in root.findall('.//item'):
                    if (it.findtext('year') or '')=='총계': continue
                    cc=it.findtext('statCd'); ck=it.findtext('statCdCntnKor1')
                    if cc in ('-',None): continue
                    a=agg.setdefault(cc,[ck,0,0])
                    a[1]+=int(it.findtext('expDlr') or 0); a[2]+=int(it.findtext('impDlr') or 0)
                for cc,(ck,e,i) in agg.items(): w.writerow([ym,nm,cc,ck,e,i])
                f.flush()
            print(f"nit {ym}")
if __name__=='__main__':
    mode=sys.argv[1]; months=sys.argv[2:]
    (run_nat if mode=='nat' else run_nit)(months)
