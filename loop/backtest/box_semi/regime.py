import pandas as pd, numpy as np
df=pd.read_csv('../panel_ohlc_long.csv',dtype={'code':str})
def get(c): return df[df.code==c].set_index('date').sort_index()
K=get('069500')
def ind(d):
    h,l,c=d.high,d.low,d.close;pc=c.shift()
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    up=h.diff();dn=-l.diff()
    pdm=np.where((up>dn)&(up>0),up,0.);mdm=np.where((dn>up)&(dn>0),dn,0.)
    w=lambda x:pd.Series(x,index=d.index).ewm(alpha=1/14,adjust=False).mean()
    atr=w(tr);pdi=100*w(pdm)/atr;mdi=100*w(mdm)/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi);adx=dx.ewm(alpha=1/14,adjust=False).mean()
    o=pd.DataFrame(index=d.index)
    o['adx']=adx
    for n in (14,20):
        o[f'chop{n}']=100*np.log10(tr.rolling(n).sum()/(h.rolling(n).max()-l.rolling(n).min()))/np.log10(n)
    o['er20']=(c-c.shift(20)).abs()/c.diff().abs().rolling(20).sum()
    ma=c.rolling(20).mean();sd=c.rolling(20).std();bw=4*sd/ma
    o['bw']=bw;o['bw_pct']=bw.expanding(250).rank(pct=True)
    w60=c.rolling(60).max()/c.rolling(60).min()-1;o['w60_pct']=w60.expanding(250).rank(pct=True)
    ma60=c.rolling(60).mean();o['ma60slope']=(ma60/ma60.shift(20)-1).abs()
    return o
I=ind(K)
DEF={
 'ADX<20':I.adx<20,'ADX<25':I.adx<25,
 'CHOP14>61.8':I.chop14>61.8,'CHOP20>61.8':I.chop20>61.8,
 'ER20<0.2':I.er20<0.2,'ER20<0.3':I.er20<0.3,
 'BW하위30%':I.bw_pct<=0.3,
 '60일폭하위30%&MA60평탄':(I.w60_pct<=0.3)&(I.ma60slope<0.02),
 '복합(ADX<20,CHOP>61.8,ER<0.3 중 2)':((I.adx<20).astype(int)+(I.chop14>61.8).astype(int)+(I.er20<0.3).astype(int))>=2,
}
valid=I.index[I.index>=20200401]   # 확장창 250일 워밍업
DEF={k:v.reindex(valid).fillna(False) for k,v in DEF.items()}
if __name__=='__main__':
    c=K.close.reindex(valid)
    # 이후 20일: |수익|, 고저폭 → 판정이 '앞으로의 박스'를 맞히나
    fr=(K.close.shift(-20)/K.close-1).abs().reindex(valid)*100
    fh=(K.high[::-1].rolling(20).max()[::-1].shift(-1)/K.low[::-1].rolling(20).min()[::-1].shift(-1)-1).reindex(valid)*100
    # 평균회귀 메커니즘: 20일 채널 위치 → 이후 10일 수익 (KODEX200, 반도체)
    pos=((K.close-K.close.rolling(20).min())/(K.close.rolling(20).max()-K.close.rolling(20).min())).reindex(valid)
    S=get('091160');f10k=(K.close.shift(-10)/K.close-1).reindex(valid)*100;f10s=(S.close.shift(-10)/S.close-1).reindex(valid)*100
    print(f'{"정의":34s} 해당일% | 이후20일|수익| 이후20일고저폭 | 채널위치↔이후10일 상관(K200/반도체) | 하단20%-상단20% 이후10일 반도체')
    base=(fr.mean(),fh.mean())
    print(f'{"(전체 평균)":34s}  100.0 | {base[0]:5.2f}  {base[1]:6.2f} | {pos.corr(f10k):+.3f} / {pos.corr(f10s):+.3f} | {f10s[pos<=.2].mean()-f10s[pos>=.8].mean():+.2f}%p')
    for k,m in DEF.items():
        m=m.astype(bool)
        lo=f10s[m&(pos<=.2)];hi=f10s[m&(pos>=.8)]
        print(f'{k:34s} {m.mean()*100:6.1f} | {fr[m].mean():5.2f}  {fh[m].mean():6.2f} | {pos[m].corr(f10k[m]):+.3f} / {pos[m].corr(f10s[m]):+.3f} | {lo.mean()-hi.mean():+.2f}%p (n={len(lo)}/{len(hi)})')
    print('\n오늘(마지막 날) 판정:',{k:bool(v.iloc[-1]) for k,v in DEF.items()}, 'ADX',round(I.adx.iloc[-1],1),'CHOP14',round(I.chop14.iloc[-1],1),'ER20',round(I.er20.iloc[-1],2),'BW%',round(I.bw_pct.iloc[-1],2),'마지막일',valid[-1])
