# -*- coding: utf-8 -*-
"""Rule R' 교차검증 게이트(v2.2 B) — 발동일 수·발동일 한정 성과·train/test 분해"""
import os,statistics
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'bt_pnl_v24.py')).read().split('def main()')[0])
def sel_R(px,name,d,dates,lam=1.0,thr=0.05,n=5):
    out=[]
    for c,m in rank_candidates(px,name,d,dates,20):
        s1=mom(px,c,d,dates,1) or 0.0
        out.append((c,m-lam*max(0.0,s1-thr)))
    out.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in out[:n]]
px,name,dates=load()
for lam,thr in [(1.0,0.05),(1.0,0.03),(2.0,0.05)]:
    trig=[];bx=[];rx=[];bh=[];rh=[]
    for i in range(20,len(dates)-1):
        d=dates[i];dn=dates[i+1]
        pb=sel_baseline(px,name,d,dates); pr=sel_R(px,name,d,dates,lam,thr)
        eb=day_excess(px,pb,d,dn); er=day_excess(px,pr,d,dn)
        hb=day_hits(px,name,pb,d,dn); hr=day_hits(px,name,pr,d,dn)
        bx.append(eb);rx.append(er);bh.append(hb);rh.append(hr)
        if set(pb)!=set(pr): trig.append((d,eb,er,hb,hr))
    print("=== Rule R' lam%.1f thr%.0f%% ==="%(lam,thr*100))
    print(" 발동일(픽이 실제로 바뀐 날): %d일 / %d일"%(len(trig),len(bx)))
    if trig:
        db=sum(t[1] for t in trig)/len(trig); dr=sum(t[2] for t in trig)/len(trig)
        hbm=sum(t[3] for t in trig)/len(trig); hrm=sum(t[4] for t in trig)/len(trig)
        print(" 발동일 한정 P&L: base %+.3f%%p -> R' %+.3f%%p (순증 %+.3f%%p)"%(db*100,dr*100,(dr-db)*100))
        print(" 발동일 한정 이진: base %.2f -> R' %.2f종"%(hbm,hrm))
        wins=sum(1 for t in trig if t[2]>t[1]); print(" 발동일 중 개선 %d / 악화 %d / 동일 %d"%(wins,sum(1 for t in trig if t[2]<t[1]),sum(1 for t in trig if abs(t[2]-t[1])<1e-12)))
        for d,eb,er,hb,hr in trig: print("   %s base %+.2f%%p -> R' %+.2f%%p | 적중 %d->%d"%(d,eb*100,er*100,hb,hr))
    print()
