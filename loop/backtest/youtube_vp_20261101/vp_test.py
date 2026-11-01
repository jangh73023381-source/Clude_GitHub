# 유튜브 'Volume Profile POC'(호두의 AI 분석실 2026-10-29) 일봉 재현 검정
# 영상: 어제 1분봉 POC 터치율 vs 대칭 비교선(2O-level). 여기선 일봉이라 1일 POC는 불가 →
# 레벨 = 어제종가(영상의 '반전': POC≈종가) · 20/60일 매물대 POC · 어제 중간값(아무 선 대조)
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/sessions'); import os
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(BT),'references','scripts'))
START='20190401'; NB=40
rng=np.random.default_rng(7)

def load_etf():
    import universe_filters as uf
    df=pd.read_csv(os.path.join(BT,'panel_ohlc_long.csv'),dtype={'code':str,'date':str})
    names=df.groupby('code')['name'].last()
    keep=[c for c,n in names.items() if uf.eligible(n)]
    df=df[df.code.isin(keep)]
    M={k:df.pivot(index='date',columns='code',values=k).sort_index() for k in ['open','high','low','close','volume']}
    flag=np.zeros(M['close'].shape,bool)
    return M['close'].index.values,{k:v.values.astype(float) for k,v in M.items()},flag

def load_stk():
    K=os.path.join(BT,'krx_full'); d=np.load(K+'/dates.npy',allow_pickle=True); i0=np.searchsorted(d,START)
    P={k:np.load(f'{K}/P_{k}.npy')[i0:].astype(float) for k in ['open','high','low','close','value','chg_pct']}
    with np.errstate(all='ignore'):
        r=P['close'][1:]/P['close'][:-1]-1
        flag=np.zeros(P['close'].shape,bool); flag[1:]=np.abs(r-P['chg_pct'][1:]/100)>0.01
        P['volume']=P['value']/((P['high']+P['low'])/2)
    codes=np.load(K+'/codes.npy',allow_pickle=True)
    return d[i0:],P,flag,codes

def poc(H,L,V,N):
    """t행에서 직전 N일(t-N..t-1) 일봉 균등분배 매물대 POC. 반환 (T,A)"""
    T,A=H.shape; out=np.full((T,A),np.nan)
    for t in range(N,T):
        h=H[t-N:t]; l=L[t-N:t]; v=V[t-N:t]
        ok=np.isfinite(h).all(0)&np.isfinite(l).all(0)&np.isfinite(v).all(0)&(v.sum(0)>0)
        if not ok.any(): continue
        h,l,v=h[:,ok],l[:,ok],v[:,ok]; lo=l.min(0); hi=h.max(0); w=(hi-lo)/NB
        e=lo[None,:,None]+w[None,:,None]*np.arange(NB+1)[None,None,:]   # 1,a,NB+1
        hh=h[:,:,None]; ll=l[:,:,None]; rgt=np.maximum(hh-ll,1e-9)
        ov=np.clip(np.minimum(hh,e[...,1:])-np.maximum(ll,e[...,:-1]),0,None)/rgt
        ov=np.where((hh-ll)<1e-9,((ll>=e[...,:-1])&(ll<e[...,1:])).astype(float),ov)
        prof=(ov*v[:,:,None]).sum(0); b=prof.argmax(1)
        out[t,np.where(ok)[0]]=lo+w*(b+0.5)
    return out

def evaluate(dates,P,mask,levels,label):
    O,H,L,C=P['open'],P['high'],P['low'],P['close']
    yr=np.array([int(x[:4]) for x in dates])[:,None]*np.ones(O.shape[1],int)
    T=len(dates); fold=np.minimum((np.arange(T)*3)//T,2)[:,None]*np.ones(O.shape[1],int)
    rows=[]
    for nm,lv in levels.items():
        with np.errstate(all='ignore'):
            d=np.abs(O-lv)/O; m=2*O-lv
            ok=mask&np.isfinite(lv)&np.isfinite(O)&(d>=0.001)&(d<=0.15)&(L>0)
            tl=(L<=lv)&(lv<=H); tm=(L<=m)&(m<=H)
            above=lv<O   # 레벨이 시가 아래 = 위에서 내려와 닿음
            hold_l=np.where(above,C>=lv,C<=lv); hold_m=np.where(above,C<=m,C>=m)
            # 집행: 시가 아래 레벨에 매수 지정가 → 종가 청산 (레벨 vs 같은 분포 거리 셔플 대조)
            buy=ok&above; fill=buy&(L<=lv); rl=np.where(fill,C/lv-1,0.0)
            dd=d[buy].copy(); rng.shuffle(dd); lc=np.full(O.shape,np.nan); lc[buy]=O[buy]*(1-dd)
            fc=buy&(L<=lc); rc=np.where(fc,C/lc-1,0.0); oc=C/O-1
        for f in [-1,0,1,2]:
            s=ok if f<0 else ok&(fold==f); b=buy if f<0 else buy&(fold==f)
            n=s.sum()
            if n==0: continue
            r=dict(group=label,level=nm,fold='all' if f<0 else f+1,n=int(n),
                   touch=tl[s].mean()*100,mirror=tm[s].mean()*100,
                   hold=hold_l[s&tl].mean()*100,hold_m=hold_m[s&tm].mean()*100,
                   nbuy=int(b.sum()),fill=(b&(L<=lv))[b].mean()*100,fill_c=(b&(L<=lc))[b].mean()*100,
                   ret_lv_bp=rl[b].mean()*1e4,ret_ctrl_bp=rc[b].mean()*1e4,
                   unfilled_oc_bp=oc[b&~(L<=lv)].mean()*1e4, filled_oc_bp=oc[b&(L<=lv)].mean()*1e4)
            rows.append(r)
            if f<0:  # 일자 클러스터 t (일별 평균 차)
                dif=np.where(b,rl-rc,np.nan); dm=np.nanmean(dif,1); dm=dm[np.isfinite(dm)]
                r['t_lv_vs_ctrl']=dm.mean()/dm.std(ddof=1)*np.sqrt(len(dm))
                tt=np.where(s,tl.astype(float)-tm.astype(float),np.nan); tm_=np.nanmean(tt,1); tm_=tm_[np.isfinite(tm_)]
                r['t_touch']=tm_.mean()/tm_.std(ddof=1)*np.sqrt(len(tm_))
    return rows

def levels_for(P,flag,ns=(20,60)):
    C=P['close']; pc=np.full(C.shape,np.nan); pc[1:]=C[:-1]
    mid=np.full(C.shape,np.nan); mid[1:]=(P['high'][:-1]+P['low'][:-1])/2
    lv={'어제종가':pc,'어제중간값(대조)':mid}
    for N in ns: lv[f'POC{N}']=poc(P['high'],P['low'],P['volume'],N)
    return lv

if __name__=='__main__':
    which=sys.argv[1]; out=[]
    if which=='etf':
        dates,P,flag=load_etf(); s=dates>=START
        P={k:v[s] for k,v in P.items()}; dates=dates[s]; flag=flag[s]
        mask=np.isfinite(P['close']); mask[0]=False
        out=evaluate(dates,P,mask,levels_for(P,flag),'ETF')
    else:
        dates,P,flag,codes=load_stk()
        # 개별주: 전일 거래대금 상위 150 (+삼성전자·하이닉스 단독)
        V=np.nan_to_num(P['value']); avg=pd.DataFrame(V).rolling(20,min_periods=20).mean().shift(1).values
        rank=(-np.nan_to_num(avg,nan=-1)).argsort(1).argsort(1)
        top=(rank<150)&(np.nan_to_num(P['close'])>=1000)
        anyflag=pd.DataFrame(flag.astype(float)).rolling(61,min_periods=1).max().values>0
        cols=np.where(top.any(0))[0]
        Q={k:v[:,cols] for k,v in P.items()}; m=top[:,cols]&~anyflag[:,cols]; m[0]=False
        lv=levels_for(Q,None)
        out=evaluate(dates,Q,m,lv,'개별주 상위150')
        for code,nm in [('005930','삼성전자'),('000660','SK하이닉스')]:
            j=list(codes[cols]).index(code); mm=np.zeros_like(m); mm[:,j]=~anyflag[:,cols][:,j]; mm[0]=False
            out+=evaluate(dates,Q,mm,lv,nm)
    df=pd.DataFrame(out); df.to_csv(os.path.join(HERE,f'result_{which}.csv'),index=False,encoding='utf-8-sig')
    pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
    print(df[df.fold=='all'].round(2).to_string(index=False))
    print(df[df.fold!='all'][['group','level','fold','touch','mirror','hold','hold_m','ret_lv_bp','ret_ctrl_bp']].round(2).to_string(index=False))
