# 영상 규칙 1~3 관문의 일봉 스크린 (10분봉 수집 대상 선별)
import csv
from collections import defaultdict
import statistics as st

P=defaultdict(list)   # code -> [(date, o,h,l,c,vol,mktcap,name,market)]
with open("krx_stock_panel.csv",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        try:
            P[r["code"]].append((r["date"],float(r["open"]),float(r["high"]),float(r["low"]),
                                 float(r["close"]),float(r["volume"]),float(r["mktcap"] or 0),
                                 r["name"],r["market"]))
        except ValueError:
            pass
for c in P: P[c].sort()

cands=[]
for c,rows in P.items():
    closes=[x[4] for x in rows]
    vols=[x[5] for x in rows]
    for i in range(20,len(rows)):
        d,o,h,l,cl,v,mc,nm,mk = rows[i]
        if cl<1000 or v<=0 or mc<=0: continue
        # 이평선은 D-1 까지로 계산 (장중 실시간 판정과 동일)
        ma5=st.mean(closes[i-5:i]); ma10=st.mean(closes[i-10:i]); ma20=st.mean(closes[i-20:i])
        shares=mc/cl                      # 상장주식수 추정
        turn=v/shares                     # 당일 회전율(상장주식수 대비)
        prev=closes[i-1]
        # 관문1: 당일 고가가 5/10/20일선 모두 위 (장중 돌파 가능)
        if not (h>ma5 and h>ma10 and h>ma20): continue
        # 관문1 보조: 전일 종가는 세 선 중 하나 아래 (= 당일에 '돌파'가 일어남)
        if prev>max(ma5,ma10,ma20): continue
        if turn<0.05: continue            # 1차 스크린(느슨) — 정밀 임계는 백테스트에서
        cands.append(dict(code=c,name=nm,market=mk,date=d,open=o,high=h,low=l,close=cl,
                          prev=prev,vol=v,turn=round(turn,4),
                          ma5=round(ma5,1),ma10=round(ma10,1),ma20=round(ma20,1)))
cands.sort(key=lambda x:(x["date"],-x["turn"]))
with open("_yt10min_cands.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(cands[0].keys())); w.writeheader(); w.writerows(cands)
print("후보 종목일:",len(cands),"고유종목:",len({x['code'] for x in cands}),
      "날짜:",len({x['date'] for x in cands}))
for th in (0.05,0.10,0.15,0.20,0.30):
    s=[x for x in cands if x["turn"]>=th]
    print(f"  회전율>={th:.0%}: {len(s)} 종목일 · 고유종목 {len({x['code'] for x in s})}")
