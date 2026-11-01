import csv, json, statistics
from collections import defaultdict

SEC=['반도체','자동차','이차전지','바이오헬스','화장품']
px=json.load(open('sector_etf_ohlc.json',encoding='utf-8'))
days=sorted(px['KODEX200'].keys()); idx={d:i for i,d in enumerate(days)}
exp=defaultdict(dict)
for r in csv.DictReader(open('sector_trade_monthly.csv',encoding='utf-8')):
    if r['sector'] in SEC: exp[r['sector']][r['yyyymm']]=int(r['expDlr'])
def ym_add(ym,k):
    y=int(ym[:4]); m=int(ym[4:6]); i=y*12+(m-1)+k
    return f"{i//12}{i%12+1:02d}"
yoy={s:{m: exp[s][m]/exp[s][ym_add(m,-12)]-1 for m in exp[s] if ym_add(m,-12) in exp[s] and exp[s][ym_add(m,-12)]} for s in SEC}
def mend(ym):   # 그 달 마지막 거래일
    last=None
    for d in days:
        if d[:6]==ym: last=d
    return last
# 월간 수익률(그 달 말 종가 기준, 전월말 대비)
def mret(sec,ym):
    a=mend(ym_add(ym,-1)); b=mend(ym)
    if not a or not b: return None
    return px[sec][b]['c']/px[sec][a]['c']-1
def yret(sec,ym):  # 그 달까지 12개월 수익률
    a=mend(ym_add(ym,-12)); b=mend(ym)
    if not a or not b: return None
    return px[sec][b]['c']/px[sec][a]['c']-1
def corr(xs,ys):
    n=len(xs)
    if n<10: return float('nan')
    mx,my=statistics.mean(xs),statistics.mean(ys)
    sx=statistics.stdev(xs); sy=statistics.stdev(ys)
    if sx==0 or sy==0: return float('nan')
    return sum((a-mx)*(b-my) for a,b in zip(xs,ys))/((n-1)*sx*sy)

months=[m for m in sorted(yoy['반도체']) if m>='201904' and m<='202607']
print("="*96)
print("Q. 수출이 좋았던 섹터는 주가도 좋았는가 — 동시대(같은 기간) 관계")
print("="*96)
print("\n[1] 연도별: 섹터 수출 YoY 평균 vs 그 해 ETF 수익률(KODEX200 대비 초과)")
print(f"{'연도':<6}"+"".join(f"{s:>21}" for s in SEC))
for yr in range(2019,2027):
    row=f"{yr:<6}"
    for s in SEC:
        ms=[m for m in months if m[:4]==str(yr)]
        if not ms: row+=f"{'-':>21}"; continue
        ey=statistics.mean(yoy[s][m] for m in ms)*100
        a=mend(ms[0]); b=mend(ms[-1])
        if not a or not b: row+=f"{'-':>21}"; continue
        pr=(px[s][b]['c']/px[s][a]['c']-1)*100
        bm=(px['KODEX200'][b]['c']/px['KODEX200'][a]['c']-1)*100
        row+=f"  수출{ey:>+6.1f}% 주가{pr-bm:>+7.1f}%p"
    print(row)

print("\n[2] 동시대 상관 — 12개월 수출 YoY vs 같은 시점 12개월 주가 초과수익")
allx=[];ally=[]
for s in SEC:
    xs=[];ys=[]
    for m in months:
        r=yret(s,m); b=yret('KODEX200',m)
        if r is None or b is None: continue
        xs.append(yoy[s][m]); ys.append(r-b)
    allx+=xs; ally+=ys
    print(f"  {s:<8} 상관 {corr(xs,ys):>+6.3f}  (n={len(xs)})")
print(f"  {'전체 pooled':<8} 상관 {corr(allx,ally):>+6.3f}  (n={len(allx)})")

print("\n[3] ★ 리드-래그 — 수출 YoY(월 M) vs 주가 12개월 초과수익(월 M+k)")
print("   k<0 = 주가가 수출보다 먼저 움직임(주가 선행) / k>0 = 수출이 주가를 선행")
print(f"{'k(개월)':>8}"+"".join(f"{s:>10}" for s in SEC)+f"{'pooled':>10}")
best={}
for k in range(-12,13,2):
    row=f"{k:>+8}"; px_all=[];py_all=[]
    for s in SEC:
        xs=[];ys=[]
        for m in months:
            t=ym_add(m,k)
            if t not in yoy[s] and t<months[0]: pass
            r=yret(s,t); b=yret('KODEX200',t)
            if r is None or b is None: continue
            xs.append(yoy[s][m]); ys.append(r-b)
        c=corr(xs,ys); row+=f"{c:>+10.3f}"; px_all+=xs; py_all+=ys
        best.setdefault(s,[]).append((c,k))
    row+=f"{corr(px_all,py_all):>+10.3f}"
    print(row)
print("\n  섹터별 상관 최대 지점(k):")
for s in SEC:
    c,k=max(best[s],key=lambda x:x[0] if x[0]==x[0] else -9)
    print(f"    {s:<8} 최대상관 {c:>+6.3f} @ k={k:>+3}개월  →  {'주가가 수출을 '+str(-k)+'개월 선행' if k<0 else ('동시' if k==0 else '수출이 주가를 '+str(k)+'개월 선행')}")
