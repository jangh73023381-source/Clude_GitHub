import sys, urllib.request, xml.etree.ElementTree as ET, csv, os, time

KEY = open(os.path.expanduser('~/mnt/loop/customs_apikey_encoded.txt')).read().strip()
BASE = "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
SECTORS = {'반도체':['8541','8542'],'자동차':['8703'],'이차전지':['8507'],'바이오헬스':['30'],'화장품':['3304']}
def sector_of(hs):
    for n,ps in SECTORS.items():
        for p in ps:
            if hs.startswith(p): return n
    return None
def fetch(ym, retries=3):
    url=f"{BASE}?serviceKey={KEY}&numOfRows=15000&pageNo=1&strtYymm={ym}&endYymm={ym}&hsSgn=&imexTp=1"
    for a in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r: data=r.read()
            root=ET.fromstring(data)
            if root.findtext('.//resultCode')!='00': raise RuntimeError(root.findtext('.//resultMsg'))
            agg={s:{'expDlr':0,'impDlr':0,'expWgt':0,'impWgt':0} for s in SECTORS}
            for it in root.findall('.//item'):
                s=sector_of(it.findtext('hsCode') or '')
                if not s: continue
                for f in ('expDlr','impDlr','expWgt','impWgt'):
                    agg[s][f]+=int(it.findtext(f) or 0)
            return agg
        except Exception:
            if a==retries-1: raise
            time.sleep(2)
if __name__=='__main__':
    out='sector_trade_pq.csv'
    seen=set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out,encoding='utf-8')): seen.add(r['yyyymm'])
    new = not os.path.exists(out)
    with open(out,'a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        if new: w.writerow(['yyyymm','sector','expDlr','impDlr','expWgt','impWgt'])
        for ym in sys.argv[1:]:
            if ym in seen: continue
            agg=fetch(ym)
            for s,v in agg.items(): w.writerow([ym,s,v['expDlr'],v['impDlr'],v['expWgt'],v['impWgt']])
            f.flush()
            up = agg['반도체']['expDlr']/agg['반도체']['expWgt'] if agg['반도체']['expWgt'] else 0
            print(f"{ym} OK 반도체단가={up:,.0f}$/kg")
