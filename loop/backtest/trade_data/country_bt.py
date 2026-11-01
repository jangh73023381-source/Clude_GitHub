import csv, json, statistics, random
from collections import defaultdict

px=json.load(open('sector_etf_ohlc.json',encoding='utf-8'))
days=sorted(px['KODEX200'].keys()); idx={d:i for i,d in enumerate(days)}
IC=defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # item -> cnty -> ym -> exp
ICtot=defaultdict(lambda: defaultdict(int))                    # item -> ym -> exp
for r in csv.DictReader(open('item_country_monthly.csv',encoding='utf-8')):
    e=int(r['expDlr']); IC[r['item']][r['cntyKor']][r['yyyymm']]+=e; ICtot[r['item']][r['yyyymm']]+=e
NAT=defaultdict(lambda: defaultdict(int))
for r in csv.DictReader(open('country_monthly.csv',encoding='utf-8')):
    NAT[r['cntyKor']][r['yyyymm']]+=int(r['expDlr'])

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
def yoymap(ser):
    return {m: ser[m]/ser[ym_add(m,-12)]-1 for m in sorted(ser) if ym_add(m,-12) in ser and ser[ym_add(m,-12)]}

def evaluate(sig, sec, lag=1, minhist=24):
    ms=sorted(sig); recs=[]
    for m in ms:
        hist=[sig[x] for x in ms if x<m]
        if len(hist)<minhist: continue
        med=statistics.median(hist)
        ed=first_td(f"{ym_add(m,lag)}01"); xd=first_td(f"{ym_add(m,lag+1)}01")
        if not ed or not xd or ed not in idx or xd not in idx or idx[ed]>=idx[xd]: continue
        exc=(px[sec][xd]['c']/px[sec][ed]['c']-1)-(px['KODEX200'][xd]['c']/px['KODEX200'][ed]['c']-1)
        recs.append((m,sig[m]>=med,exc))
    if len(recs)<30: return None
    hi=[r[2] for r in recs if r[1]]; lo=[r[2] for r in recs if not r[1]]
    if not hi or not lo: return None
    return recs,hi,lo
def line(tag,r):
    recs,hi,lo=r
    return (f"  {tag:<34} n={len(recs):>3} ↑{statistics.mean(hi)*100:>7.3f}%p(t={tstat(hi):>5.2f},n={len(hi)}) "
            f"↓{statistics.mean(lo)*100:>7.3f}%p(t={tstat(lo):>5.2f}) 차이{(statistics.mean(hi)-statistics.mean(lo))*100:>8.3f}%p")

print("="*104)
print("축 6 — 국가별 / 품목×국가별 수출  (expanding median, 룩어헤드 없음)")
print("="*104)
print("\n[6a] 주요국 총수출 YoY → 각 섹터 ETF 초과수익")
for cty in ('중국','미국','베트남','일본'):
    s=yoymap(NAT[cty])
    for sec in ('반도체','자동차','이차전지','화장품'):
        r=evaluate(s,sec)
        if r: print(line(f"대{cty} 총수출 → {sec}", r))

print("\n[6b] 품목×국가: 각 섹터의 주요 수출국 → 해당 섹터 ETF")
PAIRS=[('반도체','중국','반도체'),('반도체','홍콩','반도체'),('반도체','대만','반도체'),('반도체','베트남','반도체'),
       ('화장품','중국','화장품'),('화장품','미국','화장품'),('자동차','미국','자동차'),
       ('이차전지','미국','이차전지'),('이차전지','중국','이차전지'),('의약품','미국','바이오헬스')]
res={}
for item,cty,sec in PAIRS:
    s=yoymap(IC[item][cty])
    r=evaluate(s,sec)
    if r:
        res[(item,cty,sec)]=r
        print(line(f"{item} 대{cty} 수출 → {sec}", r))

print("\n[6c] 구성 변화: 그 품목 수출 중 특정국 비중(총액 증감과 다른 정보)")
for item,cty,sec in PAIRS:
    share={m: IC[item][cty][m]/ICtot[item][m] for m in ICtot[item] if ICtot[item][m]}
    chg={m: share[m]-share[ym_add(m,-12)] for m in sorted(share) if ym_add(m,-12) in share}
    r=evaluate(chg,sec)
    if r: print(line(f"{item} 대{cty} 비중변화 → {sec}", r))

print("\n[★ 대조군] 무관 신호 — 커피 대중국 수출 YoY 로 각 섹터 매매")
s=yoymap(IC['커피']['중국'])
for sec in ('반도체','자동차','이차전지','화장품','바이오헬스'):
    r=evaluate(s,sec)
    if r: print(line(f"커피 대중국 → {sec}", r))

print("\n[★ 대조군] 타 섹터 교차 — 화장품 대중국 신호로 다른 섹터 매매")
s=yoymap(IC['화장품']['중국'])
for sec in ('반도체','자동차','이차전지','바이오헬스','화장품'):
    r=evaluate(s,sec)
    if r: print(line(f"화장품 대중국 → {sec}", r))
