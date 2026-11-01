"""축10 — 월말·월초 수급창(TOM: 월 마지막 거래일 + 다음 달 첫 3거래일). 2026-09-29 토론에서 '효과<검출한계'로 철회만 되고
검정은 하지 않은 축. KODEX200·LV 픽·MOM 픽의 일수익을 TOM/비TOM 으로 나눠 비교. 대조군 = 같은 길이의 월중 다른 창(시차이동)."""
import os,sys,json,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
from engine import load,Engine,tstat,r5,folds
P,dates,codes,names=load(os.path.join(BT,'panel_ohlc_long.csv')); E=Engine(P,dates,codes,names)
lv=E.run(lambda i,pl:E.sel_lv(i,pl),start=20); mo=E.run(lambda i,pl:E.sel_mom(i,pl),start=20)
# 수익 실현일 = dates[i+1]
pos={}; d=pd.Series(dates); ym=d.str[:6]
first=d.groupby(ym).cumcount()+1; last=d.groupby(ym).cumcount(ascending=False)+1
pos=pd.DataFrame(dict(date=dates,fp=first.values,lp=last.values))
def lab(df):
    x=df.copy(); x['rd']=[dates[i+1] for i in x.i]; x=x.merge(pos,left_on='rd',right_on='date',suffixes=('','_r')); return x
lv=lab(lv); mo=lab(mo)
def win(x,a,b):   # 첫 a..b 거래일(양수) 또는 마지막(음수: -1=마지막날)
    return ((x.fp>=a)&(x.fp<=b)) if a>0 else ((x.lp>=-b)&(x.lp<=-a))
TOM=lambda x:(x.lp==1)|((x.fp>=1)&(x.fp<=3))
res={}
for nm,x,col in [('KODEX200',lv,'bA'),('LV 픽',lv,'A'),('MOM 픽',mo,'A'),('LV−KODEX200',lv,None),('LV(OO)',lv,'OO')]:
    v=(x.A-x.bA) if col is None else x[col]
    m=TOM(x); a=v[m]; b=v[~m]
    diff=a.mean()-b.mean(); se=np.sqrt(a.var()/len(a)+b.var()/len(b))
    # 3분할
    n=len(x); f=[]
    for j in range(3):
        s=slice(j*n//3,(j+1)*n//3); vv=v.iloc[s]; mm=m.iloc[s]; f.append(vv[mm].mean()-vv[~mm].mean())
    # 연도
    yr={y:round(v[m&(x.rd.str[:4]==y)].mean()-v[~m&(x.rd.str[:4]==y)].mean(),3) for y in sorted(x.rd.str[:4].unique())}
    # 시차이동 대조: 4일 창을 월내 다른 위치로 (첫 k..k+3, k=4..15)
    ctrl=[]
    for k in range(4,16):
        mk=(x.fp>=k)&(x.fp<=k+3); ctrl.append(v[mk].mean()-v[~mk].mean())
    ctrl=np.array(ctrl)
    # 꼬리: TOM 일 상위 3일 제거
    s=np.sort(a.values)[::-1]; d3=(s.sum()-s[:3].sum())/(len(s)-3)-b.mean()
    res[nm]=dict(tom=a.mean(),non=b.mean(),diff=diff,t=diff/se,n_tom=len(a),f=f,yr=yr,ctrl=ctrl.tolist(),ctrl_rank=float((ctrl>=diff).mean()),drop3=d3)
    print(f"{nm:12s} TOM {a.mean():+.4f}(n{len(a)}) 비TOM {b.mean():+.4f} 차 {diff:+.4f} t{diff/se:+.2f} fold[{', '.join('%+.3f'%q for q in f)}] 상위3제거 {d3:+.4f} | 시차이동 대조 12창 중 {int((ctrl>=diff).sum())}개가 같거나 큼(범위 {ctrl.min():+.3f}~{ctrl.max():+.3f})")
    print('    연도',yr)
# 각 위치별 평균 (KODEX200)
prof_=lv.assign(v=lv.bA).groupby('fp').v.agg(['mean','count']).head(8); print(prof_.round(3).T)
prof2=lv.assign(v=lv.bA).groupby('lp').v.agg(['mean','count']).head(4); print('월말쪽',prof2.round(3).T)
json.dump(res,open(HERE+'/res_tom.json','w'),default=float,indent=1,ensure_ascii=False)
