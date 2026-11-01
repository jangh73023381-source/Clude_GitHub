from docx import Document
from docx.shared import Pt,RGBColor,Cm
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
NAVY=RGBColor(0x1F,0x38,0x64)
doc=Document()
for s in doc.sections: s.left_margin=s.right_margin=Cm(1.8); s.top_margin=s.bottom_margin=Cm(1.6)
st=doc.styles['Normal']; st.font.name='맑은 고딕'; st.font.size=Pt(9.5); st.element.rPr.rFonts.set(qn('w:eastAsia'),'맑은 고딕')
def para(t,size=9.5,bold=False,color=None):
    p=doc.add_paragraph(); r=p.add_run(t); r.font.size=Pt(size); r.bold=bold
    r.font.name='맑은 고딕'; r._element.rPr.rFonts.set(qn('w:eastAsia'),'맑은 고딕')
    if color: r.font.color.rgb=color
    p.paragraph_format.space_after=Pt(3); return p
def title(t): para(t,16,True,NAVY)
def sec(t): para(t,13,True,NAVY)
def sub(t): para(t,10.5,True)
def note(t): para(t,8.5)
def shade(c,hexc):
    tcPr=c._element.get_or_add_tcPr(); sh=OxmlElement('w:shd'); sh.set(qn('w:val'),'clear'); sh.set(qn('w:color'),'auto'); sh.set(qn('w:fill'),hexc); tcPr.append(sh)
def table(hdr,rows,widths=None):
    t=doc.add_table(rows=1,cols=len(hdr)); t.style='Table Grid'
    for j,h in enumerate(hdr):
        c=t.rows[0].cells[j]; c.text=''; r=c.paragraphs[0].add_run(h); r.bold=True; r.font.size=Pt(8); r.font.color.rgb=RGBColor(255,255,255); shade(c,'1F3864')
    for row in rows:
        cs=t.add_row().cells
        for j,v in enumerate(row):
            cs[j].text=''; r=cs[j].paragraphs[0].add_run(str(v)); r.font.size=Pt(8)
            if j==len(row)-1 and ('보류' in str(v) or '근접' in str(v)): shade(cs[j],'E2EFDA')
    if widths:
        t.autofit=False
import json,os
H=os.path.dirname(os.path.abspath(__file__))
J=json.load(open(os.path.join(H,'res60.json'))); r6=J['res']; r7=json.load(open(os.path.join(H,'res7y.json')))
w=J['window']
title('루프 엔지니어링 — 최근 60거래일 한정 10축 검정 (2026-10-07)')
note(f'루프 외 사용자 요청. 판정 창 = 최근 60거래일 선정일 {w[0]}~{w[1]}(보유 종료 20261006, panel_ohlc_2y). 기준 Rule LV(v2.9). 지표 A(종가→종가)·OO(시가→시가)·이진 적중(종가 1만원↑ 전체 ETF 익일 상위 10% 안에 든 픽 수). 같은 규칙을 7년 패널(2020-04~2026-09-21, 1,577일)에도 돌려 "60일 구간 승률"과 "이번 60일 성과의 역사적 백분위"를 함께 냈다. CLAUDE.md §4-5 에 따라 60일만으로는 승격·기각을 확정하지 않는다. 코드 backtest/loop60_20261007/.')
sec('1. 결론')
para('승격 후보 없음. 최근 60일에 LV(누적 −3.6%)를 이긴 것은 MA60 국면전환(+9.8%)과 RS 상위5(OO 기준) 두 개뿐인데, 둘 다 최근 국면에서만 좋았다. MA60 국면전환의 이번 60일 우위(+0.224%p/일)는 7년 동안의 60일 구간 중 상위 3%에 해당하고, 7년 전체 우위는 +0.002%p(t 0.07)다. 이득도 마지막 20일에 몰려 있다(fold +0.68, 앞 두 구간 0).',10,True)
para('반대로 7년에서는 LV를 꾸준히 이기는 쪽(변동성 수축·최저σ 2종 제외·저가 ETF — 60일 구간 승률 62~67%)이 이번 60일에는 하위 2~17%였다. 최근 60일은 "가장 낮은 변동성 몇 종"이 유리했던 드문 구간이고, 같은 기간 LV는 KODEX200(−10.3%)보다 6.7%p 덜 잃었다. 60일 성과로 규칙을 바꾸면 국면을 쫓게 된다.')
sec('2. 최근 60거래일 성적')
rows=[]
for k,o in r6.items():
    rows.append([k,f"{o['cumA']:+.1f}%",f"{o['mddA']:.1f}",f"{o['hit']:.2f} ({o['full5']})",f"{o['dA']:+.3f}",f"{o['tA']:+.2f}",' / '.join('%+.2f'%x for x in o['fA']),f"{o['drop3']:+.3f}",f"{o['cumOO']:+.1f}%"])
table(['규칙','누적 A','MDD','적중/5 (5/5일)','LV대비 %p/일','t','20일 3분할','R5 −3일','누적 OO'],rows,[4.6,1.4,1.1,1.8,1.6,0.9,3.0,1.4,1.4])
note(f"KODEX200 같은 창 누적 {r6['LV(기준)']['bench_cum']:+.1f}%. 7/31 하루 +24% 같은 극단일이 있어 60일 평균은 상위 며칠에 크게 좌우된다(R5 −3일 열 참고).")
sec('3. 7년 교차검증 — 60일 성과가 흔한 수준인가')
rows=[]
for k,o in r7.items():
    if k.startswith('LV'): continue
    rows.append([k,f"{o['cagr']:+.1f} / {o['mdd']:.1f} / {o['sh']:.2f}",f"{o['dA']:+.4f} (t{o['tA']:+.2f})",f"{o['win60']*100:.0f}%",f"{o['edge60']:+.3f}",f"{o['pct_recent']*100:.0f}%ile"])
b=r7['LV(기준)']
table(['규칙',f"7년 CAGR/MDD/Sh (LV {b['cagr']:.1f}/{b['mdd']:.1f}/{b['sh']:.2f})",'7년 LV대비','60일 구간 승률','이번 60일 우위','역사 백분위'],rows,[4.6,4.0,2.6,1.8,1.8,1.6])
sec('4. 축별 판정')
J2=[['1','MOM(mom20 상위5)','최근 −10.0%·MDD −24.4, 7년 Sharpe 1.03(LV 1.54)','기각 — 최근에도 LV 열위'],
['2','혼합 LV3+MOM2','최근 −6.4%, 7년 우위 +0.004(t0.18)','기각'],
['3','국면전환 MA20','최근 +0.020(t0.11), 7년 Sharpe 1.21·fold3 음수','기각'],
['3b','국면전환 MA60','최근 +0.224(t2.00)이나 역사 97%ile·이득 fold3 집중, 7년 t0.07·60일 승률 44%','기각(국면 행운)'],
['4','변동성 수축','최근 −0.122(역사 2%ile), 7년 +0.017(t1.38)·승률 62%','보류 유지(오늘 오후 판정 그대로)'],
['5','최저σ 2종 제외','최근 −0.048(6%ile), 7년 +0.015(t1.22)·승률 64%','보류(무작위 동N 효과와 동형)'],
['6','RS(IBD) 상위5','최근 OO +0.25 이나 R5 −3일 −0.62·MDD −35.7, 7년 MDD −51.2','기각'],
['7','NHI(신고가 근접×지수게이트)','최근 적중 0.18/5, 7년 MDD −20.2·Sh 1.68(위험 축)','shadow 유지 — 판정은 트래커로'],
['8','SK1w 블렌드 pool','최근 t−1.68, 7년 t−1.50','기각 — shadow 종결 검토 권고'],
['9','mom5 pool','최근 −0.114, 7년 −0.024·승률 35%','기각'],
['10','저가 ETF','최근 −0.023(17%ile), 7년 +0.016(t1.27)·승률 67%','기각 유지(OO 무작위 p 0.4)']]
table(['#','축','근거','판정'],J2,[0.7,3.6,8.8,3.5])
sec('5. 기록')
note('N 대장(루프 외 합산) 841 → 852(11변형). analysis-method_rejected.md·loop-log.md 2026-10-07 60일 절. 확정 규칙·shadow 변경 없음(SK1w 종결은 사용자 판단 사항으로 제안만).')
out=os.path.join(os.path.dirname(os.path.dirname(H)),'루프엔지니어링_2026-10-07_최근60거래일_10축.docx'); doc.save(out); print(out)
