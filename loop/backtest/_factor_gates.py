import csv, math, random, statistics as st
from collections import defaultdict, Counter
src=open("bt_factor_pit_20260829.py",encoding="utf-8").read().split('print("="*140)')[0]
exec(src)
def stats(per):
    e=[a-b for _,a,b in per]; m=st.mean(e)
    t=m/(st.pstdev(e)/math.sqrt(len(e))) if st.pstdev(e) else 0
    return m,t,len(e)
def fold3(per):
    n=len(per)//3; out=[]
    for i in range(3):
        seg=per[i*n:(i+1)*n] if i<2 else per[2*n:]
        out.append(stats(seg)[0]*100)
    return out
print("관문 검정 (PIT · 거래대금>=5억 · 주가>=1000원)")
print(f"{'팩터':22s} {'평균초과':>9s} {'t':>6s} | {'중앙값기반':>10s} {'t':>6s} | fold3")
for nm in ["저PSR","저PBR","매출성장","고영업이익/자산","영업이익성장","저PER"]:
    p,_=run(single(nm)); m,t,n=stats(p)
    pm,_=run(single(nm),med=True); m2,t2,_=stats(pm)
    f=fold3(p)
    print(f"{nm:22s} {m*100:+8.2f}%p {t:+6.2f} | {m2*100:+9.2f}%p {t2:+6.2f} | {f[0]:+6.2f} {f[1]:+6.2f} {f[2]:+6.2f}")
print()
print("정의 교체 — 저PSR 계열")
p,_=run(combo(["저PSR","저PBR"])); m,t,n=stats(p); print(f"  저PSR+저PBR 순위합      {m*100:+6.2f}%p t={t:+5.2f}")
p,_=run(single("저PSR"),minmc=1000e8); m,t,n=stats(p); print(f"  저PSR 시총>=1000억      {m*100:+6.2f}%p t={t:+5.2f}")
p,_=run(single("저PSR"),delist=-1.0); m,t,n=stats(p); print(f"  저PSR 상폐 -100%        {m*100:+6.2f}%p t={t:+5.2f}")
print()
print("저PSR 포트폴리오 구성 점검 — 자주 뽑힌 종목")
_,picks=run(single("저PSR"))
c=Counter(x[1]["nm"] for x in picks)
print("  ",", ".join(f"{k}({v})" for k,v in c.most_common(18)))
print(f"  선정 연인원 {len(picks)} · 고유종목 {len(c)}")
psr=[x[1]["mc"]/x[1]["sa"] for x in picks if x[1]["sa"]]
print(f"  선정 종목 PSR 중앙 {st.median(psr):.3f} (시총이 연매출의 {st.median(psr)*100:.0f}%)")
mg=[x[1]["op"]/x[1]["sa"] for x in picks if x[1]["sa"] and x[1]["op"] is not None]
print(f"  선정 종목 영업이익률 중앙 {st.median(mg)*100:+.1f}%")
r=sorted(x[1]["fwd"] for x in picks)
print(f"  분기수익률 평균 {st.mean(r)*100:+.1f}% 중앙 {st.median(r)*100:+.1f}% p90 {r[len(r)*9//10]*100:+.1f}% 최대 {r[-1]*100:+.0f}%")
top=sorted(picks,key=lambda x:-x[1]["fwd"])[:5]
print("  최대 기여:", ", ".join(f"{x[1]['nm']} {x[1]['fwd']*100:+.0f}%" for x in top))
# 상위 5% 제거 시
cut=int(len(picks)*0.05)
trimmed=sorted(picks,key=lambda x:-x[1]["fwd"])[cut:]
byd=defaultdict(list)
for d,x in trimmed: byd[d].append(x["fwd"])
print(f"  상위 5% 수익 제거 후 평균 분기수익 {st.mean([st.mean(v) for v in byd.values()])*100:+.2f}%")
