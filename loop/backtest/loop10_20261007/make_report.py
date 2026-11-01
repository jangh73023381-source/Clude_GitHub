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
xs=json.load(open(os.path.join(H,'res_xs.json'))); vc=json.load(open(os.path.join(H,'res_vcp.json'))); vn=json.load(open(os.path.join(H,'res_vcp_null.json'))); nl=json.load(open(os.path.join(H,'res_null.json')))
title('루프 엔지니어링 — 미시도 축 10종 추가 백테스트 (2026-10-07)')
note('루프 외 사용자 요청. 확정방법 v2.9(Rule LV)·Rule MM·Rule EG·Rule CB 는 바꾸지 않았다. 기준 = Rule LV(mom20 pool30 → σ20 하위5), 판정 패널 7년(panel_ohlc_long, 공통 시작 252 → 채점 1,583일). 지표 A(종가→종가)·OO(시가→시가, 실집행). 코드·원자료 backtest/loop10_20261007/.')
sec('1. 결론')
para('10개 축 모두 승격 후보가 아니다. 9개는 기각, 변동성 수축(σ5/σ60 등)은 관문 R1·R3·R5를 통과했지만 무작위 대조 p가 0.035~0.34로 기준(p<0.01)에 못 미쳐 보류(아깝게 탈락)로 둔다. shadow 등록도 권하지 않는다.',10,True)
para('가장 중요한 발견은 대조군 쪽이다. "σ20 하위 7~10개 중 아무거나 5개"만 골라도 OO 기준 Rule LV 대비 +0.008~0.011%p/일, 최근 3분의 1 구간(fold3)에서는 +0.015~0.023%p가 난다. 이번에 OO에서 좋아 보였던 2단계 선정(상승거래량 비중·자기상관·수축)의 상당 부분이 이 구조적 효과였다. 앞으로 "σ 하위 N → 보조지표 5" 형태는 반드시 같은 N의 무작위 5개와 비교해야 한다.')
sec('2. 축별 판정')
def g(d,k):
    a=d[k]['A'];o=d[k]['OO']; return f"A {a['diff']:+.4f}(t{a['t']:+.2f}) · OO {o['diff']:+.4f}(t{o['t']:+.2f}) · Sh_OO {o['sh']:.2f}({o['bsh']:.2f})"
table(['#','축','대표 수치','판정'],[
['1','요일 효과(보유 세션 월~금, 해당 요일 지수/현금 교체)','LV−지수 요일별 |t|≤1.56, 무작위 날짜 대조 p 0.13~0.95, 연도 부호 혼재','기각'],
['2','연휴 직전·직후 세션(46회)','A 직전 +0.33%p t1.61 이나 OO +0.04 t0.15 — 집행 지표에서 소멸','기각'],
['3','옵션만기(둘째 목요일) 당일·익일·만기주','|t|≤0.89, 음수 연도 4~5/7, 지수/현금 교체 Sharpe 무개선','기각'],
['4','Amihud 비유동성(유동 선호·비유동 제외)',g(xs,'4 Amihud: σ하위15→유동 상위5')+' · 대조(비유동 선호)도 같은 크기','기각'],
['5','자기상관(60·120일 lag1, 추세지속형 선호)',g(xs,'5 AC120: σ하위10→AC 상위5')+' · 반대(AC 하위)는 무작위 대비 p 0.16','기각'],
['6','변동성 수축(σ5/σ60·σ5/σ20·σ10/σ60·ATR5/ATR60)',g(vc,'수축 σ5/σ20 σ하위8')+f" · 무작위 p(OO) {vn['수축 σ5/σ20 σ하위8']['dO']:.3f}",'보류(아깝게 탈락)'],
['7','σ 룩백 앙상블(σ10·20·60·120 랭크 평균)',g(xs,'7 앙상블 σ20+σ60+σ120')+' — 4변형 전부 0 근처','기각'],
['8','상승일 거래량 비중(OBV형 매집)',g(xs,'8 UVR: UVR 하위1/2 제외→σ5')+' · 매집 선호는 전부 음수','기각'],
['9','명목가격(저가/고가 ETF)',g(xs,'9 가격: σ하위10→저가5')+f" · OO 무작위 p {nl['저가 σ10']['p']['dO']:.2f}; 1만5천원↑ 제한은 t−2.0",'기각'],
['10','구간 최대낙폭(MDD60·120) 정렬',g(xs,'10 MDD60: pool→MDD 작은5')+' · σ20 랭크합도 음수','기각'],
],[0.6,4.6,8.6,2.6])
sec('3. 변동성 수축 — 왜 보류인가')
rows=[]
for k in ('수축 σ5/σ60 σ하위6','수축 σ5/σ60 σ하위7','수축 σ5/σ60 σ하위8','수축 σ5/σ60 σ하위9','수축 σ5/σ60 σ하위10','수축 σ5/σ60 σ하위12','수축 σ5/σ20 σ하위7','수축 σ5/σ20 σ하위8','수축 σ10/σ60 σ하위8','수축 ATR5/ATR60 σ하위7','수축 ATR5/ATR60 σ하위8'):
    o=vc[k]['OO']; p=vn.get(k,{}).get('dO','')
    rows.append([k.replace('수축 ',''),f"{o['diff']:+.4f}",f"{o['t']:+.2f}",' / '.join('%+.3f'%x for x in o['f']),f"{o['drop3']:+.4f}",f"{o['sh']:.2f}",f"{o['mdd']:.1f}",'' if p=='' else f'{p:.3f}'])
table(['정의 · 1단계 N','OO 차','t','fold 1/2/3','R5 −3일','Sh','MDD','무작위 p'],rows,[3.6,1.5,1.0,3.6,1.6,1.0,1.2,1.4])
para('통과: R1 고원(σ5/σ60 기준 N=6~10 OO 전부 양수), R3 정의 교체(4개 정의 모두 같은 방향), R5(상위 3일 제거 후에도 양수). 미달: ① 무작위 5개 대조 p 최저 0.035(σ5/σ20·N8), 나머지 0.05~0.34 — 이번 회차 누적 시도 약 50변형을 감안하면 우연 범위 ② fold2 가 0 근처(−0.007~+0.008)이고 이득이 fold3 에 몰리는데, 무작위 대조도 fold3 에서 +0.015~0.023 을 낸다 ③ N=12·15 에서 부호 반전(A).')
para('되살리는 조건: 같은 N의 무작위 대조 대비 p<0.01, fold2 양수. 그 전에는 shadow 정원을 쓰지 않는다.')
sec('4. 부수 관찰 (규칙 아님)')
para('• σ20 하위 7~8개 중 무작위 5개가 LV 하위 5개보다 OO 에서 낫다(+0.008~0.011%p, Sh 1.62~1.67 vs 1.60). 최하위 σ 몇 종이 최근 국면에서 지나치게 방어적이라는 뜻일 수 있으나, Rule LV 파라미터는 동결이므로 이번 판정에서는 관찰로만 남긴다.')
para('• 보유 세션이 화요일인 날만 현금으로 두면 OO Sharpe 1.75(기준 1.60)·MDD −18.8% 였지만, 요일 5개 × 지표 2 × 교체 2 = 20회 비교 중 하나이고 LV−지수 차(+0.018, t0.23)는 0 이다 — 시장 전체의 요일 잡음.')
para('• 연휴 직전 세션 A +0.33%p 는 갭(종가→다음 시가)에서 생기고 시가 매수로는 잡히지 않는다(OO +0.04). 7/31 Rule US 와 같은 갭 함정.')
sec('5. 기록')
note('N 대장(루프 외 합산) 831 → 841. analysis-method_rejected.md 2026-10-07 절, loop-log.md 2026-10-07 루프 외 항목에 반영. 확정 규칙·shadow 정원 변경 없음.')
out=os.path.join(os.path.dirname(os.path.dirname(H)),'루프엔지니어링_2026-10-07_미시도10축_추가_백테스트.docx')
doc.save(out); print(out)
