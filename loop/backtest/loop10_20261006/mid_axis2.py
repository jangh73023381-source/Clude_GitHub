"""축8 보강 — 신고가 근접 '현금형'의 이득이 종목 선택인가, 노출 타이밍인가.
대조군: MLV 원래 5종을 그대로 사되 트랜치 투자비중 = (근접 통과 종목수/5) — 같은 날 같은 노출."""
import os,sys,json,numpy as np,pandas as pd
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'mid_axis.py')).read().split("mom,_=M.report")[0])
from engine import prof
_,mdf=M.report('MLV',lambda i:mlv(i),quiet=True)
def yr(df):
    out={}
    for y,g in df.groupby(df.date.str[:4]): p=prof(g.port); out[y]=(round(p['cum'],1),round(p['mdd'],1))
    return out
def thirds(df):
    n=len(df); r=[]
    for j in range(3):
        p=prof(df.port.values[j*n//3:(j+1)*n//3]); r.append((round(p['sharpe'],2),round(p['mdd'],1),round(p['cagr'],1)))
    return r
res={}
for k in (0.90,0.95,0.97):
    mk=C>=H250*k
    def cnt(i,mk=mk):
        pl=M.top(M.MOM[150],i,n=30)
        if pl is None: return 0.
        q=pl[mk[i,pl]]; q=q[~np.isnan(VOL[i,q])]; return min(len(q),5)/5
    o,df=M.report(f'근접{k} 현금형',lambda i,mk=mk:mlv(i,mk,False),ref=mdf,quiet=True)
    oc,dfc=M.report(f'노출대조 {k}',lambda i:mlv(i),weight=cnt,ref=mdf,quiet=True)
    expo=np.mean([cnt(i) for i in range(M.START,M.T-1)])
    res[k]=dict(rule=o,ctrl=oc,expo=expo,thirds_rule=thirds(df),thirds_ctrl=thirds(dfc),thirds_mlv=thirds(mdf),yr_rule=yr(df),yr_ctrl=yr(dfc))
    print(f"[{k}] 평균노출 {expo:.2f} | 규칙 CAGR {o['cagr']:.1f} MDD {o['mdd']:.1f} Sh {o['sh']:.2f} | 같은 노출 MLV CAGR {oc['cagr']:.1f} MDD {oc['mdd']:.1f} Sh {oc['sh']:.2f}")
    print('   3분할(Sh,MDD,CAGR) 규칙',thirds(df),' 대조',thirds(dfc),' MLV',thirds(mdf))
    print('   연도(누적,MDD) 규칙',yr(df)); print('   연도 대조',yr(dfc))
print('MLV 연도',yr(mdf))
json.dump(res,open(os.path.join(HERE,'res_mid2.json'),'w'),default=float,indent=1)
