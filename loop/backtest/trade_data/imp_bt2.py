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
def mom(sec,d,k=20):
    i=idx[d]
    if i<k+1: return None
    return (px[sec][days[i-1]]['c']/px[sec][days[i-k-1]]['c']-1)-(px['KODEX200'][days[i-1]]['c']/px['KODEX200'][days[i-k-1]]['c']-1)

print("="*84)
print("정밀검정 — 이차전지(HS8507) 수입 YoY, expanding median (룩어헤드 제거)")
print("="*84)
ser=agg(['8507'],1)
months=sorted(ser)
recs=[]
for m in months:
    p=ym_add(m,-12)
    if p not in ser or ser[p]==0: continue
    sig=ser[m]/ser[p]-1
    hist=[]
    for mm in months:
        if mm>=m: break
        pp=ym_add(mm,-12)
        if pp in ser and ser[pp]: hist.append(ser[mm]/ser[pp]-1)
    if len(hist)<24: continue
    med=statistics.median(hist)
    ed=first_td(f"{ym_add(m,1)}01"); xd=first_td(f"{ym_add(m,2)}01")
    if not ed or not xd or ed not in idx or xd not in idx or idx[ed]>=idx[xd]: continue
    exc=(px['이차전지'][xd]['c']/px['이차전지'][ed]['c']-1)-(px['KODEX200'][xd]['c']/px['KODEX200'][ed]['c']-1)
    recs.append((m,sig,sig>=med,exc,mom('이차전지',ed)))
hi=[r[3] for r in recs if r[2]]; lo=[r[3] for r in recs if not r[2]]
print(f"n={len(recs)} ({recs[0][0]}~{recs[-1][0]})")
print(f"  수입↑ {statistics.mean(hi)*100:>7.3f}%p t={tstat(hi):>5.2f} n={len(hi)} 승률 {sum(1 for x in hi if x>0)/len(hi)*100:.1f}% 중앙값 {statistics.median(hi)*100:.3f}")
print(f"  수입↓ {statistics.mean(lo)*100:>7.3f}%p t={tstat(lo):>5.2f} n={len(lo)} 승률 {sum(1 for x in lo if x>0)/len(lo)*100:.1f}%")
print(f"  차이 {(statistics.mean(hi)-statistics.mean(lo))*100:.3f}%p")
h=len(recs)//2
tr=[r[3] for r in recs[:h] if r[2]]; te=[r[3] for r in recs[h:] if r[2]]
trl=[r[3] for r in recs[:h] if not r[2]]; tel=[r[3] for r in recs[h:] if not r[2]]
print(f"  train 차이 {(statistics.mean(tr)-statistics.mean(trl))*100:>7.3f}%p (n↑={len(tr)}) | test 차이 {(statistics.mean(te)-statistics.mean(tel))*100:>7.3f}%p (n↑={len(te)})")
srt=sorted(hi,reverse=True)
print(f"  꼬리(수입↑): 상위3 기여 {sum(srt[:3])/sum(hi)*100:.1f}% / 제거시 {statistics.mean(srt[3:])*100:.3f}%p t={tstat(srt[3:]):.2f}")
random.seed(3); obs=statistics.mean(hi)-statistics.mean(lo); pl=[]
for _ in range(2000):
    lab=[r[2] for r in recs]; random.shuffle(lab)
    a=[r[3] for r,l in zip(recs,lab) if l]; b=[r[3] for r,l in zip(recs,lab) if not l]
    pl.append(statistics.mean(a)-statistics.mean(b))
print(f"  플라시보(2000회): 셔플평균 {statistics.mean(pl)*100:.3f}%p sd={statistics.stdev(pl)*100:.3f} | 관측 {obs*100:.3f}%p | p={sum(1 for x in pl if x>=obs)/len(pl):.4f}")
val=[r for r in recs if r[4] is not None]
mm=statistics.median(r[4] for r in val)
for lab,c in (('mom상위',lambda r:r[4]>=mm),('mom하위',lambda r:r[4]<mm)):
    s=[r for r in val if c(r)]
    a=[r[3] for r in s if r[2]]; b=[r[3] for r in s if not r[2]]
    if a and b: print(f"  {lab} 내부 차이 {(statistics.mean(a)-statistics.mean(b))*100:>7.3f}%p (n↑={len(a)}, n↓={len(b)})")
cs=cb=1.0
for r in recs:
    cs*= (1+ (px['이차전지'][first_td(f"{ym_add(r[0],2)}01")]['c']/px['이차전지'][first_td(f"{ym_add(r[0],1)}01")]['c']-1 if r[2] else px['KODEX200'][first_td(f"{ym_add(r[0],2)}01")]['c']/px['KODEX200'][first_td(f"{ym_add(r[0],1)}01")]['c']-1))
    cb*= (1+ px['KODEX200'][first_td(f"{ym_add(r[0],2)}01")]['c']/px['KODEX200'][first_td(f"{ym_add(r[0],1)}01")]['c']-1)
ch=1.0
for r in recs: ch*=(1+px['이차전지'][first_td(f"{ym_add(r[0],2)}01")]['c']/px['이차전지'][first_td(f"{ym_add(r[0],1)}01")]['c']-1)
print(f"  누적: 전략(수입↑달만 이차전지, 나머지 KODEX200) {(cs-1)*100:.1f}% | KODEX200 {(cb-1)*100:.1f}% | 이차전지 상시보유 {(ch-1)*100:.1f}%")
