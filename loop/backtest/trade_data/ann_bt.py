import csv, json, statistics

SECTORS = ['반도체','자동차','이차전지','바이오헬스','화장품']
px = json.load(open('sector_etf_ohlc.json', encoding='utf-8'))
days = sorted(px['KODEX200'].keys())
idx = {d:i for i,d in enumerate(days)}

exp = {s:{} for s in SECTORS}
for row in csv.DictReader(open('sector_trade_monthly.csv', encoding='utf-8')):
    if row['sector'] in exp:
        exp[row['sector']][row['yyyymm']] = int(row['expDlr'])
def ym_add(ym,k):
    y=int(ym[:4]); m=int(ym[4:6]); i=y*12+(m-1)+k
    return f"{i//12}{i%12+1:02d}"
yoy = {s:{} for s in SECTORS}
for s in SECTORS:
    for m in exp[s]:
        p = ym_add(m,-12)
        if p in exp[s] and exp[s][p]:
            yoy[s][m] = exp[s][m]/exp[s][p]-1

def first_td(dstr):
    for d in days:
        if d >= dstr:
            return d
    return None

events = {'D01':[], 'D11':[], 'D21':[]}
y,m = 2019,4
while (y,m) <= (2026,8):
    ym = f"{y}{m:02d}"
    for tag, dd in (('D01','01'),('D11','11'),('D21','21')):
        d = first_td(f"{ym}{dd}")
        if d and idx[d] > 0 and idx[d] < len(days)-1:
            events[tag].append((ym, d))
    m += 1
    if m == 13: m, y = 1, y+1

def tstat(xs):
    n=len(xs)
    if n<2: return float('nan')
    sd = statistics.stdev(xs)
    return statistics.mean(xs)/sd*(n**0.5) if sd else float('nan')

def legs(sec, d):
    i = idx[d]; p = days[i-1]
    def r(t, kind):
        a, b = px[t][p], px[t][d]
        if kind=='A': return b['c']/a['c']-1
        if kind=='G': return b['o']/a['c']-1
        if kind=='B': return b['c']/b['o']-1
    return {k: r(sec,k)-r('KODEX200',k) for k in ('A','G','B')}

def nextday_A(sec, d):
    i = idx[d]
    if i+1 >= len(days): return None
    n = days[i+1]
    return (px[sec][n]['c']/px[sec][d]['c']-1) - (px['KODEX200'][n]['c']/px['KODEX200'][d]['c']-1)

event_days = {tag:set(d for _,d in v) for tag,v in events.items()}
all_event_days = set().union(*event_days.values())

print("="*78)
print("발표일 이벤트 검정 — 수출입 통계 발표일의 섹터 ETF 초과수익(vs KODEX200)")
print(f"2019-04~2026-08  D01 n={len(events['D01'])} / D11 n={len(events['D11'])} / D21 n={len(events['D21'])}")
print("="*78)

for tag in ('D01','D11','D21'):
    label = {'D01':'월간 확정치(익월 1일)','D11':'1~10일 잠정치(11일)','D21':'1~20일 잠정치(21일)'}[tag]
    print(f"\n### {tag} — {label}")
    for s in SECTORS:
        A=[];G=[];B=[];N1=[]
        for ym, d in events[tag]:
            L = legs(s,d); A.append(L['A']); G.append(L['G']); B.append(L['B'])
            x = nextday_A(s,d)
            if x is not None: N1.append(x)
        print(f"  {s:<7} A={statistics.mean(A)*100:>7.3f}%p t={tstat(A):>5.2f} | G={statistics.mean(G)*100:>7.3f} t={tstat(G):>5.2f} | B={statistics.mean(B)*100:>7.3f} t={tstat(B):>5.2f} | D+1={statistics.mean(N1)*100:>7.3f} t={tstat(N1):>5.2f}")

print("\n### 기준선 — 비발표일 전체")
for s in SECTORS:
    base=[]
    for i,d in enumerate(days):
        if i==0 or d in all_event_days: continue
        p=days[i-1]
        base.append((px[s][d]['c']/px[s][p]['c']-1)-(px['KODEX200'][d]['c']/px['KODEX200'][p]['c']-1))
    print(f"  {s:<7} A={statistics.mean(base)*100:>7.4f}%p t={tstat(base):>5.2f} (n={len(base)})")

print("\n" + "="*78)
print("서프라이즈 조건부 — D01에서 공개되는 '전월 수출 YoY' 중앙값 상/하 분할")
print("="*78)
for s in SECTORS:
    vals=[]
    for ym,d in events['D01']:
        rel = ym_add(ym,-1)
        if rel not in yoy[s]: continue
        vals.append((yoy[s][rel], d))
    if len(vals) < 20: continue
    med = statistics.median(v for v,_ in vals)
    hi=[];lo=[];hiG=[];loG=[];hiB=[];loB=[]
    for v,d in vals:
        L = legs(s,d)
        (hi if v>=med else lo).append(L['A'])
        (hiG if v>=med else loG).append(L['G'])
        (hiB if v>=med else loB).append(L['B'])
    print(f"  {s:<7} 고서프 A={statistics.mean(hi)*100:>7.3f}%p t={tstat(hi):>5.2f}(n={len(hi)}) | 저서프 A={statistics.mean(lo)*100:>7.3f}%p t={tstat(lo):>5.2f} | 차이={((statistics.mean(hi)-statistics.mean(lo))*100):>7.3f}%p")
    print(f"  {'':<7}   갭 G 고/저={statistics.mean(hiG)*100:>6.3f}/{statistics.mean(loG)*100:>6.3f}  집행 B 고/저={statistics.mean(hiB)*100:>6.3f}/{statistics.mean(loB)*100:>6.3f}")

print("\n" + "="*78)
print("사전 가설(기각로그 2026-07-23 지목): 반도체 — 발표일 3종 합산")
print("="*78)
allev = sorted(set(d for tag in events for _,d in events[tag]))
A=[];G=[];B=[]
for d in allev:
    L=legs('반도체',d); A.append(L['A']); G.append(L['G']); B.append(L['B'])
n=len(A)
print(f"n={n}  A={statistics.mean(A)*100:.3f}%p t={tstat(A):.2f} | G={statistics.mean(G)*100:.3f}%p t={tstat(G):.2f} | B={statistics.mean(B)*100:.3f}%p t={tstat(B):.2f}")
if statistics.mean(A)!=0:
    print(f"  A 중 갭 비중 {statistics.mean(G)/statistics.mean(A)*100:.1f}%")
half=n//2
print(f"  train(n={half}) A={statistics.mean(A[:half])*100:.3f}%p t={tstat(A[:half]):.2f} | test(n={n-half}) A={statistics.mean(A[half:])*100:.3f}%p t={tstat(A[half:]):.2f}")
srt=sorted(A,reverse=True)
print(f"  꼬리: 상위3일 기여 {sum(srt[:3])/sum(A)*100:.1f}% / 제거시 평균={statistics.mean(srt[3:])*100:.3f}%p t={tstat(srt[3:]):.2f}")
print(f"  중앙값={statistics.median(A)*100:.3f}%p 승률={sum(1 for x in A if x>0)/n*100:.1f}%")
