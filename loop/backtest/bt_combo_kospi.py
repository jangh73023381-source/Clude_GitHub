# -*- coding: utf-8 -*-
"""데일리브리핑(기술적 mom20) × 관심모멘텀 파일럿(이벤트/관심) 조합 백테스트
목표지표 = 코스피 지수(^KS11) 대비 일별 초과수익 (왕복비용 10bp 차감), KODEX200 대비 병기.
표본 = 관심신호가 forward 기록된 10거래일(2026-07-09~07-24). 룩어헤드 없음:
관심신호는 D-1 16:00~D 09:00 윈도로 사전 기록됐고, mom20은 D-1 종가까지만 사용."""
import csv,os,statistics
from collections import defaultdict
H=os.path.dirname(os.path.abspath(__file__)); COST=0.0010
px=defaultdict(dict); nm={}
for r in csv.DictReader(open(os.path.join(H,'panel_close_0724.csv'),encoding='utf-8')):
    try: px[r['code']][r['date']]=float(r['close'])
    except: pass
    nm[r['code']]=r['name']
ks={r['date']:float(r['close']) for r in csv.DictReader(open(os.path.join(H,'kospi_close.csv'),encoding='utf-8'))}
DATES=sorted(ks)
def prv(d): i=DATES.index(d); return DATES[i-1]
def ret(c,d):
    a=px.get(c,{}).get(prv(d)); b=px.get(c,{}).get(d)
    return (b/a-1.0) if (a and b) else None
def ksr(d): return ks[d]/ks[prv(d)]-1.0
def kdr(d): return ret('069500',d)

rows=list(csv.DictReader(open(os.path.join(H,'../references/attention_shadow_picks.csv'),encoding='utf-8')))
byd=defaultdict(list)
for r in rows: byd[r['date']].append(r)
SD=sorted(byd)

def is_spot(n):
    n=(n or '').replace(' ','')
    return not any(k in n for k in ['인버스','곱버스','레버리지','2X','2배','숏'])
def mom(c,d,k=20):
    i=DATES.index(d)
    if i<k: return None
    a=px.get(c,{}).get(DATES[i-k]); b=px.get(c,{}).get(d)
    return (b/a-1.0) if (a and b) else None
def ruleH(c,d):
    i=DATES.index(d)
    a=px.get(c,{}).get(DATES[i-1]); b=px.get(c,{}).get(d)
    if a and b and b/a-1>0.10: return False
    a3=px.get(c,{}).get(DATES[i-3])
    if a3 and b and b/a3-1>0.20: return False
    return True
def mom20_universe_top5(d):
    """루프 확정방법: 전체 ETF 유니버스 mom20+RuleH 상위5 (D=전일 종가 기준)"""
    p=prv(d); cand=[]
    for c in px:
        pc=px[c].get(p)
        if not pc or pc<10000 or not is_spot(nm.get(c,'')): continue
        m=mom(c,p)
        if m is None or not ruleH(c,p): continue
        cand.append((c,m))
    cand.sort(key=lambda x:-x[1])
    return [c for c,_ in cand[:5]]

def att_top5(d,key):
    return [r['code'] for r in sorted(byd[d],key=lambda r:-float(r[key]))[:5]]
def theme_mom_rank(d):
    """15개 테마ETF의 전일까지 mom20 순위(1=최고)"""
    p=prv(d); v=[]
    for r in byd[d]:
        m=mom(r['code'],p)
        v.append((r['code'], m if m is not None else -9))
    v.sort(key=lambda x:-x[1])
    return {c:i+1 for i,(c,_) in enumerate(v)}

def port(codes,d):
    rs=[ret(c,d) for c in codes]; rs=[x for x in rs if x is not None]
    return (sum(rs)/len(rs)-COST) if rs else None

# ---- 전략 정의 ----
def S_mom20(d): return mom20_universe_top5(d)
def S_att_base(d): return att_top5(d,'comp_base')
def S_att_inter(d): return att_top5(d,'comp_inter')
def S_att_search(d): return att_top5(d,'z_search')
def S_combo1(d):
    """조합1 — 관심 주도 + mom20 하방필터: 관심 상위 순으로 뽑되 테마 mom20 하위 1/3(11~15위)은 건너뜀"""
    rk=theme_mom_rank(d); out=[]
    for r in sorted(byd[d],key=lambda r:-float(r['comp_inter'])):
        if rk.get(r['code'],99)>10: continue
        out.append(r['code'])
        if len(out)==5: break
    return out
def S_combo2(d):
    """조합2 — mom20 주도 + 관심 확인: 전체 유니버스 mom20 상위 20종 중, 관심 top7 테마 ETF를 우선 채택"""
    p=prv(d); cand=[]
    for c in px:
        pc=px[c].get(p)
        if not pc or pc<10000 or not is_spot(nm.get(c,'')): continue
        m=mom(c,p)
        if m is None or not ruleH(c,p): continue
        cand.append((c,m))
    cand.sort(key=lambda x:-x[1]); cand=cand[:20]
    hot={r['code'] for r in sorted(byd[d],key=lambda r:-float(r['comp_inter']))[:7]}
    pri=[c for c,_ in cand if c in hot]; rest=[c for c,_ in cand if c not in hot]
    return (pri+rest)[:5]
def S_combo3(d):
    """조합3 — 슬롯 분리: mom20 유니버스 상위3 + 관심(INTER) 상위2(중복 제외)"""
    a=mom20_universe_top5(d)[:3]
    for c in att_top5(d,'comp_inter'):
        if c not in a: a.append(c)
        if len(a)==5: break
    return a[:5]
def S_combo4(d):
    """조합4 — z 블렌드: 테마ETF 한정, z(관심 INTER) + z(테마 mom20) 등가중"""
    p=prv(d); rs=byd[d]
    ms=[]; 
    for r in rs:
        m=mom(r['code'],p); ms.append(m if m is not None else 0.0)
    mu=sum(ms)/len(ms); sd=statistics.pstdev(ms) or 1
    cs=[float(r['comp_inter']) for r in rs]
    cu=sum(cs)/len(cs); csd=statistics.pstdev(cs) or 1
    sc=[(r['code'],(cs[i]-cu)/csd+(ms[i]-mu)/sd) for i,r in enumerate(rs)]
    sc.sort(key=lambda x:-x[1])
    return [c for c,_ in sc[:5]]
def S_sector_eq(d): return [r['code'] for r in byd[d]]

STRATS=[("① mom20 (데일리브리핑 확정방법)",S_mom20),
        ("② 관심 base",S_att_base),
        ("③ 관심 INTER(감성조건)",S_att_inter),
        ("④ 관심 검색단독",S_att_search),
        ("⑤ 조합1 관심주도+mom20 하방필터",S_combo1),
        ("⑥ 조합2 mom20주도+관심확인",S_combo2),
        ("⑦ 조합3 슬롯분리 3+2",S_combo3),
        ("⑧ 조합4 z블렌드",S_combo4),
        ("— 15섹터 등가중(기준선)",S_sector_eq)]

print("표본: %s ~ %s (%d거래일)  |  왕복비용 10bp 차감"%(SD[0],SD[-1],len(SD)))
kcum=1.0
for d in SD: kcum*= (1+ksr(d))
kd=1.0
for d in SD:
    v=kdr(d)
    if v is not None: kd*=(1+v)
print("코스피 지수 구간 누적 %+.2f%% / KODEX200 %+.2f%%\n"%((kcum-1)*100,(kd-1)*100))
print("%-32s %11s %11s %9s %9s"%("전략","코스피대비","KODEX200대비","코스피이김","누적수익"))
print("-"*80)
out={}
for lbl,fn in STRATS:
    ex=[];exk=[];cum=1.0
    for d in SD:
        pr=port(fn(d),d)
        if pr is None: continue
        ex.append(pr-ksr(d)); exk.append(pr-kdr(d)); cum*=(1+pr)
    out[lbl]=(sum(ex)/len(ex),sum(exk)/len(exk),sum(1 for x in ex if x>0),len(ex),cum-1)
    print("%-32s %+10.3f%%p %+10.3f%%p %7d/%d %+8.2f%%"%(lbl,out[lbl][0]*100,out[lbl][1]*100,out[lbl][2],out[lbl][3],(cum-1)*100))
print()
base=out["— 15섹터 등가중(기준선)"][0]
print("=== 섹터 등가중 기준선(%+.3f%%p) 대비 순수 선택력 ==="%(base*100))
for lbl,_ in STRATS[:-1]:
    print("%-32s %+.3f%%p"%(lbl,(out[lbl][0]-base)*100))

# ---------- 추가 검증: 검색 주도 조합 + 강건성 ----------
def S_combo5(d):
    """조합5 — 검색 주도 + mom20 하방필터(테마 mom20 하위 1/3 제외)"""
    rk=theme_mom_rank(d); out=[]
    for r in sorted(byd[d],key=lambda r:-float(r['z_search'])):
        if rk.get(r['code'],99)>10: continue
        out.append(r['code'])
        if len(out)==5: break
    return out
def S_combo6(d):
    """조합6 — 검색 top3 + mom20 유니버스 top2"""
    a=att_top5(d,'z_search')[:3]
    for c in mom20_universe_top5(d):
        if c not in a: a.append(c)
        if len(a)==5: break
    return a[:5]
def S_combo7(d):
    """조합7 — 검색 주도 + 뉴스감성 음(-) 테마 배제(감성을 순위가 아닌 배제필터로만 사용)"""
    out=[]
    for r in sorted(byd[d],key=lambda r:-float(r['z_search'])):
        if float(r['sent'])<-0.15: continue
        out.append(r['code'])
        if len(out)==5: break
    return out
EXTRA=[("⑨ 조합5 검색주도+mom20 하방필터",S_combo5),
       ("⑩ 조합6 검색3+mom20 2",S_combo6),
       ("⑪ 조합7 검색주도+악재감성 배제",S_combo7)]
print("\n=== 추가: 검색 주도형 조합 ===")
for lbl,fn in EXTRA:
    ex=[];exk=[];cum=1.0
    for d in SD:
        pr=port(fn(d),d); ex.append(pr-ksr(d)); exk.append(pr-kdr(d)); cum*=(1+pr)
    out[lbl]=(sum(ex)/len(ex),sum(exk)/len(exk),sum(1 for x in ex if x>0),len(ex),cum-1)
    print("%-32s %+10.3f%%p %+10.3f%%p %7d/%d %+8.2f%% | 섹터기준선대비 %+.3f%%p"%(
        lbl,out[lbl][0]*100,out[lbl][1]*100,out[lbl][2],len(ex),(cum-1)*100,(out[lbl][0]-base)*100))

print("\n=== 강건성: 일별 초과수익(코스피 대비, %p) ===")
KEY=[("① mom20",S_mom20),("④ 검색단독",S_att_search),("⑨ 조합5",S_combo5),("⑪ 조합7",S_combo7),("— 15섹터",S_sector_eq)]
print("%-10s"%"일자"+"".join("%12s"%l for l,_ in KEY))
series={l:[] for l,_ in KEY}
for d in SD:
    line="%-10s"%d
    for l,fn in KEY:
        v=(port(fn(d),d)-ksr(d))*100; series[l].append(v); line+="%+12.2f"%v
    print(line)
print("\n=== Leave-one-day-out 잭나이프(평균 초과 %p, 최악/최선 1일 제거) ===")
for l,_ in KEY:
    v=series[l]; n=len(v); m=sum(v)/n
    lo=min((sum(v)-x)/(n-1) for x in v); hi=max((sum(v)-x)/(n-1) for x in v)
    print("%-12s 평균 %+.3f | 한 날 제거 시 범위 %+.3f ~ %+.3f"%(l,m,lo,hi))
