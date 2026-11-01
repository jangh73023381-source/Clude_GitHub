"""축1 요일 · 축2 연휴 직전 · 축3 옵션만기(둘째 목요일). 규칙형 = 해당 보유일에 LV 대신 KODEX200(또는 현금).
판정: 해당일 LV−지수 평균 vs 그 외, t, 연도별 부호, 무작위 같은 개수 날짜 대조(1,000회)."""
from common import *
import datetime as dt
E,base=setup(); res={}
b=base.copy()
b['dt']=pd.to_datetime(b.date)
alld=pd.to_datetime(pd.Series(E.dates))
nxt={E.dates[j]:alld[j+1] for j in range(len(E.dates)-1)}
nxt2={E.dates[j]:alld[j+2] for j in range(len(E.dates)-2)}
b['d1']=b.date.map(nxt); b['d2']=b.date.map(nxt2)
for k in ('A','OO'): b['x'+k]=b[k]-b['b'+k]
rng=np.random.default_rng(7)
def test(name,mask,k):
    x=b['x'+k].values; m=mask.values.astype(bool)
    on=x[m]; off=x[~m]
    # 규칙: 해당일 지수 보유 → 전략 일수익
    strat=np.where(m,b['b'+k].values,b[k].values); cash=np.where(m,0.0,b[k].values)
    sims=np.array([x[rng.choice(len(x),m.sum(),replace=False)].mean() for _ in range(1000)])
    yrs=b['dt'].dt.year.values; ys={int(y):float(np.nanmean(x[m&(yrs==y)])) for y in np.unique(yrs) if (m&(yrs==y)).sum()>=3}
    o=dict(n_on=int(m.sum()),on=float(np.nanmean(on)),off=float(np.nanmean(off)),t_on=float(tstat(on)),
           p_rand=float(np.mean(sims<=on.mean())),yrs=ys,neg_years=int(sum(v<0 for v in ys.values())),
           base=prof(b[k]),swap=prof(strat),cash=prof(cash))
    res[f'{name}|{k}']=o
    print(f"{name:22s}{k:3s} n={o['n_on']:4d} LV-지수 해당일{o['on']:+.4f}(t{o['t_on']:+.2f}) 그외{o['off']:+.4f} p(무작위≤)={o['p_rand']:.3f} 음수연도{o['neg_years']}/{len(ys)} | Sh 기준{o['base']['sharpe']:.2f} 지수교체{o['swap']['sharpe']:.2f} 현금{o['cash']['sharpe']:.2f} MDD {o['base']['mdd']:.1f}/{o['swap']['mdd']:.1f}/{o['cash']['mdd']:.1f}",flush=True)
# 보유일 = A: D+1 종가까지(보유 세션 D+1), OO: D+1시가→D+2시가(보유 세션 D+1)
for wd,nm in enumerate(['월','화','수','목','금']):
    for k in ('A','OO'):
        test(f'요일 보유세션={nm}',b['d1'].dt.weekday==wd,k)
# 연휴: 보유 세션 D+1 다음 거래일까지 달력 간격 ≥4일(주말 제외 휴장 포함) → 연휴 직전 세션
gap=(b['d2']-b['d1']).dt.days
pre=(gap>=4)|((gap==3)&(b['d1'].dt.weekday!=4))
post=((b['d1']-b['dt']).dt.days>=4)|(((b['d1']-b['dt']).dt.days==3)&(b['dt'].dt.weekday!=4))
for k in ('A','OO'):
    test('연휴 직전 세션',pre,k); test('연휴 직후 세션',post,k)
# 옵션만기: 둘째 목요일(휴장 시 직전 거래일) — 보유 세션이 만기일 / 만기 다음 세션
def second_thu(y,mo):
    d=dt.date(y,mo,1); off=(3-d.weekday())%7; return pd.Timestamp(d+dt.timedelta(days=off+7))
exp=set()
tds=set(alld)
for y in range(2019,2027):
    for mo in range(1,13):
        t=second_thu(y,mo)
        while t not in tds and t>pd.Timestamp('2019-01-01'):
            t-=pd.Timedelta(days=1)
            if t<alld.min(): break
        exp.add(t)
for k in ('A','OO'):
    test('옵션만기 당일 세션',b['d1'].isin(exp),k)
    test('만기 익일 세션',b['dt'].isin(exp),k)
    wk=b['d1'].apply(lambda d: any(0<=(e-d).days<=6 for e in exp))
    test('만기주(만기 前 1주) 세션',wk,k)
json.dump(res,open(os.path.join(HERE,'res_cal.json'),'w'),default=float,indent=1)
