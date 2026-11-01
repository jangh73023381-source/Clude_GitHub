import csv, json, statistics
from collections import defaultdict
SEC=['반도체','자동차','이차전지','바이오헬스','화장품']
px=json.load(open('sector_etf_ohlc.json',encoding='utf-8'))
days=sorted(px['KODEX200'].keys())
exp=defaultdict(dict)
for r in csv.DictReader(open('sector_trade_monthly.csv',encoding='utf-8')):
    if r['sector'] in SEC: exp[r['sector']][r['yyyymm']]=int(r['expDlr'])
def ym_add(ym,k):
    y=int(ym[:4]); m=int(ym[4:6]); i=y*12+(m-1)+k
    return f"{i//12}{i%12+1:02d}"
yoy={s:{m: exp[s][m]/exp[s][ym_add(m,-12)]-1 for m in exp[s] if ym_add(m,-12) in exp[s] and exp[s][ym_add(m,-12)]} for s in SEC}
def mend(ym):
    last=None
    for d in days:
        if d[:6]==ym: last=d
    return last
def tstat(xs):
    n=len(xs); sd=statistics.stdev(xs)
    return statistics.mean(xs)/sd*(n**0.5) if sd else float('nan')
months=[m for m in sorted(yoy['반도체']) if m>='201905' and m<='202607']

print("="*88)
print("[4] 동시대 횡단면 — 그 달 수출 YoY 1위 섹터가 그 달 주가도 좋았는가")
print("="*88)
for lab,k in (('같은 달(동시) — 실전 불가, 데이터는 다음 달에 나옴',0),
              ('발표 다음 달(실전 가능) — 축 1이 검정한 것',1)):
    ics=[]; top=[]; bot=[]
    for m in months:
        a=mend(ym_add(m,k-1)); b=mend(ym_add(m,k))
        if not a or not b: continue
        rets={}
        for s in SEC:
            if m not in yoy[s]: continue
            rets[s]=(px[s][b]['c']/px[s][a]['c']-1)-(px['KODEX200'][b]['c']/px['KODEX200'][a]['c']-1)
        if len(rets)<5: continue
        sr={s:i for i,s in enumerate(sorted(rets,key=lambda s: yoy[s][m]))}
        rr={s:i for i,s in enumerate(sorted(rets,key=lambda s: rets[s]))}
        d2=sum((sr[s]-rr[s])**2 for s in rets); n=len(rets)
        ics.append(1-6*d2/(n*(n**2-1)))
        rk=sorted(rets,key=lambda s: yoy[s][m],reverse=True)
        top.append(rets[rk[0]]); bot.append(rets[rk[-1]])
    print(f"\n  {lab}")
    print(f"    횡단면 순위상관(IC) 평균 {statistics.mean(ics):>+6.3f}  t={tstat(ics):>5.2f}  (n={len(ics)})")
    print(f"    수출 1위 섹터 초과수익 {statistics.mean(top)*100:>+6.3f}%p t={tstat(top):>5.2f} | 꼴찌 섹터 {statistics.mean(bot)*100:>+6.3f}%p t={tstat(bot):>5.2f}")

print("\n"+"="*88)
print("[5] 반도체 — 수출 YoY 5분위별 '같은 달' 주가 vs '다음 달' 주가")
print("="*88)
vals=sorted((yoy['반도체'][m],m) for m in months if m in yoy['반도체'])
q=len(vals)//5
for i in range(5):
    grp=vals[i*q:(i+1)*q] if i<4 else vals[4*q:]
    same=[];nxt=[]
    for v,m in grp:
        a0,b0=mend(ym_add(m,-1)),mend(m)
        a1,b1=mend(m),mend(ym_add(m,1))
        if a0 and b0: same.append((px['반도체'][b0]['c']/px['반도체'][a0]['c']-1)-(px['KODEX200'][b0]['c']/px['KODEX200'][a0]['c']-1))
        if a1 and b1: nxt.append((px['반도체'][b1]['c']/px['반도체'][a1]['c']-1)-(px['KODEX200'][b1]['c']/px['KODEX200'][a1]['c']-1))
    print(f"  Q{i+1} 수출YoY {grp[0][0]*100:>+7.1f}~{grp[-1][0]*100:>+7.1f}%  같은달 {statistics.mean(same)*100:>+7.3f}%p | 다음달 {statistics.mean(nxt)*100:>+7.3f}%p")
