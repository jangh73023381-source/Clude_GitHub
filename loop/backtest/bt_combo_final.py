# -*- coding: utf-8 -*-
"""조합8(검색주도 + mom20 하방필터 + 악재감성 배제) 및 파라미터 민감도"""
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'bt_combo_kospi.py')).read().split('# ---- 전략 정의 ----')[0])
def is_spot2(n):
    n=(n or '').replace(' ','')
    return not any(k in n for k in ['인버스','곱버스','레버리지','2X','2배','숏'])
def mom(c,d,k=20):
    i=DATES.index(d)
    if i<k: return None
    a=px.get(c,{}).get(DATES[i-k]); b=px.get(c,{}).get(d)
    return (b/a-1.0) if (a and b) else None
def theme_mom_rank(d):
    p=prv(d); v=[]
    for r in byd[d]:
        m=mom(r['code'],p); v.append((r['code'], m if m is not None else -9))
    v.sort(key=lambda x:-x[1]); return {c:i+1 for i,(c,_) in enumerate(v)}
def port(codes,d):
    rs=[ret(c,d) for c in codes]; rs=[x for x in rs if x is not None]
    return (sum(rs)/len(rs)-COST) if rs else None
SD=sorted(byd)
def strat(d,momcut=10,sentcut=-0.15,key='z_search',n=5):
    rk=theme_mom_rank(d); out=[]
    for r in sorted(byd[d],key=lambda r:-float(r[key])):
        if momcut and rk.get(r['code'],99)>momcut: continue
        if sentcut is not None and float(r['sent'])<sentcut: continue
        out.append(r['code'])
        if len(out)==n: break
    return out
def run(**kw):
    ex=[];cum=1.0
    for d in SD:
        pr=port(strat(d,**kw),d); ex.append(pr-ksr(d)); cum*=(1+pr)
    n=len(ex); m=sum(ex)/n
    lo=min((sum(ex)-x)/(n-1) for x in ex); hi=max((sum(ex)-x)/(n-1) for x in ex)
    return m*100,sum(1 for x in ex if x>0),(cum-1)*100,lo*100,hi*100
print("코스피 구간(10일 매매) 누적 %+.2f%%\n"%((__import__('functools').reduce(lambda a,d:a*(1+ksr(d)),SD,1.0)-1)*100))
print("%-46s %9s %7s %9s %20s"%("전략","코스피대비","이김","누적","잭나이프(1일제거 범위)"))
print("-"*98)
cfgs=[("기준 ④ 검색단독(필터 없음)",dict(momcut=0,sentcut=None)),
      ("⑨ 조합5 = 검색 + mom20 하방필터(하위1/3 제외)",dict(momcut=10,sentcut=None)),
      ("⑪ 조합7 = 검색 + 악재감성 배제(sent<-0.15)",dict(momcut=0,sentcut=-0.15)),
      ("⑫ 조합8 = 검색 + mom20 하방필터 + 악재감성 배제",dict(momcut=10,sentcut=-0.15))]
for lbl,kw in cfgs:
    m,w,c,lo,hi=run(**kw); print("%-46s %+8.3f%%p %5d/10 %+8.2f%%   %+.3f ~ %+.3f"%(lbl,m,w,c,lo,hi))
print("\n=== 파라미터 민감도 (조합8) — 임계값을 흔들어도 방향이 유지되는가 ===")
print("%-30s %9s %7s %20s"%("파라미터","코스피대비","이김","잭나이프"))
for mc in [8,9,10,11,12]:
    m,w,c,lo,hi=run(momcut=mc,sentcut=-0.15); print("%-30s %+8.3f%%p %5d/10   %+.3f ~ %+.3f"%("mom20 하위컷 상위%d위까지"%mc,m,w,lo,hi))
for sc in [-0.30,-0.20,-0.15,-0.10,-0.05]:
    m,w,c,lo,hi=run(momcut=10,sentcut=sc); print("%-30s %+8.3f%%p %5d/10   %+.3f ~ %+.3f"%("감성 배제 임계 %.2f"%sc,m,w,lo,hi))
print("\n=== 픽 수 민감도 ===")
for n in [3,4,5,6,7]:
    m,w,c,lo,hi=run(momcut=10,sentcut=-0.15,n=n); print("%-30s %+8.3f%%p %5d/10   %+.3f ~ %+.3f"%("픽 %d종"%n,m,w,lo,hi))
print("\n=== 참고: 랭킹 소스를 바꾸면 (조합8 틀 유지) ===")
for k,l in [('z_search','데이터랩 검색'),('sent','뉴스감성'),('z_ytnet','유튜브전체'),('comp_base','기존 composite'),('comp_inter','INTER')]:
    m,w,c,lo,hi=run(momcut=10,sentcut=-0.15,key=k); print("%-30s %+8.3f%%p %5d/10   %+.3f ~ %+.3f"%(l,m,w,lo,hi))
