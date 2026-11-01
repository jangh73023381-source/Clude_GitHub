import json, pickle, statistics, random
from bt_attn import *
px, names = load_px()
cc = pickle.load(open('_cache.pkl','rb')); dates, cands = cc['dates'], cc['cands']
base = [(d, v) for d, v in json.load(open('_base.json'))['base']]
ser, _ = load_search('sector_search.csv')

def show(tag, s):
    r = compare(base, s)
    print(f"{tag:<22}{r['cand']:+9.4f}{r['diff']:+9.4f}{r['t']:+7.2f}"
          f"{r['folds'][0]:+8.4f}{r['folds'][1]:+8.4f}{r['folds'][2]:+8.4f}{r['top3']:+10.4f}")
    return r

print("■ R1 — MA 조합 격자 (변형 A(20)·B(0.3) 고정)")
print(f"{'(a,b)':<22}{'후보평균':>9}{'차이':>9}{'t':>7}{'fold1':>8}{'fold2':>8}{'fold3':>8}{'상위3제거':>10}")
for a,b in [(1,20),(3,20),(5,20),(5,60),(10,60),(20,60)]:
    sc = attn_scores(ser, a, b)
    show(f"A(20) MA{a}/{b}", series(px,dates,cands,mk_picker('A',20,sc)))
print()
print("■ 역방향 — 관심도 낮은 쪽 선호 (부호 반전)")
print(f"{'변형':<22}{'후보평균':>9}{'차이':>9}{'t':>7}{'fold1':>8}{'fold2':>8}{'fold3':>8}{'상위3제거':>10}")
sc5 = attn_scores(ser, 5, 20)
inv = {k: {d: -v for d, v in s.items()} for k, s in sc5.items()}
for p in [10,15,20,25]:
    show(f"A역({p})", series(px,dates,cands,mk_picker('A',p,inv)))
for w in [0.3,0.5]:
    show(f"B역({w})", series(px,dates,cands,mk_picker('B',w,inv)))
