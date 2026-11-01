"""주기적 재최적화 워크포워드 — 고정 공통식 vs K개월마다 학습창에서 최적 조건식 재선정."""
import os,pickle,itertools,time,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
O,H,L,C,V,MA20,MA60,VA,dates=[d[k] for k in ['O','H','L','C','V','MA20','MA60','VA','dates']]
M,N=C.shape; Cf=pd.DataFrame(C.T).ffill().values.T; Bf=pd.Series(d['bench']).ffill().values
def sh(x,k):
    y=np.full_like(x,np.nan); y[:,k:]=x[:,:-k]; return y
rmin=lambda x,w: pd.DataFrame(x.T).rolling(w,min_periods=w).min().values.T
L5,L10=rmin(L,5),rmin(L,10)
core=(C>=MA20)&(MA20>sh(MA20,1))&(C>MA60)&(MA60>=sh(MA60,5))
RET={h:np.full((M,N),np.nan) for h in (10,20,30)}
for h in RET: RET[h][:,:-h]=Cf[:,h:]/Cf[:,:-h]-1
egrid=list(itertools.product([5,10],[1.00,1.02,1.05],[1.0,1.3,1.5,2.0],[0.5,0.6,0.7],[True,False],[True,False]))
t0=time.time(); SIG={}
red=(sh(C,1)<sh(O,1)); eng=(C>=sh(O,1)); green=(C>O)
for g in egrid:
    pw,pk,vm,cp,r,e=g
    s=core&((L5 if pw==5 else L10)<=MA20*pk)&green&(C>=L+(H-L)*cp)&(V>=VA*vm)
    if r: s=s&red
    if e: s=s&eng
    SIG[g]=np.nan_to_num(s,nan=False)
print(f'signal masks {len(SIG)} in {time.time()-t0:.0f}s')
CUR=(5,1.02,1.3,0.6,True,True); V12=(10,1.02,1.3,0.6,True,True)
ym=np.array([int(str(x)[:6]) for x in dates])
def month_idx(y,m): return np.searchsorted(ym,y*100+m)
def best_formula(lo,hi,minn=30):
    """[lo,hi) 구간에서 t-stat 최대 조합(보유 포함). 20일 수익은 hi-h 까지만 알 수 있음(룩어헤드 방지)."""
    best=None
    for g,s in SIG.items():
        for h in (10,20,30):
            m=s[:,lo:hi-h]; r=RET[h][:,lo:hi-h][m]
            if len(r)<minn: continue
            t=r.mean()/r.std()*np.sqrt(len(r)) if r.std()>0 else 0
            if best is None or t>best[0]: best=(t,g,h,len(r),r.mean())
    return best
def oos_trades(g,h,lo,hi):
    s=SIG[g][:,lo:hi]; idx=np.where(s); return [(m,lo+t,h) for m,t in zip(*idx)]
def sim(trades):
    """5슬롯, 점수 없이 도착 순(동일가중), 거래별 보유일 h."""
    byday={}
    for m,t,h in trades: byday.setdefault(t,[]).append((m,h))
    cash=1.0;pos={};eq=np.ones(N); t0=min(byday) if byday else N
    for t in range(t0,N):
        for m in list(pos):
            if t>=pos[m][1]: cash+=pos[m][0]*Cf[m,t]; del pos[m]
        eqv=cash+sum(u*Cf[m,t] for m,(u,_) in pos.items())
        for m,h in byday.get(t,[]):
            if m in pos or len(pos)>=5: continue
            amt=min(cash,eqv/5); pos[m]=(amt/Cf[m,t],t+h); cash-=amt
        eq[t]=cash+sum(u*Cf[m,t] for m,(u,_) in pos.items())
    return eq,t0
def stats(eq,a,b):
    e=eq[a:b+1]; r=np.diff(e)/e[:-1]; yrs=(b-a)/245
    return (e[-1]/e[0])**(1/yrs)-1,(e/np.maximum.accumulate(e)-1).min(),(r.mean()/r.std()*np.sqrt(245) if r.std()>0 else 0)
START_Y,START_M=2021,4   # OOS 시작(학습창 24개월 확보)
END=N
def run(period_m,window_m,label):
    trades=[]; picks=[]; y,m=START_Y,START_M
    while True:
        lo=month_idx(y,m)
        if lo>=N: break
        my=m+period_m; yy=y+(my-1)//12; mm=(my-1)%12+1
        hi=min(month_idx(yy,mm),N)
        if window_m is None: tlo=60
        else:
            wy=m-window_m; ty=y+(wy-1)//12; tm=(wy-1)%12+1; tlo=max(60,month_idx(ty,tm))
        b=best_formula(tlo,lo)
        if b is None: y,m=yy,mm; continue
        _,g,h,n,mn=b; picks.append((y*100+m,g,h,n,mn))
        trades+=oos_trades(g,h,lo,hi)
        y,m=yy,mm
    return trades,picks
res={}
s0=month_idx(START_Y,START_M)
def report(label,trades):
    r=np.array([RET[h][m,t] for m,t,h in trades if t+h<N]); hs=np.array([h for m,t,h in trades if t+h<N])
    eq,t0=sim(trades); st=stats(eq,s0,N-1)
    print(f'{label:34s} 거래 {len(r):5d} 평균 {r.mean()*100:+5.2f}% 승률 {(r>0).mean()*100:4.1f} 일당 {(r/hs).mean()*1e4:5.1f}bp | 5슬롯 CAGR {st[0]*100:5.1f}% MDD {st[1]*100:6.1f} Sharpe {st[2]:.2f}')
print(f'OOS 구간 {dates[s0]}~{dates[N-1]} · KODEX200 B&H CAGR {stats(Bf,s0,N-1)[0]*100:.1f}%')
for nm,g in [('고정 현행식(눌림5, 20일)',CUR),('고정 v1.2(눌림10, 20일)',V12)]:
    report(nm,oos_trades(g,20,s0,N))
for pm,wm,lab in [(2,24,'2개월 재최적화 · 24개월창'),(6,24,'6개월 재최적화 · 24개월창'),(12,24,'12개월 재최적화 · 24개월창'),
                  (2,36,'2개월 재최적화 · 36개월창'),(6,36,'6개월 재최적화 · 36개월창'),(12,36,'12개월 재최적화 · 36개월창'),
                  (6,None,'6개월 재최적화 · 누적창'),(12,None,'12개월 재최적화 · 누적창')]:
    t1=time.time(); trades,picks=run(pm,wm,lab); report(lab,trades)
    if pm in (6,12) and wm in (24,None):
        chg=sum(1 for i in range(1,len(picks)) if picks[i][1:3]!=picks[i-1][1:3])
        print(f'     선택 조건식 변경 {chg}/{len(picks)-1}회 · 예: '+' / '.join(f"{p[0]}:눌림{p[1][0]}×{p[1][1]:.2f} V{p[1][2]} 위치{p[1][3]} {'음봉' if p[1][4] else '-'}{'장악' if p[1][5] else '-'} {p[2]}일" for p in picks[::max(1,len(picks)//4)]))

print('\n=== 목적함수 변경: 평균수익(n≥50) / 하루당 수익(n≥50) ===')
def best_formula2(lo,hi,obj,minn=50):
    best=None
    for g,s in SIG.items():
        for h in (10,20,30):
            m=s[:,lo:hi-h]; r=RET[h][:,lo:hi-h][m]
            if len(r)<minn: continue
            v=r.mean() if obj=='mean' else r.mean()/h
            if best is None or v>best[0]: best=(v,g,h,len(r),r.mean())
    return best
def run2(period_m,window_m,obj):
    trades=[]; picks=[]; y,m=START_Y,START_M
    while True:
        lo=month_idx(y,m)
        if lo>=N: break
        my=m+period_m; yy=y+(my-1)//12; mm=(my-1)%12+1; hi=min(month_idx(yy,mm),N)
        wy=m-window_m; ty=y+(wy-1)//12; tm=(wy-1)%12+1; tlo=max(60,month_idx(ty,tm))
        b=best_formula2(tlo,lo,obj)
        if b: picks.append((y*100+m,b[1],b[2],b[3])); trades+=oos_trades(b[1],b[2],lo,hi)
        y,m=yy,mm
    return trades,picks
for obj in ('mean','perday'):
    for pm,wm in [(6,24),(12,24),(6,36),(12,36)]:
        trades,picks=run2(pm,wm,obj); report(f'{obj:6s} {pm:2d}개월 재최적화·{wm}개월창',trades)
        print('     '+' / '.join(f"{p[0]}:눌림{p[1][0]}×{p[1][1]:.2f} V{p[1][2]} 위치{p[1][3]} {'음봉' if p[1][4] else '-'}{'장악' if p[1][5] else '-'} {p[2]}일(n{p[3]})" for p in picks[::max(1,len(picks)//3)]))
