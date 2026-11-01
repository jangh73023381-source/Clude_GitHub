from mid import *
import pickle
base=pickle.load(open('mbase.pkl','rb'))
r=lambda k:(C/lag(C,k)-1)*100
ADM=r(21)+r(63)+r(126)
ADMw=r(21)+r(63)/3+r(126)/6
def absf(score):
    def f(i):
        p=top(score,i)
        if p is None: return None
        return p[score[i,p]>0]   # 음수 점수 슬롯은 현금(빈 슬롯은 0 수익으로 계산)
    return f
def absf_cashslots(score):
    # 슬롯 단위 현금: 5슬롯 중 k개만 양수면 나머지는 현금
    def f(i):
        p=top(score,i)
        if p is None: return None
        return p, (score[i,p]>0).mean()
    return f
res=[]
o,_=report('가속듀얼 점수(1+3+6개월) 상위5',lambda i: top(ADM,i),ref=base); res.append(o)
o,_=report('가속듀얼 가중(1+3/3+6/6) 상위5',lambda i: top(ADMw,i),ref=base); res.append(o)
# 절대모멘텀: 양수 슬롯만 투자, 음수 슬롯 현금 → weight 로 구현
for nm,S in (('가속듀얼',ADM),('mom150',MOM[150])):
    sel=lambda i,S=S: (lambda p: None if p is None else p[S[i,p]>0])(top(S,i))
    wt=lambda i,S=S: (lambda p: 0.0 if p is None else float((S[i,p]>0).mean()))(top(S,i))
    o,_=report(f'{nm} + 절대모멘텀(음수 슬롯 현금)',sel,weight=wt,ref=base); res.append(o)
pickle.dump(res,open('m5.pkl','wb'))
