"""축6 Rule Y(모멘텀확인 역전제외) · 축7 RS(IBD 가중) pool — 둘 다 Rule LV(v2.9) 위에서 재판정.
7년 panel_ohlc_long, 공통 시작 252. 지표 A(종가→종가)·OO(시가→시가). 기준 = LV(mom20 pool30 → σ20 하위5)."""
import os,sys,json,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
os.chdir(os.path.join(BT,'loop10_20260926'))
from engine import load,Engine,prof,tstat,r5,folds
P,dates,codes,names=load(os.path.join(BT,'panel_ohlc_long.csv')); E=Engine(P,dates,codes,names); C=E.C
print('기간',dates[0],dates[-1],len(dates))
lag=lambda X,k:np.vstack([np.full((k,X.shape[1]),np.nan),X[:-k]])
S=252
base=E.run(lambda i,pl:E.sel_lv(i,pl),start=S)
r1=(C/lag(C,1)-1)*100; m5=(C/lag(C,5)-1)*100
res={}
def comp(name,df,extra=None):
    m=base.merge(df,on='date',suffixes=('_b',''))
    out={}
    for k in ('A','OO'):
        d=(m[k]-m[k+'_b']).values; pb=prof(m[k+'_b']); pc=prof(m[k])
        rr=r5(d)
        out[k]=dict(n=len(d),diff=d.mean(),t=tstat(d),f=folds(d),med=rr['median'],drop3=rr['drop3'],drop10=rr['drop10'],
                    cagr=pc['cagr'],mdd=pc['mdd'],sh=pc['sharpe'],bcagr=pb['cagr'],bmdd=pb['mdd'],bsh=pb['sharpe'])
    if extra: out.update(extra)
    res[name]=out
    a,o=out['A'],out['OO']
    print(f"{name:34s} A: 차{a['diff']:+.4f} t{a['t']:+.2f} fold[{', '.join('%+.3f'%x for x in a['f'])}] -3일{a['drop3']:+.4f} | CAGR {a['cagr']:.1f}({a['bcagr']:.1f}) MDD {a['mdd']:.1f}({a['bmdd']:.1f}) Sh {a['sh']:.2f}({a['bsh']:.2f}) || OO: 차{o['diff']:+.4f} t{o['t']:+.2f} fold[{', '.join('%+.3f'%x for x in o['f'])}] Sh {o['sh']:.2f}({o['bsh']:.2f}) MDD {o['mdd']:.1f}({o['bmdd']:.1f})",flush=True)
print('기준 LV A',prof(base.A),' OO',prof(base.OO))
# ---- 축6 Rule Y: pool30 안에서 D일 반전 종목 제외 후 σ20 하위5
def selY(th,kind='r1'):
    X=r1 if kind=='r1' else m5
    def f(i,pl):
        keep=pl[~(X[i,pl]<=th)]
        if len(keep)<5: keep=pl
        return E.sel_lv(i,keep)
    return f
for th in (-1,-2,-3):
    comp(f'Y: D일 등락<={th}% 제외',E.run(selY(th),start=S))
for th in (0,-3):
    comp(f'Y: mom5<={th}% 제외',E.run(selY(th,'m5'),start=S))
# 플라시보(Y -2%): 같은 개수 무작위 제외 100회 → A Sharpe/OO Sharpe 분포
rng=np.random.default_rng(3)
def selRand(th):
    def f(i,pl):
        k=int((r1[i,pl]<=th).sum()); 
        if k==0 or len(pl)-k<5: return E.sel_lv(i,pl)
        keep=np.delete(pl,rng.choice(len(pl),k,replace=False)); return E.sel_lv(i,keep)
    return f
sims=[];
for _ in range(100):
    df=E.run(selRand(-2),start=S); sims.append((prof(df.A)['sharpe'],prof(df.OO)['sharpe'],prof(df.A)['mdd']))
sims=np.array(sims); res['Y_placebo_-2']=dict(shA=sims[:,0].tolist(),shOO=sims[:,1].tolist(),mddA=sims[:,2].tolist())
y2=res['Y: D일 등락<=-2% 제외']
print(f"Y-2 플라시보: A Sh 귀무 {sims[:,0].mean():.3f} p={np.mean(sims[:,0]>=y2['A']['sh']):.3f} | OO Sh 귀무 {sims[:,1].mean():.3f} p={np.mean(sims[:,1]>=y2['OO']['sh']):.3f} | MDD 귀무 {sims[:,2].mean():.1f} p={np.mean(sims[:,2]>=y2['A']['mdd']):.3f}")
# ---- 축7 RS(IBD 40/20/20/20) pool → σ20 하위5
R=lambda k:(C/lag(C,k)-1)
RS=0.4*R(63)+0.2*R(126)+0.2*R(189)+0.2*R(252)
R12_1=(lag(C,21)/lag(C,252)-1)
for n in (20,30,40):
    comp(f'RS(IBD) pool{n} → σ20 하위5',E.run(lambda i,pl,n=n:E.sel_lv(i,E.pool(i,n=n,score=RS)),start=S))
comp('RS 12-1개월 pool30 → σ20 하위5',E.run(lambda i,pl:E.sel_lv(i,E.pool(i,n=30,score=R12_1)),start=S))
comp('RS(IBD) 순수 상위5(참고)',E.run(lambda i,pl:E.pool(i,n=5,score=RS),start=S))
json.dump(res,open(os.path.join(HERE,'res_lv.json'),'w'),default=float,indent=1)
