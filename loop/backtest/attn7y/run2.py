import json, pickle, statistics
from bt_attn import *
px, names = load_px()
cc = pickle.load(open('_cache.pkl','rb')); dates, cands = cc['dates'], cc['cands']
base = [(d, v) for d, v in json.load(open('_base.json'))['base']]
ser, _ = load_search('sector_search.csv')
sc = attn_scores(ser, 5, 20)
print(f"{'변형':<16}{'후보평균':>9}{'차이':>9}{'t':>7}{'fold1':>8}{'fold2':>8}{'fold3':>8}{'상위3제거':>10}{'중앙':>8}")
rows=[]
for kind, params in [('A',[10,15,20,25]),('C',[5,10,15]),('B',[0.2,0.3,0.5,0.7])]:
    for p in params:
        s = series(px, dates, cands, mk_picker(kind, p, sc))
        r = compare(base, s); r['tag']=f"{kind}({p})"; rows.append(r)
        print(f"{r['tag']:<16}{r['cand']:+9.4f}{r['diff']:+9.4f}{r['t']:+7.2f}"
              f"{r['folds'][0]:+8.4f}{r['folds'][1]:+8.4f}{r['folds'][2]:+8.4f}"
              f"{r['top3']:+10.4f}{r['med']:+8.4f}")
json.dump(rows, open('_run2.json','w'))
