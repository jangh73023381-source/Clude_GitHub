import csv,os,sys,math,statistics as st,random
from collections import defaultdict
src=open("bt_pick_bounce_20260829.py",encoding="utf-8").read().split('for LVMODE,LBL in')[0]
exec(src)
idx={d:i for i,d in enumerate(dates)}
PK={d:picks(d,True) for d in dates}
def port(mode,hold_th=0.0):
    """일별 포트 수익(동일가중)과 KODEX200 대비 초과. mode: base | hold_down | hold_up"""
    rows=[]; carry=[]   # carry: 전일 보유 중 유지할 종목
    for i in range(1,len(dates)-1):
        d,n=dates[i],dates[i+1]     # d=선정일, n=보유일
        if d not in px[BENCH] or n not in px[BENCH]: continue
        newp=[c for c in PK.get(d,[]) if d in px[c] and n in px[c]]
        if mode=="base": sel=newp[:NPICK]
        else:
            keep=[c for c in carry if d in px[c] and n in px[c]]
            sel=keep[:NPICK]+[c for c in newp if c not in keep][:NPICK-len(keep[:NPICK])]
        if len(sel)<NPICK: sel=(sel+newp)[:NPICK]
        if not sel: continue
        b=(px[BENCH][n][3]/px[BENCH][d][3]-1)*100
        rr=[(px[c][n][3]/px[c][d][3]-1)*100 for c in sel]
        rows.append((n,st.mean(rr)-b,st.mean(rr),b))
        # 다음 회차로 넘길 종목 결정 (보유일 n 종가 시점에 판정 — 룩어헤드 없음)
        if mode=="hold_down":
            carry=[c for c in sel if (px[c][n][3]/px[c][d][3]-1)*100 < hold_th]
        elif mode=="hold_up":
            carry=[c for c in sel if (px[c][n][3]/px[c][d][3]-1)*100 > hold_th]
        else: carry=[]
    return rows
def rep(rows,lab):
    e=[x[1] for x in rows]; m=st.mean(e)
    byd=defaultdict(list)
    for x in rows: byd[x[0]].append(x[1])
    dm=[st.mean(v) for v in byd.values()]
    rnd=random.Random(3); bs=[]
    for _ in range(1500): bs.append(sum(rnd.choice(dm) for _ in range(len(dm)))/len(dm))
    bs.sort()
    cum=1.0; eq=[]
    for x in rows: cum*=(1+x[2]/100); eq.append(cum)
    pk=-1e9; mdd=0
    for v in eq: pk=max(pk,v); mdd=min(mdd,v/pk-1)
    n3=len(e)//3
    f=[st.mean(e[:n3]),st.mean(e[n3:2*n3]),st.mean(e[2*n3:])]
    s=sorted(range(len(e)),key=lambda i:-e[i])
    j3=st.mean([e[i] for i in range(len(e)) if i not in s[:3]])
    print(f"{lab:26s} 일 {len(e)} | 초과 {m:+.4f}%p/일 [{bs[37]:+.4f},{bs[1462]:+.4f}] | 중앙 {st.median(e):+.4f} "
          f"| 누적 {(cum-1)*100:+7.1f}% | MDD {mdd*100:6.1f}% | fold3 {f[0]:+.3f}/{f[1]:+.3f}/{f[2]:+.3f} | 상위3일제거 {j3:+.4f}")
print("■ 포트폴리오 비교 (Rule LV, 7년 1,798일, 동일가중, 무비용)")
base=port("base"); rep(base,"  현행(매일 새 픽)")
rep(port("hold_down"),"  하락 픽 하루 더 홀딩")
rep(port("hold_down",hold_th=-0.5),"  -0.5% 이하만 홀딩")
rep(port("hold_down",hold_th=-1.5),"  -1.5% 이하만 홀딩")
rep(port("hold_up"),"  [대조] 상승 픽 홀딩")
# KODEX200
b=[(x[0],0.0,x[3],x[3]) for x in base]
cum=1.0
for x in base: cum*=(1+x[3]/100)
print(f"  {'KODEX200':26s} 누적 {(cum-1)*100:+.1f}%")
