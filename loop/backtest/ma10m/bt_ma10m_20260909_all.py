# -*- coding: utf-8 -*-
"""유튜브 월봉10이평(성승현, 2026-09-05) 검정 — 2026-09-09. 데이터: monthly.csv/idx_monthly.csv/us_monthly.csv (네이버 월봉·Yahoo).
실행: fetch_m.py -> fetch_idx_us.py -> bt_ma10m.py -> bt2.py -> bt3.py -> bt4.py -> bt5.py -> verify.py
"""

# ================= fetch_m.py =================
import urllib.request, json, csv, time, sys, os, re
UA={'User-Agent':'Mozilla/5.0','Referer':'https://finance.naver.com/'}
def bars(sym, tf='month', s='19950101', e='20260908'):
    u=f'https://api.finance.naver.com/siseJson.naver?symbol={sym}&requestType=1&startTime={s}&endTime={e}&timeframe={tf}'
    d=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30).read().decode('utf-8')
    d=d.strip().replace("'",'"')
    arr=json.loads(d)
    return arr[1:]
if __name__=='__main__':
    codes=[r for r in csv.DictReader(open('universe.csv',encoding='utf-8'))]
    done=set()
    out='monthly.csv'
    if os.path.exists(out):
        for r in csv.reader(open(out,encoding='utf-8')):
            if r and r[0]!='code': done.add(r[0])
    f=open(out,'a',newline='',encoding='utf-8'); w=csv.writer(f)
    if not done: w.writerow(['code','date','open','high','low','close','vol'])
    n=0
    for r in codes:
        c=r['code']
        if c in done: continue
        try:
            for b in bars(c):
                w.writerow([c,b[0],b[1],b[2],b[3],b[4],b[5]])
            n+=1
        except Exception as ex:
            print('ERR',c,ex, flush=True)
        if n%25==0: f.flush(); print('done',n,flush=True)
        time.sleep(0.12)
    f.close(); print('FIN',n)

# ================= fetch_idx_us.py =================
import urllib.request, json, csv, time, sys
sys.path.insert(0,'.')
from fetch_m import bars
# 1) 한국 지수
with open('idx_monthly.csv','w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['code','date','open','high','low','close','vol'])
    for s in ['KOSPI','KOSDAQ']:
        for b in bars(s):
            w.writerow([s,b[0],b[1],b[2],b[3],b[4],b[5]])
        time.sleep(0.3)
print('idx ok')
# 2) 미국
US = """SPY QQQ AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO LLY JPM V UNH XOM MA JNJ PG HD COST
ABBV MRK ADBE CRM NFLX AMD PEP KO TMO WMT CSCO ACN MCD ABT LIN DHR TXN NEE PM VZ
INTC ORCL QCOM IBM AMGN HON UPS BA CAT GE SBUX GS MS BLK NOW ISRG BKNG MDT DE LMT
DASH ABNB UBER SHOP PLTR SNOW CRWD PANW MU ADI""".split()
UA={'User-Agent':'Mozilla/5.0'}
with open('us_monthly.csv','w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['code','date','close'])
    for t in US:
        try:
            u=f'https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=30y&interval=1mo&events=div%2Csplit'
            d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30).read())
            r=d['chart']['result'][0]
            ts=r['timestamp']; adj=r['indicators'].get('adjclose',[{}])[0].get('adjclose') or r['indicators']['quote'][0]['close']
            import datetime as dt
            for a,b in zip(ts,adj):
                if b is None: continue
                w.writerow([t, dt.datetime.utcfromtimestamp(a).strftime('%Y%m%d'), b])
        except Exception as e:
            print('ERR',t,e)
        time.sleep(0.2)
print('us ok')

# ================= engine.py =================
# -*- coding: utf-8 -*-
"""월봉 10이평 돌파/이탈 추세추종 규칙(성승현, 머니인사이드 2026-09-05) 검정 엔진."""
import numpy as np, pandas as pd

def load_monthly(path='monthly.csv'):
    df = pd.read_csv(path, dtype={'code':str})
    df = df[df['date'].astype(str).str.len()==8]
    df['date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
    df = df[df['close']>0].drop_duplicates(['code','date']).sort_values(['code','date'])
    return df

def series_stats(r, ann=12):
    """r: monthly simple returns (np array). Returns CAGR, MDD, Sharpe, vol."""
    r = np.asarray(r, dtype=float)
    if len(r)==0: return dict(cagr=np.nan, mdd=np.nan, sharpe=np.nan, vol=np.nan, n=0)
    eq = np.cumprod(1+r)
    yrs = len(r)/ann
    cagr = eq[-1]**(1/yrs)-1 if eq[-1]>0 else -1.0
    peak = np.maximum.accumulate(eq)
    mdd = float((eq/peak-1).min())
    sd = r.std(ddof=1) if len(r)>1 else np.nan
    sharpe = (r.mean()*ann)/(sd*np.sqrt(ann)) if sd and sd>0 else np.nan
    return dict(cagr=float(cagr), mdd=mdd, sharpe=float(sharpe) if sharpe==sharpe else np.nan,
                vol=float(sd*np.sqrt(ann)) if sd==sd else np.nan, n=len(r))

def run_symbol(c, lookback=10, cost=0.0, min_months=None):
    """c: pd.Series of monthly closes indexed by date.
    신호: 월 종가 > MA(lookback) -> 다음 달 보유. 집행은 그 달 말일 종가(=시차 1개월 없음, 룩어헤드 없음).
    반환: DataFrame(ret_bh, ret_rule, pos)"""
    c = c.astype(float)
    ma = c.rolling(lookback).mean()
    sig = (c > ma).astype(float)          # 월말 종가 기준 판정
    pos = sig.shift(1)                     # t월 수익률은 t-1월말 신호로 결정  (룩어헤드 없음)
    ret = c.pct_change()
    df = pd.DataFrame({'ret_bh':ret, 'pos':pos})
    df = df.dropna()
    turn = df['pos'].diff().abs().fillna(df['pos'].abs())
    df['ret_rule'] = df['pos']*df['ret_bh'] - turn*cost
    return df

def trades_from_pos(pos, ret):
    """포지션 시퀀스에서 개별 거래(진입~청산) 수익률 목록."""
    out=[]; cur=None
    for i,(d,p) in enumerate(pos.items()):
        if p==1 and cur is None: cur=[d,1.0]
        if cur is not None and p==1: cur[1]*= (1+ret.loc[d])
        if p==0 and cur is not None:
            out.append((cur[0],d,cur[1]-1)); cur=None
    if cur is not None: out.append((cur[0],pos.index[-1],cur[1]-1))
    return out

# ================= bt_ma10m.py =================
# -*- coding: utf-8 -*-
import numpy as np, pandas as pd, json, sys
from engine import load_monthly, series_stats

START='2000-01-01'
MINM=60          # 최소 60개월(5년) 관측
def prep(path='monthly.csv', start=START, code_col='code'):
    df=load_monthly(path)
    df=df[df['date']>=start]
    df['ym']=df['date'].dt.to_period('M')
    df=df.sort_values(['code','ym','date']).drop_duplicates(['code','ym'],keep='last')
    piv=df.pivot(index='ym', columns='code', values='close').sort_index()
    keep=[c for c in piv.columns if piv[c].notna().sum()>=MINM]
    return piv[keep]

def panel_rule(piv, lookback=10, cost=0.0):
    """returns (ret_bh, pos) aligned DataFrames"""
    ma=piv.rolling(lookback, min_periods=lookback).mean()
    sig=(piv>ma).astype(float).where(piv.notna() & ma.notna())
    pos=sig.shift(1)
    ret=piv.pct_change()
    valid = pos.notna() & ret.notna()
    ret=ret.where(valid); pos=pos.where(valid)
    turn=pos.diff().abs()
    rule=pos*ret - turn.fillna(0)*cost
    return ret, pos, rule

def ew_curve(x):
    """equal-weight across available symbols each month"""
    return x.mean(axis=1, skipna=True)

def main():
    piv=prep()
    ret,pos,rule=panel_rule(piv,10,0.0)
    bh_ew=ew_curve(ret); ru_ew=ew_curve(rule)
    m=bh_ew.notna()&ru_ew.notna()
    bh_ew,ru_ew=bh_ew[m],ru_ew[m]
    print('=== 표본 ===')
    print('종목수', piv.shape[1], '기간', str(piv.index.min()), '~', str(piv.index.max()),
          '월수', len(bh_ew))
    print('평균 편입종목/월', ret.notna().sum(axis=1)[m].mean().round(1))
    print()
    print('=== [1] 동일가중 포트폴리오 (한국 대형주 %d종) ==='%piv.shape[1])
    for nm,s in (('규칙(월봉10이평)',ru_ew),('매수후보유(B&H)',bh_ew)):
        st=series_stats(s.values)
        print(f"{nm:18s} CAGR {st['cagr']*100:7.2f}%  MDD {st['mdd']*100:8.2f}%  Sharpe {st['sharpe']:5.2f}  vol {st['vol']*100:5.1f}%")
    ex=(ru_ew-bh_ew)
    print(f"월평균 초과 {ex.mean()*100:+.4f}%p  t={ex.mean()/ex.std(ddof=1)*np.sqrt(len(ex)):.2f}  승월 {(ex>0).mean()*100:.1f}%")
    expo=pos.mean(axis=1)[m].mean()
    print(f"평균 시장노출 {expo*100:.1f}%")
    print()
    # 종목별
    rows=[]
    for c in piv.columns:
        r=ret[c].dropna(); u=rule[c].dropna()
        idx=r.index.intersection(u.index)
        if len(idx)<MINM: continue
        a=series_stats(u.loc[idx].values); b=series_stats(r.loc[idx].values)
        p=pos[c].loc[idx]
        # 거래 수
        tr=int(((p.diff()==1).sum()))
        rows.append(dict(code=c,n=len(idx),cagr_rule=a['cagr'],cagr_bh=b['cagr'],
                         mdd_rule=a['mdd'],mdd_bh=b['mdd'],shp_rule=a['sharpe'],shp_bh=b['sharpe'],
                         expo=float(p.mean()), trades=tr, tr_per_yr=tr/(len(idx)/12)))
    R=pd.DataFrame(rows)
    R.to_csv('per_symbol.csv',index=False)
    print('=== [2] 종목별 (n=%d) ==='%len(R))
    print(f"CAGR 개선 중앙값 {(R.cagr_rule-R.cagr_bh).median()*100:+.2f}%p  평균 {(R.cagr_rule-R.cagr_bh).mean()*100:+.2f}%p  규칙 우위 비율 {(R.cagr_rule>R.cagr_bh).mean()*100:.1f}%")
    print(f"MDD  개선 중앙값 {(R.mdd_rule-R.mdd_bh).median()*100:+.2f}%p  (양수=개선)  개선 비율 {(R.mdd_rule>R.mdd_bh).mean()*100:.1f}%")
    print(f"Sharpe 개선 중앙값 {(R.shp_rule-R.shp_bh).median():+.3f}  개선 비율 {(R.shp_rule>R.shp_bh).mean()*100:.1f}%")
    print(f"연 거래횟수 중앙값 {R.tr_per_yr.median():.2f}회  평균 노출 {R.expo.mean()*100:.1f}%")
    print()
    # R1 고원
    print('=== [3] R1 파라미터 고원 (룩백 개월) ===')
    print(f"{'룩백':>4} {'CAGR':>8} {'MDD':>9} {'Sharpe':>7} {'월초과%p':>9} {'t':>6} {'노출%':>6}")
    plateau={}
    for lb in [3,5,6,8,10,12,15,18,24]:
        r2,p2,u2=panel_rule(piv,lb,0.0)
        b=ew_curve(r2); a=ew_curve(u2); mm=b.notna()&a.notna(); b,a=b[mm],a[mm]
        st=series_stats(a.values); e=(a-b)
        t=e.mean()/e.std(ddof=1)*np.sqrt(len(e))
        plateau[lb]=dict(cagr=st['cagr'],mdd=st['mdd'],sharpe=st['sharpe'],ex=e.mean(),t=t)
        print(f"{lb:>4} {st['cagr']*100:7.2f}% {st['mdd']*100:8.2f}% {st['sharpe']:7.2f} {e.mean()*100:+8.4f} {t:6.2f} {p2.mean(axis=1)[mm].mean()*100:5.1f}")
    json.dump({str(k):v for k,v in plateau.items()}, open('plateau.json','w'))
    print()
    # R2 3분할
    print('=== [4] R2 3분할 fold ===')
    n=len(ru_ew); ed=np.array_split(np.arange(n),3)
    for i,ix in enumerate(ed,1):
        a=ru_ew.iloc[ix]; b=bh_ew.iloc[ix]
        sa=series_stats(a.values); sb=series_stats(b.values)
        e=(a-b)
        print(f"fold{i} {a.index[0]}~{a.index[-1]}  규칙CAGR {sa['cagr']*100:6.2f}% vs B&H {sb['cagr']*100:6.2f}%  MDD {sa['mdd']*100:7.2f}% vs {sb['mdd']*100:7.2f}%  월초과 {e.mean()*100:+.3f}%p")
    print()
    # R5 꼬리
    print('=== [5] R5 꼬리 기여도 (월별 초과) ===')
    e=(ru_ew-bh_ew).sort_values(ascending=False)
    base=e.mean()
    for k in [0,1,3,5,10]:
        v=e.iloc[k:] if k else e
        print(f"상위 {k:>2}개월 제거: 평균 {v.mean()*100:+.4f}%p  중앙값 {v.median()*100:+.4f}%p")
    print(f"윈저화(5%) 평균 {e.clip(e.quantile(.05),e.quantile(.95)).mean()*100:+.4f}%p")
    print()
    # 국면
    print('=== [6] 국면별 (B&H 동일가중 월수익 기준) ===')
    up=bh_ew>0
    for nm,msk in (('상승월',up),('하락월',~up)):
        a=ru_ew[msk]; b=bh_ew[msk]
        print(f"{nm} n={msk.sum():3d}  규칙 {a.mean()*100:+.2f}%  B&H {b.mean()*100:+.2f}%  초과 {(a-b).mean()*100:+.2f}%p")
    print()
    # 플라시보: 노출 매칭 무작위 신호
    print('=== [7] 플라시보 — 노출 매칭 무작위 타이밍 (200회) ===')
    rng=np.random.default_rng(7)
    real=ru_ew.mean(); reals=series_stats(ru_ew.values)
    sims_cagr=[]; sims_mdd=[]; sims_shp=[]
    P=pos.values.copy()
    for _ in range(200):
        Q=P.copy()
        for j in range(Q.shape[1]):
            col=Q[:,j]; ok=~np.isnan(col)
            v=col[ok]; rng.shuffle(v); col[ok]=v
        sim=pd.DataFrame(Q,index=pos.index,columns=pos.columns)*ret
        s=ew_curve(sim); s=s[m]
        st=series_stats(s.values); sims_cagr.append(st['cagr']); sims_mdd.append(st['mdd']); sims_shp.append(st['sharpe'])
    for nm,arr,val,hi in (('CAGR',sims_cagr,reals['cagr'],True),('MDD',sims_mdd,reals['mdd'],True),('Sharpe',sims_shp,reals['sharpe'],True)):
        arr=np.array(arr); p=(arr>=val).mean() if hi else (arr<=val).mean()
        print(f"{nm:6s} 실제 {val:8.4f}  무작위 중앙 {np.median(arr):8.4f}  경험적 p(무작위≥실제) {p:.3f}")
if __name__=='__main__':
    main()

# ================= bt2.py =================
# -*- coding: utf-8 -*-
import numpy as np, pandas as pd
from engine import load_monthly, series_stats
from bt_ma10m import prep, panel_rule, ew_curve

CASH_ANN=0.025   # 현금 연 2.5% (2000~2026 한국 단기금리 대략)
CASH_M=(1+CASH_ANN)**(1/12)-1

def report(name, ru, bh, extra=''):
    a=series_stats(ru.values); b=series_stats(bh.values); e=ru-bh
    t=e.mean()/e.std(ddof=1)*np.sqrt(len(e)) if e.std(ddof=1)>0 else np.nan
    print(f"{name:28s} 규칙 CAGR {a['cagr']*100:6.2f}% MDD {a['mdd']*100:7.2f}% Sh {a['sharpe']:4.2f} | "
          f"B&H CAGR {b['cagr']*100:6.2f}% MDD {b['mdd']*100:7.2f}% Sh {b['sharpe']:4.2f} | "
          f"월초과 {e.mean()*100:+.3f}%p t={t:5.2f} {extra}")

piv=prep()
ret,pos,rule=panel_rule(piv,10,0.0)
bh=ew_curve(ret); ru=ew_curve(rule); m=bh.notna()&ru.notna(); bh,ru=bh[m],ru[m]
posm=pos[m.reindex(pos.index,fill_value=False)] if False else pos.loc[bh.index]

print('=== [8] 현금수익률·거래비용 반영 ===')
report('기본(현금 0%, 비용 0)', ru, bh)
cashw=(1-posm.mean(axis=1))
ru_c=ru+cashw*CASH_M
report(f'현금 연{CASH_ANN*100:.1f}% 가산', ru_c, bh)
for cst in (0.001,0.002,0.003):
    r2,p2,u2=panel_rule(piv,10,cst); b2=ew_curve(r2); a2=ew_curve(u2)
    mm=b2.notna()&a2.notna()
    report(f'현금0%+왕복비용 {cst*200:.1f}bp', a2[mm], b2[mm])
print()
print('=== [9] 변동성 정합 비교 (규칙을 B&H와 같은 변동성으로 레버리지) ===')
k=bh.std()/ru.std()
rul=ru*k
sa=series_stats(rul.values); sb=series_stats(bh.values)
print(f"레버리지 배수 {k:.2f}x  →  규칙 CAGR {sa['cagr']*100:.2f}% MDD {sa['mdd']*100:.2f}% Sh {sa['sharpe']:.2f}  vs  B&H {sb['cagr']*100:.2f}% / {sb['mdd']*100:.2f}% / {sb['sharpe']:.2f}")
print("  ※ 영상은 레버리지 사용을 명시적으로 금지한다 — 참고용 계산")
print()
print('=== [10] 시가총액 구간별 (현재 시총 순위 기준, 사후정보 주의) ===')
uni=pd.read_csv('universe.csv',dtype={'code':str}).set_index('code')
for lo,hi,nm in ((1,100,'초대형 1~100위'),(101,250,'대형 101~250위'),(251,400,'중형 251위~')):
    cols=[c for c in piv.columns if lo<=uni['rank'].get(c,9999)<=hi]
    if len(cols)<10: continue
    r2=ret[cols]; u2=rule[cols]
    b2=ew_curve(r2); a2=ew_curve(u2); mm=b2.notna()&a2.notna()
    report(f'{nm} (n={len(cols)})', a2[mm], b2[mm])
print()
print('=== [11] 지수 (생존편의 없음) — 영상이 직접 보여준 대상 ===')
idx=load_monthly('idx_monthly.csv'); idx['ym']=idx['date'].dt.to_period('M')
idx=idx.sort_values(['code','ym','date']).drop_duplicates(['code','ym'],keep='last')
ip=idx.pivot(index='ym',columns='code',values='close').sort_index()
for c in ip.columns:
    s=ip[c].dropna()
    ma=s.rolling(10).mean(); sig=(s>ma).astype(float).shift(1)
    r=s.pct_change(); d=pd.DataFrame({'r':r,'p':sig}).dropna()
    report(f'{c} 지수 ({d.index[0]}~{d.index[-1]})', d['p']*d['r'], d['r'], f"노출 {d['p'].mean()*100:.0f}%")
print()
print('=== [12] 미국 대형주 70종 (영상: 미장에서 더 잘 맞는다) ===')
us=pd.read_csv('us_monthly.csv',dtype={'code':str})
us['ym']=pd.to_datetime(us['date'].astype(str),format='%Y%m%d').dt.to_period('M')
us=us.sort_values(['code','ym']).drop_duplicates(['code','ym'],keep='last')
up=us.pivot(index='ym',columns='code',values='close').sort_index()
up=up[[c for c in up.columns if up[c].notna().sum()>=60]]
ur,upos,uru=panel_rule(up,10,0.0)
b3=ew_curve(ur); a3=ew_curve(uru); mm=b3.notna()&a3.notna()
report(f'미국 {up.shape[1]}종 동일가중', a3[mm], b3[mm], f"노출 {upos.mean(axis=1)[mm].mean()*100:.0f}%")
for t in ['SPY','QQQ','DASH','NFLX']:
    if t not in up.columns: continue
    s=up[t].dropna(); ma=s.rolling(10).mean(); sig=(s>ma).astype(float).shift(1)
    r=s.pct_change(); d=pd.DataFrame({'r':r,'p':sig}).dropna()
    report(f'  {t} ({d.index[0]}~{d.index[-1]})', d['p']*d['r'], d['r'], f"노출 {d['p'].mean()*100:.0f}%")

# ================= bt3.py =================
# -*- coding: utf-8 -*-
import numpy as np, pandas as pd
from engine import load_monthly, series_stats
from bt_ma10m import prep, panel_rule, ew_curve

def st(x): return series_stats(np.asarray(x,dtype=float))
def line(nm,ru,bh,extra=''):
    a=st(ru); b=st(bh); e=np.asarray(ru)-np.asarray(bh)
    t=e.mean()/e.std(ddof=1)*np.sqrt(len(e)) if e.std(ddof=1)>0 else np.nan
    print(f"{nm:30s} CAGR {a['cagr']*100:6.2f}% MDD {a['mdd']*100:7.2f}% Sh {a['sharpe']:4.2f} | 기준 {b['cagr']*100:6.2f}% / {b['mdd']*100:7.2f}% / {b['sharpe']:4.2f} | 초과 {e.mean()*100:+.3f}%p t={t:5.2f} {extra}")

print('=== [13] 지수 강건성 (KOSPI 1995~2026, 379개월) ===')
idx=load_monthly('idx_monthly.csv'); idx['ym']=idx['date'].dt.to_period('M')
idx=idx.sort_values(['code','ym','date']).drop_duplicates(['code','ym'],keep='last')
ip=idx.pivot(index='ym',columns='code',values='close').sort_index()
for c in ['KOSPI','KOSDAQ']:
    s=ip[c].dropna()
    print(f'--- {c} ---')
    for lb in [6,8,10,12,15,18,24]:
        ma=s.rolling(lb).mean(); p=(s>ma).astype(float).shift(1)
        r=s.pct_change(); d=pd.DataFrame({'r':r,'p':p}).dropna()
        a=st(d['p']*d['r']); b=st(d['r']); e=(d['p']*d['r']-d['r'])
        print(f"  룩백{lb:>3}  CAGR {a['cagr']*100:6.2f}%  MDD {a['mdd']*100:7.2f}%  Sh {a['sharpe']:4.2f}  월초과 {e.mean()*100:+.3f}%p  노출 {d['p'].mean()*100:.0f}%")
    ma=s.rolling(10).mean(); p=(s>ma).astype(float).shift(1)
    r=s.pct_change(); d=pd.DataFrame({'r':r,'p':p}).dropna()
    e=(d['p']*d['r']-d['r']).sort_values(ascending=False)
    print('  R5 꼬리: ' + '  '.join(f"상위{k}제거 {e.iloc[k:].mean()*100:+.3f}" for k in [0,1,3,5,10]) + f"  중앙값 {e.median()*100:+.3f}")
    n=len(d); fs=np.array_split(np.arange(n),3)
    print('  fold: ' + '  '.join(f"f{i+1} {(d['p'].iloc[ix]*d['r'].iloc[ix]-d['r'].iloc[ix]).mean()*100:+.3f}%p" for i,ix in enumerate(fs)))
print()
print('=== [14] 거래량 확인 변형 (돌파월 거래량 >= 직전 10개월 평균 x k) ===')
df=load_monthly('monthly.csv'); df=df[df['date']>='2000-01-01']
df['ym']=df['date'].dt.to_period('M')
df=df.sort_values(['code','ym','date']).drop_duplicates(['code','ym'],keep='last')
pc=df.pivot(index='ym',columns='code',values='close').sort_index()
pv=df.pivot(index='ym',columns='code',values='vol').sort_index()
keep=[c for c in pc.columns if pc[c].notna().sum()>=60]
pc,pv=pc[keep],pv[keep]
ma=pc.rolling(10).mean(); base=(pc>ma)
vavg=pv.rolling(10).mean()
ret=pc.pct_change()
for k in [0.0,1.0,1.2,1.5]:
    sig=base.copy().astype(float)
    if k>0:
        cross=base & (~base.shift(1).fillna(False))          # 돌파 시점
        ok=(pv>=vavg*k)
        s=sig.copy()
        # 돌파월에 거래량 미달이면 그 진입은 무시(다음 돌파까지 관망)
        arr=s.values.copy(); C=cross.values; O=ok.values
        for j in range(arr.shape[1]):
            on=False
            for i in range(arr.shape[0]):
                if np.isnan(arr[i,j]): continue
                if C[i,j]:
                    on = bool(O[i,j]) if O[i,j]==O[i,j] else False
                elif arr[i,j]==0: on=False
                arr[i,j]=1.0 if (on and arr[i,j]==1.0) else 0.0
        sig=pd.DataFrame(arr,index=s.index,columns=s.columns)
    p=sig.shift(1)
    v=p.notna()&ret.notna()
    b=ew_curve(ret.where(v)); a=ew_curve((p*ret).where(v)); m=b.notna()&a.notna()
    line(f'거래량배수 {k if k else "필터없음"}', a[m], b[m], f"노출 {p.where(v).mean(axis=1)[m].mean()*100:.0f}%")
print()
print('=== [15] 시장 게이트로 사용 (KOSPI 월봉10이평 상태 → 익월 한국주식 동일가중) ===')
piv=prep(); ret2,pos2,_=panel_rule(piv,10,0.0)
bh=ew_curve(ret2)
s=ip['KOSPI'].dropna(); ma=s.rolling(10).mean(); g=(s>ma).astype(float).shift(1)
d=pd.DataFrame({'bh':bh,'g':g}).dropna()
line('KOSPI게이트 ON만 보유', d['g']*d['bh'], d['bh'], f"노출 {d['g'].mean()*100:.0f}%")
line('게이트 OFF시 비중 1/2', (d['g']+(1-d['g'])*0.5)*d['bh'], d['bh'])
print(f"  게이트 ON 월 평균 {d['bh'][d['g']==1].mean()*100:+.2f}% (n={(d['g']==1).sum()})  OFF 월 평균 {d['bh'][d['g']==0].mean()*100:+.2f}% (n={(d['g']==0).sum()})")
diff=d['bh'][d['g']==1].mean()-d['bh'][d['g']==0].mean()
from math import sqrt
x=d['bh'][d['g']==1]; y=d['bh'][d['g']==0]
tt=diff/sqrt(x.var(ddof=1)/len(x)+y.var(ddof=1)/len(y))
print(f"  ON−OFF 차 {diff*100:+.2f}%p, t={tt:.2f}")

# ================= bt4.py =================
# -*- coding: utf-8 -*-
import numpy as np, pandas as pd
from engine import series_stats
from bt_ma10m import prep, panel_rule, ew_curve
def st(x): return series_stats(np.asarray(x,float))
piv=prep(); ret,pos,rule=panel_rule(piv,10,0.0)
bh=ew_curve(ret); ru=ew_curve(rule); m=bh.notna()&ru.notna(); bh,ru=bh[m],ru[m]
expo=pos.loc[bh.index].mean(axis=1).mean()
print('=== [16] ★ 핵심 대조군 — 정적 비중 vs 규칙 (같은 평균 노출) ===')
a=st(ru); print(f"규칙(월봉10이평)     노출 {expo*100:.1f}%  CAGR {a['cagr']*100:6.2f}%  MDD {a['mdd']*100:7.2f}%  Sharpe {a['sharpe']:.2f}")
for w in [expo, 0.5, 0.6, 0.7, 1.0]:
    s=st(bh.values*w)
    print(f"정적 {w*100:4.1f}% 주식+현금0%   CAGR {s['cagr']*100:6.2f}%  MDD {s['mdd']*100:7.2f}%  Sharpe {s['sharpe']:.2f}")
print()
print('=== [17] MDD 감소의 출처 분해 ===')
sw=st(bh.values*expo)
print(f"B&H MDD                 {st(bh.values)['mdd']*100:7.2f}%")
print(f"정적 {expo*100:.0f}% 비중 MDD        {sw['mdd']*100:7.2f}%   ← 단순히 절반만 들고 있어서 줄어드는 몫")
print(f"규칙 MDD                {a['mdd']*100:7.2f}%   ← 신호가 추가로 줄인 몫 = {(a['mdd']-sw['mdd'])*100:+.2f}%p")
print()
print('=== [18] 연도별 규칙−B&H 초과 (동일가중, %p/년) ===')
yr=pd.DataFrame({'ru':ru,'bh':bh}); yr.index=yr.index.to_timestamp()
g=yr.groupby(yr.index.year).apply(lambda d: pd.Series({'ru':(1+d.ru).prod()-1,'bh':(1+d.bh).prod()-1}))
g['ex']=g.ru-g.bh
print('  ' + '  '.join(f"{i}:{v*100:+.0f}" for i,v in g['ex'].items()))
print(f"  규칙이 이긴 해 {(g.ex>0).sum()}/{len(g)}년")

# ================= bt5.py =================
import numpy as np, pandas as pd, json
from engine import series_stats
from bt_ma10m import prep, panel_rule, ew_curve
piv=prep(); ret,pos,rule=panel_rule(piv,10,0.0)
bh=ew_curve(ret); ru=ew_curve(rule); m=bh.notna()&ru.notna(); bh,ru=bh[m],ru[m]
out={}
print('=== [19] 급락 국면별 방어력 (동일가중 누적) ===')
per=[('2008 금융위기','2008-06','2008-11'),('2011 유럽위기','2011-08','2011-09'),
     ('2018 조정','2018-10','2018-12'),('2020 코로나','2020-02','2020-03'),
     ('2022 베어','2022-01','2022-09'),('2026-07 급락','2026-07','2026-08')]
rowsA=[]
for nm,a,b in per:
    sl=slice(pd.Period(a,'M'),pd.Period(b,'M'))
    x=(1+ru.loc[sl]).prod()-1; y=(1+bh.loc[sl]).prod()-1
    print(f"{nm:14s} 규칙 {x*100:+7.2f}%   B&H {y*100:+7.2f}%   방어 {(x-y)*100:+6.2f}%p")
    rowsA.append((nm,x,y))
out['crash']=rowsA
print()
print('=== [20] 거래 단위 통계 (종목별 진입~청산) ===')
tr=[]
for c in piv.columns:
    p=pos[c].dropna(); r=ret[c].reindex(p.index)
    cur=None
    for d,v in p.items():
        if v==1:
            if cur is None: cur=[d,1.0]
            cur[1]*= (1+ (r.loc[d] if r.loc[d]==r.loc[d] else 0))
        else:
            if cur is not None: tr.append(cur[1]-1); cur=None
    if cur is not None: tr.append(cur[1]-1)
tr=np.array(tr)
print(f"거래 {len(tr):,}건  평균 {tr.mean()*100:+.2f}%  중앙 {np.median(tr)*100:+.2f}%  승률 {(tr>0).mean()*100:.1f}%")
print(f"  5%분위 {np.percentile(tr,5)*100:+.1f}%  95%분위 {np.percentile(tr,95)*100:+.1f}%  최악 {tr.min()*100:+.1f}%  최선 {tr.max()*100:+.1f}%")
print(f"  상위 5% 거래가 총이익에서 차지하는 비중 {np.sort(tr)[-int(len(tr)*0.05):].sum()/tr[tr>0].sum()*100:.1f}%")
out['trades']=dict(n=int(len(tr)),mean=float(tr.mean()),med=float(np.median(tr)),win=float((tr>0).mean()))
json.dump(out,open('extra.json','w'),default=str)

# ================= verify.py =================
# -*- coding: utf-8 -*-
"""독립 재계산 (V1): pandas 패널을 쓰지 않고 순수 python 루프로 동일 수치를 재현한다."""
import csv, math
from collections import defaultdict
rows=defaultdict(dict)
for r in csv.DictReader(open('monthly.csv',encoding='utf-8')):
    d=r['date']
    if len(d)!=8: continue
    ym=d[:6]
    if ym<'200001': continue
    try: c=float(r['close'])
    except: continue
    if c<=0: continue
    # 같은 (code,ym)은 마지막 날짜로
    k=(r['code'],ym)
    prev=rows[r['code']].get(ym)
    if prev is None or d>=prev[0]: rows[r['code']][ym]=(d,c)
codes=[c for c in rows if len(rows[c])>=60]
allym=sorted({y for c in codes for y in rows[c]})
LB=10
port_bh=defaultdict(list); port_ru=defaultdict(list); expo=defaultdict(list)
for c in codes:
    ys=sorted(rows[c]); px=[rows[c][y][1] for y in ys]
    for i in range(1,len(ys)):
        if i-1 < LB-1: continue                      # t-1 시점 MA 필요
        ma=sum(px[i-LB:i])/LB                        # t-1 종가까지 LB개
        sig=1.0 if px[i-1]>ma else 0.0
        r=px[i]/px[i-1]-1
        port_bh[ys[i]].append(r); port_ru[ys[i]].append(sig*r); expo[ys[i]].append(sig)
ym=sorted(y for y in port_bh if len(port_bh[y])>=5)
bh=[sum(port_bh[y])/len(port_bh[y]) for y in ym]
ru=[sum(port_ru[y])/len(port_ru[y]) for y in ym]
ex=[a-b for a,b in zip(ru,bh)]
def stats(rs):
    eq=1.0; peak=1.0; mdd=0.0
    for r in rs:
        eq*=(1+r); peak=max(peak,eq); mdd=min(mdd, eq/peak-1)
    yrs=len(rs)/12; cagr=eq**(1/yrs)-1
    mu=sum(rs)/len(rs); sd=math.sqrt(sum((x-mu)**2 for x in rs)/(len(rs)-1))
    return cagr, mdd, mu*12/(sd*math.sqrt(12))
m=sum(ex)/len(ex); sd=math.sqrt(sum((x-m)**2 for x in ex)/(len(ex)-1))
print(f"[V1 독립재계산] 종목 {len(codes)}  월수 {len(ym)}  {ym[0]}~{ym[-1]}")
print("규칙  CAGR %.2f%%  MDD %.2f%%  Sharpe %.2f"%tuple(x*100 if i<2 else x for i,x in enumerate(stats(ru))))
print("B&H   CAGR %.2f%%  MDD %.2f%%  Sharpe %.2f"%tuple(x*100 if i<2 else x for i,x in enumerate(stats(bh))))
print("월평균 초과 %+.4f%%p  t=%.2f  평균노출 %.1f%%"%(m*100, m/sd*math.sqrt(len(ex)),
      100*sum(sum(expo[y])/len(expo[y]) for y in ym)/len(ym)))
