import csv,os,sys,math,statistics as st,random
from collections import defaultdict
exec(open("_bounce_port.py",encoding="utf-8").read().split('print("■ 포트폴리오')[0])
def port2(mode,hold_th=0.0,cost_bp=0.0):
    rows=[];carry=[];prev=[]
    for i in range(1,len(dates)-1):
        d,n=dates[i],dates[i+1]
        if d not in px[BENCH] or n not in px[BENCH]: continue
        newp=[c for c in PK.get(d,[]) if d in px[c] and n in px[c]]
        if mode=="base": sel=newp[:NPICK]
        else:
            keep=[c for c in carry if d in px[c] and n in px[c]]
            sel=keep[:NPICK]+[c for c in newp if c not in keep][:NPICK-len(keep[:NPICK])]
        if len(sel)<NPICK: sel=(sel+[c for c in newp if c not in sel])[:NPICK]
        if not sel: continue
        turn=len(set(sel)-set(prev))/len(sel) if prev else 1.0
        b=(px[BENCH][n][3]/px[BENCH][d][3]-1)*100
        rr=[(px[c][n][3]/px[c][d][3]-1)*100 for c in sel]
        net=st.mean(rr)-turn*cost_bp/100.0
        rows.append((n,net-b,net,b,turn))
        prev=sel
        if mode=="hold_down": carry=[c for c in sel if (px[c][n][3]/px[c][d][3]-1)*100<hold_th]
        elif mode=="hold_up": carry=[c for c in sel if (px[c][n][3]/px[c][d][3]-1)*100>hold_th]
        else: carry=[]
    return rows
def paired(a,b,lab):
    ma={x[0]:x[1] for x in a}; mb={x[0]:x[1] for x in b}
    ks=[k for k in ma if k in mb]
    d=[ma[k]-mb[k] for k in ks]
    m=st.mean(d); sd=st.pstdev(d); t=m/(sd/math.sqrt(len(d))) if sd else 0
    rnd=random.Random(9); bs=[]
    for _ in range(3000): bs.append(sum(rnd.choice(d) for _ in range(len(d)))/len(d))
    bs.sort()
    s=sorted(range(len(d)),key=lambda i:-d[i])
    j=[st.mean([d[i] for i in range(len(d)) if i not in s[:k]]) for k in (1,3,5,10)]
    n3=len(d)//3
    f=[st.mean(d[:n3]),st.mean(d[n3:2*n3]),st.mean(d[2*n3:])]
    print(f"{lab:30s} 차이 {m:+.4f}%p/일 t={t:+5.2f} CI[{bs[75]:+.4f},{bs[2924]:+.4f}] | 중앙 {st.median(d):+.4f} "
          f"| 승 {sum(1 for x in d if x>0)}/{len(d)} | fold3 {f[0]:+.3f}/{f[1]:+.3f}/{f[2]:+.3f} | 상위1/3/5/10일제거 {j[0]:+.4f}/{j[1]:+.4f}/{j[2]:+.4f}/{j[3]:+.4f}")
base=port2("base")
print("■ 현행 대비 '하락 픽 홀딩'의 일별 페어 차이 (7년 1,799일)")
for th,lab in [(0.0,"하락 픽 전부 홀딩"),(-0.5,"-0.5% 이하 홀딩"),(-1.0,"-1.0% 이하 홀딩"),(-1.5,"-1.5% 이하 홀딩")]:
    paired(port2("hold_down",th),base,f"  {lab}")
paired(port2("hold_up",0.0),base,"  [대조] 상승 픽 홀딩")
print()
print("■ 교체율과 비용 반영")
for lab,rows in [("현행",base),("하락 픽 홀딩",port2("hold_down"))]:
    print(f"  {lab:14s} 일평균 교체율 {st.mean(x[4] for x in rows)*100:5.1f}%")
for cb in (0,10,20,30):
    a=port2("hold_down",0.0,cb); b=port2("base",0.0,cb)
    ea=st.mean(x[1] for x in a); eb=st.mean(x[1] for x in b)
    print(f"  왕복 {cb:2d}bp: 현행 {eb:+.4f}%p/일 · 하락홀딩 {ea:+.4f}%p/일 · 차이 {ea-eb:+.4f}")
