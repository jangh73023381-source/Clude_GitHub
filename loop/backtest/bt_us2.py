import sys; sys.path.insert(0,'/sessions/exciting-sharp-albattani/mnt/loop/backtest')
from bt_engine import load, score, is_spot
import csv, statistics as st
px,name,dates=load()
us={}
rows=list(csv.DictReader(open('us_sox.csv')))
for i in range(1,len(rows)):
    us[rows[i]['date']]={'sox':float(rows[i]['sox'])/float(rows[i-1]['sox'])-1}
usd=sorted(us)
def us_overnight(scoreday):  # scoreday(D+1)를 구동하는 실제 오버나잇 = scoreday 직전 최신 미국일 (장전 선정시 가용)
    c=[d for d in usd if d<scoreday]; return us[c[-1]]['sox'] if c else 0.0
def ret(c,d,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d); return (b/a-1.0) if (a and b) else None
SEMI=('반도체','AI','HBM','반도','테크','전공정','소부장','메모리')
def sel(d,dn,strat,n=5):
    sox=us_overnight(dn)
    s=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<10000 or not is_spot(name[c]): continue
        m=ret(c,d,20)
        if m is None: continue
        key=m
        semi=any(k in name[c] for k in SEMI)
        if strat=='morn_semitilt' and sox>0.015 and semi: key=m+1.0
        if strat=='morn_semitilt_both':
            if sox>0.015 and semi: key=m+1.0
            elif sox<-0.02 and semi: key=m-1.0
        s.append((c,key))
    s.sort(key=lambda x:x[1],reverse=True); return [c for c,_ in s[:n]]
def run(strat,lo,hi):
    H=[]
    for i in range(20,len(dates)-1):
        if i<lo or i>=hi: continue
        d,dn=dates[i],dates[i+1]
        p=sel(d,dn,strat)
        if len(p)<5: continue
        sc=score(px,name,d,dn,p)
        if sc and sc['hit'] is not None: H.append(sc['hit'])
    return st.mean(H) if H else 0
# 진단: 익일 한국ETF평균 vs 그날 구동 오버나잇(장전 가용)
xs=[];ys=[]
for i in range(20,len(dates)-1):
    d,dn=dates[i],dates[i+1]
    rr=[px[c][dn]/px[c][d]-1 for c in px if px[c].get(d) and px[c].get(dn) and px[c][d]>=10000]
    if rr: xs.append(us_overnight(dn)); ys.append(st.mean(rr))
def corr(a,b):
    n=len(a);ma=sum(a)/n;mb=sum(b)/n
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/((sum((x-ma)**2 for x in a)**0.5)*(sum((y-mb)**2 for y in b)**0.5))
n=len(dates)
print(f"진단(장전 타이밍): 한국ETF 익일평균 vs 그날 구동 美SOX 오버나잇 상관 = {corr(xs,ys):+.2f} (n={len(xs)})")
print(f"mom20 baseline 전체적중 = {run('mom20',20,n-1):.2f}")
print(f"morn_semitilt(美강세시 반도체우선) = {run('morn_semitilt',20,n-1):.2f}")
print(f"morn_semitilt_both(강세우선/약세후순위) = {run('morn_semitilt_both',20,n-1):.2f}")
