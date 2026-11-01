import csv, statistics, random
from collections import defaultdict

# ---------- HS chapter/heading -> KSIC 2자리 업종 매핑 ----------
MAP = {
 '10':['16','17','18','19','20','21'],          # 식료품
 '11':['22'],                                    # 음료
 '13':['50','51','52','53','54','55','56','57','58','59','60'],  # 섬유
 '14':['61','62','63'],                          # 의복
 '15':['41','42','43','64'],                     # 가죽·신발
 '16':['44'],                                    # 목재
 '17':['47','48'],                               # 펄프·종이
 '19':['27'],                                    # 석유정제
 '20':['28','29','32','33','34','35','38'],      # 화학(화장품 3304 포함)
 '21':['30'],                                    # 의약품
 '22':['39','40'],                               # 고무·플라스틱
 '23':['68','69','70'],                          # 비금속광물
 '24':['72','73','74','75','76','78','79','80','81'],  # 1차금속
 '25':['82','83'],                               # 금속가공
 '26':['8471','8473','8517','8518','8523','8525','8526','8527','8528','8529','8531','8532','8533','8534','8535','8536','8537','8538','8539','8540','8541','8542','8548'],  # 전자부품·컴퓨터·통신
 '27':['90','91'],                               # 의료·정밀·광학
 '28':['8501','8502','8503','8504','8505','8506','8507','8508','8509','8510','8511','8512','8513','8514','8515','8516','8543','8544','8545','8546','8547'],  # 전기장비
 '29':['8401','8402','8403','8404','8405','8406','8407','8408','8409','8410','8411','8412','8413','8414','8415','8416','8417','8418','8419','8420','8421','8422','8423','8424','8425','8426','8427','8428','8429','8430','8431','8432','8433','8434','8435','8436','8437','8438','8439','8440','8441','8442','8443','8444','8445','8446','8447','8448','8449','8450','8451','8452','8453','8454','8455','8456','8457','8458','8459','8460','8461','8462','8463','8464','8465','8466','8467','8468','8469','8470','8472','8474','8475','8476','8477','8478','8479','8480','8481','8482','8483','8484','8485','8486','8487'],  # 기타기계
 '30':['8701','8702','8703','8704','8705','8706','8707','8708'],  # 자동차
 '31':['86','88','89'],                          # 기타운송장비(조선·항공)
 '32':['94'],                                    # 가구
}
# ---------- 수출 데이터 ----------
H=defaultdict(lambda: defaultdict(int))
for r in csv.DictReader(open('hs4_monthly.csv',encoding='utf-8')):
    H[r['hs4']][r['yyyymm']] += int(r['expDlr'])
def ind_series(prefs):
    o=defaultdict(int)
    for hs4,mm in H.items():
        if any(hs4.startswith(p) for p in prefs):
            for ym,v in mm.items(): o[ym]+=v
    return dict(o)
def ym_add(ym,k):
    y=int(ym[:4]); m=int(ym[4:6]); i=y*12+(m-1)+k
    return f"{i//12}{i%12+1:02d}"
EXP={k:ind_series(v) for k,v in MAP.items()}
YOY={}
for k,ser in EXP.items():
    YOY[k]={m: ser[m]/ser[ym_add(m,-12)]-1 for m in ser if ym_add(m,-12) in ser and ser[ym_add(m,-12)]}

# ---------- 종목 ----------
sec={}
for r in csv.DictReader(open('../stock_sector_dart.csv',encoding='utf-8-sig')):
    ic=(r.get('induty_code') or '')[:2]
    if ic in MAP: sec[r['code']]=ic
px=defaultdict(dict)
for r in csv.DictReader(open('../_px_weekly_2019_2026.csv',encoding='utf-8-sig')):
    if r['code'] in sec:
        try: px[r['code']][r['date']]=float(r['close'])
        except: pass
wdates=sorted({d for c in px for d in px[c]})
# PIT 유니버스
pit=defaultdict(dict)
for r in csv.DictReader(open('../_krx_pit.csv',encoding='utf-8-sig')):
    try:
        pit[r['date']][r['code']]=(float(r['close']),float(r['mktcap']),float(r['value']))
    except: pass
pitdates=sorted(pit)
def universe(dstr):
    snap=None
    for p in pitdates:
        if p<=dstr: snap=p
        else: break
    if snap is None: return None
    return {c for c,(cl,mc,val) in pit[snap].items() if val>=5e8 and mc>=3e10 and cl>=1000}
def near_w(dstr):
    for d in wdates:
        if d>=dstr: return d
def tstat(xs):
    n=len(xs)
    if n<2: return float('nan')
    sd=statistics.stdev(xs)
    return statistics.mean(xs)/sd*(n**0.5) if sd else float('nan')

months=sorted(set.intersection(*[set(YOY[k]) for k in YOY]))
months=[m for m in months if m>='201901' and m<='202606']
print("="*88)
print("축 5 — 개별종목 횡단면 확대 (HS→KSIC 업종 21개, PIT 유니버스, 유동성 필터)")
print("="*88)
recs=[]
for m in months:
    ed=near_w(f"{ym_add(m,1)}01"); xd=near_w(f"{ym_add(m,2)}01")
    if not ed or not xd or ed>=xd: continue
    uni=universe(ed)
    if not uni: continue
    row={}
    for k in MAP:
        if m not in YOY[k]: continue
        rets=[]
        for c,ic in sec.items():
            if ic!=k or c not in uni: continue
            if ed in px[c] and xd in px[c] and px[c][ed]>0:
                rets.append(px[c][xd]/px[c][ed]-1)
        if len(rets)>=5:
            row[k]=(YOY[k][m], statistics.mean(rets), len(rets))
    if len(row)>=10:
        recs.append((m,ed,xd,row))
print(f"사용 가능 월 {len(recs)}개 ({recs[0][0]}~{recs[-1][0]}), 월평균 업종수 {statistics.mean(len(r[3]) for r in recs):.1f}")

# Q상위5 - Q하위5 (횡단면 랭킹, 임계값 없음 → 룩어헤드 없음)
spread=[]; topx=[]; botx=[]
for m,ed,xd,row in recs:
    ranked=sorted(row, key=lambda k: row[k][0], reverse=True)
    n=len(ranked); q=max(3,n//5)
    top=[row[k][1] for k in ranked[:q]]; bot=[row[k][1] for k in ranked[-q:]]
    mkt=statistics.mean(row[k][1] for k in row)
    spread.append(statistics.mean(top)-statistics.mean(bot))
    topx.append(statistics.mean(top)-mkt); botx.append(statistics.mean(bot)-mkt)
print(f"\n수출 YoY 상위20% 업종 - 하위20% 업종 (월간, 등가중)")
print(f"  스프레드 평균 {statistics.mean(spread)*100:>7.3f}%p  t={tstat(spread):>5.2f}  n={len(spread)}  승률 {sum(1 for x in spread if x>0)/len(spread)*100:.1f}%  중앙값 {statistics.median(spread)*100:.3f}%p")
print(f"  상위20% vs 전체업종평균 {statistics.mean(topx)*100:>7.3f}%p t={tstat(topx):>5.2f} | 하위20% {statistics.mean(botx)*100:>7.3f}%p t={tstat(botx):>5.2f}")
h=len(spread)//2
print(f"  train(n={h}) {statistics.mean(spread[:h])*100:>7.3f}%p t={tstat(spread[:h]):>5.2f} | test(n={len(spread)-h}) {statistics.mean(spread[h:])*100:>7.3f}%p t={tstat(spread[h:]):>5.2f}")
srt=sorted(spread,reverse=True)
print(f"  꼬리: 상위3 기여 {sum(srt[:3])/sum(spread)*100:.1f}% / 제거시 {statistics.mean(srt[3:])*100:.3f}%p t={tstat(srt[3:]):.2f}")
random.seed(5); pl=[]
for _ in range(1000):
    s=[]
    for m,ed,xd,row in recs:
        ks=list(row); random.shuffle(ks)
        n=len(ks); q=max(3,n//5)
        s.append(statistics.mean(row[k][1] for k in ks[:q])-statistics.mean(row[k][1] for k in ks[-q:]))
    pl.append(statistics.mean(s))
obs=statistics.mean(spread)
print(f"  플라시보(1000회): 셔플평균 {statistics.mean(pl)*100:.3f}%p sd={statistics.stdev(pl)*100:.3f} | 관측 {obs*100:.3f}%p | p={sum(1 for x in pl if x>=obs)/len(pl):.4f}")
# 업종 잭나이프
print("\n  업종 잭나이프(하나씩 제외):")
res=[]
for ex in MAP:
    s=[]
    for m,ed,xd,row in recs:
        rr={k:v for k,v in row.items() if k!=ex}
        if len(rr)<8: continue
        ranked=sorted(rr,key=lambda k: rr[k][0],reverse=True); n=len(ranked); q=max(3,n//5)
        s.append(statistics.mean(rr[k][1] for k in ranked[:q])-statistics.mean(rr[k][1] for k in ranked[-q:]))
    if s: res.append((ex,statistics.mean(s)*100,tstat(s)))
res.sort(key=lambda x:x[1])
for ex,mn,tt in res[:4]+res[-3:]:
    print(f"    -{ex}: {mn:>7.3f}%p t={tt:>5.2f}")
