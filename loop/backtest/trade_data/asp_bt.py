import csv, json, statistics, random

px=json.load(open('sector_etf_ohlc.json',encoding='utf-8'))
days=sorted(px['KODEX200'].keys()); idx={d:i for i,d in enumerate(days)}
asp={}
for r in csv.DictReader(open('asp_monthly.csv',encoding='utf-8')):
    d,w=int(r['expDlr']),int(r['expWgt'])
    asp.setdefault(r['item'],{})[r['yyyymm']] = (d/w if w else None, d)

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

PAIRS=[('디램','반도체'),('집적회로전체','반도체'),('승용차','자동차'),('이차전지','이차전지'),('의약품','바이오헬스'),('화장품','화장품')]

print("="*80)
print("수출 단가(ASP) 모멘텀 → 익월 섹터 ETF 초과수익  [PIT: 월 M 데이터는 M+1월 1일 공개]")
print("="*80)

def build(item, sec, sigfn, label):
    recs=[]
    months=sorted(asp[item])
    for m in months:
        p, dl = asp[item][m]
        if p is None: continue
        sig = sigfn(item, m)
        if sig is None: continue
        ed = first_td(f"{ym_add(m,1)}01"); xd = first_td(f"{ym_add(m,2)}01")
        if not ed or not xd or ed not in idx or xd not in idx or idx[ed]>=idx[xd]: continue
        if idx[xd] >= len(days): continue
        exc = (px[sec][xd]['c']/px[sec][ed]['c']-1) - (px['KODEX200'][xd]['c']/px['KODEX200'][ed]['c']-1)
        abs_ret = px[sec][xd]['c']/px[sec][ed]['c']-1
        bench = px['KODEX200'][xd]['c']/px['KODEX200'][ed]['c']-1
        recs.append((m, sig, exc, abs_ret, bench))
    return recs

def mom(item,m,k):
    a=asp[item].get(m); b=asp[item].get(ym_add(m,-k))
    if not a or not b or a[0] is None or b[0] is None or b[0]==0: return None
    return a[0]/b[0]-1

for item,sec in PAIRS:
    print(f"\n### {item} 단가 → {sec} ETF")
    for k,lab in ((1,'MoM'),(3,'3M'),(12,'YoY')):
        recs=build(item,sec,lambda i,m,k=k: mom(i,m,k), lab)
        if len(recs)<30: continue
        pos=[r[2] for r in recs if r[1]>0]; neg=[r[2] for r in recs if r[1]<=0]
        if not pos or not neg: continue
        print(f"  {lab:>4}: 단가상승월 초과 {statistics.mean(pos)*100:>7.3f}%p t={tstat(pos):>5.2f}(n={len(pos)}) | "
              f"하락월 {statistics.mean(neg)*100:>7.3f}%p t={tstat(neg):>5.2f}(n={len(neg)}) | 차이 {(statistics.mean(pos)-statistics.mean(neg))*100:>7.3f}%p")

# 핵심 후보 정밀검정: 디램 3M 단가모멘텀 → 반도체
print("\n" + "="*80)
print("정밀검정 — 디램 단가 3개월 모멘텀 > 0 이면 KODEX 반도체 보유(익월), 아니면 미보유")
print("="*80)
recs=build('디램','반도체',lambda i,m: mom(i,m,3),'3M')
print(f"n={len(recs)} ({recs[0][0]}~{recs[-1][0]})")
pos=[r for r in recs if r[1]>0]; neg=[r for r in recs if r[1]<=0]
P=[r[2] for r in pos]; N=[r[2] for r in neg]
print(f"  상승월: 초과 {statistics.mean(P)*100:.3f}%p t={tstat(P):.2f} n={len(P)} 승률 {sum(1 for x in P if x>0)/len(P)*100:.1f}% 중앙값 {statistics.median(P)*100:.3f}")
print(f"  하락월: 초과 {statistics.mean(N)*100:.3f}%p t={tstat(N):.2f} n={len(N)} 승률 {sum(1 for x in N if x>0)/len(N)*100:.1f}%")
print(f"  차이 {(statistics.mean(P)-statistics.mean(N))*100:.3f}%p")
half=len(recs)//2
tr=[r[2] for r in recs[:half] if r[1]>0]; te=[r[2] for r in recs[half:] if r[1]>0]
print(f"  train 상승월 {statistics.mean(tr)*100:.3f}%p t={tstat(tr):.2f}(n={len(tr)}) | test 상승월 {statistics.mean(te)*100:.3f}%p t={tstat(te):.2f}(n={len(te)})")
srt=sorted(P,reverse=True)
print(f"  꼬리: 상위3 기여 {sum(srt[:3])/sum(P)*100:.1f}% / 제거시 {statistics.mean(srt[3:])*100:.3f}%p t={tstat(srt[3:]):.2f}")
random.seed(11)
pl=[]
for _ in range(2000):
    sig=[r[1] for r in recs]; random.shuffle(sig)
    v=[r[2] for r,s in zip(recs,sig) if s>0]
    pl.append(statistics.mean(v) if v else 0)
obs=statistics.mean(P)
print(f"  플라시보(2000회): 셔플평균 {statistics.mean(pl)*100:.3f}%p sd={statistics.stdev(pl)*100:.3f} | 관측 {obs*100:.3f}%p | p={sum(1 for x in pl if x>=obs)/len(pl):.4f}")
cum_s=cum_b=1.0
for r in recs:
    cum_s *= (1 + (r[3] if r[1]>0 else r[4]))
    cum_b *= (1 + r[4])
print(f"  누적: 전략(상승월 반도체·나머지 KODEX200) {(cum_s-1)*100:.1f}% vs KODEX200 상시보유 {(cum_b-1)*100:.1f}%")
cum_h=1.0
for r in recs: cum_h*=(1+r[3])
print(f"        반도체 상시보유 {(cum_h-1)*100:.1f}%")
