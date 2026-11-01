from regime_bt import *
S=get('091160');rows=[]
for W,wp,sl in itertools.product([40,60,90],[0.2,0.3,0.4],[0.01,0.02,0.03]):
    reg=regime(W,wp,sl)
    for L,(lo,hi),ex in itertools.product([10,20,40],[(.2,.8),(.1,.9),(.3,.7)],[True,False]):
        r,tr,rets,idx,rg=run(S,reg,L,lo,hi,ex)
        if len(rets)==0: continue
        rows.append(dict(W=W,wp=wp,sl=sl,L=L,lo=lo,ex=ex,ntr=len(rets),mean=np.mean(rets)*100,med=np.median(rets)*100,epi=episodes(reg),cagr=stats(r)[0]))
G=pd.DataFrame(rows);G.to_csv('regime_grid.csv',index=False)
print('KODEX반도체 · 코스피 박스 국면 × 코스피 채널 매매 · 변형',len(G))
print('거래수 중앙',G.ntr.median(),'· 최대',G.ntr.max(),'· 에피소드 중앙',G.epi.median())
print('건당 평균: 중앙 %.2f%% · 양수 비율 %.0f%% · 상위10%% %.2f · 하위10%% %.2f'%(G['mean'].median(),(G['mean']>0).mean()*100,G['mean'].quantile(.9),G['mean'].quantile(.1)))
print('건당 중앙값 양수 비율 %.0f%%'%((G.med>0).mean()*100))
print('\n축별 평균(건당 평균 %):')
for k in ['W','wp','sl','L','lo','ex']: print(k,G.groupby(k)['mean'].mean().round(2).to_dict())
print('\n거래 15건 이상 변형만:',len(G[G.ntr>=15]),'개, 건당 평균 중앙',round(G[G.ntr>=15]['mean'].median(),2))
# 국면 기간 반도체 그냥 보유 vs 전체
reg=regime();idx=S.index[S.index>=20200401];rg=reg.reindex(idx).fillna(False)
d=S.close.pct_change().reindex(idx)
print('\n반도체 일평균 수익: 박스국면일 %.3f%% vs 그 외 %.3f%%'%(d.shift(-1)[rg].mean()*100,d.shift(-1)[~rg].mean()*100))
# 다른 정의(ADX 등)로 같은 매매
from regime import DEF
print('\n다른 박스 정의로 같은 매매(L20,0.2/0.8,국면이탈시 청산):')
for k,m in DEF.items():
    reg2=m.reindex(K.index).fillna(False)
    r,tr,rets,idx2,rg2=run(S,reg2,20,.2,.8,True)
    print(f'  {k:34s} 거래 {len(rets):3d} 건당 평균 {np.mean(rets)*100:+.2f}% 중앙 {np.median(rets)*100:+.2f}% 승률 {np.mean(np.array(rets)>0)*100:.0f}% CAGR {stats(r)[0]:+.1f}')
