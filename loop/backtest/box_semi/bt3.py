exec(open('bt2.py').read().split('rows=[]')[0])
# 게이트: KODEX200 이 '박스권'일 때만 진입 (60일 폭이 과거(확장창) 하위 30% & 60일 수익 |r| < 폭/4)
k=P['069500'].close; W=k.rolling(60).max()/k.rolling(60).min()-1
thr=W.expanding(250).quantile(.3); ret60=k/k.shift(60)-1
g=((W<=thr)&(ret60.abs()<W/4))
print('KODEX200 박스 판정일 비율',round(g.mean()*100,1),'% / 최근값',bool(g.iloc[-1]),'60일폭',round(W.iloc[-1]*100,1),'임계',round(thr.iloc[-1]*100,1))
for code in ['091160','396500','395160']:
    d=P[code];gate=g.reindex(d.index).fillna(False).values;bh=stats(d.close.pct_change())
    res=[]
    for N,lo,hi,stop in itertools.product([20,40,60],[0.1,0.2,0.3],[0.7,0.8,0.9],[None,0.05]):
        r,tr,exp=run(d,N,lo,hi,stop,gate=gate);s=stats(r);w=[x[2] for x in tr]
        res.append((N,lo,hi,stop,*s,len(tr),np.mean(w)*100 if w else np.nan,exp*100))
    X=pd.DataFrame(res,columns='N lo hi stop cagr sh mdd ntr avgtr exp'.split())
    print(codes[code],'B&H Sh',round(bh[1],2),'| 박스게이트 54변형: Sh 중앙',round(X.sh.median(),2),'최고',round(X.sh.max(),2),'| 거래수 중앙',X.ntr.median(),'| 건당 평균 중앙',round(X.avgtr.median(),2),'% | 노출 중앙',round(X.exp.median(),1),'%')
    r,tr,_=run(d,20,.2,.8,None,gate=gate)
    print('  N20 0.2/0.8 거래:',[(d.index[a],b-a,round(x*100,1)) for a,b,x in tr])
