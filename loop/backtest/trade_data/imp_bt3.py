import csv, json, statistics, random
from collections import defaultdict
px=json.load(open('sector_etf_ohlc.json',encoding='utf-8'))
days=sorted(px['KODEX200'].keys()); idx={d:i for i,d in enumerate(days)}
H=defaultdict(lambda: defaultdict(lambda:[0,0]))
for r in csv.DictReader(open('hs4_monthly.csv',encoding='utf-8')):
    v=H[r['hs4']][r['yyyymm']]; v[0]+=int(r['expDlr']); v[1]+=int(r['impDlr'])
def agg(pref,f):
    o=defaultdict(int)
    for hs4,mm in H.items():
        if any(hs4.startswith(p) for p in pref):
            for ym,v in mm.items(): o[ym]+=v[f]
    return dict(o)
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

def evaluate(sigmap, sec, label, lag=1):
    """sigmap: ym -> signal value. lag=1 이면 월 M 신호 → M+1월 1일 진입"""
    months=sorted(sigmap)
    recs=[]
    for m in months:
        hist=[sigmap[x] for x in months if x<m]
        if len(hist)<24: continue
        med=statistics.median(hist)
        ed=first_td(f"{ym_add(m,lag)}01"); xd=first_td(f"{ym_add(m,lag+1)}01")
        if not ed or not xd or ed not in idx or xd not in idx or idx[ed]>=idx[xd]: continue
        exc=(px[sec][xd]['c']/px[sec][ed]['c']-1)-(px['KODEX200'][xd]['c']/px['KODEX200'][ed]['c']-1)
        recs.append((m, sigmap[m]>=med, exc))
    if len(recs)<30: return None
    hi=[r[2] for r in recs if r[1]]; lo=[r[2] for r in recs if not r[1]]
    if not hi or not lo: return None
    return len(recs), statistics.mean(hi)*100, tstat(hi), len(hi), statistics.mean(lo)*100, tstat(lo), len(lo), (statistics.mean(hi)-statistics.mean(lo))*100

def yoy_map(ser):
    out={}
    for m in sorted(ser):
        p=ym_add(m,-12)
        if p in ser and ser[p]: out[m]=ser[m]/ser[p]-1
    return out

print("="*92)
print("대조군 검정 — 이차전지 수입 YoY 신호가 '가격 모멘텀'이나 '아무 신호'로 대체되는가")
print("="*92)
imp8507=yoy_map(agg(['8507'],1))
r=evaluate(imp8507,'이차전지','수입')
print(f"{'[본신호] 이차전지 수입 YoY':<34} n={r[0]:>3} ↑{r[1]:>7.3f}%p(t={r[2]:>5.2f},n={r[3]}) ↓{r[4]:>7.3f}%p(t={r[5]:>5.2f}) 차이{r[7]:>8.3f}%p")

# (c) 가격 모멘텀 대조군: 이차전지 ETF 자체 12개월 모멘텀을 같은 프레임에
pm={}
for m in sorted(imp8507):
    ed=first_td(f"{ym_add(m,1)}01")
    if not ed or ed not in idx: continue
    i=idx[ed]
    if i<252: continue
    pm[m]=px['이차전지'][days[i-1]]['c']/px['이차전지'][days[i-252]]['c']-1
r2=evaluate(pm,'이차전지','가격모멘텀')
if r2: print(f"{'[대조] 이차전지 ETF 12M 가격모멘텀':<32} n={r2[0]:>3} ↑{r2[1]:>7.3f}%p(t={r2[2]:>5.2f},n={r2[3]}) ↓{r2[4]:>7.3f}%p(t={r2[5]:>5.2f}) 차이{r2[7]:>8.3f}%p")
pm3={}
for m in sorted(imp8507):
    ed=first_td(f"{ym_add(m,1)}01")
    if not ed or ed not in idx: continue
    i=idx[ed]
    if i<63: continue
    pm3[m]=px['이차전지'][days[i-1]]['c']/px['이차전지'][days[i-63]]['c']-1
r3=evaluate(pm3,'이차전지','가격모멘텀3M')
if r3: print(f"{'[대조] 이차전지 ETF 3M 가격모멘텀':<33} n={r3[0]:>3} ↑{r3[1]:>7.3f}%p(t={r3[2]:>5.2f},n={r3[3]}) ↓{r3[4]:>7.3f}%p(t={r3[5]:>5.2f}) 차이{r3[7]:>8.3f}%p")

# (b) 무관 품목 플라시보
print("\n[무관 품목 플라시보 — 같은 규칙, 이차전지와 무관한 수입 품목]")
for nm,pref in (('원유(2709)',['2709']),('의류(6109)',['6109']),('커피(0901)',['0901']),('의약품(3004)',['3004']),('전체수입(모든품목)',[''])):
    if pref==['']:
        o=defaultdict(int)
        for hs4,mmm in H.items():
            for ym,v in mmm.items(): o[ym]+=v[1]
        s=yoy_map(dict(o))
    else:
        s=yoy_map(agg(pref,1))
    rr=evaluate(s,'이차전지',nm)
    if rr: print(f"  {nm:<20} 차이 {rr[7]:>8.3f}%p  (↑t={rr[2]:>5.2f} ↓t={rr[5]:>5.2f})")

# (d) 시차 감쇠: lag 2,3 (정보가 오래될수록 약해져야 진짜)
print("\n[시차 감쇠 — 같은 신호를 1·2·3개월 더 늦게 사용]")
for lg in (1,2,3):
    rr=evaluate(imp8507,'이차전지','',lag=lg)
    if rr: print(f"  lag={lg}개월: 차이 {rr[7]:>8.3f}%p (↑{rr[1]:>7.3f} t={rr[2]:>5.2f} / ↓{rr[4]:>7.3f} t={rr[5]:>5.2f})")

# (a) 타 섹터 교차 적용: 이차전지 수입 신호를 다른 섹터 ETF에
print("\n[타 섹터 교차 — 이차전지 수입 신호로 다른 섹터를 매매하면? (진짜면 이차전지에서만 나와야)]")
for sec in ('반도체','자동차','바이오헬스','화장품'):
    rr=evaluate(imp8507,sec,'')
    if rr: print(f"  → {sec:<8} 차이 {rr[7]:>8.3f}%p (↑t={rr[2]:>5.2f} ↓t={rr[5]:>5.2f})")

# 각 섹터 자기 수입 신호 (일관성 확인)
print("\n[각 섹터의 '자기 품목 수입 YoY' 동일 규칙 — 이차전지만 되는가]")
for sec,pref in (('반도체',['8541','8542']),('자동차',['8703']),('바이오헬스',['3004']),('화장품',['3304']),('이차전지',['8507'])):
    s=yoy_map(agg(pref,1))
    rr=evaluate(s,sec,'')
    if rr: print(f"  {sec:<8} 차이 {rr[7]:>8.3f}%p (↑{rr[1]:>7.3f} t={rr[2]:>5.2f} / ↓{rr[4]:>7.3f} t={rr[5]:>5.2f})")
