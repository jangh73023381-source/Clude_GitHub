import sys, urllib.request, xml.etree.ElementTree as ET, csv, os, time
from collections import defaultdict
KEY=open(os.path.expanduser('~/mnt/loop/customs_apikey_encoded.txt')).read().strip()
B="https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
def fetch(ym,retries=3):
    url=f"{B}?serviceKey={KEY}&numOfRows=15000&pageNo=1&strtYymm={ym}&endYymm={ym}&hsSgn=&imexTp=1"
    for a in range(retries):
        try:
            root=ET.fromstring(urllib.request.urlopen(url,timeout=40).read())
            if root.findtext('.//resultCode')!='00': raise RuntimeError('api')
            agg=defaultdict(lambda:[0,0,0,0])
            for it in root.findall('.//item'):
                hs=(it.findtext('hsCode') or '')
                if len(hs)<4: continue
                k=hs[:4]
                v=agg[k]
                v[0]+=int(it.findtext('expDlr') or 0); v[1]+=int(it.findtext('impDlr') or 0)
                v[2]+=int(it.findtext('expWgt') or 0); v[3]+=int(it.findtext('impWgt') or 0)
            return agg
        except Exception:
            if a==retries-1: raise
            time.sleep(2)
if __name__=='__main__':
    out='hs4_monthly.csv'; seen=set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out,encoding='utf-8')): seen.add(r['yyyymm'])
    new=not os.path.exists(out)
    with open(out,'a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        if new: w.writerow(['yyyymm','hs4','expDlr','impDlr','expWgt','impWgt'])
        for ym in sys.argv[1:]:
            if ym in seen: continue
            a=fetch(ym)
            for k in sorted(a):
                v=a[k]; w.writerow([ym,k,v[0],v[1],v[2],v[3]])
            f.flush()
            print(f"{ym} OK hs4={len(a)}")
