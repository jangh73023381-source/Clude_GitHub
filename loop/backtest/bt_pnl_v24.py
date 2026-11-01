# -*- coding: utf-8 -*-
"""2026-07-26 루프 iteration 1 — Rule CV(커버드콜/파생오버레이 구조 디웨이팅) 검증.
1차 지표 = 일별 초과수익(픽5 동일가중 1일보유 -10bp - KODEX200 당일수익) 평균 (v2.3)
보조 지표 = 상위10% 적중 종목수 평균 (이진)
과최적화 가드: 변형 채택은 full·train·test 모두 baseline 초과일 때만."""
import csv,os,math
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
PANEL=os.path.join(HERE,'panel_close_0724.csv'); BENCH='069500'; COST=0.0010

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

def is_overlay(nm):
    """파생 인컴 오버레이(커버드콜 계열) 구조 판별 — 종목명만으로 사전 식별 가능(룩어헤드 없음)."""
    n=(nm or '').replace(' ','')
    return ('커버드콜' in n) or ('타겟위클리' in n) or ('프리미엄' in n and '콜' in n)

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

def rank_candidates(px,name,d,dates,window=20,minp=10000):
    cand=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name.get(c,'')): continue
        m=mom(px,c,d,dates,window)
        if m is None: continue
        if not rule_h_ok(px,c,d,dates): continue
        cand.append((c,m))
    cand.sort(key=lambda x:x[1],reverse=True)
    return cand

def sel_baseline(px,name,d,dates,n=5):
    return [c for c,_ in rank_candidates(px,name,d,dates,20)[:n]]

def sel_cv_exclude(px,name,d,dates,n=5):
    """CV-A: 오버레이 구조 전면 제외, 차순위 현물로 충원"""
    out=[c for c,_ in rank_candidates(px,name,d,dates,20) if not is_overlay(name.get(c,''))]
    return out[:n]

def sel_cv_cap1(px,name,d,dates,n=5):
    """CV-B: 오버레이 구조 최대 1종만 허용(완화형)"""
    out=[]; ov=0
    for c,_ in rank_candidates(px,name,d,dates,20):
        if is_overlay(name.get(c,'')):
            if ov>=1: continue
            ov+=1
        out.append(c)
        if len(out)>=n: break
    return out

def day_excess(px,picks,d,dn):
    rs=[]
    for c in picks:
        a=px[c].get(d); b=px[c].get(dn)
        if a and b: rs.append(b/a-1.0)
    port=(sum(rs)/len(rs)) if rs else 0.0
    a=px[BENCH].get(d); b=px[BENCH].get(dn); kr=(b/a-1.0) if (a and b) else 0.0
    return port-COST-kr

def day_hits(px,name,picks,d,dn,minp=10000,toppct=10.0):
    uni=[]
    for c in px:
        a=px[c].get(d); b=px[c].get(dn)
        if not a or not b or a<minp: continue
        if '숏' in (name.get(c,'') or '').replace(' ',''): continue
        uni.append((c,b/a-1.0))
    if not uni: return 0
    uni.sort(key=lambda x:x[1],reverse=True)
    cut=max(1,math.ceil(len(uni)*toppct/100.0))
    top={c for c,_ in uni[:cut]}
    return sum(1 for c in picks if c in top)

def track(px,name,dates,fn,start=20):
    xs=[];hs=[];dd=[]
    for i in range(start,len(dates)-1):
        d=dates[i]; dn=dates[i+1]
        picks=fn(px,name,d,dates)
        xs.append(day_excess(px,picks,d,dn)); hs.append(day_hits(px,name,picks,d,dn)); dd.append(d)
    return xs,hs,dd

def stats(v):
    n=len(v); h=n//2
    return sum(v)/n, sum(v[:h])/h, sum(v[h:])/(n-h), n

def main():
    px,name,dates=load()
    print("패널:%d종×%d일 %s~%s"%(len(px),len(dates),dates[0],dates[-1]))
    ov=[ (c,name[c]) for c in px if is_overlay(name.get(c,'')) and is_spot(name.get(c,'')) ]
    print("오버레이(커버드콜계열) 판별 종목: %d종 → %s\n"%(len(ov),', '.join(n for _,n in ov[:12])))
    variants=[("baseline mom20+H",sel_baseline),
              ("CV-A 오버레이 전면제외",sel_cv_exclude),
              ("CV-B 오버레이 최대1종",sel_cv_cap1)]
    res={}
    for lbl,fn in variants:
        xs,hs,dd=track(px,name,dates,fn)
        m,tr,te,n=stats(xs); hm,htr,hte,_=stats(hs)
        wi=sum(1 for x in xs if x>=0)
        res[lbl]=(m,tr,te,hm,htr,hte,wi,n,xs,hs,dd)
        print("%-22s [P&L] 평균 %+.3f%%p | train %+.3f%%p test %+.3f%%p | 지수이김 %d/%d  [이진] 평균 %.3f종 (tr %.3f/te %.3f)"%(
            lbl,m*100,tr*100,te*100,wi,n,hm,htr,hte))
    b=res["baseline mom20+H"]
    print("\n=== 과최적화 가드 (채택=1차지표 full·train·test 모두 baseline 초과) ===")
    for lbl,_ in variants[1:]:
        r=res[lbl]
        ok=(r[0]>b[0] and r[1]>b[1] and r[2]>b[2])
        print("%-22s full %s train %s test %s | 이진 full %s -> %s"%(lbl,
            "▲" if r[0]>b[0] else "▼","▲" if r[1]>b[1] else "▼","▲" if r[2]>b[2] else "▼",
            "▲" if r[3]>b[3] else "▼","**채택후보**" if ok else "기각"))
    print("\n=== 오늘(D=20260723 → 채점 20260724) in-sample 재선정 ===")
    kr=px[BENCH]['20260724']/px[BENCH]['20260723']-1
    for lbl,fn in variants:
        picks=fn(px,name,'20260723',dates)
        ex=day_excess(px,picks,'20260723','20260724'); h=day_hits(px,name,picks,'20260723','20260724')
        print("%-22s 초과 %+.3f%%p 적중 %d/5 픽 %s"%(lbl,ex*100,h,[name[c][:16] for c in picks]))
    print("KODEX200 7/24 수익: %+.2f%%"%(kr*100))
main()
