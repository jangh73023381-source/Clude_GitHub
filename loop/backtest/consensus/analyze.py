import pandas as pd, numpy as np, glob, json
from scipy import stats
import os as _os; SP=_os.path.dirname(_os.path.abspath(__file__))
df=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(SP+'/raw_*.csv'))],ignore_index=True)
df=df.drop_duplicates('code')
df['code']=df.code.astype(str).str.zfill(6)
print(f'수집 {len(df)}종 (요청 416종, 커버율 {100*len(df)/416:.0f}%)')
df=df[df.n>=3].copy()
print(f'애널리스트 3명 이상: {len(df)}종  (중앙 {df.n.median():.0f}명)')

# 수익률 (21거래일 = 약 1개월)
df['r_late']=df.p0/df.p21-1; df['r_mid']=df.p21/df.p42-1; df['r_early']=df.p42/df.p63-1; df['r_e2']=df.p63/df.p84-1
# 가격정규화 revision: ΔEPS / 시작가  (부호·0 문제 회피 — 실무 표준)
for tag,(a,b,px) in {'late':('e_cur','e30','p21'),'mid':('e30','e60','p42'),'early':('e60','e90','p63')}.items():
    df['rv_'+tag]=(df[a]-df[b])/df[px].abs()
    df['fv_'+tag]=(df[a.replace('e','f')]-df[b.replace('e','f')])/df[px].abs() if a!='e_cur' else (df['f_cur']-df['f30'])/df[px].abs()
# 비율형(참고)
def rr(a,b):
    m=(np.sign(a)==np.sign(b))&(b.abs()>1e-9)
    return np.where(m,a/b-1,np.nan)
df['pc_late']=rr(df.e_cur,df.e30); df['pc_mid']=rr(df.e30,df.e60)
df['upside']=df.tp_mean/df.tp_cur-1
tot=df[['sb','bu','ho','se','ss']].sum(axis=1)
df['buyratio']=(df.sb+df.bu)/tot.replace(0,np.nan)
df=df.replace([np.inf,-np.inf],np.nan)
df.to_csv(SP+'/panel.csv',index=False)

def sp(a,b,lbl,d=None):
    d=df if d is None else d
    z=d[[a,b]].dropna()
    if len(z)<20: print(f'{lbl:<44} n={len(z)} 부족'); return
    r,p=stats.spearmanr(z[a],z[b])
    star='  ★' if p<0.05 else ''
    print(f'{lbl:<44} n={len(z):3d}  rho={r:+.3f}  p={p:.3f}{star}')

print('\n'+'='*72)
print('축 1. 당해연도 EPS 추정치 수정 (가격정규화 ΔEPS/주가)')
print('='*72)
print('[동시 k=0]')
sp('rv_late','r_late','  최근1개월 수정 ↔ 최근1개월 주가')
sp('rv_mid','r_mid','  1~2개월전 수정 ↔ 같은기간 주가')
sp('rv_early','r_early','  2~3개월전 수정 ↔ 같은기간 주가')
print('[후행 — 주가가 먼저, 수정이 나중]')
sp('rv_late','r_mid','  최근1개월 수정 ↔ 1~2개월전 주가')
sp('rv_mid','r_early','  1~2개월전 수정 ↔ 2~3개월전 주가')
sp('rv_late','r_early','  최근1개월 수정 ↔ 2~3개월전 주가')
print('[선행 — 수정이 먼저, 주가가 나중  ★핵심]')
sp('rv_mid','r_late','  1~2개월전 수정 → 이후 1개월 주가')
sp('rv_early','r_mid','  2~3개월전 수정 → 이후 1개월 주가')
sp('rv_early','r_late','  2~3개월전 수정 → 이후 2개월 주가')
print('[비율형(ΔEPS/EPS) 교차확인 — R3 정의교체]')
sp('pc_mid','r_late','  1~2개월전 수정률 → 이후 1개월 주가')
sp('pc_late','r_late','  최근1개월 수정률 ↔ 최근1개월 주가(동시)')
