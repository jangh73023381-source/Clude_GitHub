import csv, statistics as st, math
from collections import defaultdict
exec(open("_bias_test.py",encoding="utf-8").read().split("def run(")[0])

def picks(n=20, minmc=300e8, minval=0, minpx=0, delist=-0.5):
    allsel=[]; per=[]
    for i in range(len(DTS)-1):
        d0,d1=DTS[i],DTS[i+1]; pool=[]
        for c,(cl,mc,sh,nm,val) in D[d0].items():
            if mc<minmc or val<minval or cl<minpx: continue
            f=fwd(c,d0,d1,delist)
            if f is None: continue
            pool.append((c,mc,f,nm,val,cl,d1 not in D or c not in D[d1]))
        if len(pool)<50: continue
        sel=sorted(pool,key=lambda x:x[1])[:n]
        allsel+=[(d0,d1)+s for s in sel]
        per.append((st.mean(x[2] for x in sel)-0.004, st.mean(x[2] for x in pool)))
    return allsel,per

sel,per=picks()
r=[x[4] for x in sel]
v=sorted(x[6] for x in sel); p=sorted(x[7] for x in sel)
print(f"선정 건수 {len(sel)} · 상장폐지(다음 시점 부재) {sum(1 for x in sel if x[8])}건 ({sum(1 for x in sel if x[8])/len(sel)*100:.1f}%)")
print(f"선정 종목 거래대금(원): 중앙 {v[len(v)//2]:,.0f} · p10 {v[len(v)//10]:,.0f} · p90 {v[len(v)*9//10]:,.0f}")
print(f"선정 종목 주가(원):   중앙 {p[len(p)//2]:,.0f} · p10 {p[len(p)//10]:,.0f}")
rs=sorted(r)
print(f"분기수익률: 평균 {st.mean(r)*100:+.1f}% 중앙 {st.median(r)*100:+.1f}% p10 {rs[len(rs)//10]*100:+.1f}% p90 {rs[len(rs)*9//10]*100:+.1f}% 최대 {rs[-1]*100:+.0f}%")
print("\n상위 12개 수익 (허위 수익률=유상증자 오조정 점검)")
for x in sorted(sel,key=lambda z:-z[4])[:12]:
    print(f"  {x[0]} {x[2]} {x[5][:16]:16s} 수익 {x[4]*100:+8.0f}% 종가 {x[7]:>8,} 거래대금 {x[6]:>14,}")
print("\n★ 평균 vs 중앙값 기반 포트(꼬리 의존도)")
q=[st.median([y[4] for y in sel if y[0]==d]) for d in sorted({x[0] for x in sel})]
print(f"  분기별 선정 20종 '중앙값' 수익 평균: {st.mean(q)*100:+.2f}%")
print()
print("★ 유동성·가격 필터 추가 시")
for mv,mp,lab in [(0,0,"필터 없음"),(1e8,0,"거래대금>=1억"),(5e8,0,"거래대금>=5억"),
                  (1e9,0,"거래대금>=10억"),(5e8,1000,"거래대금>=5억 & 주가>=1000원"),
                  (1e9,2000,"거래대금>=10억 & 주가>=2000원")]:
    s2,p2=picks(minval=mv,minpx=mp)
    if not p2: continue
    e=[a-b for a,b in p2]; m=st.mean(e); t=m/(st.pstdev(e)/math.sqrt(len(e))) if st.pstdev(e) else 0
    cum=1.0
    for a,b in p2: cum*=(1+a)
    print(f"  {lab:28s} 기 {len(p2)} | 초과 {m*100:+6.2f}%p t={t:+5.2f} | CAGR {(cum**(4/len(p2))-1)*100:+6.1f}%")
