# 금리 충격의 갭(전일종가→시가) vs 장중(시가→종가) 분해 (2026-10-03)
import pandas as pd, numpy as np, sys, os, json
LOOP=os.path.expanduser('~/mnt/loop'); sys.path.insert(0, os.path.join(LOOP,'references','scripts'))
import etf_sector_map as sm, universe_filters as uf
p=pd.read_csv(os.path.join(LOOP,'backtest','panel_ohlc_long.csv'),dtype={'code':str}); p['date']=p['date'].astype(str)
nm=p.groupby('code')['name'].last(); p=p[p.code.isin([c for c,n in nm.items() if uf.is_spot(n)])]
O=p.pivot(index='date',columns='code',values='open').sort_index(); C=p.pivot(index='date',columns='code',values='close').sort_index()
G=(O/C.shift(1)-1)*100; I=(C/O-1)*100; G=G.where(G.abs()<30); I=I.where(I.abs()<30)
sec=pd.Series({c:sm.sector(nm[c]) for c in C.columns})
def us(f):
    s=pd.read_csv(f,dtype={'date':str}).set_index('date')['close']; return s[~s.index.duplicated()]
tnx=us('TNX.csv'); sox=us('../wallst/SOX.csv'); D=C.index
def lag(s):
    idx=np.searchsorted(s.index.values,D.values,side='left')-1
    return pd.Series(np.where(idx>=0,s.values[np.clip(idx,0,None)],np.nan),index=D)
lu=pd.Series(np.searchsorted(tnx.index.values,D.values,side='left')-1,index=D)
X=pd.DataFrame({'dt':lag(tnx.diff()*100),'sox':lag(sox.pct_change()*100)})[~lu.duplicated()].dropna()
def ols(y):
    a=pd.concat([y,X],axis=1).dropna(); Y=a.iloc[:,0].values; Z=np.column_stack([np.ones(len(a)),a[['dt','sox']].values])
    b,*_=np.linalg.lstsq(Z,Y,rcond=None); e=Y-Z@b; V=np.linalg.inv(Z.T@Z)*(e@e/(len(Y)-3)); return b[1]*10,b[1]/np.sqrt(V[1,1])
rows=[]
for s in ['KODEX200','귀금속','채권','2차전지','바이오','IT테크','반도체','은행금융','미국지수']:
    cols=['069500'] if s=='KODEX200' else list(sec[sec==s].index)
    g,tg=ols(G[cols].mean(axis=1)); i,ti=ols(I[cols].mean(axis=1))
    rows.append(dict(sector=s,gap_per10bp=round(g,3),t_gap=round(tg,2),intraday_per10bp=round(i,3),t_intra=round(ti,2),gap_share=round(g/(g+i)*100,0) if (g+i)!=0 else None))
T=pd.DataFrame(rows); T.to_csv('shock_gap_split.csv',index=False); print(T.to_string(index=False))

# 안정성: 연도별 장중 계수 + 시차이동 대조군(금리 변화를 다른 날로 섞어 300회)
yi={}
for s,cols in [('KODEX200',['069500']),('반도체',list(sec[sec=='반도체'].index)),('2차전지',list(sec[sec=='2차전지'].index))]:
    y=I[cols].mean(axis=1); yi[s]={}
    for yr in sorted(set(i[:4] for i in X.index)):
        idx=[i for i in X.index if i[:4]==yr]; a=pd.concat([y.loc[idx],X.loc[idx]],axis=1).dropna()
        Z=np.column_stack([np.ones(len(a)),a[['dt','sox']].values]); b,*_=np.linalg.lstsq(Z,a.iloc[:,0].values,rcond=None); yi[s][yr]=round(b[1]*10,2)
print('연도별 장중(10bp당 %):',json.dumps(yi,ensure_ascii=False))
rng=np.random.default_rng(3); y=I['069500']; obs=ols(y)[1]; X0=X.copy(); null=[]
for k in rng.integers(20,len(X)-20,300):
    X['dt']=np.roll(X0.dt.values,k); null.append(ols(y)[1])
X['dt']=X0.dt
print('KODEX200 장중 t 관측',round(obs,2),'대조군 |t| 95%분위',round(np.quantile(np.abs(null),0.95),2),'p',np.mean(np.abs(null)>=abs(obs)))
