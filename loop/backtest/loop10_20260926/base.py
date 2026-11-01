from engine import *
import pickle,time
t=time.time()
P,dates,codes,names=load()
E=Engine(P,dates,codes,names)
print('load',time.time()-t, E.T, E.N, dates[0], dates[-1])
m=E.run(E.sel_mom); l=E.run(E.sel_lv)
print(len(m), m.date.iloc[0], m.date.iloc[-1])
for nm,df in (('MOM',m),('LV',l)):
    for k in ('A','OO','B','G'):
        print(nm,k,fmt(prof(df[k])), ' | bench',fmt(prof(df['b'+k])))
pickle.dump((m,l),open('base.pkl','wb'))
