# 재무·가치 팩터 백테스트 (분기 리밸런싱, 2020-04 ~ 2026-06, 25기)
import csv, random, math, statistics as st
from collections import defaultdict

COST=0.004   # 리밸런싱 1회당 왕복 비용 40bp
P=defaultdict(list)
for r in csv.DictReader(open("_factor_panel.csv",encoding="utf-8")):
    def f(k):
        v=r[k]
        return None if v in ("","None") else float(v)
    P[r["rb"]].append(dict(code=r["code"],mc=f("mktcap"),eq=f("eq"),ta=f("ta"),tl=f("tl"),
        ni=f("ni"),sa=f("sa"),op=f("op"),ni_p=f("ni_p"),sa_p=f("sa_p"),op_p=f("op_p"),
        vol=f("vol"),fwd=f("fwd")))
RBS=sorted(P)

def base_filter(x):
    return (x["mc"] and x["mc"]>300e8 and x["eq"] and x["eq"]>0 and x["ta"] and x["ta"]>0
            and x["fwd"] is not None)

FACT={
 "저PER":      lambda x: (x["mc"]/x["ni"], 1) if x["ni"] and x["ni"]>0 else None,
 "저PBR":      lambda x: (x["mc"]/x["eq"], 1),
 "저PSR":      lambda x: (x["mc"]/x["sa"], 1) if x["sa"] and x["sa"]>0 else None,
 "고영업이익/자산": lambda x: (x["op"]/x["ta"], -1) if x["op"] is not None else None,
 "저변동성":     lambda x: (x["vol"], 1) if x["vol"] else None,
 "소형주":       lambda x: (x["mc"], 1),
 "매출성장":     lambda x: (x["sa"]/x["sa_p"]-1, -1) if x["sa"] and x["sa_p"] and x["sa_p"]>0 else None,
 "영업이익성장":  lambda x: (x["op"]/x["op_p"]-1, -1) if x["op"] and x["op_p"] and x["op_p"]>0 else None,
 "저부채비율":    lambda x: (x["tl"]/x["eq"], 1) if x["tl"] is not None else None,
}

def ranks(pool, name):
    fn=FACT[name]; vals=[]
    for x in pool:
        v=fn(x)
        if v is None: continue
        vals.append((v[0]*v[1], x["code"]))
    vals.sort()
    return {c:i for i,(_,c) in enumerate(vals)}, len(vals)

def run(picker, n=20, small_only=False, seed=None, label=""):
    per=[]
    rnd=random.Random(seed)
    for rb in RBS:
        pool=[x for x in P[rb] if base_filter(x)]
        if small_only:
            pool.sort(key=lambda x:x["mc"]); pool=pool[:max(50,len(pool)//5)]
        if len(pool)<50: continue
        sel=picker(pool,n,rnd)
        if not sel: continue
        sr=st.mean(x["fwd"] for x in sel)-COST
        br=st.mean(x["fwd"] for x in pool)
        per.append((rb,sr,br,sr-br))
    return per

def single(name):
    def p(pool,n,rnd):
        rk,_=ranks(pool,name)
        c=[x for x in pool if x["code"] in rk]
        c.sort(key=lambda x:rk[x["code"]])
        return c[:n]
    return p

def combo(names,weights=None):
    def p(pool,n,rnd):
        agg=defaultdict(float); cnt=defaultdict(int)
        for nm in names:
            rk,tot=ranks(pool,nm)
            for c,i in rk.items():
                agg[c]+= (i/max(tot-1,1)); cnt[c]+=1
        ok=[x for x in pool if cnt[x["code"]]==len(names)]
        ok.sort(key=lambda x:agg[x["code"]])
        return ok[:n]
    return p

def rnd_pick(pool,n,rnd): return rnd.sample(pool,min(n,len(pool)))

def rep(per,label):
    if len(per)<5: print(f"{label:34s} 기간 {len(per)}"); return None
    e=[x[3] for x in per]; s=[x[1] for x in per]; b=[x[2] for x in per]
    m=st.mean(e); sd=st.pstdev(e); t=m/(sd/math.sqrt(len(e))) if sd else 0
    cum=1.0
    for x in per: cum*=(1+x[1])
    cb=1.0
    for x in per: cb*=(1+x[2])
    yrs=len(per)/4
    cagr=cum**(1/yrs)-1; cagrb=cb**(1/yrs)-1
    # MDD
    eq=[]; v=1.0
    for x in per: v*=(1+x[1]); eq.append(v)
    peak=-1e9; mdd=0
    for v in eq:
        peak=max(peak,v); mdd=min(mdd,v/peak-1)
    print(f"{label:34s} 기 {len(per):2d} | 분기초과 {m*100:+6.2f}%p t={t:+5.2f} | 승 {sum(1 for x in e if x>0)}/{len(e)}"
          f" | CAGR {cagr*100:+6.1f}% (유니버스 {cagrb*100:+5.1f}%) | MDD {mdd*100:6.1f}%")
    return m,t

print("="*120)
print("A. 단일 팩터 상위 20종 (분기 리밸런싱 · 유니버스 동일가중 대비 초과)")
res={}
for nm in FACT: res[nm]=rep(run(single(nm)), f"  {nm}")
print()
print("B. 대조군 — 무작위 20종")
for s in (1,2,3,4,5): rep(run(rnd_pick,seed=s), f"  무작위 seed{s}")
print()
print("C. 강환국 울트라 근사 (가치3 + 퀄리티2 + 성장2 순위합)")
ULT=["저PER","저PBR","저PSR","고영업이익/자산","저변동성","매출성장","영업이익성장"]
rep(run(combo(ULT)), "  울트라 근사(전체)")
rep(run(combo(ULT),small_only=True), "  울트라 근사(소형주 하위20%)")
rep(run(combo(["저PER","저PBR","저PSR"])), "  가치3만")
rep(run(combo(["고영업이익/자산","저변동성"])), "  퀄리티2만")
rep(run(combo(["매출성장","영업이익성장"])), "  성장2만")
