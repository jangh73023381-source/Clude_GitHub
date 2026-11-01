# 전일 미국 10년물 일변화(bp) → 한국 D(+1,+2,+3) 섹터 수익. SOX 동시 충격을 통제한 편회귀 (2026-10-03)
import pandas as pd, numpy as np, json
P=pd.read_pickle('/tmp/rates_panel.pkl'); C,R,sec=P['C'],P['R'],P['sec']
def us(f,col='close'):
    s=pd.read_csv(f,dtype={'date':str}).set_index('date')[col]; return s[~s.index.duplicated()]
tnx=us('TNX.csv'); sox=us('../wallst/SOX.csv')
dt=(tnx.diff()*100)                      # bp
sx=sox.pct_change()*100
D=R.index
def lag(s):
    idx=np.searchsorted(s.index.values,D.values,side='left')-1
    return pd.Series(np.where(idx>=0,s.values[np.clip(idx,0,None)],np.nan),index=D)
# 미국 연휴 등으로 같은 미국일이 두 한국일에 붙는 경우 첫 한국일만 쓴다
last_us=pd.Series(np.searchsorted(tnx.index.values,D.values,side='left')-1,index=D)
first=~last_us.duplicated()
X=pd.DataFrame({'dt':lag(dt),'sox':lag(sx)})[first].dropna()
secs=[s for s,n in sec.value_counts().items() if n>=2 and s!='기타']
SR=pd.DataFrame({s:R[sec[sec==s].index].mean(axis=1) for s in secs}); SR['KODEX200']=R['069500']
def ols(y,X):
    a=pd.concat([y,X],axis=1).dropna(); Y=a.iloc[:,0].values; Z=np.column_stack([np.ones(len(a)),a.iloc[:,1:].values])
    b,*_=np.linalg.lstsq(Z,Y,rcond=None); e=Y-Z@b
    V=np.linalg.inv(Z.T@Z)*(e@e/(len(Y)-Z.shape[1])); return b,np.sqrt(np.diag(V)),len(Y)
bins=[-99,-10,-3,3,10,99]; lab=['≤-10bp','-10~-3','±3','+3~+10','≥+10bp']
X['bk']=pd.cut(X.dt,bins,labels=lab)
out=[]; buck={}
for s in ['KODEX200']+secs:
    row={'sector':s}
    for h in [0,1,2]:                    # h=0: 미국 다음 한국 첫날(D+1) / h=1,2: 그 다음 날
        y=SR[s].shift(-h).loc[X.index]
        b,se,n=ols(y,X[['dt','sox']])
        row[f'b_dt_h{h}']=round(b[1]*10,3); row[f't_dt_h{h}']=round(b[1]/se[1],2)   # 10bp당 %
        if h==0: row['b_sox']=round(b[2],3)
    g=SR[s].loc[X.index].groupby(X.bk,observed=True)
    buck[s]={k:[round(v,3),int(c)] for (k,v),c in zip(g.mean().items(),g.count())}
    out.append(row)
T=pd.DataFrame(out); T.to_csv('shock_partial.csv',index=False)
# 연도별 안정성: KODEX200 · 반도체 · 2차전지 · 미국지수 h0 계수
yr={}
for s in ['KODEX200','반도체','2차전지','미국지수','바이오','은행금융','채권']:
    yr[s]={}
    for y_ in sorted(set(i[:4] for i in X.index)):
        idx=[i for i in X.index if i[:4]==y_]
        b,se,n=ols(SR[s].loc[idx],X.loc[idx,['dt','sox']]); yr[s][y_]=round(b[1]*10,2)
json.dump({'n':len(X),'corr_dt_sox':round(X.dt.corr(X.sox),3),'bucket_raw':buck,'yearly_b_per10bp':yr},open('shock_summary.json','w'),ensure_ascii=False,indent=1)
print('n',len(X),'corr(dTNX,SOX)',round(X.dt.corr(X.sox),3)); print(X.bk.value_counts().to_string())
print(T.sort_values('t_dt_h0').to_string(index=False))
print(json.dumps(yr,ensure_ascii=False))
print(json.dumps({k:buck[k] for k in ['KODEX200','반도체','은행금융','채권','미국지수']},ensure_ascii=False))
