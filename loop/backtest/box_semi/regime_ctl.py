import warnings;warnings.filterwarnings('ignore')
from regime_bt import *
from regime import I
S=get('091160')
def allctl(S,idx,tr,reps=500):   # 국면 무관, 전체 기간 무작위 진입(같은 보유일수)
    c=S.close.reindex(idx).values;o=S.open.reindex(idx).values;n=len(idx);durs=[b-a for a,b in tr];out=[]
    for _ in range(reps):
        tot=[]
        for dl in durs:
            a=rng.integers(1,n-dl-1);b=a+dl;tot.append(o[b]/o[a]-1)
        out.append(np.mean(tot))
    return np.array(out)
cands={'ADX<20':I.adx<20,'ER20<0.3':I.er20<0.3,'복합2of3':((I.adx<20).astype(int)+(I.chop14>61.8).astype(int)+(I.er20<0.3).astype(int))>=2,'60일폭&평탄':regime()}
for k,m in cands.items():
    r,tr,rets,idx,rg=run(S,m,20,.2,.8,True);rets=np.array(rets)
    c1=randctl(S,idx,rg,tr);c2=allctl(S,idx,tr)
    folds=[]
    for a,b in [(20200401,20220531),(20220601,20240630),(20240701,20261231)]:
        sel=[x for (s,_),x in zip(tr,rets) if a<=idx[s]<=b];folds.append((len(sel),round(np.mean(sel)*100,2) if sel else None))
    srt=np.sort(rets)[::-1]
    print(f'\n[{k}] 거래 {len(rets)} 평균 {rets.mean()*100:+.2f}% 평균보유 {np.mean([b-a for a,b in tr]):.1f}일')
    print(f'  대조① 국면 안 무작위 진입: 중앙 {np.median(c1)*100:+.2f}% p={np.mean(c1>=rets.mean()):.3f}')
    print(f'  대조② 기간 전체 무작위 진입(=그냥 들고 있기): 중앙 {np.median(c2)*100:+.2f}% p={np.mean(c2>=rets.mean()):.3f}')
    print(f'  fold(거래수, 건당평균): {folds}')
    print(f'  R5 상위1/3건 제거 평균: {srt[1:].mean()*100:+.2f} / {srt[3:].mean()*100:+.2f}')
# R1 고원 — ADX 임계 · 채널 L · lo/hi
print('\nR1 ADX 임계×L (건당평균%, 거래수)')
for th in [15,18,20,22,25]:
    line=[]
    for L in [10,20,40]:
        r,tr,rets,idx,rg=run(S,I.adx<th,L,.2,.8,True);line.append(f'L{L}: {np.mean(rets)*100:+.2f}({len(rets)})')
    print(f'  ADX<{th}: '+'  '.join(line))
for lo,hi in [(.1,.9),(.2,.8),(.3,.7)]:
    r,tr,rets,idx,rg=run(S,I.adx<20,20,lo,hi,True);print(f'  ADX<20 L20 {lo}/{hi}: {np.mean(rets)*100:+.2f}({len(rets)})')
r,tr,rets,idx,rg=run(S,I.adx<20,20,.2,.8,False);print(f'  ADX<20 L20 국면이탈 청산 안함: {np.mean(rets)*100:+.2f}({len(rets)})')
for code in ['396500','395160']:
    S2=get(code);r,tr,rets,idx,rg=run(S2,I.adx<20,20,.2,.8,True);c2=allctl(S2,idx,tr)
    print(f'  R3 {SEMI[code]} ADX<20: {np.mean(rets)*100:+.2f}%({len(rets)}) vs 그냥보유 대조 중앙 {np.median(c2)*100:+.2f}% p={np.mean(c2>=np.mean(rets)):.3f}')
