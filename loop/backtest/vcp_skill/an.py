import pickle, numpy as np, pandas as pd
rows=pickle.load(open('bt_1_0.pkl','rb'))+pickle.load(open('bt_1_1.pkl','rb'))
df=pd.DataFrame(rows,columns='date code ret kodex nh pf tt vcp state score mae'.split())
df['ret']*=100; df['kodex']*=100; df['mae']*=100
act=df.state.isin(['Pre-breakout','Breakout'])
G={'U 유니버스':df.ret.notna(),'NH 신고가근접(250일고점-5%)':df.nh==1,'PF 스킬 1차필터':df.pf==1,
   'TT 트렌드템플릿 통과':df.tt==1,'ACT TT∩돌파직전/돌파':(df.tt==1)&act,
   'SC70 점수70+∩실행가능':(df.score>=70)&act,'STRICT 유효VCP∩실행가능':(df.vcp==1)&act}
um=df.groupby('date').ret.mean(); dates=np.array(sorted(um.index))
def nw_t(x,lag=19):
    x=np.asarray(x)-np.mean(x); n=len(x); g0=(x*x).mean(); s=g0
    for k in range(1,lag+1): s+=2*(1-k/(lag+1))*(x[k:]*x[:-k]).mean()
    return np.mean(x+0)/1 if False else None, np.sqrt(s/n)
out=[]
for name,m in G.items():
    g=df[m]; gm=g.groupby('date').ret.mean(); ex=(gm-um.reindex(gm.index)).dropna()
    _,se=nw_t(ex.values); t=ex.mean()/se if se>0 else np.nan
    srt=np.sort(ex.values)[::-1]
    folds=[ex[(ex.index>=a)&(ex.index<=b)].mean() for a,b in [(dates[0],dates[len(dates)//3]),(dates[len(dates)//3+1],dates[2*len(dates)//3]),(dates[2*len(dates)//3+1],dates[-1])]]
    out.append(dict(군=name,신호일=len(ex),일평균종목=round(len(g)/max(len(ex),1),1),
      초과평균=ex.mean(),NW_t=t,중앙=ex.median(),승률=(g.ret>0).mean()*100,종목평균20일=g.ret.mean(),
      KODEX대비=(g.ret-g.kodex).mean(),MAE중앙=g.mae.median(),
      fold1=folds[0],fold2=folds[1],fold3=folds[2],
      상위3일제거=srt[3:].mean() if len(srt)>10 else np.nan,상위10일제거=srt[10:].mean() if len(srt)>20 else np.nan))
r=pd.DataFrame(out).set_index('군'); pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
print(r.round(2).to_string())
print('기간',dates[0],dates[-1],'유니버스 평균20일',df.ret.mean().round(2),'KODEX200',df.groupby("date").kodex.first().mean().round(2))
# incremental: VCP within NH vs NH, using same dates
for name,m in [('ACT',(df.tt==1)&act),('STRICT',(df.vcp==1)&act),('SC70',(df.score>=70)&act)]:
    a=df[m].groupby('date').ret.mean(); b=df[df.nh==1].groupby('date').ret.mean().reindex(a.index)
    d=(a-b).dropna(); _,se=nw_t(d.values); print(name,'- NH 같은날 차',round(d.mean(),2),'t',round(d.mean()/se,2),'n',len(d))
df.to_pickle('bt_all.pkl')
