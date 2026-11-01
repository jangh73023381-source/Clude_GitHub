import sys, urllib.request, xml.etree.ElementTree as ET, csv, os, time
KEY=open(os.path.expanduser('~/mnt/loop/customs_apikey_encoded.txt')).read().strip()
B="https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
# 단가가 경제적으로 의미있는 '동질적' 품목만
CODES={'디램':'8542321010','플래시':'8542321030','복합구조칩':'8542323000','모노리식IC':'8542311000',
       '집적회로전체':'8542','승용차':'8703','이차전지':'8507','의약품':'3004','화장품':'3304',
       '광전지':'854142'}
def fetch(ym,retries=3):
    url=f"{B}?serviceKey={KEY}&numOfRows=15000&pageNo=1&strtYymm={ym}&endYymm={ym}&hsSgn=&imexTp=1"
    for a in range(retries):
        try:
            root=ET.fromstring(urllib.request.urlopen(url,timeout=30).read())
            if root.findtext('.//resultCode')!='00': raise RuntimeError('api')
            agg={k:{'d':0,'w':0} for k in CODES}
            for it in root.findall('.//item'):
                hs=it.findtext('hsCode') or ''
                d=int(it.findtext('expDlr') or 0); w=int(it.findtext('expWgt') or 0)
                for k,p in CODES.items():
                    if hs.startswith(p): agg[k]['d']+=d; agg[k]['w']+=w
            return agg
        except Exception:
            if a==retries-1: raise
            time.sleep(2)
if __name__=='__main__':
    out='asp_monthly.csv'; seen=set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out,encoding='utf-8')): seen.add(r['yyyymm'])
    new=not os.path.exists(out)
    with open(out,'a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        if new: w.writerow(['yyyymm','item','expDlr','expWgt'])
        for ym in sys.argv[1:]:
            if ym in seen: continue
            a=fetch(ym)
            for k,v in a.items(): w.writerow([ym,k,v['d'],v['w']])
            f.flush()
            dr=a['디램']; print(f"{ym} 디램 {dr['d']/1e9:5.2f}B {dr['w']/1e3:8.0f}t 단가={dr['d']/dr['w'] if dr['w'] else 0:8.1f}$/kg")
