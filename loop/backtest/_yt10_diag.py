import csv, random, statistics as st
from collections import defaultdict
exec(open("bt_yt10min_20260829.py",encoding="utf-8").read().split('print("="*118)')[0])

def run2(turn_th=0.10, fibs=(0.382,0.50,0.618), use_stop=True, lookahead=False):
    out=[]
    for key,c in cand.items():
        if key not in bars or float(c["turn"])<turn_th: continue
        bs=bars[key]
        if len(bs)<30: continue
        code,date=key
        shares=float(c["vol"])/float(c["turn"])
        gate=max(float(c["ma5"]),float(c["ma10"]),float(c["ma20"]))
        gi=None
        for i,(hm,o,h,l,cl,av) in enumerate(bs):
            if hm>="1520": break
            if lookahead:
                gi=0; break
            if h>gate and av/shares>=turn_th: gi=i; break
        if gi is None: continue
        seg=bs[:gi+1]; H=max(x[2] for x in seg); L=min(x[3] for x in seg); rng=H-L
        if rng<=0: continue
        lv2=H-fibs[0]*rng; lv3=H-fibs[1]*rng; lv4=H-fibs[2]*rng
        post=bs[gi+1:]
        if not post: continue
        fills=[]; ei=None
        for k,(hm,o,h,l,cl,av) in enumerate(post):
            if not fills and l<=lv2:
                fills.append(min(lv2,o)); ei=k
                if l<=lv3: fills.append(min(lv3,o))
                break
        if not fills: continue
        buy=sum(fills)/len(fills)
        rest=post[ei:]
        mfe=max(x[2] for x in rest)/buy-1
        mae=min(x[3] for x in rest)/buy-1
        exitpx=None; stopped=False
        if use_stop:
            for hm,o,h,l,cl,av in rest:
                if l<=lv4: exitpx=lv4; stopped=True; break
        if exitpx is None: exitpx=bs[-1][4]
        out.append(dict(date=date,ret=exitpx/buy-1-COST,mfe=mfe,mae=mae,stopped=stopped))
    return out

def rep(res,lab):
    if not res: print(lab,"거래 0"); return
    r=[x["ret"] for x in res]
    print(f"{lab:34s} 거래 {len(res):4d} | 절대 {st.mean(r)*100:+6.2f}% | 승률 {sum(1 for x in r if x>0)/len(r)*100:4.1f}%"
          f" | 손절 {sum(1 for x in res if x['stopped'])/len(res)*100:4.1f}%"
          f" | MFE 평균 {st.mean(x['mfe'] for x in res)*100:+5.2f}% 중앙 {st.median(x['mfe'] for x in res)*100:+5.2f}%"
          f" | MAE 평균 {st.mean(x['mae'] for x in res)*100:+5.2f}%")

print("진입 후 당일 최대상승(MFE)·최대하락(MAE) — 영상이 말하는 '열려 있던 수익 구간'의 정체")
rep(run2(), "원안(손절 O)")
rep(run2(use_stop=False), "손절 제거(종가청산만)")
rep(run2(lookahead=True), "영상 그대로(사후조건·09:00부터)")
print()
res=run2()
m=sorted(x["mfe"] for x in res)
print("MFE 분위: p10 %.1f%% p25 %.1f%% 중앙 %.1f%% p75 %.1f%% p90 %.1f%% 최대 %.1f%%"%tuple(
    m[int(len(m)*q)]*100 for q in (0.1,0.25,0.5,0.75,0.9))+ (" ",))
print("MFE>=10%% 인 거래 비율: %.1f%%  /  >=5%%: %.1f%%"%(
    sum(1 for x in res if x['mfe']>=0.10)/len(res)*100, sum(1 for x in res if x['mfe']>=0.05)/len(res)*100))
