import pandas as pd, numpy as np
from scipy import stats
import os as _os; SP=_os.path.dirname(_os.path.abspath(__file__))
df=pd.read_csv(SP+'/panel.csv',dtype={'code':str})
sec=pd.read_csv(SP+'/../stock_sector_dart.csv',dtype=str)
sec['ind2']=sec.induty_code.astype(str).str[:2]
df=df.merge(sec[['code','ind2']],on='code',how='left')
IND={'26':'전자부품·반도체','27':'의료·정밀기기','28':'전기장비','29':'기계장비','30':'자동차','31':'기타운송(조선)','20':'화학','21':'의약품','24':'1차금속','64':'금융','65':'보험','66':'금융서비스','58':'출판·게임','62':'소프트웨어','63':'정보서비스','41':'건설','10':'식품','46':'도매','47':'소매','35':'전기가스','49':'육상운송','50':'수상운송','51':'항공운송','68':'부동산','72':'연구개발','13':'섬유','45':'차량판매','23':'비금속','22':'고무플라스틱','25':'금속가공','61':'통신','52':'운송서비스','73':'전문서비스','70':'본사·경영'}
df['sname']=df.ind2.map(IND).fillna('기타('+df.ind2.fillna('NA')+')')

print('='*72); print('축 5. 섹터 집계 — "반도체 전망 좋다 → 반도체 산다" 형태'); print('='*72)
g=df.dropna(subset=['rv_mid','r_late']).groupby('sname').agg(
    n=('code','size'), 수정=('rv_mid','median'), 이후수익=('r_late','mean'), 동시수익=('r_mid','mean'))
g=g[g.n>=4].sort_values('수정',ascending=False)
g['수정']=(g['수정']*100).round(2); g['이후수익']=(g['이후수익']*100).round(2); g['동시수익']=(g['동시수익']*100).round(2)
print(g.to_string())
r,p=stats.spearmanr(g['수정'],g['이후수익']); print(f'\n  섹터 수정 중앙값 → 이후 1개월 섹터 수익률   섹터수={len(g)}  rho={r:+.3f}  p={p:.3f}')
r2,p2=stats.spearmanr(g['수정'],g['동시수익']); print(f'  섹터 수정 중앙값 ↔ 동시 섹터 수익률(k=0)               rho={r2:+.3f}  p={p2:.3f}')
top=g.head(5).index.tolist(); bot=g.tail(5).index.tolist()
print(f'\n  상위5섹터 이후수익 평균 {g.loc[top,"이후수익"].mean():+.2f}%  vs  하위5섹터 {g.loc[bot,"이후수익"].mean():+.2f}%  (차 {g.loc[top,"이후수익"].mean()-g.loc[bot,"이후수익"].mean():+.2f}%p)')

print('\n'+'='*72); print('대조군 — 섹터 라벨 무작위 셔플 500회 (09-02 신설 관문)'); print('='*72)
d=df.dropna(subset=['rv_mid','r_late','sname']).copy()
d=d[d.sname.isin(g.index)]
obs=g.loc[top,'이후수익'].mean()-g.loc[bot,'이후수익'].mean()
rng=np.random.default_rng(7); null=[]
for _ in range(500):
    s=d.copy(); s['sname']=rng.permutation(s.sname.values)
    gg=s.groupby('sname').agg(n=('code','size'),수정=('rv_mid','median'),이후=('r_late','mean'))
    gg=gg[gg.n>=4].sort_values('수정',ascending=False)
    if len(gg)<10: continue
    null.append(100*(gg.head(5)['이후'].mean()-gg.tail(5)['이후'].mean()))
null=np.array(null)
print(f'  관측 스프레드 {obs:+.2f}%p   셔플 귀무 평균 {null.mean():+.2f}%p  sd {null.std():.2f}')
print(f'  경험적 p(|셔플| >= |관측|) = {np.mean(np.abs(null)>=abs(obs)):.3f}   귀무 90% 구간 [{np.percentile(null,5):+.2f}, {np.percentile(null,95):+.2f}]')

print('\n'+'='*72); print('축 6. 역모멘텀 통제 — 수정 신호가 과거 주가와 별개인가'); print('='*72)
z=df[['rv_mid','r_late','r_mid']].dropna()
def pcorr(x,y,c):
    rx=stats.rankdata(x); ry=stats.rankdata(y); rc=stats.rankdata(c)
    rxy,rxc,ryc=np.corrcoef(rx,ry)[0,1],np.corrcoef(rx,rc)[0,1],np.corrcoef(ry,rc)[0,1]
    return (rxy-rxc*ryc)/np.sqrt((1-rxc**2)*(1-ryc**2))
print(f'  단순:   rv_mid → r_late   rho={stats.spearmanr(z.rv_mid,z.r_late)[0]:+.3f}')
print(f'  r_mid 통제 후 부분상관              rho={pcorr(z.rv_mid,z.r_late,z.r_mid):+.3f}   (n={len(z)})')

print('\n'+'='*72); print('축 2 정정 — 목표주가 괴리율의 시점 정합성'); print('='*72)
z2=df[['upside','r_late','r_mid','r_early']].dropna()
print(f'  괴리율 ↔ 최근1개월 주가 (동시)     rho={stats.spearmanr(z2.upside,z2.r_late)[0]:+.3f}')
print(f'  괴리율 ↔ 1~2개월전 주가            rho={stats.spearmanr(z2.upside,z2.r_mid)[0]:+.3f}')
print(f'  괴리율 ↔ 2~3개월전 주가            rho={stats.spearmanr(z2.upside,z2.r_early)[0]:+.3f}')
print('  → 괴리율은 오늘 주가로 계산되므로 "오늘 괴리 → 최근 수익" 관계는 예측이 아니라 항등에 가깝다.')
