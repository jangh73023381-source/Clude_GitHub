import csv, json, statistics, random

SECTORS = ['반도체','자동차','이차전지','바이오헬스','화장품']
px = json.load(open('sector_etf_ohlc.json', encoding='utf-8'))
days = sorted(px['KODEX200'].keys()); idx = {d:i for i,d in enumerate(days)}

exp = {s:{} for s in SECTORS}
for row in csv.DictReader(open('sector_trade_monthly.csv', encoding='utf-8')):
    if row['sector'] in exp: exp[row['sector']][row['yyyymm']] = int(row['expDlr'])
def ym_add(ym,k):
    y=int(ym[:4]); m=int(ym[4:6]); i=y*12+(m-1)+k
    return f"{i//12}{i%12+1:02d}"
yoy = {s:{} for s in SECTORS}
for s in SECTORS:
    for m in exp[s]:
        p = ym_add(m,-12)
        if p in exp[s] and exp[s][p]: yoy[s][m] = exp[s][m]/exp[s][p]-1

def first_td(dstr):
    for d in days:
        if d >= dstr: return d
    return None
def tstat(xs):
    n=len(xs)
    if n<2: return float('nan')
    sd=statistics.stdev(xs)
    return statistics.mean(xs)/sd*(n**0.5) if sd else float('nan')
def legs(sec,d):
    i=idx[d]; p=days[i-1]
    def r(t,k):
        a,b = px[t][p], px[t][d]
        return b['c']/a['c']-1 if k=='A' else (b['o']/a['c']-1 if k=='G' else b['c']/b['o']-1)
    return {k: r(sec,k)-r('KODEX200',k) for k in ('A','G','B')}
def mom20(sec,d):
    i=idx[d]
    if i<21: return None
    return (px[sec][days[i-1]]['c']/px[sec][days[i-21]]['c']-1) - (px['KODEX200'][days[i-1]]['c']/px['KODEX200'][days[i-21]]['c']-1)

# D01 이벤트: 매월 1일 이후 첫 거래일. 그날 발표되는 값 = 전월 수출 YoY
ev=[]
y,m=2019,4
while (y,m)<=(2026,8):
    ym=f"{y}{m:02d}"; d=first_td(f"{ym}01")
    if d and idx[d]>0: ev.append((ym,d))
    m+=1
    if m==13: m,y=1,y+1

print("="*78)
print("정밀검정 — D01 발표일 × 수출 서프라이즈 (룩어헤드 제거: expanding median)")
print("="*78)

# expanding median: 그 시점 이전에 발표된 값들만으로 임계 산출 (최소 24개월 확보 후 시작)
rows=[]   # (ym, d, sector, sig_high, A, G, B, mom)
for ym,d in ev:
    rel=ym_add(ym,-1)
    for s in SECTORS:
        if rel not in yoy[s]: continue
        hist=[yoy[s][k] for k in sorted(yoy[s]) if k < rel]   # 발표 이전 월들만
        if len(hist)<24: continue
        med=statistics.median(hist)
        L=legs(s,d); mo=mom20(s,d)
        rows.append((ym,d,s,yoy[s][rel]>=med,L['A'],L['G'],L['B'],mo))

months=sorted(set(r[0] for r in rows))
print(f"관측 {len(rows)}건 / {len(months)}개월 ({months[0]}~{months[-1]}), 섹터당 최대 {len(months)}건")

for key,ki in (('A',4),('G',5),('B',6)):
    hi=[r[ki] for r in rows if r[3]]; lo=[r[ki] for r in rows if not r[3]]
    print(f"  {key}: 고서프 {statistics.mean(hi)*100:>7.3f}%p (n={len(hi)}) | 저서프 {statistics.mean(lo)*100:>7.3f}%p (n={len(lo)}) | 차이 {(statistics.mean(hi)-statistics.mean(lo))*100:>7.3f}%p")

# 월 단위 클러스터: 각 발표일에서 (고서프 평균 - 저서프 평균) 시계열
print("\n### 월 단위 스프레드(고서프 - 저서프), 같은 날 상관 제거")
for key,ki in (('A',4),('G',5),('B',6)):
    spread=[]
    for ym in months:
        h=[r[ki] for r in rows if r[0]==ym and r[3]]
        l=[r[ki] for r in rows if r[0]==ym and not r[3]]
        if h and l: spread.append(statistics.mean(h)-statistics.mean(l))
    print(f"  {key}: 평균 {statistics.mean(spread)*100:>7.3f}%p  t={tstat(spread):>5.2f}  n={len(spread)}  승률={sum(1 for x in spread if x>0)/len(spread)*100:.1f}%  중앙값={statistics.median(spread)*100:>6.3f}%p")
    if key=='B':
        half=len(spread)//2
        print(f"     train(n={half}) {statistics.mean(spread[:half])*100:.3f}%p t={tstat(spread[:half]):.2f} | test(n={len(spread)-half}) {statistics.mean(spread[half:])*100:.3f}%p t={tstat(spread[half:]):.2f}")
        srt=sorted(spread,reverse=True)
        print(f"     꼬리: 상위3 기여 {sum(srt[:3])/sum(spread)*100:.1f}% / 제거시 {statistics.mean(srt[3:])*100:.3f}%p t={tstat(srt[3:]):.2f}")

# 섹터 잭나이프 (B 기준)
print("\n### 섹터 잭나이프 (B, 월단위 스프레드)")
for excl in SECTORS:
    sub=[r for r in rows if r[2]!=excl]
    sp=[]
    for ym in months:
        h=[r[6] for r in sub if r[0]==ym and r[3]]; l=[r[6] for r in sub if r[0]==ym and not r[3]]
        if h and l: sp.append(statistics.mean(h)-statistics.mean(l))
    print(f"  -{excl:<7} {statistics.mean(sp)*100:>7.3f}%p t={tstat(sp):>5.2f} (n={len(sp)})")

# 섹터별 B
print("\n### 섹터별 B(집행구간) 고/저 서프라이즈")
for s in SECTORS:
    h=[r[6] for r in rows if r[2]==s and r[3]]; l=[r[6] for r in rows if r[2]==s and not r[3]]
    if h and l:
        print(f"  {s:<7} 고={statistics.mean(h)*100:>7.3f}%p t={tstat(h):>5.2f}(n={len(h)}) | 저={statistics.mean(l)*100:>7.3f}%p t={tstat(l):>5.2f}(n={len(l)}) | 차이={(statistics.mean(h)-statistics.mean(l))*100:>7.3f}%p")

# mom20 중립화: 모멘텀 2분할 내에서 고/저 서프 스프레드
print("\n### mom20 중립화 (모멘텀 상/하 각 그룹 내부에서 재계산, B 기준)")
valid=[r for r in rows if r[7] is not None]
mmed=statistics.median(r[7] for r in valid)
for grp,cond in (('mom상위',lambda r:r[7]>=mmed),('mom하위',lambda r:r[7]<mmed)):
    sub=[r for r in valid if cond(r)]
    h=[r[6] for r in sub if r[3]]; l=[r[6] for r in sub if not r[3]]
    print(f"  {grp}: 고={statistics.mean(h)*100:>7.3f}%p(n={len(h)}) 저={statistics.mean(l)*100:>7.3f}%p(n={len(l)}) 차이={(statistics.mean(h)-statistics.mean(l))*100:>7.3f}%p t차이추정={tstat(h)-tstat(l):>5.2f}")

# 플라시보: 서프라이즈 라벨을 섹터간 셔플
random.seed(7)
obs_sp=[]
for ym in months:
    h=[r[6] for r in rows if r[0]==ym and r[3]]; l=[r[6] for r in rows if r[0]==ym and not r[3]]
    if h and l: obs_sp.append(statistics.mean(h)-statistics.mean(l))
obs=statistics.mean(obs_sp)
pl=[]
for _ in range(1000):
    sp=[]
    for ym in months:
        grp=[r for r in rows if r[0]==ym]
        labs=[r[3] for r in grp]; random.shuffle(labs)
        h=[g[6] for g,lb in zip(grp,labs) if lb]; l=[g[6] for g,lb in zip(grp,labs) if not lb]
        if h and l: sp.append(statistics.mean(h)-statistics.mean(l))
    pl.append(statistics.mean(sp))
p=sum(1 for x in pl if x>=obs)/len(pl)
print(f"\n### 플라시보(라벨 셔플 1000회, B): 셔플평균 {statistics.mean(pl)*100:.3f}%p sd={statistics.stdev(pl)*100:.3f} | 관측 {obs*100:.3f}%p | p={p:.3f}")

# 실전형: 매월 발표일 고서프 섹터만 시가매수-종가매도 (동일가중), vs 5섹터 전체 동일 매매
print("\n### 실전형 — 발표일 시가매수→종가매도(당일청산), 고서프 섹터만 vs 전체")
sel=[];allx=[]
for ym in months:
    grp=[r for r in rows if r[0]==ym]
    h=[r[6] for r in grp if r[3]]
    if h: sel.append(statistics.mean(h))
    allx.append(statistics.mean([r[6] for r in grp]))
print(f"  고서프만: 평균 {statistics.mean(sel)*100:.3f}%p/회 t={tstat(sel):.2f} 승률={sum(1 for x in sel if x>0)/len(sel)*100:.1f}% (n={len(sel)})")
print(f"  전체5종 : 평균 {statistics.mean(allx)*100:.3f}%p/회 t={tstat(allx):.2f}")
cum=1.0
for x in sel: cum*=(1+x)
print(f"  고서프만 누적(발표일 당일만 보유, {len(sel)}회): {(cum-1)*100:.1f}%p 상당")
