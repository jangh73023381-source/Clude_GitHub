from engine import *
import pickle, json, sys
P,dates,codes,names=load(); E=Engine(P,dates,codes,names)
_, LVB = pickle.load(open('/home/claude/w/base.pkl','rb')) if False else (None,None)
BASE = {'MOM': E.run(E.sel_mom), 'LV': E.run(E.sel_lv)}
MET = ('A','OO','L1')
def evaluate(name, sel, ref='LV', quiet=False, df=None):
    c = E.run(sel) if df is None else df
    b = BASE[ref]
    j = c.merge(b, on='i', suffixes=('','_r'))
    out = {'name': name, 'n': len(j), 'cov': len(c)}
    lines=[]
    for k in MET:
        pc, pb = prof(j[k]), prof(j[k+'_r'])
        d = j[k]-j[k+'_r']
        f3 = folds(d.values,3)
        rr = r5(d.values)
        out[k] = dict(cagr=pc['cagr'], mdd=pc['mdd'], sh=pc['sharpe'], dcagr=pc['cagr']-pb['cagr'], dmdd=pc['mdd']-pb['mdd'],
                      dsh=pc['sharpe']-pb['sharpe'], dmean=d.mean(), t=tstat(d), f3=f3, med=rr['median'], drop3=rr['drop3'])
        lines.append(f"  {k:3s} CAGR{pc['cagr']:+6.1f}(Δ{pc['cagr']-pb['cagr']:+5.1f}) MDD{pc['mdd']:6.1f}(Δ{pc['mdd']-pb['mdd']:+5.1f}) Sh{pc['sharpe']:5.2f}(Δ{pc['sharpe']-pb['sharpe']:+.2f}) | Δ일{d.mean():+.4f} t{tstat(d):+.2f} fold{['%+.3f'%x for x in f3]} 중앙{rr['median']:+.4f} 상위3제거{rr['drop3']:+.4f}")
    if not quiet:
        print(f"[{name}] vs {ref} · n={len(j)}")
        print('\n'.join(lines))
    return out, c
if __name__=='__main__':
    for k in ('A','OO','L1','OOx'):
        for nm in ('MOM','LV'):
            print(nm,k,fmt(prof(BASE[nm][k])),' bench',fmt(prof(BASE[nm]['b'+k])))
