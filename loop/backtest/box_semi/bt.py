import pandas as pd, numpy as np, itertools, json
df=pd.read_csv('../panel_ohlc_long.csv',dtype={'code':str})
codes={'069500':'KODEX200','091160':'KODEX반도체','091230':'TIGER반도체','396500':'TIGER반도체TOP10','395160':'KODEX AI반도체TOP2+'}
px={c:df[df.code==c].set_index('date').sort_index() for c in codes}
k2=px['069500']
# --- 전제 확인: 반도체 ETF와 KOSPI200 상관/베타
out={}
for c in codes:
    if c=='069500':continue
    j=pd.concat([px[c].close.pct_change(),k2.close.pct_change()],axis=1,keys=['s','k']).dropna()
    out[codes[c]]=dict(n=len(j),corr=round(j.corr().iloc[0,1],3),beta=round(np.polyfit(j.k,j.s,1)[0],2),
        vol_ratio=round(j.s.std()/j.k.std(),2))
print('상관',out)
# --- 현재 박스권인가
c=k2.close
for N in (20,60,120):
    w=c.iloc[-N:]; print(f'KODEX200 최근{N}일: 고{w.max():.0f} 저{w.min():.0f} 폭{(w.max()/w.min()-1)*100:.1f}% 현위치{(c.iloc[-1]-w.min())/(w.max()-w.min()):.2f} 수익{(c.iloc[-1]/c.iloc[-N-1]-1)*100:+.1f}%')
    s=px['396500'].close; w=s.iloc[-N:]; print(f'  TIGER반도체TOP10 {N}일: 폭{(w.max()/w.min()-1)*100:.1f}% 현위치{(s.iloc[-1]-w.min())/(w.max()-w.min()):.2f} 수익{(s.iloc[-1]/s.iloc[-N-1]-1)*100:+.1f}%')
# 과거 '박스권' 판정의 지속성: 60일 폭이 좁은 날(하위 30%) 이후 60일 동안 박스 안에 머문 비율
def box_persist(s,N=60,look=60):
    H=s.rolling(N).max();L=s.rolling(N).min();wid=H/L-1
    thr=wid.quantile(.3);res=[]
    for i in range(N,len(s)-look):
        if wid.iloc[i]<=thr:
            f=s.iloc[i+1:i+1+look]
            res.append(((f<=H.iloc[i]*1.0)&(f>=L.iloc[i])).all())
    return np.mean(res),len(res),thr
for c_ in ('069500','091160','396500'):
    p,n,t=box_persist(px[c_].close);print(f'박스지속 {codes[c_]}: 60일폭 하위30%(≤{t*100:.1f}%)인 날 이후 60일 내내 박스 유지 {p*100:.1f}% (n={n})')
json.dump(out,open('corr.json','w'),ensure_ascii=False)
