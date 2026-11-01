# -*- coding: utf-8 -*-
"""중기 추천 ETF 종가베팅 백테스트
전략: 브리핑일 D에 발표된 [6-2] 중기 ETF 5종 중, D 당일 상승률이 임계값 T 미만
      (또는 코스피 대비 열위)인 종목만 D 종가에 매수.
청산: (V1) D+1 종가 청산   (V2) 다음 브리핑에도 중기 추천되면 계속 보유, 빠진 첫날 종가 청산
"""
import csv, json, collections, statistics as st

PANEL='/sessions/zealous-laughing-mccarthy/mnt/loop/backtest/panel_close_0724.csv'
KOSPI='/sessions/zealous-laughing-mccarthy/mnt/loop/backtest/kospi_close.csv'
PICKS='/tmp/bt/picks_mid_etf.json'
COST=0.0010   # 왕복 10bp

px=collections.defaultdict(dict); names={}
for r in csv.DictReader(open(PANEL)):
    px[r['code']][r['date']]=float(r['close']); names[r['code']]=r['name']
kospi={r['date']:float(r['close']) for r in csv.DictReader(open(KOSPI))}
dates=sorted(kospi)                     # 거래일 달력
idx={d:i for i,d in enumerate(dates)}

picks_raw=json.load(open(PICKS))
picks={d.replace('-',''):v['codes'] for d,v in picks_raw.items()}
bdays=sorted(picks)                      # 브리핑 발행일 = 종가베팅 후보일
for d in bdays: assert d in idx, ('브리핑일이 거래일 달력에 없음',d)

def ret(code,d0,d1):
    a=px[code].get(d0); b=px[code].get(d1)
    return None if (a is None or b is None or a==0) else b/a-1
def kret(d0,d1):
    a,b=kospi.get(d0),kospi.get(d1)
    return None if not a or not b else b/a-1
def prev(d): return dates[idx[d]-1]
def nxt(d):
    i=idx[d]+1
    return dates[i] if i<len(dates) else None

# --- V2 청산일: D 이후 브리핑에서 연속 재추천되는 마지막 날의 다음 브리핑 미포함일 ---
def exit_v2(code,D):
    """연속 재추천 동안 보유. 재추천 끊긴 첫 브리핑일의 종가에 청산.
    반환 (청산일, 보유거래일수, open_flag)"""
    i=bdays.index(D)
    last=D
    for j in range(i+1,len(bdays)):
        if code in picks[bdays[j]]:
            last=bdays[j]
        else:
            return bdays[j], idx[bdays[j]]-idx[D], False
    # 데이터 끝까지 재추천 지속 → 마지막 보유가능일 종가로 평가(미청산)
    end=dates[-1]
    return end, idx[end]-idx[D], True

def run(thresh=None, rel=False, exitmode='v1'):
    """thresh: D당일 상승률 < thresh 인 종목만 (None=조건없음)
       rel: D당일 코스피 대비 열위 종목만 (조건 AND)"""
    trades=[]; daily=[]
    for D in bdays:
        n1=nxt(D)
        if exitmode=='v1' and n1 is None: continue
        kD=kret(prev(D),D)
        sel=[]
        for c in picks[D]:
            rD=ret(c,prev(D),D)
            if rD is None: continue
            if thresh is not None and not (rD < thresh): continue
            if rel and not (rD < kD): continue
            sel.append((c,rD))
        rs=[]
        for c,rD in sel:
            if exitmode=='v1':
                xd, hold, op = n1, 1, False
            else:
                xd, hold, op = exit_v2(c,D)
            r=ret(c,D,xd)
            if r is None: continue
            kb=kret(D,xd)
            trades.append(dict(D=D,code=c,name=names[c],rD=rD,exit=xd,hold=hold,r=r,
                               rnet=r-COST,kb=kb,exc=r-COST-kb,open=op))
            rs.append(r-COST)
        if exitmode=='v1':
            kb=kret(D,n1)
            daily.append(dict(D=D,n=len(rs),port=(sum(rs)/len(rs) if rs else 0.0),k=kb))
    return trades,daily

def summ(trades,daily,label):
    if not trades:
        return dict(label=label,n=0)
    r=[t['rnet'] for t in trades]; e=[t['exc'] for t in trades]
    eq=1.0
    for d in daily: eq*= (1+d['port'])
    keq=1.0
    for d in daily: keq*=(1+(d['k'] or 0))
    days_in=sum(1 for d in daily if d['n']>0)
    return dict(label=label,n=len(trades),mean=st.mean(r)*100,med=st.median(r)*100,
                win=sum(1 for x in r if x>0)/len(r)*100,
                exc=st.mean(e)*100, excwin=sum(1 for x in e if x>0)/len(e)*100,
                eq=(eq-1)*100, keq=(keq-1)*100, days=len(daily), daysin=days_in,
                avghold=st.mean([t['hold'] for t in trades]))
if __name__=='__main__':
    print('브리핑일수',len(bdays), bdays[0],'~',bdays[-1])
