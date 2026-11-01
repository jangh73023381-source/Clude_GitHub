import sys,json,time; from engine import *
t=time.time()
ev,df=run(nrand=100)
df.to_pickle('r1_main.pkl'); print('rows',len(df),time.time()-t)
