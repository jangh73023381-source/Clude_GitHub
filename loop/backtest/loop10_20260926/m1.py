from mid import *
import pickle, time
t=time.time()
o,base=report('mom150 상위5 (Rule MM 기준선)', base_sel)
print('KODEX200', prof(base.bench))
report('mom20 상위5', lambda i: top(MOM[20],i))
def lv20(i):
    pl=top(MOM[20],i,30)
    if pl is None: return None
    v=E.vol(20)[i,pl]; m=~np.isnan(v); return pl[m][np.argsort(v[m])[:5]]
report('mom20 pool30→σ20 (현행 단기 LV, 20일 보유)', lv20)
for k in (120,200,250): report(f'mom{k} 상위5', lambda i,k=k: top(MOM[k],i))
for H in (40,60): report(f'mom150 보유{H}일', base_sel, H=H)
report('mom150 익일 종가 진입(1일 지연)', base_sel, lagd=1)
pickle.dump(base,open('mbase.pkl','wb'))
print(time.time()-t)
