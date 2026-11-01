import pandas as pd, numpy as np, os
B=os.path.expanduser('~/mnt/loop/backtest'); S=B+'/sjh'
d=pd.read_csv(S+'/px_daily.csv',dtype={'code':str})
d=d[d.date>=20190101]
bench=d[d.code=='069500'].set_index('date')[['open','close']].rename(columns={'open':'b_open','close':'b_close'})
d=d[d.code!='069500']
C=d.pivot(index='date',columns='code',values='close').sort_index()
O=d.pivot(index='date',columns='code',values='open').sort_index()
V=d.pivot(index='date',columns='code',values='volume').sort_index()
dates=C.index.values; codes=np.array(C.columns)
np.save(S+'/dates.npy',dates); np.save(S+'/codes.npy',codes)
for n,M in [('C',C),('O',O),('V',V)]: np.save(S+'/%s.npy'%n,M.values.astype('float32'))
bench=bench.reindex(dates).ffill()
np.save(S+'/bench.npy',bench[['b_open','b_close']].values.astype('float64'))
print('grid',C.shape)

# PIT 유니버스 멤버십 + 시총/거래대금(스냅샷)
pit=pd.read_csv(B+'/_krx_pit.csv',dtype={'code':str})
snaps=sorted(pit.date.unique())
ci={c:i for i,c in enumerate(codes)}
MEM=np.zeros((len(dates),len(codes)),dtype=bool)   # PIT 멤버 & 유동성 통과
SHR=np.full((len(dates),len(codes)),np.nan,dtype='float32')
for k,sd in enumerate(snaps):
    g=pit[pit.date==sd]
    g=g[(g.value>=5e8)&(g.close>=1000)&(g.mktcap>=3e10)]
    idx=[ci[c] for c in g.code if c in ci]
    shr=[s for c,s in zip(g.code,g.shrs) if c in ci]
    lo=np.searchsorted(dates,sd); hi=np.searchsorted(dates,snaps[k+1]) if k+1<len(snaps) else len(dates)
    MEM[lo:hi,idx]=True; SHR[lo:hi,idx]=np.array(shr,dtype='float32')
np.save(S+'/MEM.npy',MEM); np.save(S+'/SHR.npy',SHR)
print('mem per day', MEM.sum(1).min(), MEM.sum(1).mean().round(0), MEM.sum(1).max())

# 섹터 (KSIC 2자리) + yfinance 섹터(정의교체용)
sd=pd.read_csv(B+'/stock_sector_dart.csv',dtype={'code':str,'induty_code':str})
sd['ind2']=sd.induty_code.str[:2]
m=dict(zip(sd.code,sd.ind2))
sec=np.array([m.get(c,'NA') if isinstance(m.get(c,'NA'),str) else 'NA' for c in codes])
sy=pd.read_csv(B+'/stock_sector_yf.csv',dtype={'code':str}); my=dict(zip(sy.code,sy.sector))
secy=np.array([str(my.get(c,'NA')) for c in codes])
np.save(S+'/sec.npy',sec); np.save(S+'/secy.npy',secy)
print('sec cov',(sec!='NA').mean().round(3),'yf cov',(secy!='nan').mean().round(3),len(set(sec)),len(set(secy)))

# 재무: 날짜×종목 → 최신 가용 보고서의 sa_g/op_g/op_pos
fu=pd.read_csv(S+'/fund.csv',dtype={'code':str}).sort_values('avail')
SAG=np.full((len(dates),len(codes)),np.nan,dtype='float32')
OPG=np.full_like(SAG,np.nan); OPP=np.zeros((len(dates),len(codes)),dtype=bool)
fu=fu[fu.code.isin(ci)]
fu['ci']=fu.code.map(ci); fu['di']=np.searchsorted(dates,fu.avail.values)
fu=fu[fu.di<len(dates)]
for r in fu.itertuples():
    sg=np.clip(r.sa_g,-3,3) if np.isfinite(r.sa_g) else np.nan
    og=np.clip(r.op_g,-3,3) if np.isfinite(r.op_g) else np.nan
    SAG[r.di:,r.ci]=sg; OPG[r.di:,r.ci]=og; OPP[r.di:,r.ci]=bool(r.op_pos)
np.save(S+'/SAG.npy',SAG); np.save(S+'/OPG.npy',OPG); np.save(S+'/OPP.npy',OPP)
print('fund cov at end', np.isfinite(SAG[-1]).sum(), OPP[-1].sum())
