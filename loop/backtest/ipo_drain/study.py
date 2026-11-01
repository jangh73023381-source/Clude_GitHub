import pandas as pd,numpy as np,json
d=pd.read_csv('px.csv',dtype={'date':str}).drop_duplicates(['sym','date'],keep='last')
P=d.pivot(index='date',columns='sym',values='close').sort_index()
VOL=d.pivot(index='date',columns='sym',values='volume').sort_index()
def ser(s): return P[s].dropna()
def ret(s,a,b):
    x=ser(s); x=x[(x.index>=a)&(x.index<=b)]
    # 기준: a 이전 마지막 종가 → b 이하 마지막 종가
    full=ser(s); pa=full[full.index<a]
    if len(pa)==0 or len(x)==0: return None
    return (x.iloc[-1]/pa.iloc[-1]-1)*100
def pct_rank(s,a,b,years=3):
    x=ser(s); x=x[x.index>=str(int(b[:4])-years)+b[4:]]
    full=ser(s); idx=full.index
    L=len(idx[(idx>=a)&(idx<=b)])
    r=(x/x.shift(L)-1).dropna()*100
    v=ret(s,a,b)
    return v,float((r<v).mean()*100),L
out={}
W=[('S-1 공개 → 로드쇼 직전','20260520','20260602'),('로드쇼·청약(6/3~6/11)','20260603','20260611'),
   ('상장 첫 주(6/12~6/19)','20260612','20260619'),('상장 후 2~4주(6/22~7/6, NDX 편입 전)','20260622','20260706'),
   ('NDX 편입 후 1주(7/7~7/14)','20260707','20260714'),('상장~30거래일(6/12~7/24)','20260612','20260724')]
SY=['SPCX','^NDX','QQQ','RSP','SPY','IWM','^SOX','RKLB','ASTS','LUNR','UFO','^KS11','^KQ11','012450.KS','047810.KS','099320.KQ','451760.KQ','189300.KQ','211270.KQ','462350.KQ','272210.KS']
rows=[]
for lab,a,b in W:
    r={'window':lab,'a':a,'b':b}
    for s in SY:
        v=ret(s,a,b)
        if v is None: r[s]=None; continue
        if s!='SPCX':
            _,p,L=pct_rank(s,a,b); r[s]=(round(v,2),round(p))
        else: r[s]=(round(v,2),None)
    rows.append(r)
out['spacex']=rows
# 상대: QQQ-RSP (대형 기술 vs 동일가중), IWM-SPY, KQ-KS, 한국 우주 바스켓
kr=['012450.KS','047810.KS','099320.KQ','451760.KQ','189300.KQ','211270.KQ','462350.KQ','272210.KS']
for r in rows:
    g=lambda s:(r[s][0] if r[s] else np.nan)
    r['QQQ-RSP']=round(g('QQQ')-g('RSP'),2); r['IWM-SPY']=round(g('IWM')-g('SPY'),2); r['KQ-KS']=round(g('^KQ11')-g('^KS11'),2)
    r['KR우주바스켓']=round(np.nanmean([g(s) for s in kr]),2); r['US우주피어']=round(np.nanmean([g(s) for s in ['RKLB','ASTS','LUNR']]),2)
# 거래량: 한국 지수 거래량 6/12~6/19 vs 직전 20일
def vr(s,a,b):
    v=VOL[s].dropna(); pre=v[v.index<a].iloc[-20:].mean(); w=v[(v.index>=a)&(v.index<=b)].mean(); return round(w/pre,2)
out['vol']={s:{lab:vr(s,a,b) for lab,a,b in W[:4]} for s in ['^KS11','^KQ11','QQQ','IWM']}
# 2) 대형 IPO 이벤트 스터디 (청약 시작일, 상장일)
KR=[('SK바이오팜','20200623','20200702'),('카카오게임즈','20200901','20200910'),('빅히트(하이브)','20201005','20201015'),
    ('SK바이오사이언스','20210309','20210318'),('SK아이이테크놀로지','20210428','20210511'),('카카오뱅크','20210726','20210806'),
    ('크래프톤','20210802','20210810'),('카카오페이','20211025','20211103'),('LG에너지솔루션','20220118','20220127'),
    ('HD현대마린솔루션','20240425','20240508'),('LG CNS','20250121','20250205')]
US=[('Facebook','20120518'),('Alibaba','20140919'),('Uber','20190510'),('Airbnb','20201210'),('Rivian','20211110'),('Arm','20230914'),('SpaceX','20260612')]
def nth(s,day,k):
    idx=ser(s).index; i=idx.searchsorted(day); j=min(max(i+k,0),len(idx)-1); return idx[j]
def wret(s,a_day,ka,b_day,kb):
    a=nth(s,a_day,ka); b=nth(s,b_day,kb); x=ser(s); ia=x.index.get_loc(a); return (x.loc[b]/x.iloc[ia-1]-1)*100, x.index.get_loc(b)-ia+1
def placebo(s,L):
    x=ser(s); x=x[x.index>='20120101']; r=(x/x.shift(L)-1).dropna()*100; return r
ev=[]
for nm,sub,lst in KR:
    e={'name':nm,'sub':sub,'list':lst}
    for s in ['^KS11','^KQ11']:
        v1,L1=wret(s,sub,0,lst,0)        # 청약 시작~상장일
        v2,L2=wret(s,lst,1,lst,10)       # 상장 다음날~+10
        p1=placebo(s,L1); p2=placebo(s,L2)
        e[s]=dict(pre=round(v1,2),pre_pct=round(float((p1<v1).mean()*100)),pre_ex=round(v1-p1.mean(),2),post=round(v2,2),post_pct=round(float((p2<v2).mean()*100)),post_ex=round(v2-p2.mean(),2))
    ev.append(e)
out['kr_events']=ev
for s in ['^KS11','^KQ11']:
    pre=np.array([e[s]['pre_ex'] for e in ev]); post=np.array([e[s]['post_ex'] for e in ev])
    out[f'kr_summary_{s}']=dict(pre_mean=round(pre.mean(),2),pre_t=round(pre.mean()/(pre.std(ddof=1)/np.sqrt(len(pre))),2),pre_neg=int((pre<0).sum()),
                               post_mean=round(post.mean(),2),post_t=round(post.mean()/(post.std(ddof=1)/np.sqrt(len(post))),2),post_neg=int((post<0).sum()),n=len(pre))
uev=[]
for nm,lst in US:
    e={'name':nm,'list':lst}
    for s in ['^GSPC','^IXIC','IWM']:
        v1,L1=wret(s,lst,-7,lst,-1); v2,L2=wret(s,lst,0,lst,10)
        p1=placebo(s,L1); p2=placebo(s,L2)
        e[s]=dict(pre=round(v1,2),pre_ex=round(v1-p1.mean(),2),pre_pct=round(float((p1<v1).mean()*100)),post=round(v2,2),post_ex=round(v2-p2.mean(),2),post_pct=round(float((p2<v2).mean()*100)))
    uev.append(e)
out['us_events']=uev
for s in ['^GSPC','^IXIC','IWM']:
    pre=np.array([e[s]['pre_ex'] for e in uev]); post=np.array([e[s]['post_ex'] for e in uev])
    out[f'us_summary_{s}']=dict(pre_mean=round(pre.mean(),2),pre_neg=int((pre<0).sum()),post_mean=round(post.mean(),2),post_neg=int((post<0).sum()),n=len(pre))
json.dump(out,open('result.json','w'),ensure_ascii=False,indent=1,default=str)
for r in out['spacex']: print(r)
print(out['vol'])
for e in ev: print(e)
for k in out:
    if 'summary' in k: print(k,out[k])
for e in uev: print(e)
