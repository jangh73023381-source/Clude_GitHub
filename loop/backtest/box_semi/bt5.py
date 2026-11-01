exec(open('bt2.py').read().split('rows=[]')[0])
A=20260801
for code in ['091160','395160','069500']:
    d=P[code];r,tr,_=run(d,10,.2,.8,None)
    print(codes[code],'8~9월 N10 거래:',[(int(d.index[a]),int(d.index[min(b,len(d)-1)]),f'{x*100:+.1f}%') for a,b,x in tr if d.index[a]>=A])
print('\n7년 N10 (동일 규칙) 전체기간 vs B&H')
for code in ['091160','396500','395160']:
    d=P[code];bh=stats(d.close.pct_change())
    for lo,hi in [(.2,.8),(.1,.9),(.3,.7)]:
        r,tr,exp=run(d,10,lo,hi,None);s=stats(r)
        print(f'{codes[code]} N10 {lo}/{hi}: CAGR {s[0]:.1f} Sh {s[1]:.2f} MDD {s[2]:.1f} 거래{len(tr)} | B&H {bh[0]:.1f}/{bh[1]:.2f}/{bh[2]:.1f}')
# 2개월 창을 7년 전체에서 굴려보기: N10 0.2/0.8 이 B&H 이긴 2개월 창 비율
print('\n40거래일 창 롤링(20일 간격): N10 0.2/0.8 가 B&H 이긴 비율')
for code in ['091160','396500']:
    d=P[code];r,tr,_=run(d,10,.2,.8,None);bh=d.close.pct_change().fillna(0)
    wins=[];diffs=[]
    for s in range(20,len(d)-40,20):
        a=((1+r.iloc[s:s+40]).prod()-1);b=((1+bh.iloc[s:s+40]).prod()-1);wins.append(a>b);diffs.append((a-b)*100)
    print(f'{codes[code]}: {np.mean(wins)*100:.0f}% ({len(wins)}창), 초과 중앙 {np.median(diffs):+.1f}%p')
