# 유튜브 '오전 10분봉 5점매매' 백테스트 (주식탐구소 2026-08-29, mluWucvHtxc)
import csv, random, statistics as st
from collections import defaultdict

COST = 0.0025   # 왕복 비용(수수료+거래세) 25bp

bars=defaultdict(list)
for r in csv.DictReader(open("_yt10min_bars.csv",encoding="utf-8")):
    bars[(r["code"],r["date"])].append((r["hhmm"],int(r["open"]),int(r["high"]),
                                        int(r["low"]),int(r["close"]),int(r["accvol"])))
for k in bars: bars[k].sort()

cand={}
for r in csv.DictReader(open("_yt10min_cands.csv",encoding="utf-8")):
    cand[(r["code"],r["date"])]=r

bench=defaultdict(dict)
for r in csv.DictReader(open("_yt10min_bench.csv",encoding="utf-8")):
    bench[r["date"]][r["hhmm"]]=int(r["close"])

def bench_ret(d,hm0,hm1):
    b=bench.get(d)
    if not b: return None
    ks=sorted(b)
    def px(h):
        c=[x for x in ks if x>=h]
        return b[c[0]] if c else b[ks[-1]]
    a,z=px(hm0),px(hm1)
    return z/a-1 if a else None

def run(turn_th=0.10, fibs=(0.382,0.50,0.618), exit_mode="close",
        am_only=False, entry="rule", seed=0, tp=0.05):
    rnd=random.Random(seed); out=[]
    for key,c in cand.items():
        if key not in bars: continue
        if float(c["turn"])<turn_th: continue
        bs=bars[key]
        if len(bs)<30: continue
        code,date=key
        shares=float(c["close"]) and float(c["vol"])/float(c["turn"])
        gate=max(float(c["ma5"]),float(c["ma10"]),float(c["ma20"]))
        # --- 실시간 게이트: 이평선 돌파 + 누적회전율 충족한 첫 봉
        gi=None
        for i,(hm,o,h,l,cl,av) in enumerate(bs):
            if hm>="1520": break
            if h>gate and av/shares>=turn_th:
                gi=i; break
        if gi is None: continue
        if am_only and bs[gi][0]>="1200": continue
        seg=bs[:gi+1]
        H=max(x[2] for x in seg); L=min(x[3] for x in seg)
        rng=H-L
        if rng<=0: continue
        lv2=H-fibs[0]*rng; lv3=H-fibs[1]*rng; lv4=H-fibs[2]*rng
        post=bs[gi+1:]
        if not post: continue
        # --- 진입
        fills=[]; stopped=False; exitpx=None; exit_hm=None; entry_hm=None
        if entry=="random":
            j=rnd.randrange(len(post))
            fills=[post[j][4]]; entry_hm=post[j][0]; post2=post[j+1:]
        else:
            post2=None
            for k,(hm,o,h,l,cl,av) in enumerate(post):
                if len(fills)<2 and l<=lv2 and len(fills)==0:
                    fills.append(min(lv2,o)); entry_hm=entry_hm or hm
                if l<=lv3 and len(fills)<2 and fills:
                    fills.append(min(lv3,o)); 
                elif l<=lv3 and not fills:
                    fills.append(min(lv2,o)); fills.append(min(lv3,o)); entry_hm=entry_hm or hm
                if fills:
                    post2=post[k+1:] if l>lv4 else post[k:]
                    if l<=lv4: break
                    if len(fills)>=2: break
            if not fills: continue
            post2=post2 if post2 is not None else []
        buy=sum(fills)/len(fills)
        # --- 청산
        for hm,o,h,l,cl,av in post2:
            if l<=lv4:
                exitpx=lv4; exit_hm=hm; stopped=True; break
            if exit_mode=="tp" and h>=buy*(1+tp):
                exitpx=buy*(1+tp); exit_hm=hm; break
            if exit_mode=="line1" and h>=H:
                exitpx=H; exit_hm=hm; break
        if exitpx is None:
            exitpx=bs[-1][4]; exit_hm=bs[-1][0]
        ret=exitpx/buy-1-COST
        br=bench_ret(date,entry_hm or bs[gi][0],exit_hm)
        out.append(dict(code=code,date=date,ret=ret,exc=None if br is None else ret-br,
                        stopped=stopped,nfill=len(fills)))
    return out

def summarize(res,label):
    if not res:
        print(f"{label:38s} 거래 0"); return
    r=[x["ret"] for x in res]; e=[x["exc"] for x in res if x["exc"] is not None]
    byd=defaultdict(list)
    for x in res:
        if x["exc"] is not None: byd[x["date"]].append(x["exc"])
    ds=list(byd); rnd=random.Random(99); bsr=[]
    for _ in range(2000):
        s=[v for _ in ds for v in byd[rnd.choice(ds)]]
        bsr.append(st.mean(s))
    bsr.sort()
    lo,hi=bsr[50],bsr[1949]
    print(f"{label:38s} 거래 {len(res):4d} 날짜 {len(ds):3d} | 절대 {st.mean(r)*100:+6.2f}% | "
          f"초과 {st.mean(e)*100:+6.2f}%p [{lo*100:+.2f},{hi*100:+.2f}] | "
          f"승률 {sum(1 for x in r if x>0)/len(r)*100:4.1f}% | 손절 {sum(1 for x in res if x['stopped'])/len(res)*100:4.1f}%")

print("="*118)
print("A. 원안 (피보 38.2/50/61.8 · 회전율 10% · 당일 종가청산)")
base=run(); summarize(base,"  원안")
for s in (1,2,3):
    summarize(run(entry="random",seed=s), f"  [대조군] 무작위 진입 seed{s}")
print()
print("B. 회전율 임계 민감도")
for th in (0.10,0.15,0.20,0.30):
    summarize(run(turn_th=th), f"  회전율>={th:.0%}")
print()
print("C. 되돌림 수준 민감도 (2차/3차/손절)")
for f in [(0.236,0.382,0.50),(0.382,0.50,0.618),(0.50,0.618,0.786),(0.382,0.618,0.786)]:
    summarize(run(fibs=f), f"  {f}")
print()
print("D. 청산 규칙 민감도")
for m,lab in [("close","당일 종가"),("tp","+5% 익절"),("line1","1차선(고가) 도달")]:
    summarize(run(exit_mode=m), f"  {lab}")
print()
print("E. 오전(12시 이전) 진입만")
summarize(run(am_only=True), "  오전 한정")
for s in (1,2):
    summarize(run(am_only=True,entry="random",seed=s), f"  [대조군] 오전 무작위 seed{s}")
