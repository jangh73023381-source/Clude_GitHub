#!/usr/bin/env python3
"""수출입 참고지표 — 예측 주장 없음, 국면 설명·집행 참고 전용.
사용법: python3 trade_monitor.py [YYYYMM]   (생략 시 최신 확보월 자동)
매월 1일 이후 실행하면 전월 데이터가 반영된다(관세청 GW, 익월 15일경 확정 현행화)."""
import sys, os, csv, urllib.request, xml.etree.ElementTree as ET
from collections import defaultdict

BASE="https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
KEY=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','customs_apikey_encoded.txt')).read().strip()
HERE=os.path.dirname(os.path.abspath(__file__))

ITEMS={'반도체(IC)':['8542'],'디램':['8542321010'],'자동차':['8703'],'이차전지':['8507'],
       '선박':['8901','8902','8905','8906'],'철강':['72'],'석유제품':['2710'],
       '의약품':['3004'],'화장품':['3304'],'기계':['84'],'디스플레이':['8524']}

def ym_add(ym,k):
    y=int(ym[:4]); m=int(ym[4:6]); i=y*12+(m-1)+k
    return f"{i//12}{i%12+1:02d}"

def fetch(ym):
    url=f"{BASE}?serviceKey={KEY}&numOfRows=15000&pageNo=1&strtYymm={ym}&endYymm={ym}&hsSgn=&imexTp=1"
    root=ET.fromstring(urllib.request.urlopen(url,timeout=40).read())
    if root.findtext('.//resultCode')!='00': raise RuntimeError(root.findtext('.//resultMsg'))
    out=defaultdict(lambda:[0,0,0])   # exp, imp, expWgt
    for it in root.findall('.//item'):
        hs=it.findtext('hsCode') or ''
        e=int(it.findtext('expDlr') or 0); i_=int(it.findtext('impDlr') or 0); w=int(it.findtext('expWgt') or 0)
        for k,pref in ITEMS.items():
            if any(hs.startswith(p) for p in pref):
                v=out[k]; v[0]+=e; v[1]+=i_; v[2]+=w
    return out

def latest_available():
    ym=None
    import datetime
    t=datetime.date.today()
    cand=f"{t.year}{t.month:02d}"
    for k in range(1,5):
        c=ym_add(cand,-k)
        try:
            d=fetch(c)
            if d and d['반도체(IC)'][0]>0: return c
        except Exception: pass
    return None

def main():
    ym = sys.argv[1] if len(sys.argv)>1 else latest_available()
    if not ym: print("데이터 없음"); return
    cur=fetch(ym); prev=fetch(ym_add(ym,-12))
    print(f"[수출입 참고지표] {ym[:4]}년 {int(ym[4:]):d}월 확정 (관세청 품목별 수출입실적)")
    print(f"{'품목':<12}{'수출($B)':>10}{'전년동월비':>11}{'수입($B)':>10}{'무역수지($B)':>12}")
    for k in ITEMS:
        e,i_,w = cur[k]; pe = prev[k][0]
        yoy = (e/pe-1)*100 if pe else float('nan')
        print(f"{k:<12}{e/1e9:>10.2f}{yoy:>10.1f}%{i_/1e9:>10.2f}{(e-i_)/1e9:>12.2f}")
    dw=cur['디램'][2]; de=cur['디램'][0]
    pdw=prev['디램'][2]; pde=prev['디램'][0]
    if dw and pdw:
        print(f"\n디램 실현단가(수출금액/중량): {de/dw:,.0f}$/kg  (전년동월 {pde/pdw:,.0f}, {(de/dw)/(pde/pdw)*100-100:+.1f}%)")
    print("\n※ 참고 정보입니다. 이 지표로 종목을 고르는 규칙은 3개 축·5개 형태 백테스트에서 모두 기각됐습니다")
    print("  (수출입데이터_섹터로테이션_검정_20260902.md). 국면 설명·집행 참고 용도로만 쓰십시오.")

if __name__=='__main__': main()
