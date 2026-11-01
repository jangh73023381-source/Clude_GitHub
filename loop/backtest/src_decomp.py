# -*- coding: utf-8 -*-
"""정보 소스별 예측력 분해 — 뉴스감성(sent)·데이터랩검색(z_search)·유튜브전체(z_ytnet)·상위20채널(z_yt20)
지표: (1) rank-IC(당일 컴포넌트 z ↔ 당일 섹터ETF 수익률), (2) 단독 top5 픽의 코스피 대비 초과수익,
      (3) 커버리지(비영값 비율)."""
import csv,os,statistics
from collections import defaultdict
H=os.path.dirname(os.path.abspath(__file__))
px=defaultdict(dict)
for r in csv.DictReader(open(os.path.join(H,'panel_close_0724.csv'),encoding='utf-8')):
    try: px[r['code']][r['date']]=float(r['close'])
    except: pass
ks={r['date']:float(r['close']) for r in csv.DictReader(open(os.path.join(H,'kospi_close.csv'),encoding='utf-8'))}
dates=sorted(ks)
def prev(d):
    i=dates.index(d); return dates[i-1] if i>0 else None
def ret(code,d):
    p=prev(d)
    a=px.get(code,{}).get(p); b=px.get(code,{}).get(d)
    return (b/a-1.0) if (a and b) else None
def ksret(d):
    p=prev(d); return ks[d]/ks[p]-1.0

rows=list(csv.DictReader(open(os.path.join(H,'../references/attention_shadow_picks.csv'),encoding='utf-8')))
byd=defaultdict(list)
for r in rows: byd[r['date']].append(r)
COMPS=[('sent','뉴스 감성'),('z_search','데이터랩 검색'),('z_ytnet','유튜브 전체'),('z_yt20','유튜브 상위20채널')]

def spearman(a,b):
    def rk(v):
        idx=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for pos,i in enumerate(idx): r[i]=pos+1
        return r
    ra,rb=rk(a),rk(b); n=len(a)
    ma=sum(ra)/n; mb=sum(rb)/n
    num=sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    da=(sum((x-ma)**2 for x in ra))**.5; db=(sum((x-mb)**2 for x in rb))**.5
    return num/(da*db) if da and db else 0.0

print("표본: %d거래일 × 15섹터 = %d 섹터-일\n"%(len(byd),len(rows)))
print("%-20s %8s %8s %10s %10s %10s"%("소스","커버리지","평균 IC","IC>0 일수","top5 초과(코스피)","지수이김"))
print("-"*76)
summary={}
for key,label in COMPS:
    ics=[];exs=[];cov=0;tot=0
    for d in sorted(byd):
        rs=byd[d]
        vals=[];rets=[]
        for r in rs:
            v=float(r[key]); rr=ret(r['code'],d)
            tot+=1
            if abs(v)>1e-9: cov+=1
            if rr is not None: vals.append(v); rets.append(rr)
        if len(vals)>=8: ics.append(spearman(vals,rets))
        top=sorted(rs,key=lambda r:-float(r[key]))[:5]
        pr=[ret(r['code'],d) for r in top]; pr=[x for x in pr if x is not None]
        if pr: exs.append(sum(pr)/len(pr)-ksret(d))
    mic=sum(ics)/len(ics); mex=sum(exs)/len(exs)
    summary[key]=(mic,mex,sum(1 for x in exs if x>0),len(exs),cov/tot)
    print("%-20s %7.0f%% %+8.3f %6d/%d %+13.3f%%p %8d/%d"%(label,cov/tot*100,mic,sum(1 for x in ics if x>0),len(ics),mex*100,sum(1 for x in exs if x>0),len(exs)))
print()
# 조합 컴포짓들
print("=== 참고: 무작위/등가중 기준선 ===")
allex=[]
for d in sorted(byd):
    pr=[ret(r['code'],d) for r in byd[d]]; pr=[x for x in pr if x is not None]
    allex.append(sum(pr)/len(pr)-ksret(d))
print("15섹터 등가중(무작위 기대) 초과: %+.3f%%p, 지수이김 %d/%d"%(sum(allex)/len(allex)*100,sum(1 for x in allex if x>0),len(allex)))
