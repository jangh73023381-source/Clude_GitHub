#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attention_pilot.py — 장전(전일16:00→금일09:00) 관심 모멘텀 라이브 파일럿.

뉴스/유튜브는 과거 소급검증이 불가하므로 '전방(forward) 페이퍼검증'으로만 유효성 확인.
매 영업일 아침(장전) 에이전트가 MCP로 테마별 관심 신호(뉴스기사수·검색모멘텀·유튜브신규영상수)를
수집해 raw CSV로 만든 뒤 이 스크립트로 (1)오늘 픽 기록, (2)지난 픽 채점을 수행한다.

서브커맨드:
  record --date YYYYMMDD --raw raw.csv
     raw.csv 헤더(v1.1): theme,news_total,news_buy,news_sell,news_neutral,search,
                          yt_total,yt_buy,yt_sell,yt_neutral  (구버전 theme,news,search,youtube 도 호환)
     composite = z(news_total) + z(search) + z(yt_total)  (매수/매도 건수는 선정 로직에 미반영, 표기용)
     → 상위 5테마 선정 → 대표 ETF로 매핑, 전일종가(entry) 조회 후 attention_pilot_picks.csv에 append
       (news_buy/news_sell/yt_buy/yt_sell 매수·매도 참고건수도 함께 기록).
  score --date YYYYMMDD [--prices PATH]
     해당 거래일(=picks의 date)의 픽을 채점: 유니버스(etf_universe.csv, 숏선물 제외) 전일→당일
     종가로 상위10% 컷오프 산정 후 각 픽의 순위·수익·적중 기록 → attention_pilot_results.csv.
     --prices 주면 그 CSV(code,name,prev_close,next_close) 재사용, 없으면 키움으로 유니버스 수집.
  status  현재 누적 픽·채점 요약(적중률 등) 출력.

룩어헤드 금지: record는 전일 종가까지 정보(장전 신호)만 사용. score의 next_close(결과)는 채점 전용.
정보 제공 목적이며 투자 자문이 아님.
"""
import argparse, csv, math, os, sys, statistics as st
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # loop/
THEMES=os.path.join(BASE,'references','attention_pilot_themes.csv')
PICKS=os.path.join(BASE,'references','attention_pilot_picks.csv')
RESULTS=os.path.join(BASE,'references','attention_pilot_results.csv')
UNIV=os.path.join(BASE,'etf_universe.csv')

def load_themes():
    m={}
    for r in csv.DictReader(open(THEMES,encoding='utf-8')):
        m[r['theme'].strip()]=(r['code'].strip(), r['etf'].strip())
    return m

def is_short(n): return '숏' in (n or '').replace(' ','')

# 2026-08-06 — 유니버스 정렬(사용자 지시). 이 파일의 이진 채점(cmd_score)만 종전
# '전일종가 1만원 이상 + 숏 제외' 를 쓰고 있어 다른 스크립트와 달랐다. 공용 상수로
# 통일한다(최소가격 필터는 2026-07-30 폐지, 파생·현금성 제외로 대체).
# 주의: 이 경로는 트랙 B 승격 판정 지표(코스피 대비 초과수익)에 쓰이지 않는다 —
# 판정은 combo_shadow_tracker.csv 로 하고, 여기 결과 파일은 2026-07-09 이후 갱신
# 이력이 없다. 따라서 이 정렬로 shadow 표본이 오염되지 않으며 분절도 필요 없다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from universe_filters import eligible  # noqa: E402

def _kiwoom():
    sys.path.insert(0,BASE)
    import kiwoom_api as k
    k.LOOP_DIR=BASE; k.APPKEY_FILE=BASE+'/46238499_appkey.txt'
    k.SECRETKEY_FILE=BASE+'/46238499_secretkey.txt'; k.TOKEN_CACHE=BASE+'/.kiwoom_token.json'
    return k

def prev_close_on(k, code, date):
    """date(장전) 기준 최근 종가 = date 이전(또는 date 당일 있으면 그 전날) 가장 최근 거래일 종가."""
    r=k.get_daily_chart(code, date)
    lst=r.get('stk_dt_pole_chart_qry') or []
    dc=sorted([(x['dt'],abs(float(x['cur_prc']))) for x in lst if x.get('cur_prc')],reverse=True)
    for d,c in dc:
        if d < date: return c  # 장전이므로 date 미포함, 직전 거래일 종가
    return dc[-1][1] if dc else None

def zscores(vals):
    xs=[v for v in vals if v is not None]
    if len(xs)<2: return [0.0 for _ in vals]
    m=st.mean(xs); s=st.pstdev(xs) or 1.0
    return [((v-m)/s if v is not None else 0.0) for v in vals]

def cmd_record(a):
    themes=load_themes()
    rows=list(csv.DictReader(open(a.raw,encoding='utf-8')))
    th=[r['theme'].strip() for r in rows]
    def col(*names):
        out=[]
        for r in rows:
            v=None
            for name in names:
                if name in r and r[name] not in (None,''):
                    try: v=float(r[name]); break
                    except: pass
            out.append(v)
        return out
    def icol(*names):
        # 정수 카운트 열(매수/매도/중립). 없으면 0.
        out=[]
        for r in rows:
            v=0
            for name in names:
                if name in r and r[name] not in (None,''):
                    try: v=int(float(r[name])); break
                    except: pass
            out.append(v)
        return out
    # v1.1: news_total/yt_total 우선, 구버전 news/youtube 열도 호환
    news=col('news_total','news'); search=col('search'); yt=col('yt_total','youtube')
    news_buy=icol('news_buy'); news_sell=icol('news_sell'); news_neu=icol('news_neutral')
    yt_buy=icol('yt_buy'); yt_sell=icol('yt_sell'); yt_neu=icol('yt_neutral')
    nz=zscores(news); sz=zscores(search); yz=zscores(yt)
    comp=[(th[i], nz[i]+sz[i]+yz[i], nz[i],sz[i],yz[i],
           news_buy[i],news_sell[i],news_neu[i],yt_buy[i],yt_sell[i],yt_neu[i]) for i in range(len(th))]
    comp.sort(key=lambda x:x[1],reverse=True)
    top=comp[:5]
    k=_kiwoom(); k.get_access_token(force=True)
    with open(PICKS,'a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        for rank,(t,c,nzz,szz,yzz,nb,ns,nn,yb,ys,yn) in enumerate(top,1):
            if t not in themes:
                print("WARN 테마 매핑 없음:",t); continue
            code,etf=themes[t]
            try: entry=prev_close_on(k,code,a.date)
            except Exception as e: entry=None; print("entry 조회 실패",code,e)
            w.writerow([a.date,rank,t,code,etf,f"{c:.3f}",f"{nzz:.2f}",f"{szz:.2f}",f"{yzz:.2f}",
                        int(entry) if entry else '', nb,ns,nn,yb,ys,yn])
            print(f"  {rank}. {t:6} {etf} ({code}) comp={c:+.2f} entry={entry} "
                  f"news매수{nb}/매도{ns}/중립{nn} yt매수{yb}/매도{ys}/중립{yn}")
    print(f"기록 완료: {a.date} 픽 5종 → {PICKS}")

def _universe_from_kiwoom(k, date):
    codes=[]
    for r in csv.DictReader(open(UNIV,encoding='utf-8-sig')):
        codes.append((r['티커'].strip(), r['종목명'].strip()))
    import time
    rows=[]
    for code,name in codes:
        if not eligible(name): continue
        try:
            r=k.get_daily_chart(code,date); lst=r.get('stk_dt_pole_chart_qry') or []
            dc=sorted([(x['dt'],abs(float(x['cur_prc']))) for x in lst if x.get('cur_prc')],reverse=True)
            nc=None; pc=None
            for i,(d,c) in enumerate(dc):
                if d==date: nc=c; pc=dc[i+1][1] if i+1<len(dc) else None; break
            if nc and pc: rows.append((code,name,pc,nc))
        except: pass
        time.sleep(0.05)
    return rows

def cmd_score(a):
    # picks for trading day a.date
    picks=[r for r in csv.DictReader(open(PICKS,encoding='utf-8')) if r['date']==a.date]
    if not picks: sys.exit(f"{a.date} 기록된 픽 없음")
    if a.prices and os.path.exists(a.prices):
        rows=[]
        for r in csv.DictReader(open(a.prices,encoding='utf-8')):
            if not eligible(r.get('name','')): continue
            try: pc=float(r['prev_close']); nc=float(r['next_close'])
            except: continue
            rows.append((r['code'].strip(),r.get('name',''),pc,nc))
    else:
        k=_kiwoom(); k.get_access_token(force=True); rows=_universe_from_kiwoom(k,a.date)
    rank={}; N=len(rows)
    order=sorted(rows,key=lambda x:x[3]/x[2]-1,reverse=True)
    cutoff=max(1,math.ceil(N*0.10))
    for i,(c,n,pc,nc) in enumerate(order,1): rank[c]=(i,nc/pc-1)
    hit=0
    with open(RESULTS,'a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        for p in picks:
            code=p['code']; rk=rank.get(code) or rank.get(code.zfill(6))
            if rk:
                ok=rk[0]<=cutoff; hit+=ok
                w.writerow([a.date,p['theme'],code,p['etf'],f"{rk[1]*100:.2f}",rk[0],N,cutoff,int(ok),''])
                print(f"  {p['theme']:6} {p['etf'][:16]:<16} 순위 {rk[0]}/{N} 수익 {rk[1]*100:+.2f}% {'적중' if ok else '미달'}")
            else:
                w.writerow([a.date,p['theme'],code,p['etf'],'','',N,cutoff,'','유니버스 없음'])
                print(f"  {p['theme']:6} {p['etf'][:16]:<16} 유니버스 없음")
    print(f"채점 완료: {a.date} 적중 {hit}/{len(picks)} (컷오프 상위{cutoff}/{N}) → {RESULTS}")

def cmd_status(a):
    res=list(csv.DictReader(open(RESULTS,encoding='utf-8')))
    days=sorted({r['score_date'] for r in res})
    print(f"채점된 영업일: {len(days)}일")
    byday={}
    for r in res:
        if r['hit']!='': byday.setdefault(r['score_date'],[]).append(int(r['hit']))
    tot=0; cnt=0
    for d in sorted(byday):
        h=sum(byday[d]); n=len(byday[d]); tot+=h; cnt+=n
        print(f"  {d}: 적중 {h}/{n}")
    if cnt: print(f"누적 적중률: {tot}/{cnt} = {tot/cnt*100:.1f}% (무작위 기대 10%)")

if __name__=='__main__':
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    r=sub.add_parser('record'); r.add_argument('--date',required=True); r.add_argument('--raw',required=True); r.set_defaults(fn=cmd_record)
    s=sub.add_parser('score'); s.add_argument('--date',required=True); s.add_argument('--prices',default=''); s.set_defaults(fn=cmd_score)
    st_=sub.add_parser('status'); st_.set_defaults(fn=cmd_status)
    a=ap.parse_args(); a.fn(a)
