# 분기 재무·가치 팩터 패널 구축 (룩어헤드 없음: 공시 마감 후 리밸런싱)
import csv, math, datetime as dt
from collections import defaultdict
import statistics as st

# 1) 주간 가격
PX=defaultdict(dict)          # code -> date(str) -> close
for r in csv.reader(open("_px_weekly_2019_2026.csv",encoding="utf-8")):
    if r[0]=="code": continue
    try: PX[r[0]][r[1]]=float(r[2])
    except ValueError: pass
DATES=sorted({d for v in PX.values() for d in v})

# 2) 현재 주식수 (2026-08-14 시총/종가)
SH={}
for r in csv.DictReader(open("_uni_2026.csv",encoding="utf-8")):
    try:
        c=float(r["close"]); 
        if c>0: SH[r["code"]]=float(r["mktcap"])/c
    except ValueError: pass

# 3) 재무: (code,year,reprt) -> {account: (amt, addamt)} , CFS 우선
FIN=defaultdict(dict)
for r in csv.DictReader(open("_dart_fin_2019_2026.csv",encoding="utf-8")):
    k=(r["code"],r["year"],r["reprt"]); a=r["account"]
    cur=FIN[k].get(a)
    if cur and cur[2]=="CFS" and r["fs"]!="CFS": continue
    amt = int(r["amt"]) if r["amt"] not in ("","None") else None
    add = int(r["addamt"]) if r["addamt"] not in ("","None") else None
    FIN[k][a]=(amt, add, r["fs"])

def cum(code,y,rp,acct):
    v=FIN.get((code,str(y),rp),{}).get(acct)
    if not v: return None
    return v[1] if v[1] is not None else v[0]
def bs(code,y,rp,acct):
    v=FIN.get((code,str(y),rp),{}).get(acct)
    return v[0] if v else None
def ttm(code,y,rp,acct):
    c=cum(code,y,rp,acct)
    if c is None: return None
    if rp=="11011": return c
    fy=cum(code,y-1,"11011",acct); pr=cum(code,y-1,rp,acct)
    if fy is None or pr is None: return None
    return c+fy-pr

# 4) 리밸런싱 시점: 보고서 → 실제 매매일 (공시 마감 이후 첫 주간 관측)
SCHED=[("11011","0401"),("11013","0601"),("11012","0901"),("11014","1201")]
def first_date_on_or_after(s):
    for d in DATES:
        if d>=s: return d
    return None

rows=[]
for y in range(2020,2027):
    for rp,mmdd in SCHED:
        ry = y if rp!="11011" else y      # 사업보고서(y-1년치)는 y년 4월에 쓴다
        fy = y-1 if rp=="11011" else y
        rb = first_date_on_or_after(f"{y}{mmdd}")
        if rb is None or rb>"20260828": continue
        for code in SH:
            px=PX.get(code,{}).get(rb)
            if not px: continue
            mc=px*SH[code]
            eq=bs(code,fy,rp,"자본총계"); ta=bs(code,fy,rp,"자산총계"); tl=bs(code,fy,rp,"부채총계")
            ni=ttm(code,fy,rp,"당기순이익(손실)"); sa=ttm(code,fy,rp,"매출액"); op=ttm(code,fy,rp,"영업이익")
            if eq is None or ta in (None,0): continue
            ni_p=ttm(code,fy-1,rp,"당기순이익(손실)"); sa_p=ttm(code,fy-1,rp,"매출액"); op_p=ttm(code,fy-1,rp,"영업이익")
            hist=[PX[code].get(d) for d in DATES if d<=rb][-53:]
            hist=[x for x in hist if x]
            vol=None
            if len(hist)>=40:
                rr=[hist[i+1]/hist[i]-1 for i in range(len(hist)-1) if hist[i]>0]
                if rr: vol=st.pstdev(rr)
            rows.append(dict(rb=rb, code=code, mktcap=mc, close=px,
                eq=eq, ta=ta, tl=tl, ni=ni, sa=sa, op=op,
                ni_p=ni_p, sa_p=sa_p, op_p=op_p, vol=vol, rp=rp, fy=fy))
print("패널 행",len(rows),"리밸런싱 시점",len({r['rb'] for r in rows}))

# 5) 다음 리밸런싱까지 수익률
rbs=sorted({r["rb"] for r in rows})
nxt={rbs[i]:rbs[i+1] for i in range(len(rbs)-1)}
out=[]
for r in rows:
    n=nxt.get(r["rb"])
    if not n: continue
    p1=PX.get(r["code"],{}).get(n)
    if not p1 or r["close"]<=0: continue
    r["fwd"]=p1/r["close"]-1
    out.append(r)
cols=["rb","code","rp","fy","close","mktcap","eq","ta","tl","ni","sa","op","ni_p","sa_p","op_p","vol","fwd"]
with open("_factor_panel.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore"); w.writeheader(); w.writerows(out)
print("최종",len(out),"행 · 시점",sorted({r['rb'] for r in out}))
