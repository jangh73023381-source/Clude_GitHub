from gA import *
mlv=pickle.load(open('mlv.pkl','rb'))
for k in (20,60):
    o,df=report(f'풀=mom{k} top30→σ20 (20일 보유)',lvsel(30,Vs[20],MOM[k]),ref=base)
    j=df.merge(mlv[['date','port']],on='date',suffixes=('','_m')); j['y']=j.date.str[:4]
    print('  vs MLV: Sh %.2f/%.2f MDD %.1f/%.1f'%(prof(j.port)['sharpe'],prof(j.port_m)['sharpe'],prof(j.port)['mdd'],prof(j.port_m)['mdd']))
    print('  연도별 누적(이 규칙/MLV):',' '.join(f"{y}:{prof(s.port)['cum']:+.0f}/{prof(s.port_m)['cum']:+.0f}" for y,s in j.groupby('y')))
# R5 3일
j=mlv.merge(base[['date','port']],on='date',suffixes=('','_b')); d=(j.port-j.port_b).values
x=j.port.values.copy(); idx=np.argsort(-d)[:3]; x[idx]=j.port_b.values[idx]; print('R5 3일 대체 MDD %.1f Sh %.2f'%(prof(x)['mdd'],prof(x)['sharpe']))
