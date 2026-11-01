from ev import *
m,l=BASE['MOM'],BASE['LV']
for k in ('A','OO','L1','OOx'):
    d=l[k]-m[k]; e=l[k]-l['b'+k]
    rr=r5(d.values)
    print(k,'LV-MOM 평균%+.4f t%+.2f 3fold'%(d.mean(),tstat(d)),['%+.3f'%x for x in folds(d.values)],'중앙%+.4f 상위3제거%+.4f'%(rr['median'],rr['drop3']),
          '| MDD 3fold LV/MOM',[ (round(prof(l[k].values[j*len(l)//3:(j+1)*len(l)//3])['mdd'],1), round(prof(m[k].values[j*len(m)//3:(j+1)*len(m)//3])['mdd'],1)) for j in range(3)])
l['y']=l.date.str[:4]; m['y']=m.date.str[:4]
print('연도별 OO 누적: LV / MOM / KODEX200')
for y,g in l.groupby('y'):
    gm=m[m.y==y]
    print(y, len(g), '%+.1f / %+.1f / %+.1f'%(prof(g.OO)['cum'],prof(gm.OO)['cum'],prof(g.bOO)['cum']), ' MDD %.1f / %.1f / %.1f'%(prof(g.OO)['mdd'],prof(gm.OO)['mdd'],prof(g.bOO)['mdd']))
