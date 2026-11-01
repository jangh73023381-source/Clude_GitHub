"""생존편의 없는 패널(2012~2026, 상폐 포함)로 가격 기반 보류 후보 재판정: NH(250일 신고가 근접) · PVC(고가-거래량 10일 상관 낮음) · NH+PVC 순위평균.
유니버스: 주가≥1,000원 · 20일 평균 거래대금≥10억(그날 상장 종목 전부). 20거래일 비중첩 리밸런싱(오프셋 0/5/10/15), 상위 10% 동일가중.
수익은 KRX 등락률(기준가 조정) 누적. 상장폐지 종목은 마지막 거래일 이후 0%로 둔다(정리매매 손실은 등락률에 포함).
대조: 같은 계산을 '2026-10 현재 생존 종목만'으로 돌려 생존편의 크기를 잰다."""
import numpy as np,pandas as pd,warnings; warnings.filterwarnings('ignore')
d=np.load('dates.npy',allow_pickle=True).astype(str); R=np.load('P_chg_pct.npy').astype('float64')/100
C=np.load('P_close.npy'); H=np.load('P_high.npy'); V=np.load('P_value.npy'); MC=np.load('P_mktcap.npy')
meta=pd.read_csv('codes_meta.csv',dtype=str); alive=(meta['last'].values==d[-1])
T,N=R.shape
G=np.nan_to_num(R,nan=0.0)                       # 상장 전·폐지 후 0
LG=np.cumsum(np.log1p(G),0)                      # 누적 로그수익(수정 가격 지수)
P=np.exp(LG)                                     # 수정 가격 지수
listed=~np.isnan(C)
rm=lambda X,w:pd.DataFrame(X).rolling(w,min_periods=w).mean().values
VA=rm(np.where(listed,V,np.nan),20)
elig=listed&(C>=1000)&(VA>=1e9)
# 신호
HI=pd.DataFrame(np.where(listed,P,np.nan)).rolling(250,min_periods=200).max().values
NH=P/HI
# 고가 수정: 기준가 조정 비율 = 수정지수/원종가 를 고가에 곱함
adj=P/np.where(listed,C,np.nan); Hadj=H*adj
lv=np.log(np.where(listed&(V>0),V,np.nan))
def rcorr(a,b,w=10):
    A=pd.DataFrame(a); B=pd.DataFrame(b); return A.rolling(w).corr(B).values
PVC=-rcorr(Hadj,lv,10)
def rank(X,mask):
    Y=np.where(mask,X,np.nan); return pd.DataFrame(Y).rank(axis=1,pct=True).values
H20=20
def bt(score,mask,top=.1):
    res=[]
    for off in (0,5,10,15):
        for t in range(260+off,T-H20-1,H20):
            m=mask[t]&~np.isnan(score[t]); idx=np.where(m)[0]
            if len(idx)<50: continue
            fwd=np.exp(LG[t+H20]-LG[t])-1          # t 종가 → t+20 종가 (폐지 종목 포함, 폐지 후 0)
            q=np.quantile(score[t,idx],1-top); sel=idx[score[t,idx]>=q]
            res.append((d[t],off,fwd[sel].mean()*100,fwd[idx].mean()*100,np.average(fwd[idx],weights=MC[t,idx])*100))
    x=pd.DataFrame(res,columns=['date','off','top','uni','capw']); return x
def summ(nm,x):
    ex=x.top-x.uni; t=ex.mean()/ex.std()*np.sqrt(len(ex)/4)          # 오프셋 4개 겹침 보정(대략)
    n=len(ex); fo=[ex.iloc[j*n//3:(j+1)*n//3].mean() for j in range(3)]
    s=np.sort(ex.values); r5=s[:-int(n*.05)].mean()
    vsc=(x.top-x.capw).mean()
    print(f"{nm:34s} 유니버스 대비 {ex.mean():+.2f}%p/20일 t≈{t:+.2f} fold[{', '.join('%+.2f'%v for v in fo)}] 상위5%제거 {r5:+.2f} | 시총가중(지수 대용) 대비 {vsc:+.2f}")
    return ex.mean()
rNH=rank(NH,elig); rPVC=rank(PVC,elig); combo=(rNH+rPVC)/2
print('기간',d[260],'~',d[-1],' 평균 유니버스 종목',int(elig.sum(1)[260:].mean()))
out={}
for nm,sc in [('NH 신고가 근접',NH),('PVC 고가-거래량 상관↓',PVC),('NH+PVC 순위평균',combo)]:
    a=summ(nm+' [상폐 포함]',bt(sc,elig)); b=summ(nm+' [현 생존만]',bt(sc,elig&alive[None,:])); out[nm]=(a,b)
x=bt(NH,elig); y=bt(NH,elig&alive[None,:])
print(f"\n유니버스 자체 평균 20일 수익: 상폐 포함 {x.uni.mean():+.2f}% vs 현 생존만 {y.uni.mean():+.2f}% → 생존편의 {y.uni.mean()-x.uni.mean():+.2f}%p/20일")
for nm,sc in [('NH',NH),('PVC',PVC)]:
    x=bt(sc,elig); x['y']=x.date.str[:4]; print(nm,'연도별 유니버스 대비', {k:round((g.top-g.uni).mean(),2) for k,g in x.groupby('y')})

print('\n[NH+PVC vs 시총가중 유니버스(지수 대용) 상세]')
x=bt(combo,elig); ex=x.top-x.capw; n=len(ex)
print(f"평균 {ex.mean():+.2f}%p/20일 t≈{ex.mean()/ex.std()*np.sqrt(n/4):+.2f} 중앙 {ex.median():+.2f} 승률 {(ex>0).mean()*100:.0f}% fold {[round(ex.iloc[j*n//3:(j+1)*n//3].mean(),2) for j in range(3)]}")
x['y']=x.date.str[:4]; print('연도별',{k:round((g.top-g.capw).mean(),2) for k,g in x.groupby('y')})
# 회전율(오프셋0)
sel_prev=None; tos=[]
for t in range(260,T-H20-1,H20):
    m=elig[t]&~np.isnan(combo[t]); idx=np.where(m)[0]; q=np.quantile(combo[t,idx],.9); s=set(idx[combo[t,idx]>=q])
    if sel_prev is not None: tos.append(1-len(s&sel_prev)/len(s))
    sel_prev=s
print(f"회전율 {np.mean(tos)*100:.0f}%/회 → 왕복 0.2% 가정 비용 {np.mean(tos)*0.2*2/2:.2f}%p/20일(매수·매도 각 0.1%+세금 근사)")
