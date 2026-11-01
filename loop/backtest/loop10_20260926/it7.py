from ev import *
dates=E.dates
ym=[d[:6] for d in dates]
exd=set()
for j in range(len(dates)-1):
    if ym[j+1]!=ym[j] and j>=1: exd.add(dates[j-1])   # 월 마지막 영업일(j)의 직전 영업일 = 분배락 추정일
qex=set(d for d in exd if d[4:6] in ('01','04','07','10'))
for nm in ('MOM','LV'):
    df=BASE[nm].copy()
    df['nxt']=[dates[i+1] for i in df.i]
    for lab,S in (('월말분배락',exd),('분기분배락(1·4·7·10월)',qex)):
        m=df.nxt.isin(S)
        e=df.A-df.bA
        print(f"{nm} {lab}: n={m.sum()}  초과(A) 분배락일 {e[m].mean():+.3f}%p  그외 {e[~m].mean():+.3f}%p  | 절대수익 분배락일 {df.A[m].mean():+.3f} 벤치 {df.bA[m].mean():+.3f}")
# 종목별: 분기 분배락일 평균 수익 - 전체 평균 (가장 큰 하락 종목)
R=E.R; idx=[dates.index(d) for d in sorted(qex)]
rq=np.nanmean(R[idx],0); ra=np.nanmean(R,0); cnt=(~np.isnan(R[idx])).sum(0)
o=np.argsort(rq-ra)[:15]
for j in o: print(E.codes[j], E.names[E.codes[j]][:28], f'{rq[j]-ra[j]:+.2f}', cnt[j])
# LV/MOM 픽의 분배락일 편입 종목 중 월배당·배당·커버드콜 명칭 비중
import re
kw=re.compile('배당|커버드콜|인컴|리츠|월배당|고배당|채|프리미엄')
for nm,sel in (('MOM',E.sel_mom),('LV',E.sel_lv)):
    tot=hit=0
    for i in range(20,E.T-3):
        pl=E.pool(i)
        if len(pl)<5: continue
        for c in sel(i,pl): tot+=1; hit+= bool(kw.search(E.names[E.codes[c]]))
    print(nm,'인컴·배당·채권형 명칭 비중',round(hit/tot,3))
