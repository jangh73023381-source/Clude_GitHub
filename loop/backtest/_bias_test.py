import csv, random, math, statistics as st
from collections import defaultdict
D=defaultdict(dict)
for r in csv.DictReader(open("_krx_pit.csv",encoding="utf-8")):
    try:
        cl=int(r["close"]); mc=int(r["mktcap"]); sh=int(r["shrs"])
    except ValueError: continue
    if cl<=0 or mc<=0 or sh<=0: continue
    code=r["code"]
    if not code.endswith("0"): continue          # 우선주 제외
    if "스팩" in r["name"]: continue
    D[r["date"]][code]=(cl,mc,sh,r["name"],int(r["value"] or 0))
DTS=sorted(D)
SURV=set(r["code"] for r in csv.DictReader(open("_uni_2026.csv",encoding="utf-8")))

def fwd(code,d0,d1,delist):
    a=D[d0].get(code); b=D[d1].get(code)
    if not a: return None
    if not b: return delist
    ratio=b[2]/a[2]
    r=b[0]/a[0]
    if ratio>=1.5 and abs(ratio-round(ratio))<0.03: r*=ratio          # 액면분할/무상증자
    elif ratio<=0.67 and abs(1/ratio-round(1/ratio))<0.03: r*=ratio   # 액면병합
    return r-1

def run(n=20, delist=-0.5, surv_only=False, minmc=300e8, seed=None, mode="small"):
    per=[]; rnd=random.Random(seed)
    for i in range(len(DTS)-1):
        d0,d1=DTS[i],DTS[i+1]
        pool=[]
        for c,(cl,mc,sh,nm,val) in D[d0].items():
            if mc<minmc: continue
            if surv_only and c not in SURV: continue
            f=fwd(c,d0,d1,delist)
            if f is None: continue
            pool.append((c,mc,f))
        if len(pool)<50: continue
        if mode=="small": sel=sorted(pool,key=lambda x:x[1])[:n]
        elif mode=="large": sel=sorted(pool,key=lambda x:-x[1])[:n]
        else: sel=rnd.sample(pool,n)
        per.append((d0, st.mean(x[2] for x in sel)-0.004, st.mean(x[2] for x in pool)))
    e=[a-b for _,a,b in per]
    m=st.mean(e); t=m/(st.pstdev(e)/math.sqrt(len(e))) if st.pstdev(e) else 0
    cum=1.0; cb=1.0; eq=[]; v=1.0
    for _,a,b in per: cum*=(1+a); cb*=(1+b); v*=(1+a); eq.append(v)
    yrs=len(per)/4; peak=-1e9; mdd=0
    for x in eq:
        peak=max(peak,x); mdd=min(mdd,x/peak-1)
    return dict(n=len(per),m=m,t=t,cagr=cum**(1/yrs)-1,cagrb=cb**(1/yrs)-1,mdd=mdd)

def show(lab,r):
    print(f"{lab:44s} 기 {r['n']:2d} | 분기초과 {r['m']*100:+6.2f}%p t={r['t']:+5.2f} | "
          f"CAGR {r['cagr']*100:+6.1f}% (유니버스 {r['cagrb']*100:+5.1f}%) | MDD {r['mdd']*100:6.1f}%")

print("★ 생존편의 측정 — 소형주 상위 20종 (시총 하위 20종)")
show("  PIT 유니버스 · 상폐 -50%", run(delist=-0.5))
show("  PIT 유니버스 · 상폐 -100%", run(delist=-1.0))
show("  PIT 유니버스 · 상폐 0%", run(delist=0.0))
show("  [편향] 2026년 생존종목만 · 상폐 0%", run(surv_only=True,delist=0.0))
print()
print("대조: 대형주 20종 / 무작위 20종 (PIT · 상폐 -50%)")
show("  대형주", run(mode="large"))
for s in (1,2,3): show(f"  무작위 seed{s}", run(mode="rand",seed=s))
print()
print("유니버스 자체 수익률 비교 (동일가중 CAGR)")
for lab,kw in [("PIT 전체",dict()),("생존종목만",dict(surv_only=True,delist=0.0))]:
    r=run(**kw); print(f"  {lab:20s} {r['cagrb']*100:+.1f}%")
