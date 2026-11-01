import csv,os,sys,math,statistics as st,random
from collections import defaultdict
src=open("bt_pick_bounce_20260829.py",encoding="utf-8").read().split('for LVMODE,LBL in')[0]
exec(src)
A=build(True)
# 1) 하락폭 분위별 익일
dn=[r for r in A if r['r1']<0]
dn.sort(key=lambda r:r['r1'])
print("■ 보유일 하락폭 5분위별 익일 성과 (Rule LV)")
k=len(dn)//5
for i in range(5):
    seg=dn[i*k:(i+1)*k] if i<4 else dn[4*k:]
    print(f"  Q{i+1} (r1 {seg[0]['r1']:+5.2f}~{seg[-1]['r1']:+5.2f}%) n={len(seg):4d} | "
          f"익일 절대 {st.mean(x['r2'] for x in seg):+6.3f}% 중앙 {st.median([x['r2'] for x in seg]):+6.3f}% "
          f"승률 {sum(1 for x in seg if x['r2']>0)/len(seg)*100:4.1f}% | 초과 {st.mean(x['ex2'] for x in seg):+6.3f}%p")
print("\n■ 상승폭 5분위별 (대조)")
up=sorted([r for r in A if r['r1']>0],key=lambda r:r['r1'])
k=len(up)//5
for i in range(5):
    seg=up[i*k:(i+1)*k] if i<4 else up[4*k:]
    print(f"  Q{i+1} (r1 {seg[0]['r1']:+5.2f}~{seg[-1]['r1']:+5.2f}%) n={len(seg):4d} | "
          f"익일 절대 {st.mean(x['r2'] for x in seg):+6.3f}% 승률 {sum(1 for x in seg if x['r2']>0)/len(seg)*100:4.1f}% "
          f"| 초과 {st.mean(x['ex2'] for x in seg):+6.3f}%p")
# 2) 유니버스 전체 기저 — 하락한 ETF 전체의 익일
print("\n■ 대조군: 픽이 아닌 유니버스 전체 ETF (같은 기간, 같은 조건)")
uni_dn=[];uni_up=[];uni_all=[]
for i in range(len(dates)-2):
    d,n,n2=dates[i],dates[i+1],dates[i+2]
    if not all(x in px[BENCH] for x in (n,n2)): continue
    b2=(px[BENCH][n2][3]/px[BENCH][n][3]-1)*100
    for c in ELIG:
        if not all(x in px[c] for x in (d,n,n2)): continue
        r1=(px[c][n][3]/px[c][d][3]-1)*100
        r2=(px[c][n2][3]/px[c][n][3]-1)*100
        rec=(r1,r2,r2-b2,n)
        uni_all.append(rec)
        (uni_dn if r1<0 else uni_up).append(rec)
def s(v,lab):
    print(f"  {lab:26s} n={len(v):6d} | 익일 절대 {st.mean(x[1] for x in v):+6.3f}% 중앙 {st.median([x[1] for x in v]):+6.3f}% "
          f"승률 {sum(1 for x in v if x[1]>0)/len(v)*100:4.1f}% | 초과 {st.mean(x[2] for x in v):+6.3f}%p")
s(uni_all,"전체 ETF-일")
s(uni_dn,"당일 하락 ETF")
s(uni_up,"당일 상승 ETF")
# 3) 며칠 뒤까지 반등이 오나
print("\n■ 하락 픽을 더 오래 들고 갈 때 (보유일 종가 기준 누적 초과, KODEX200 대비)")
idx={d:i for i,d in enumerate(dates)}
for H in (1,2,3,5,10):
    v=[]
    for r in dn:
        i=idx[r['n']]
        if i+H>=len(dates): continue
        e=dates[i+H]
        if e not in px[r['code']] or e not in px[BENCH]: continue
        pr=(px[r['code']][e][3]/px[r['code']][r['n']][3]-1)*100
        br=(px[BENCH][e][3]/px[BENCH][r['n']][3]-1)*100
        v.append(pr-br)
    print(f"  +{H:2d}일 보유: n={len(v):4d} 초과 {st.mean(v):+6.3f}%p 중앙 {st.median(v):+6.3f}%p 승률 {sum(1 for x in v if x>0)/len(v)*100:4.1f}%")
