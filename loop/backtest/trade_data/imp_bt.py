import csv, json, statistics, random
from collections import defaultdict

px=json.load(open('sector_etf_ohlc.json',encoding='utf-8'))
days=sorted(px['KODEX200'].keys()); idx={d:i for i,d in enumerate(days)}
H=defaultdict(lambda: defaultdict(lambda:[0,0]))   # hs4 -> ym -> [exp, imp]
for r in csv.DictReader(open('hs4_monthly.csv',encoding='utf-8')):
    v=H[r['hs4']][r['yyyymm']]
    v[0]+=int(r['expDlr']); v[1]+=int(r['impDlr'])

def agg(prefixes, field):
    out=defaultdict(int)
    for hs4,mm in H.items():
        if any(hs4.startswith(p) for p in prefixes):
            for ym,v in mm.items(): out[ym]+=v[field]
    return dict(out)

def ym_add(ym,k):
    y=int(ym[:4]); m=int(ym[4:6]); i=y*12+(m-1)+k
    return f"{i//12}{i%12+1:02d}"
def first_td(s):
    for d in days:
        if d>=s: return d
def tstat(xs):
    n=len(xs)
    if n<2: return float('nan')
    sd=statistics.stdev(xs)
    return statistics.mean(xs)/sd*(n**0.5) if sd else float('nan')

# 선행지표 후보: 수입 (설비투자·가동률 선행)
CAND=[
 ('반도체장비 수입',['8486'],'반도체'),
 ('웨이퍼·도핑화학원소 수입',['3818'],'반도체'),
 ('포토레지스트 등 수입',['3707'],'반도체'),
 ('반도체 소재3종 수입',['8486','3818','3707'],'반도체'),
 ('리튬화합물 수입',['2836','2825'],'이차전지'),
 ('이차전지 수입',['8507'],'이차전지'),
 ('자동차부품 수입',['8708'],'자동차'),
 ('원유 수입',['2709'],'자동차'),
]
print("="*84)
print("축 4 — 수입 데이터(설비투자·가동률 선행) → 익월 섹터 ETF 초과수익")
print("PIT: 월 M 데이터 → M+1월 1일 진입 → M+2월 1일 청산")
print("="*84)
def run(name, prefixes, sec, field=1, k=3):
    ser=agg(prefixes, field)
    recs=[]
    for m in sorted(ser):
        p=ym_add(m,-k)
        if p not in ser or ser[p]==0: continue
        sig=ser[m]/ser[p]-1
        ed=first_td(f"{ym_add(m,1)}01"); xd=first_td(f"{ym_add(m,2)}01")
        if not ed or not xd or ed not in idx or xd not in idx or idx[ed]>=idx[xd]: continue
        exc=(px[sec][xd]['c']/px[sec][ed]['c']-1)-(px['KODEX200'][xd]['c']/px['KODEX200'][ed]['c']-1)
        recs.append((m,sig,exc))
    if len(recs)<40: return None
    med=statistics.median(r[1] for r in recs)
    hi=[r[2] for r in recs if r[1]>=med]; lo=[r[2] for r in recs if r[1]<med]
    return recs,hi,lo

for name,pref,sec in CAND:
    for k,lab in ((3,'3M'),(12,'YoY')):
        out=run(name,pref,sec,1,k)
        if not out: continue
        recs,hi,lo=out
        print(f"  {name:<22}{lab:>4} 수입↑ {statistics.mean(hi)*100:>7.3f}%p t={tstat(hi):>5.2f}(n={len(hi)}) | 수입↓ {statistics.mean(lo)*100:>7.3f}%p t={tstat(lo):>5.2f} | 차이 {(statistics.mean(hi)-statistics.mean(lo))*100:>7.3f}%p")

print("\n(참고) 같은 프레임, 수출 기준")
for name,pref,sec in CAND[:4]:
    out=run(name,pref,sec,0,3)
    if not out: continue
    recs,hi,lo=out
    print(f"  {name:<22} 3M(수출) 차이 {(statistics.mean(hi)-statistics.mean(lo))*100:>7.3f}%p")
