"""섹터별 매수 조건식 차별화 검정 — 대표 ETF 4종(반도체·2차전지·은행·화장품) + 섹터 풀 보조.
전반부(2019-04~2022-12) 최적화 → 후반부(2023-01~2026-09) OOS 검증. 공통식(현행 EG·v1.2)과 비교."""
import os,pickle,itertools,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
O,H,L,C,V,MA20,MA60,VA,dates,codes,names,secs=[d[k] for k in ['O','H','L','C','V','MA20','MA60','VA','dates','codes','names','secs']]
M,N=C.shape; Cf=pd.DataFrame(C.T).ffill().values.T
def sh(x,k):
    y=np.full_like(x,np.nan); y[:,k:]=x[:,:-k]; return y
rmin=lambda x,w: pd.DataFrame(x.T).rolling(w,min_periods=w).min().values.T
L5,L10=rmin(L,5),rmin(L,10)
core=(C>=MA20)&(MA20>sh(MA20,1))&(C>MA60)&(MA60>=sh(MA60,5))
RET={h:np.full((M,N),np.nan) for h in (10,20,30)}
for h in RET: RET[h][:,:-h]=Cf[:,h:]/Cf[:,:-h]-1
SPLIT=np.searchsorted(dates,20230101)
grid=list(itertools.product([5,10],[1.00,1.02,1.05],[1.0,1.3,1.5,2.0],[0.5,0.6,0.7],[True,False],[True,False],[10,20,30]))
def signal(pw,pk,vm,cp,red,eng):
    pull=(L5 if pw==5 else L10)<=MA20*pk
    s=core&pull&(C>O)&(C>=L+(H-L)*cp)&(V>=VA*vm)
    if red: s=s&(sh(C,1)<sh(O,1))
    if eng: s=s&(C>=sh(O,1))
    return np.nan_to_num(s,nan=False)
def ev(s,rows,h,lo,hi):
    mask=np.zeros(N,bool); mask[lo:hi]=True
    r=RET[h][np.ix_(rows,np.arange(N))][ :, mask][s[np.ix_(rows,np.arange(N))][:,mask]]
    r=r[~np.isnan(r)]
    return r
COMMON=dict(cur=(5,1.02,1.3,0.6,True,True,20), v12=(10,1.02,1.3,0.6,True,True,20))
REPS={'반도체':'091160','2차전지':'305720','은행금융':'091170','화장품':'228790'}
out=[]
for sec,rep in REPS.items():
    rows_rep=[codes.index(rep)]; rows_pool=[i for i in range(M) if secs[i]==sec]
    for label,rows in [('대표 '+names[rep],rows_rep),(f'섹터 풀({len(rows_pool)}종)',rows_pool)]:
        res=[]
        for g in grid:
            s=signal(*g[:6]); h=g[6]
            a=ev(s,rows,h,60,SPLIT-h)
            if len(a)<8: continue
            t=a.mean()/a.std()*np.sqrt(len(a)) if a.std()>0 else 0
            res.append((t,a.mean(),len(a),g))
        res.sort(key=lambda x:-x[0]); best=res[0] if res else None
        line=f'\n== {sec} · {label} =='
        print(line)
        if best is None: print('  전반부 신호 부족'); continue
        g=best[3]; s=signal(*g[:6]); h=g[6]
        oos=ev(s,rows,h,SPLIT,N-h)
        print(f'  전반부 최적: 눌림{g[0]}일×{g[1]:.2f} 거래량{g[2]}배 종가위치{g[3]} 전일음봉{"O" if g[4] else "X"} 장악{"O" if g[5] else "X"} 보유{g[6]}일'
              f' | IS n={best[2]} 평균 {best[1]*100:+.2f}%/{h}일 t={best[0]:.2f}')
        print(f'  → 후반부 OOS: n={len(oos)} 평균 {oos.mean()*100 if len(oos) else 0:+.2f}%/{h}일 승률 {(oos>0).mean()*100 if len(oos) else 0:.1f}%'
              f'  (일당 {oos.mean()/h*1e4 if len(oos) else 0:.1f}bp)')
        for cn,cg in COMMON.items():
            s=signal(*cg[:6]); a=ev(s,rows,20,SPLIT,N-20); b=ev(s,rows,20,60,SPLIT-20)
            print(f'  공통식 {cn:4s}: 전반부 n={len(b)} {b.mean()*100 if len(b) else 0:+.2f}%  후반부 n={len(a)} {a.mean()*100 if len(a) else 0:+.2f}% 승률 {(a>0).mean()*100 if len(a) else 0:.1f}% (일당 {a.mean()/20*1e4 if len(a) else 0:.1f}bp)')
        # 상위 5 조합의 OOS 평균(최적 1개의 우연성 완화)
        top5=[]
        for t,mn,n,g in res[:5]:
            s=signal(*g[:6]); o=ev(s,rows,g[6],SPLIT,N-g[6]); top5.append(o.mean()/g[6]*1e4 if len(o) else np.nan)
        print(f'  전반부 상위5 조합의 후반부 일당 평균: {np.nanmean(top5):.1f}bp  (개별 {", ".join(f"{x:.0f}" for x in top5)})')
        # 후반부 자체 최적(사후) — 참고용
        res2=[]
        for g in grid:
            s=signal(*g[:6]); a=ev(s,rows,g[6],SPLIT,N-g[6])
            if len(a)>=8: res2.append((a.mean()/a.std()*np.sqrt(len(a)) if a.std()>0 else 0,a.mean(),len(a),g))
        res2.sort(key=lambda x:-x[0])
        if res2:
            t,mn,n,g=res2[0]; print(f'  (참고) 후반부 사후 최적: 눌림{g[0]}×{g[1]:.2f} 거래량{g[2]} 위치{g[3]} 음봉{"O" if g[4] else "X"} 장악{"O" if g[5] else "X"} 보유{g[6]} n={n} {mn*100:+.2f}% — 전반부 최적과 {"동일" if g==best[3] else "다름"}')

print('\n=== 안정성 검사: 공통식(v1.2) 신호의 섹터별 보유기간 10/20/30일 수익 — 전반부 vs 후반부 (섹터 풀) ===')
s=signal(*COMMON['v12'][:6])
for sec in REPS:
    rows=[i for i in range(M) if secs[i]==sec]
    line=f'{sec:6s}'
    for lo,hi,tag in [(60,SPLIT,'전'),(SPLIT,N,'후')]:
        vals=[]
        for h in (10,20,30):
            a=ev(s,rows,h,lo,hi-h); vals.append(f'{h}일 {a.mean()*100 if len(a) else float("nan"):+5.2f}%(n{len(a)})')
        line+=f' | {tag}: '+' '.join(vals)
    print(line)
print('=== 거래량 배수 축만: 섹터별 1.0/1.3/2.0 (v1.2 나머지 고정, 20일) 전/후 ===')
for sec in REPS:
    rows=[i for i in range(M) if secs[i]==sec]; line=f'{sec:6s}'
    for lo,hi,tag in [(60,SPLIT,'전'),(SPLIT,N,'후')]:
        vals=[]
        for vm in (1.0,1.3,2.0):
            a=ev(signal(10,1.02,vm,0.6,True,True),rows,20,lo,hi-20); vals.append(f'{vm}배 {a.mean()*100 if len(a) else float("nan"):+5.2f}%(n{len(a)})')
        line+=f' | {tag}: '+' '.join(vals)
    print(line)
