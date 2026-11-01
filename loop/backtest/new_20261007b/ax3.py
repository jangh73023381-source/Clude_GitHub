"""신축 3: 워크포워드 GBM(LightGBM) — 연 1회 재학습(확장창, 학습 타깃은 학습 종료일 이전에 완결된 OO 만), 순위 예측."""
from common import *
import lightgbm as lgb
E,base=setup(); res={}; C,R=E.C,E.R; V=E.P['volume']; T,N=C.shape
def lagm(X,k): return np.vstack([np.full((k,N),np.nan),X[:-k]])
feat={}
for k in (1,3,5,20,60,120): feat[f'm{k}']=(C/lagm(C,k)-1)*100
for k in (5,20,60): feat[f's{k}']=E.vol(k)
feat['vr']=V/pd.DataFrame(V).rolling(20,min_periods=10).mean().values
feat['hi250']=C/pd.DataFrame(C).rolling(250,min_periods=120).max().values-1
feat['max20']=pd.DataFrame(R).rolling(20,min_periods=15).max().values
feat['gap']=(E.O/lagm(C,1)-1)*100
names=list(feat); F=np.stack([feat[k] for k in names],-1)   # T,N,K
# 횡단면 순위 정규화(날짜별)
Fr=np.full_like(F,np.nan)
for t in range(T):
    m=E.ok[t]
    if m.sum()<10: continue
    for k in range(F.shape[2]):
        v=F[t,m,k]; Fr[t,m,k]=pd.Series(v).rank(pct=True).values
Y=E.fOO.copy()
Yr=np.full_like(Y,np.nan)
for t in range(T):
    m=E.ok[t]&~np.isnan(Y[t])
    if m.sum()>=10: Yr[t,m]=pd.Series(Y[t,m]).rank(pct=True).values-0.5
pred=np.full((T,N),np.nan); years=sorted(set(d[:4] for d in E.dates))
for y in years[2:]:
    te=[t for t,d in enumerate(E.dates) if d[:4]==y]; t0=te[0]
    tr=[t for t in range(60,t0-2)]          # OO(t) = open(t+2)/open(t+1) → t0-2 까지 완결
    X=Fr[tr].reshape(-1,len(names)); yy=Yr[tr].reshape(-1); m=~np.isnan(yy)&~np.isnan(X).all(1)
    mdl=lgb.LGBMRegressor(n_estimators=300,learning_rate=0.03,num_leaves=15,min_child_samples=200,subsample=0.8,subsample_freq=1,colsample_bytree=0.8,verbose=-1,random_state=0)
    mdl.fit(X[m],yy[m])
    pred[te]=mdl.predict(Fr[te].reshape(-1,len(names))).reshape(len(te),N)
    print(y,'학습',m.sum(),'중요도',dict(sorted(zip(names,mdl.feature_importances_),key=lambda x:-x[1])[:5]),flush=True)
pred[~E.ok]=np.nan
st=E.dates.index([d for d in E.dates if d[:4]==years[2]][0])
b2=E.run(lambda i,pl:E.sel_lv(i,pl),start=st)
def top(i,pl,c=None):
    c=pl if c is None else c; v=pred[i,c]; ok=~np.isnan(v)
    if ok.sum()<5: return E.sel_lv(i,pl)
    return c[ok][np.argsort(-v[ok])[:5]]
comp(b2,'10 GBM pool30 예측상위5',E.run(lambda i,pl:top(i,pl),start=st),res)
comp(b2,'10 GBM σ하위10→예측상위5',E.run(lambda i,pl:top(i,pl,E.sel_lv(i,pl,n=10)),start=st),res)
comp(b2,'10 GBM 전체유니버스 예측상위5',E.run(lambda i,pl:(lambda c:c[np.argsort(-pred[i,c])[:5]])(np.where(~np.isnan(pred[i]))[0]),start=st),res)
# 동N 무작위
rng=np.random.default_rng(3); bO=b2.set_index('date').OO; sims=[]
for s in range(200):
    df=E.run(lambda i,pl:rng.permutation(E.sel_lv(i,pl,n=10))[:5],start=st).set_index('date'); j=df.index.intersection(bO.index)
    sims.append(((df.OO[j]-bO[j]).mean(),prof(df.OO)['sharpe']))
sims=np.array(sims); r=res['10 GBM σ하위10→예측상위5']['OO']
res['10 GBM σ하위10→예측상위5']['null_p']=dict(dO=float(np.mean(sims[:,0]>=r['diff'])),shO=float(np.mean(sims[:,1]>=r['sh'])))
print('   ↳ 동N 무작위 p',res['10 GBM σ하위10→예측상위5']['null_p'],'귀무 평균 dOO',sims[:,0].mean())
np.save('gbm_pred.npy',pred)
json.dump(res,open('res_ax3.json','w'),default=float,indent=1); print('DONE')
