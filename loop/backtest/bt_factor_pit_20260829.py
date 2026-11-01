# 재무·가치 팩터 백테스트 — KRX 시점(PIT) 유니버스 + DART 재무, 유동성 필터 포함
import csv, random, math, statistics as st
from collections import defaultdict
COST=0.004
D=defaultdict(dict)
for r in csv.DictReader(open("_krx_pit.csv",encoding="utf-8")):
    try: cl,mc,sh,val=int(r["close"]),int(r["mktcap"]),int(r["shrs"]),int(r["value"] or 0)
    except ValueError: continue
    if cl<=0 or mc<=0 or sh<=0: continue
    if not r["code"].endswith("0") or "스팩" in r["name"]: continue
    D[r["date"]][r["code"]]=(cl,mc,sh,val,r["name"])
DTS=sorted(D)
def fwd(c,d0,d1,delist=-0.5):
    a=D[d0].get(c); b=D[d1].get(c)
    if not a: return None
    if not b: return delist
    ratio=b[2]/a[2]; r=b[0]/a[0]
    if ratio>=1.5 and abs(ratio-round(ratio))<0.03: r*=ratio
    elif ratio<=0.67 and abs(1/ratio-round(1/ratio))<0.03: r*=ratio
    return r-1
# DART
FIN=defaultdict(dict)
for r in csv.DictReader(open("_dart_fin_2019_2026.csv",encoding="utf-8")):
    k=(r["code"],r["year"],r["reprt"]); a=r["account"]
    cur=FIN[k].get(a)
    if cur and cur[2]=="CFS" and r["fs"]!="CFS": continue
    FIN[k][a]=(int(r["amt"]) if r["amt"] not in ("","None") else None,
               int(r["addamt"]) if r["addamt"] not in ("","None") else None, r["fs"])
def cum(c,y,rp,a):
    v=FIN.get((c,str(y),rp),{}).get(a)
    return None if not v else (v[1] if v[1] is not None else v[0])
def bs(c,y,rp,a):
    v=FIN.get((c,str(y),rp),{}).get(a); return v[0] if v else None
def ttm(c,y,rp,a):
    x=cum(c,y,rp,a)
    if x is None: return None
    if rp=="11011": return x
    fy=cum(c,y-1,"11011",a); pr=cum(c,y-1,rp,a)
    return None if fy is None or pr is None else x+fy-pr
SCHED={"0403":"11011","0402":"11011","0401":"11011","0405":"11011","0407":"11011","0404":"11011",
       "0605":"11013","0604":"11013","0603":"11013","0602":"11013","0607":"11013",
       "0904":"11012","0903":"11012","0902":"11012","0901":"11012","0906":"11012","0905":"11012",
       "1204":"11014","1203":"11014","1202":"11014","1201":"11014","1206":"11014","1205":"11014"}
def build(d0):
    rp=SCHED[d0[4:]]; y=int(d0[:4]); fy=y-1 if rp=="11011" else y
    out=[]
    for c,(cl,mc,sh,val,nm) in D[d0].items():
        eq=bs(c,fy,rp,"자본총계"); ta=bs(c,fy,rp,"자산총계"); tl=bs(c,fy,rp,"부채총계")
        ni=ttm(c,fy,rp,"당기순이익(손실)"); sa=ttm(c,fy,rp,"매출액"); op=ttm(c,fy,rp,"영업이익")
        sa_p=ttm(c,fy-1,rp,"매출액"); op_p=ttm(c,fy-1,rp,"영업이익")
        out.append(dict(code=c,cl=cl,mc=mc,val=val,nm=nm,eq=eq,ta=ta,tl=tl,ni=ni,sa=sa,op=op,sa_p=sa_p,op_p=op_p))
    return out
FACT={
 "저PER":lambda x:(x["mc"]/x["ni"],1) if x["ni"] and x["ni"]>0 else None,
 "저PBR":lambda x:(x["mc"]/x["eq"],1) if x["eq"] and x["eq"]>0 else None,
 "저PSR":lambda x:(x["mc"]/x["sa"],1) if x["sa"] and x["sa"]>0 else None,
 "고영업이익/자산":lambda x:(x["op"]/x["ta"],-1) if x["op"] is not None and x["ta"] else None,
 "소형주":lambda x:(x["mc"],1),
 "매출성장":lambda x:(x["sa"]/x["sa_p"]-1,-1) if x["sa"] and x["sa_p"] and x["sa_p"]>0 else None,
 "영업이익성장":lambda x:(x["op"]/x["op_p"]-1,-1) if x["op"] and x["op_p"] and x["op_p"]>0 else None,
 "저부채비율":lambda x:(x["tl"]/x["eq"],1) if x["tl"] is not None and x["eq"] and x["eq"]>0 else None,
}
def ranks(pool,nm):
    fn=FACT[nm]; v=[]
    for x in pool:
        r=fn(x)
        if r is None: continue
        v.append((r[0]*r[1],x["code"]))
    v.sort(); return {c:i for i,(_,c) in enumerate(v)}, len(v)
def run(picker,n=20,minval=5e8,minpx=1000,minmc=300e8,seed=None,delist=-0.5,med=False):
    per=[]; rnd=random.Random(seed); picks=[]
    for i in range(len(DTS)-1):
        d0,d1=DTS[i],DTS[i+1]
        pool=[]
        for x in build(d0):
            if x["mc"]<minmc or x["val"]<minval or x["cl"]<minpx: continue
            f=fwd(x["code"],d0,d1,delist)
            if f is None: continue
            x["fwd"]=f; pool.append(x)
        if len(pool)<50: continue
        sel=picker(pool,n,rnd)
        if not sel: continue
        agg=st.median if med else st.mean
        per.append((d0,agg([x["fwd"] for x in sel])-COST,st.mean(x["fwd"] for x in pool)))
        picks+= [(d0,x) for x in sel]
    return per,picks
def single(nm):
    def p(pool,n,rnd):
        rk,_=ranks(pool,nm); c=[x for x in pool if x["code"] in rk]
        c.sort(key=lambda x:rk[x["code"]]); return c[:n]
    return p
def combo(names):
    def p(pool,n,rnd):
        agg=defaultdict(float); cnt=defaultdict(int)
        for nm in names:
            rk,tot=ranks(pool,nm)
            for c,i in rk.items(): agg[c]+=i/max(tot-1,1); cnt[c]+=1
        ok=[x for x in pool if cnt[x["code"]]==len(names)]
        ok.sort(key=lambda x:agg[x["code"]]); return ok[:n]
    return p
def rnd_pick(pool,n,rnd): return rnd.sample(pool,min(n,len(pool)))
def rep(per,lab):
    if len(per)<5: print(f"{lab:32s} 기간부족"); return
    e=[a-b for _,a,b in per]; m=st.mean(e)
    t=m/(st.pstdev(e)/math.sqrt(len(e))) if st.pstdev(e) else 0
    cum=1.0;cb=1.0;eq=[];v=1.0
    for _,a,b in per: cum*=(1+a); cb*=(1+b); v*=(1+a); eq.append(v)
    yrs=len(per)/4; pk=-1e9; mdd=0
    for x in eq: pk=max(pk,x); mdd=min(mdd,x/pk-1)
    n1=len(per)//2
    e1=st.mean(e[:n1]); e2=st.mean(e[n1:])
    print(f"{lab:32s} 기 {len(per):2d} | 초과 {m*100:+6.2f}%p t={t:+5.2f} | 승 {sum(1 for x in e if x>0):2d}/{len(e)}"
          f" | CAGR {cum**(1/yrs)*100-100:+6.1f}% (유니버스 {cb**(1/yrs)*100-100:+5.1f}%) | MDD {mdd*100:6.1f}%"
          f" | 전반 {e1*100:+5.2f} 후반 {e2*100:+5.2f}")
print("="*140)
print("PIT 유니버스 · 거래대금>=5억 · 주가>=1000원 · 시총>=300억 · 상폐 -50% · 왕복 40bp")
print("\nA. 단일 팩터 상위 20종")
for nm in FACT:
    p,_=run(single(nm)); rep(p,f"  {nm}")
print("\nB. 대조군 무작위 20종")
for s in (1,2,3,4,5):
    p,_=run(rnd_pick,seed=s); rep(p,f"  무작위 seed{s}")
print("\nC. 조합 (강환국 울트라 근사)")
ULT=["저PER","저PBR","저PSR","고영업이익/자산","매출성장","영업이익성장"]
for names,lab in [(ULT,"울트라 근사(가치3+퀄1+성장2)"),(["저PER","저PBR","저PSR"],"가치3"),
                  (["매출성장","영업이익성장"],"성장2"),(["저PSR","고영업이익/자산"],"저PSR+수익성")]:
    p,_=run(combo(names)); rep(p,f"  {lab}")
print("\nD. 저PSR 강건성 (종목수·꼬리·유동성)")
for n in (10,20,30,50):
    p,_=run(single("저PSR"),n=n); rep(p,f"  저PSR 상위{n}종")
p,_=run(single("저PSR"),med=True); rep(p,"  저PSR 중앙값 기반(꼬리제거)")
for mv,mp in ((1e8,0),(1e9,2000),(3e9,2000)):
    p,_=run(single("저PSR"),minval=mv,minpx=mp); rep(p,f"  저PSR 거래대금>={mv/1e8:.0f}억,주가>={mp}")
