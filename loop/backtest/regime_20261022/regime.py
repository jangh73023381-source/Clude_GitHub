"""국면별 방법 전환 검정 (PREREG.md 고정 설계 그대로)."""
import os,sys,json,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
import engine as _E
PANEL=sys.argv[1] if len(sys.argv)>1 else os.path.join(BT,'panel_ohlc_long.csv')
_E.load.__defaults__=(PANEL,)
from engine import load,Engine,prof,tstat,r5,folds
P,dates,codes,names=load(PANEL); E=Engine(P,dates,codes,names); C=E.C; T,N=C.shape; bi=E.bi
lag=lambda X,k:np.vstack([np.full((k,X.shape[1]),np.nan),X[:-k]])
B=pd.Series(C[:,bi]).ffill()
def regime(ma): return (B<B.rolling(ma).mean()).values   # True = BEAR
BEAR=regime(60); BEAR120=regime(120)
mom60=(C/lag(C,60)-1)*100
VOL=E.vol(20)
def lv(i,pl): return E.sel_lv(i,pl)
def mom(i,pl): return pl[:5]
def minvol(i,pl):
    idx=np.where(E.ok[i]&~np.isnan(VOL[i]))[0]; return idx[np.argsort(VOL[i,idx])[:5]]
def lv60(i,pl): return E.sel_lv(i,E.pool(i,n=30,score=mom60))
S=60
def run(sel): return E.run(sel,start=S)
base=run(lv)
def sw(bull,bear,R=BEAR): return lambda i,pl:(bear if R[i] else bull)(i,pl)
cands={'MOM 상시(참고)':run(mom),'S1 강세=MOM/약세=LV':run(sw(mom,lv)),'S2 강세=LV/약세=최소변동':run(sw(lv,minvol)),
       'S3 강세=LV/약세=mom60 LV':run(sw(lv,lv60))}
def scale(df,w):
    x=df.copy(); m=np.array([BEAR[i] for i in x.i])
    for k in ('A','OO'): x[k]=np.where(m,x[k]*w,x[k])
    return x
cands['E1 LV + 약세 비중50%']=scale(base,0.5); cands['E2 LV + 약세 현금']=scale(base,0.0)
def evaluate(name,df,R=BEAR,placebo=None):
    m=base.merge(df,on='i',suffixes=('_b',''))
    out={}
    for k in ('A','OO'):
        a=m[k].values; b=m[k+'_b'].values; d=a-b; reg=np.array([R[i] for i in m.i])
        pa,pb=prof(a),prof(b); rr=r5(d)
        out[k]=dict(cagr=pa['cagr'],mdd=pa['mdd'],sh=pa['sharpe'],bcagr=pb['cagr'],bmdd=pb['mdd'],bsh=pb['sharpe'],
                    bull=float(d[~reg].mean()),bull_t=tstat(d[~reg]),bear=float(d[reg].mean()) if reg.any() else 0,bear_t=tstat(d[reg]) if reg.sum()>2 else 0,
                    f=folds(d),drop3=rr['drop3'],med=rr['median'],n=len(d),bear_days=int(reg.sum()))
    sws=int(np.abs(np.diff(R[S:].astype(int))).sum())
    out['switches']=sws
    return out
res={}
for nm,df in cands.items(): res[nm]=evaluate(nm,df)
# 대조군: 국면 라벨 원형 시차이동 200회
rng=np.random.default_rng(1022)
def shifted():
    k=rng.integers(250,T-250); return np.roll(BEAR,k)
pl={}
for nm,mk in [('S1 강세=MOM/약세=LV',lambda R:sw(mom,lv,R)),('S2 강세=LV/약세=최소변동',lambda R:sw(lv,minvol,R)),('S3 강세=LV/약세=mom60 LV',lambda R:sw(lv,lv60,R))]:
    sims=[]
    for _ in range(60):
        R=shifted(); df=run(mk(R)); sims.append(prof(df.OO)['sharpe'])
    pl[nm]=sims
for nm,w in [('E1 LV + 약세 비중50%',0.5),('E2 LV + 약세 현금',0.0)]:
    sims=[]
    for _ in range(200):
        R=shifted(); x=base.copy(); mm=np.array([R[i] for i in x.i]); x['OO']=np.where(mm,x.OO*w,x.OO); sims.append(prof(x.OO)['sharpe'])
    pl[nm]=sims
for nm,s in pl.items(): res[nm]['placebo_p']=float(np.mean(np.array(s)>=res[nm]['OO']['sh'])); res[nm]['placebo_mean']=float(np.mean(s))
# 강건성: MA120 국면
for nm,(bu,be) in {'S1@MA120':(mom,lv),'S2@MA120':(lv,minvol),'S3@MA120':(lv,lv60)}.items():
    res[nm]=evaluate(nm,run(sw(bu,be,BEAR120)),R=BEAR120)
res['E2@MA120']=evaluate('E2@MA120',(lambda x:(x.__setitem__('OO',np.where(np.array([BEAR120[i] for i in x.i]),0,x.OO)) or x.__setitem__('A',np.where(np.array([BEAR120[i] for i in x.i]),0,x.A)) or x))(base.copy()),R=BEAR120)
bp=prof(base.OO); ba=prof(base.A)
print(f'패널 {dates[S]}~{dates[-1]} · 약세일 {int(BEAR[S:].sum())}/{T-S} · 전환 {int(np.abs(np.diff(BEAR[S:].astype(int))).sum())}회')
print(f"기준 LV  A: CAGR {ba['cagr']:.1f} MDD {ba['mdd']:.1f} Sh {ba['sharpe']:.2f} | OO: CAGR {bp['cagr']:.1f} MDD {bp['mdd']:.1f} Sh {bp['sharpe']:.2f}")
for nm,r in res.items():
    o=r['OO']; a=r['A']
    print(f"{nm:24s} OO CAGR {o['cagr']:6.1f} MDD {o['mdd']:6.1f} Sh {o['sh']:.2f} | 강세 {o['bull']:+.3f}(t{o['bull_t']:+.1f}) 약세 {o['bear']:+.3f}(t{o['bear_t']:+.1f}) fold[{', '.join('%+.3f'%x for x in o['f'])}] -3일 {o['drop3']:+.4f} | A Sh {a['sh']:.2f} MDD {a['mdd']:.1f}"
          + (f" | 대조 Sh {r['placebo_mean']:.2f} p={r['placebo_p']:.3f}" if 'placebo_p' in r else ''),flush=True)
json.dump(res,open(os.path.join(HERE,'res_short_'+os.path.basename(PANEL).replace('.csv','')+'.json'),'w'),default=float,indent=1,ensure_ascii=False)
