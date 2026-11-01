# -*- coding: utf-8 -*-
"""관심 파일럿 × mom20 조합 개념검증 (forward 기록 9일, 섹터-ETF 레벨). 표본 9 극소=방향성만.
INTER = 순수관심(감성조건화, 가격無). 조합군은 mom20(가격)을 관심에 결합한 것들."""
import csv, statistics
from collections import defaultdict
px=defaultdict(dict)
for r in csv.DictReader(open("backtest/panel_close_0723.csv",encoding="utf-8")):
    try: px[r["code"].strip().zfill(6)][r["date"]]=float(r["close"])
    except: pass
pdates=sorted({d for c in px for d in px[c]})
sp=defaultdict(dict)
for r in csv.DictReader(open("references/attention_shadow_picks.csv",encoding="utf-8")):
    sp[r["date"]][r["theme"]]={"code":r["code"].strip().zfill(6),"base":float(r["comp_base"]),"inter":float(r["comp_inter"])}
ns2=defaultdict(dict)
for r in csv.DictReader(open("references/attention_shadow_ns2_picks.csv",encoding="utf-8")):
    ns2[r["date"]][r["theme"]]=float(r["comp_ns2"])
dates=sorted(sp.keys())
def mom20(code,sd):
    i=pdates.index(sd); a=px[code].get(pdates[i-21]); b=px[code].get(pdates[i-1])
    return (b/a-1.0) if (a and b) else None
def ret_day(code,sd):
    i=pdates.index(sd); a=px[code].get(pdates[i-1]); b=px[code].get(sd)
    return (b/a-1.0) if (a and b) else None
def z(d):
    v=list(d.values()); m=statistics.mean(v); s=statistics.pstdev(v) or 1e-9
    return {k:(x-m)/s for k,x in d.items()}
strats=["MOM20(가격단독)","ATT_base(관심)","ATT_ns2(관심)","INTER(순수관심·감성조건)",
        "z(관심)+z(mom20)","2·z(관심)+z(mom20)","관심top5−mom20하위3제거"]
acc={s:{"exc":[],"raw":[],"t3":[],"win":0} for s in strats}
for sd in dates:
    secs=list(sp[sd].keys()); code={s:sp[sd][s]["code"] for s in secs}
    mom={s:(mom20(code[s],sd) or -9) for s in secs}
    base={s:sp[sd][s]["base"] for s in secs}; inter={s:sp[sd][s]["inter"] for s in secs}
    nsig={s:ns2[sd].get(s,-9) for s in secs}
    zmom=z(mom); zns=z(nsig)
    combA={s:zns[s]+zmom[s] for s in secs}; combB={s:2*zns[s]+zmom[s] for s in secs}
    rets={s:(ret_day(code[s],sd) or 0) for s in secs}; mkt=statistics.mean(rets.values())
    t3=set(sorted(secs,key=lambda s:rets[s],reverse=True)[:3])
    def top5(dd): return sorted(secs,key=lambda s:dd[s],reverse=True)[:5]
    mlow3=set(sorted(secs,key=lambda s:mom[s])[:3])  # mom20 최하위3
    attord=sorted(secs,key=lambda s:nsig[s],reverse=True)
    gate=[s for s in attord if s not in mlow3][:5]
    picks={"MOM20(가격단독)":top5(mom),"ATT_base(관심)":top5(base),"ATT_ns2(관심)":top5(nsig),
           "INTER(순수관심·감성조건)":top5(inter),"z(관심)+z(mom20)":top5(combA),
           "2·z(관심)+z(mom20)":top5(combB),"관심top5−mom20하위3제거":gate}
    for s in strats:
        p=picks[s]; pr=statistics.mean(rets[x] for x in p)
        acc[s]["raw"].append(pr); acc[s]["exc"].append(pr-mkt); acc[s]["t3"].append(len(set(p)&t3))
        if pr-mkt>0: acc[s]["win"]+=1
n=len(dates)
print("=== 관심×mom20 조합 개념검증 (섹터-ETF, forward %d일 %s~%s) ==="%(n,dates[0],dates[-1]))
print("%-26s %10s %9s %8s %8s"%("전략","평균초과%p","평균수익%","top3적중","지수이김"))
for s in strats:
    print("%-26s %+10.3f %+9.3f %8.2f %5d/%d"%(s,statistics.mean(acc[s]["exc"])*100,
        statistics.mean(acc[s]["raw"])*100,statistics.mean(acc[s]["t3"]),acc[s]["win"],n))
print("\n(초과=15섹터 등가중 평균 대비, top3적중 무작위기대 1.0. 표본 9일 극소=방향성만)")
