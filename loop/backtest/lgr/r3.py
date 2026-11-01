import engine as E, numpy as np, json
P=E.POOL; res={}
def m(mask,R): return float(np.nanmean(E.ew(mask,R)))*100
print('POOL raw: GAP %.3f  A1 %.3f  B1 %.3f  A2 %.3f B2 %.3f B5 %.3f B20 %.3f'%(m(P,E.GAP),m(P,E.A1),m(P,E.B1),m(P,E.A2),m(P,E.B2),m(P,E.B5),m(P,E.B20)))
U=E.MEMU
print('UNI  raw: GAP %.3f  A1 %.3f  B1 %.3f  A2 %.3f B2 %.3f B5 %.3f B20 %.3f'%(m(U,E.GAP),m(U,E.A1),m(U,E.B1),m(U,E.A2),m(U,E.B2),m(U,E.B5),m(U,E.B20)))
print('bench: A1 %.3f B1 %.3f B2 %.3f B20 %.3f'%(np.nanmean(E.bA1)*100,np.nanmean(E.bB1)*100,np.nanmean(E.bB2)*100,np.nanmean(E.bB20)*100))
# 등락률 구간별 풀 익일 수익 (상승폭이 클수록?)
R=E.R1
for lo,hi in ((0,0.02),(0.02,0.05),(0.05,0.10),(0.10,0.20),(0.20,1)):
    mk=P&(R>=lo)&(R<hi); print(f'ret_D [{lo:.0%},{hi:.0%}) n/day {mk.sum(1).mean():.1f}  GAP {m(mk,E.GAP):+.3f} B1 {m(mk,E.B1):+.3f} B2 {m(mk,E.B2):+.3f}')
# 시총 필터
MC=E.MC
for cap in (3e11,1e12):
    Pc=P&(MC>=cap); print(f'시총≥{cap/1e8:.0f}억: n/day {Pc.sum(1).mean():.1f} POOL B2 raw {m(Pc,E.B2):+.3f} | 사모top10 B2 raw {m(E.select_topk(E.rSAMO,Pc,10),E.B2):+.3f} 연기금top10 {m(E.select_topk(E.rPEN,Pc,10),E.B2):+.3f} 기관top10 {m(E.select_topk(E.rORG,Pc,10),E.B2):+.3f}')
# 기관 순매수 부호별 풀 (1박2일 '다음날까지 간다' 검정)
for nm,mk in (('기관>0',P&(E.rORG>0)),('기관<0',P&(E.rORG<0)),('사모>0',P&(E.rSAMO>0)),('사모<0',P&(E.rSAMO<0)),('연기금>0',P&(E.rPEN>0)),('연기금<0',P&(E.rPEN<0))):
    print(f'{nm}: n/day {mk.sum(1).mean():.1f} A1 {m(mk,E.A1):+.3f} B1 {m(mk,E.B1):+.3f} B2 {m(mk,E.B2):+.3f} B5 {m(mk,E.B5):+.3f} B20 {m(mk,E.B20):+.3f}')
# 강도 분위 (사모 시총대비 %) — 단조성
sc=np.where(P,E.rSAMO,np.nan)
for q in ((0,0.5),(0.5,0.8),(0.8,0.95),(0.95,1.0)):
    lo=np.nanquantile(sc,q[0],axis=1); hi=np.nanquantile(sc,q[1],axis=1)
    mk=P&(sc>=lo[:,None])&(sc<=hi[:,None]); print(f'사모 강도 분위 {q}: B2 raw {m(mk,E.B2):+.3f} B5 {m(mk,E.B5):+.3f}')
# 사모 순매수 상위 종목의 '절대' 강도 임계 (시총의 0.1%/0.3%/0.5% 이상)
for th in (0.1,0.3,0.5,1.0):
    mk=P&(E.rSAMO>=th); print(f'사모 ≥{th}%시총: n/day {mk.sum(1).mean():.2f} 발동일 {int((mk.sum(1)>0).sum())} B1 raw {m(mk,E.B1):+.3f} B2 raw {m(mk,E.B2):+.3f} B5 {m(mk,E.B5):+.3f}')
