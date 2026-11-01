import os,sys,json,random,statistics
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from bt_usx_exec_20260821 import load, NPICK
days=load()
def series(lam, shuffle=None):
    out=[]
    for day in days:
        sc=[]
        for mom,th,fcc,foc,fgap in day['rows']:
            s=mom
            if lam:
                t2=shuffle[th] if shuffle else th
                u=day['us'].get(t2)
                if u is not None: s=mom+lam*u
            sc.append((s,foc))
        sc.sort(reverse=True); t=sc[:NPICK]
        out.append(sum(x[1] for x in t)/len(t)-day['bo'])
    return out
def avg(x): return sum(x)/len(x)
def folds(x,k=3):
    n=len(x)//k; return [x[i*n:(i+1)*n if i<k-1 else len(x)] for i in range(k)]
b=series(0); print('B baseline %+.4f  fold %s'%(avg(b),' / '.join('%+.4f'%avg(f) for f in folds(b))))
print('=== B(시가→종가) lam 격자 ===')
best=None
for lam in (1,2,5,12,20,50,100,200):
    x=series(lam); f=[avg(g) for g in folds(x)]
    ok='통과' if all(fi>avg(bf) for fi,bf in zip(f,folds(b))) else '미달'
    print(f'  lam={lam:>4} full {avg(x):+.4f}  fold {f[0]:+.4f}/{f[1]:+.4f}/{f[2]:+.4f}  R2 {ok}')
    if lam==50: best=x
# R5 꼬리
d=[x-y for x,y in zip(best,b)]
s=sorted(d,reverse=True)
tot=sum(d)
print('\n=== R5 꼬리 기여도 (lam=50, B지표) ===')
for k in (1,3,5,10):
    print(f'  상위{k:>2}일 제거 평균 {(tot-sum(s[:k]))/(len(d)-k):+.4f}%p   (상위{k}일 기여 {sum(s[:k])/tot*100:.1f}%)')
print(f'  중앙값 차 {statistics.median(d):+.4f}%p')
# R4 플라시보 (테마 라벨 셔플)
ths=sorted({th for day in days for _,th,_,_,_ in day['rows']})
random.seed(20260821); null=[]
for _ in range(200):
    p=ths[:]; random.shuffle(p)
    null.append(avg(series(50, dict(zip(ths,p))))-avg(b))
null.sort(); real=avg(best)-avg(b)
p=sum(1 for x in null if x>=real)/len(null)
print(f'\n=== R4 플라시보 순열 200회 (B지표) ===\n  실제 Δ{real:+.4f}  귀무 평균 {avg(null):+.4f} · 95분위 {null[189]:+.4f} → 경험적 p={p:.3f}')
