"""2026-10-06 루프 외 10축 검정 — 축1~5: 트랙 D(Rule EG v1.2, 눌림 10일) 보완 필터.
2026-09-03 formula.py 에서 '양수지만 미채택(다음 검정 후보)'으로 남긴 5축을 v1.2 기준으로 재검정.
신호 단위 20거래일 수익(진입=신호일 종가 / 보조: D+1 종가). 비교 기준 = v1.2 전체 신호.
관문: R1(인접 파라미터) · R2(3분할 fold vs v1.2) · R4(일내 층화 무작위 솎기 500회) · R5(일별차 상위3일 제거·중앙값).
"""
import os,pickle,numpy as np,pandas as pd,json
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
d=pickle.load(open(os.path.join(BT,'eg_review','_eg_cache.pkl'),'rb'))
O,H,L,C,V,MA20,MA60,VA,AMT,trend,B,dates=[d[k] for k in ['O','H','L','C','V','MA20','MA60','VA','AMT','trend','bench','dates']]
M,N=C.shape; Cf=pd.DataFrame(C.T).ffill().values.T
def sh(x,k):
    y=np.full_like(x,np.nan); y[:,k:]=x[:,:-k]; return y
def rm(x,w): return pd.DataFrame(x.T).rolling(w,min_periods=w).mean().values.T
def rmax(x,w): return pd.DataFrame(x.T).rolling(w,min_periods=w).max().values.T
def rmin(x,w): return pd.DataFrame(x.T).rolling(w,min_periods=w).min().values.T
TR=np.maximum(H-L,np.maximum(abs(H-sh(C,1)),abs(L-sh(C,1)))); ATR=rm(TR,14); H250=rmax(H,250)
t_=(C>=MA20)&(MA20>sh(MA20,1))&(C>MA60)&(MA60>=sh(MA60,5))
p_=(rmin(L,10)<=MA20*1.02)
c_=(C>=sh(O,1))&(C>O)&(sh(C,1)<sh(O,1))&(C>=L+(H-L)*0.6)
v_=(V>=VA*1.3)
valid=np.zeros((M,N),bool); valid[:,250:N-22]=True   # 250일 고점 가용 시점부터 공통 표본
base=np.nan_to_num(t_&p_&c_&v_,nan=0).astype(bool)&valid
r20=np.full((M,N),np.nan); r20[:,:-20]=Cf[:,20:]/Cf[:,:-20]-1
r20d1=np.full((M,N),np.nan); r20d1[:,:-21]=Cf[:,21:]/Cf[:,1:-20]-1
chg=C/sh(C,1)-1
folds=np.array_split(np.arange(250,N-22),3)
rng=np.random.default_rng(20261006)
def daymean(s,R):
    i,t=np.where(s); r=R[i,t]; df=pd.DataFrame(dict(t=t,r=r)).dropna(); return df.groupby('t').r.mean()
bday=daymean(base,r20)
bi,bt=np.where(base); bret=r20[bi,bt]
def ev(name,extra):
    s=base&np.nan_to_num(extra,nan=0).astype(bool)
    r=r20[s]; r=r[~np.isnan(r)]; n=len(r)
    if n<30: return dict(name=name,n=n)
    m=r.mean()*100; bm=np.nanmean(bret)*100
    f=[]; 
    for fd in folds:
        sl=slice(fd[0],fd[-1]+1)
        a=np.nanmean(r20[:,sl][s[:,sl]]); b=np.nanmean(r20[:,sl][base[:,sl]]); f.append((a-b)*100)
    cd=daymean(s,r20); dd=(cd-bday.reindex(cd.index))*100
    srt=dd.sort_values(ascending=False).values
    r5=dict(mean=dd.mean(),med=dd.median(),drop3=(srt.sum()-srt[:3].sum())/(len(srt)-3),drop10=(srt.sum()-srt[:10].sum())/(len(srt)-10),days=len(dd))
    # R4 일내 층화 무작위 솎기
    i,t=np.where(s); cnt=pd.Series(t).value_counts()
    bdf=pd.DataFrame(dict(t=bt,r=bret)).dropna()
    groups={k:g.r.values for k,g in bdf.groupby('t')}
    sims=[]
    for _ in range(500):
        tot=0;k=0
        for tt,c in cnt.items():
            g=groups.get(tt)
            if g is None: continue
            c=min(c,len(g)); pick=rng.choice(g,c,replace=False); tot+=pick.sum(); k+=c
        sims.append(tot/k*100)
    sims=np.array(sims); p=(sims>=m).mean()
    md1=np.nanmean(r20d1[s])*100-np.nanmean(r20d1[base])*100
    return dict(name=name,n=n,perday=n/len(range(250,N-22)),mean=m,vs=m-bm,win=(r>0).mean()*100,med=np.median(r)*100,
                f=f,r5=r5,p=p,null=sims.mean(),d1=md1)
rows=[dict(name='v1.2 전체(기준)',n=int(base.sum()),mean=np.nanmean(bret)*100,win=(bret[~np.isnan(bret)]>0).mean()*100,med=np.nanmedian(bret)*100)]
grid={
 '1 갭상승 시가':[('O>C(1)',O>sh(C,1)),('O>C(1)*1.005',O>sh(C,1)*1.005),('O>C(1)*1.01',O>sh(C,1)*1.01)],
 '2 거래량 배수':[('V>=1.5VA',V>=VA*1.5),('V>=1.75VA',V>=VA*1.75),('V>=2.0VA',V>=VA*2.0),('V>=2.5VA',V>=VA*2.5)],
 '3 250일고점 근접':[('C>=H250*0.97',C>=H250*0.97),('C>=H250*0.95',C>=H250*0.95),('C>=H250*0.92',C>=H250*0.92),('C>=H250*0.90',C>=H250*0.90)],
 '4 몸통 ATR':[('C-O>=0.5ATR',(C-O)>=0.5*ATR),('C-O>=0.75ATR',(C-O)>=0.75*ATR),('C-O>=1.0ATR',(C-O)>=1.0*ATR),('C-O>=1.25ATR',(C-O)>=1.25*ATR)],
 '5 눌림 거래량감소':[('avgV(1..3)<0.8VA',(sh(V,1)+sh(V,2)+sh(V,3))/3<0.8*VA),('avgV(1..3)<1.0VA',(sh(V,1)+sh(V,2)+sh(V,3))/3<VA),
                    ('avgV(1..3)<1.2VA',(sh(V,1)+sh(V,2)+sh(V,3))/3<1.2*VA),('avgV(1..5)<1.0VA',rm(V,5)/1>0) ],
}
# 5번 마지막 변형: 직전 5일 평균
v5=(sh(V,1)+sh(V,2)+sh(V,3)+sh(V,4)+sh(V,5))/5
grid['5 눌림 거래량감소'][3]=('avgV(1..5)<1.0VA',v5<VA)
out={}
print(f"기준 v1.2 n={rows[0]['n']} 평균 {rows[0]['mean']:+.2f}% 중앙 {rows[0]['med']:+.2f}% 승률 {rows[0]['win']:.1f}%")
for ax,vs in grid.items():
    out[ax]=[]
    print('==',ax)
    for nm,ex in vs:
        r=ev(nm,ex); out[ax].append(r)
        if 'f' not in r: print(nm,'n',r['n']); continue
        print(f"{nm:20s} n{r['n']:5d} {r['perday']:.2f}/일 평균{r['mean']:+.2f} vs기준{r['vs']:+.2f} 승{r['win']:.1f} 중앙{r['med']:+.2f} fold[{', '.join('%+.2f'%x for x in r['f'])}] "
              f"R5 일차평균{r['r5']['mean']:+.2f} 중앙{r['r5']['med']:+.2f} -3일{r['r5']['drop3']:+.2f} -10일{r['r5']['drop10']:+.2f} R4 p={r['p']:.3f}(귀무{r['null']:+.2f}) D+1진입차{r['d1']:+.2f}")
json.dump(dict(base=rows[0],axes=out),open(os.path.join(HERE,'res_eg.json'),'w'),ensure_ascii=False,default=float,indent=1)
