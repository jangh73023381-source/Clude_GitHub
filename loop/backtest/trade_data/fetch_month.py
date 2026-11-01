import sys, urllib.request, xml.etree.ElementTree as ET, csv, os, time

KEY = open(os.path.expanduser('~/mnt/loop/customs_apikey_encoded.txt')).read().strip()
BASE = "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"

SECTORS = {
    '반도체':  ['8541','8542'],
    '자동차':  ['8703'],
    '이차전지': ['8507'],
    '바이오헬스': ['30'],
    '화장품':  ['3304'],
}

def sector_of(hscode):
    for name, prefixes in SECTORS.items():
        for p in prefixes:
            if hscode.startswith(p):
                return name
    return None

def fetch_month(yyyymm, retries=3):
    url = f"{BASE}?serviceKey={KEY}&numOfRows=15000&pageNo=1&strtYymm={yyyymm}&endYymm={yyyymm}&hsSgn=&imexTp=1"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = resp.read()
            root = ET.fromstring(data)
            code = root.findtext('.//resultCode')
            if code != '00':
                msg = root.findtext('.//resultMsg')
                raise RuntimeError(f"API error {code}: {msg}")
            items = root.findall('.//item')
            agg = {s: {'expDlr':0, 'impDlr':0} for s in SECTORS}
            agg['TOTAL'] = {'expDlr':0, 'impDlr':0}
            for it in items:
                hs = it.findtext('hsCode') or ''
                exp = int(it.findtext('expDlr') or 0)
                imp = int(it.findtext('impDlr') or 0)
                agg['TOTAL']['expDlr'] += exp
                agg['TOTAL']['impDlr'] += imp
                s = sector_of(hs)
                if s:
                    agg[s]['expDlr'] += exp
                    agg[s]['impDlr'] += imp
            return len(items), agg
        except Exception as e:
            if attempt == retries-1:
                raise
            time.sleep(2)

if __name__ == '__main__':
    months = sys.argv[1:]
    outpath = os.path.expanduser('~/mnt/loop/backtest/trade_data/sector_trade_monthly.csv')
    existing = set()
    if os.path.exists(outpath):
        with open(outpath, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                existing.add(row['yyyymm'])
    write_header = not os.path.exists(outpath)
    with open(outpath, 'a', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(['yyyymm','sector','expDlr','impDlr'])
        for ym in months:
            if ym in existing:
                print(f"{ym} skip (exists)")
                continue
            n, agg = fetch_month(ym)
            for s, v in agg.items():
                w.writerow([ym, s, v['expDlr'], v['impDlr']])
            f.flush()
            print(f"{ym} OK items={n} 반도체exp={agg['반도체']['expDlr']} TOTALexp={agg['TOTAL']['expDlr']}")
