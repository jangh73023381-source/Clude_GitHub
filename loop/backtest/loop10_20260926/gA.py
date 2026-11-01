from mid import *
import pickle, sys
base=pickle.load(open('mbase.pkl','rb'))
Vs={k:pd.DataFrame(Rd).rolling(k,min_periods=max(10,int(k*.66))).std().values for k in (20,40,60)}
def lvsel(pool,V,S=MOM[150],hi=False):
    def f(i):
        pl=top(S,i,pool)
        if pl is None: return None
        v=V[i,pl]; m=~np.isnan(v)
        if m.sum()<5: return pl[:5]
        o=np.argsort(-v[m] if hi else v[m],kind='stable')
        return pl[m][o[:5]]
    return f
part=sys.argv[1] if len(sys.argv)>1 else ''
if part=='r1':
    print('pool × σ룩백: ΔCAGR/ΔMDD/ΔSh (통과=MDD+5↑·Sh+0.1↑·CAGR≥-2)')
    npass=0; tot=0
    for pool in (10,15,20,25,30,40,50):
        row=f'pool{pool:<3d}'
        for k in (20,40,60):
            o,_=report('',lvsel(pool,Vs[k]),ref=base,quiet=True); tot+=1
            ok=o['dmdd']>=5 and o['dsh']>=0.1 and o['dcagr']>=-2; npass+=ok
            row+=f"  k{k}: {o['dcagr']:+5.1f}/{o['dmdd']:+5.1f}/{o['dsh']:+.2f}{'✔' if ok else ' '}"
        print(row)
    print(f'통과 {npass}/{tot}')
if part=='r2':
    o,cand=report('MLV pool30 σ20',lvsel(30,Vs[20]),ref=base)
    j=cand.merge(base[['date','port']],on='date',suffixes=('','_b'))
    for K in (3,6):
        print(f'[{K}분할]',end=' ')
        for q in range(K):
            s=j.iloc[q*len(j)//K:(q+1)*len(j)//K]; a,b=prof(s.port),prof(s.port_b)
            print(f"f{q+1} MDD {a['mdd']:.1f}/{b['mdd']:.1f} Sh {a['sharpe']:.2f}/{b['sharpe']:.2f} 누적 {a['cum']:+.0f}/{b['cum']:+.0f} |",end=' ')
        print()
    j['y']=j.date.str[:4]
    for y,s in j.groupby('y'):
        a,b,c=prof(s.port),prof(s.port_b),prof(s.bench)
        print(y,len(s),f"누적 MLV {a['cum']:+.1f} / mom150 {b['cum']:+.1f} / KODEX200 {c['cum']:+.1f} | MDD {a['mdd']:.1f} / {b['mdd']:.1f} / {c['mdd']:.1f}")
    pickle.dump(cand,open('mlv.pkl','wb'))
if part=='r3':
    for S,nm in ((MOM[120],'mom120'),(MOM[200],'mom200'),(MOM[250],'mom250')):
        report(f'풀={nm} top30→σ20',lvsel(30,Vs[20],S),ref=base)
    dsd=pd.DataFrame(np.where(Rd<0,Rd,0)**2).rolling(20,min_periods=13).mean().values**.5
    report('위험척도=하방편차20',lvsel(30,dsd),ref=base)
    report('(대조) pool30 고변동 5종',lvsel(30,Vs[20],hi=True),ref=base)
if part=='r4':
    rng=np.random.default_rng(7); out=[]
    pools={i:top(MOM[150],i,30) for i in range(START,T-1)}
    for rep in range(200):
        ch={i:(None if p is None else rng.choice(p,5,replace=False)) for i,p in pools.items()}
        o,_=report('',lambda i: ch[i],ref=base,quiet=True); out.append((o['mdd'],o['sh'],o['cagr']))
    out=np.array(out); np.save('r4mlv.npy',out)
    real=report('',lvsel(30,Vs[20]),quiet=True)[0]
    for j,k in enumerate(('mdd','sh','cagr')):
        print(k,'귀무 평균 %.2f p95 %.2f 실제 %.2f p=%.3f'%(out[:,j].mean(),np.quantile(out[:,j],.95),real[k],(out[:,j]>=real[k]).mean()))
