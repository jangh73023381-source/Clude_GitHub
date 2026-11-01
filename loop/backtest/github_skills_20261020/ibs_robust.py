import numpy as np, pandas as pd
from gh_stats import nw_se
exec(open('timing_pack.py').read().split("S = {}")[0])
def perf(r):
    eq = np.cumprod(1 + r); y = len(r) / 245
    return (eq[-1] ** (1 / y) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0
def run(code, lo, hi, mode='hold'):
    q=p[p.code==code].sort_values('date'); 
    if len(q)<600: return None
    o,h,l,c=(q[x].values.astype(float) for x in ('open','high','low','close'))
    rn=np.r_[c[1:]/c[:-1]-1,np.nan]; ib=(c-l)/(h-l+1e-12)
    pos=np.zeros(len(c)); st=0
    for t in range(len(c)):
        if mode=='1d': pos[t]=1 if ib[t]<lo else 0; continue
        if st==0 and ib[t]<lo: st=1
        elif st==1 and ib[t]>hi: st=0
        pos[t]=st
    s0=max(252,0); r=np.nan_to_num(pos[s0:-1]*rn[s0:-1]); b=rn[s0:-1]
    return perf(r), perf(b), pos[s0:-1].mean(), r, b, rn[s0:-1], pos[s0:-1], q.open.values[s0:], c[s0:]
print('== R1 고원 (KODEX200): 진입 IBS< lo / 청산 IBS> hi')
for lo in (.1,.15,.2,.25,.3):
    line=[]
    for hi in (.6,.7,.8,.9,'1d'):
        x=run('069500',lo,hi if hi!='1d' else 0,'1d' if hi=='1d' else 'hold'); (cg,md,sh)=x[0]
        line.append(f"{hi}: Sh {sh:.2f} CAGR {cg:.1f} MDD {md:.1f}")
    print(f'lo {lo}: '+' | '.join(line))
x=run('069500',.2,.8); r,b,pos=x[3],x[4],x[6]
inr=b[pos==1]; sr=np.sort(inr)[::-1]
print('\n== R5 (보유일 수익, %)', '평균',round(inr.mean()*100,3),'중앙',round(np.median(inr)*100,3),'상위3일 제거',round(sr[3:].mean()*100,3),'상위10일 제거',round(sr[10:].mean()*100,3),'| 전체일 평균',round(b.mean()*100,3))
# 갭(밤사이) vs 장중 분해: 보유일 수익 = 익일 시가갭 + 익일 장중
o=x[7]; c=x[8]; gap=o[1:]/c[:-1]-1; intra=c[1:]/o[1:]-1
print('보유일 갭 평균',round(gap[pos==1].mean()*100,3),'장중 평균',round(intra[pos==1].mean()*100,3),' | 비보유일 갭',round(gap[pos==0].mean()*100,3),'장중',round(intra[pos==0].mean()*100,3))
print('\n== R3 다른 ETF 재현 (IBS<0.2 → >0.8), 7년 데이터 있는 지수·섹터형')
nm=p.drop_duplicates('code',keep='last').set_index('code').name
cands=['102110','148020','229200','133690','091160','091170','139260','117700','305720','157490','143860','266420','244580','228790']
for cd in cands:
    if cd not in nm.index: continue
    y=run(cd,.2,.8)
    if y is None: continue
    (cg,md,sh),(bcg,bmd,bsh)=y[0],y[1]
    print(f'{cd} {nm[cd][:18]:18s} 전략 Sh {sh:.2f} CAGR {cg:5.1f} MDD {md:6.1f} | 보유 Sh {bsh:.2f} CAGR {bcg:5.1f} MDD {bmd:6.1f} | 노출 {y[2]*100:.0f}%')
