# -*- coding: utf-8 -*-
"""v2.3 P&L 1차지표 백테스트 — baseline vs 신규 distinct 변형.
지표 = 일별 초과수익(픽5 동일가중 1일보유 -10bp - KODEX200 당일수익)의 평균.
과최적화 가드: 변형 채택은 full·train·test 모두 baseline 초과일 때만."""
import csv,os
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
PANEL=os.path.join(HERE,'panel_close_0723.csv'); BENCH='069500'; COST=0.0010
def load():
    px=defaultdict(dict); name={}
    for r in csv.DictReader(open(PANEL,encoding='utf-8')):
        try: px[r['code']][r['date']]=float(r['close'])
        except: pass
        name[r['code']]=r['name']
    dates=sorted({d for c in px for d in px[c]})
    return px,name,dates
def is_spot(nm):
    n=(nm or '').replace(' ','')
    return not('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n or '숏' in n)
def mom(px,c,d,dates,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None
def rule_h_ok(px,c,d,dates):
    s=mom(px,c,d,dates,1); c3=mom(px,c,d,dates,3)
    if s is not None and s>0.10: return False
    if c3 is not None and c3>0.20: return False
    return True
def sel(px,name,d,dates,window=20,n=5,minp=10000):
    cand=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name.get(c,'')): continue
        m=mom(px,c,d,dates,window)
        if m is None: continue
        if not rule_h_ok(px,c,d,dates): continue
        cand.append((c,m))
    cand.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in cand[:n]]
def sel_baseline(px,name,d,dates): return sel(px,name,d,dates,20)
def sel_mom5(px,name,d,dates): return sel(px,name,d,dates,5)
def sel_updetilt(px,name,d,dates):
    # 강세장 감지: KODEX200 당일(D-1->D) 수익 > +2%면 mom5, else mom20
    i=dates.index(d)
    if i>=1:
        a=px[BENCH].get(dates[i-1]); b=px[BENCH].get(d)
        if a and b and (b/a-1.0)>0.02:
            return sel(px,name,d,dates,5)
    return sel(px,name,d,dates,20)
def sel_blend(px,name,d,dates):
    # mom20 top3 유지 + mom5 상위 중 미중복 2종 추가
    b20=sel(px,name,d,dates,20,n=5)
    b5=sel(px,name,d,dates,5,n=10)
    out=b20[:3]
    for c in b5:
        if c not in out: out.append(c)
        if len(out)>=5: break
    return out[:5]
def day_excess(px,picks,d,dnext):
    rs=[]
    for c in picks:
        a=px[c].get(d); b=px[c].get(dnext)
        if a and b: rs.append(b/a-1.0)
    port=(sum(rs)/len(rs)) if rs else 0.0
    a=px[BENCH].get(d); b=px[BENCH].get(dnext); kr=(b/a-1.0) if (a and b) else 0.0
    return port-COST-kr
def track(px,name,dates,selfn):
    start=20; xs=[]; ddays=[]
    i=start
    while i+1<len(dates):
        d=dates[i]; dn=dates[i+1]
        picks=selfn(px,name,d,dates)
        xs.append(day_excess(px,picks,d,dn)); ddays.append(d)
        i+=1
    return xs,ddays
def stats(xs):
    n=len(xs); mean=sum(xs)/n
    half=n//2
    tr=sum(xs[:half])/half; te=sum(xs[half:])/(n-half)
    winidx=sum(1 for x in xs if x>=0)
    return mean,tr,te,winidx,n
def main():
    px,name,dates=load()
    print("패널:%d종×%d일 %s~%s\n"%(len(px),len(dates),dates[0],dates[-1]))
    variants=[("baseline mom20+H",sel_baseline),("V1 mom5+H",sel_mom5),
              ("V2 up>+2%→mom5",sel_updetilt),("V3 blend mom20x3+mom5x2",sel_blend)]
    res={}
    for lbl,fn in variants:
        xs,dd=track(px,name,dates,fn)
        m,tr,te,wi,n=stats(xs)
        res[lbl]=(m,tr,te,wi,n,xs,dd)
        print("%-26s 평균초과 %+.3f%%p | train %+.3f%%p test %+.3f%%p | 지수이김 %d/%d(%.0f%%)"%(
            lbl,m*100,tr*100,te*100,wi,n,wi/n*100))
    bm,btr,bte,_,_,_,_=res["baseline mom20+H"][:7]
    print("\n=== 과최적화 가드 판정 (변형 채택=full·train·test 모두 baseline 초과) ===")
    for lbl,_ in variants[1:]:
        m,tr,te=res[lbl][0],res[lbl][1],res[lbl][2]
        ok=(m>bm and tr>btr and te>bte)
        print("%-26s full %s train %s test %s -> %s"%(lbl,
            "▲" if m>bm else "▼","▲" if tr>btr else "▼","▲" if te>bte else "▼",
            "채택후보" if ok else "기각"))
    # 7/22 결정일(→7/23 채점) 각 변형 재선정 결과 (오늘 in-sample)
    d="20260722"
    print("\n=== 오늘(D=7/22→7/23) in-sample 재선정 ===")
    kr=px[BENCH]['20260723']/px[BENCH]['20260722']-1
    for lbl,fn in variants:
        picks=fn(px,name,d,dates)
        ex=day_excess(px,picks,"20260722","20260723")
        print("%-26s 초과 %+.3f%%p 픽 %s"%(lbl,ex*100,picks))
    print("KODEX200 7/23 수익: %+.2f%%"%(kr*100))
main()
