import json, pickle, statistics, random, math
from bt_attn import *
px, names = load_px()
cc = pickle.load(open('_cache.pkl','rb')); dates, cands = cc['dates'], cc['cands']

DAYS=[]
for i,d in enumerate(dates[:-1]):
    n=dates[i+1]; bm=fwd(px,BENCH,d,n); cd=cands.get(d)
    if bm is None or not cd or len(cd)<NPICK: continue
    pool=cd[:LV_POOL]; ent=[]
    for _,c,sg,sec in pool:
        r=fwd(px,c,d,n)
        if r is not None: ent.append((c,sg,sec,r))
    if len(ent)<NPICK: continue
    DAYS.append((d,ent,bm))
print("선정일",len(DAYS))

def run(abd, N):
    out=[]
    for d,ent,bm in DAYS:
        at=abd.get(d,{})
        keep=sorted(ent,key=lambda x:-at.get(x[2],0.0))[:N]
        if len(keep)<NPICK: keep=ent
        pk=sorted(keep,key=lambda x:x[1])[:NPICK]
        out.append((d,sum(x[3] for x in pk)/len(pk)-bm))
    return out

base=[(d,v) for d,v in json.load(open('_base.json'))['base']]
ser,_=load_search('sector_search.csv')
sc=attn_scores(ser,5,60)
sbd={d:{s:a_of(sc,s,d) for s in sc} for d,_,_ in DAYS}
obs=compare(base, run(sbd,20))
print("관측 A(20) MA5/60  차이 %+.4f%%p  t=%+.2f  fold %+.4f/%+.4f/%+.4f  상위3제거 %+.4f"%(
      obs['diff'],obs['t'],obs['folds'][0],obs['folds'][1],obs['folds'][2],obs['top3']))

pser,pcols=load_search('placebo_search.csv')
psc=attn_scores(pser,5,60)
pbd={d:{g:a_of(psc,g,d) for g in psc} for d,_,_ in DAYS}
sectors=sorted(sc.keys())
random.seed(20260908)
diffs=[]
for it in range(200):
    perm=pcols[:]; random.shuffle(perm)
    m=dict(zip(sectors,perm))
    abd={d:{s:pbd[d][m[s]] for s in sectors} for d,_,_ in DAYS}
    diffs.append(compare(base, run(abd,20))['diff'])
diffs.sort()
p=sum(1 for x in diffs if x>=obs['diff'])/len(diffs)
print("무관 대조군 200회: 평균 %+.4f  sd %.4f  최대 %+.4f  95%%분위 %+.4f"%(
      statistics.mean(diffs),statistics.stdev(diffs),diffs[-1],diffs[189]))
print("★ 경험적 p (관측 이상인 무관 신호 비율) = %.3f"%p)
json.dump({'obs':obs,'placebo':diffs}, open('_run4.json','w'))
