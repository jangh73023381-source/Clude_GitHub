// gen_attention_report_v2.js — 관심 모멘텀 파일럿 데일리 리포트(docx) 생성기
// 사용법: node gen_attention_report_v2.js <YYYYMMDD> [출력경로.docx]
//   - v2/v3 스키마: attention_pilot_v2_picks.csv / attention_pilot_v2_results.csv
//   - 채점 기준: 15개 섹터 ETF 당일 종가수익률 상위3위가 추천5개에 전부 포함 = SUCCESS
//   - v2.3(2026-07-14): yt20(상위20채널 종목언급) 신호 반영 시 composite_v3 표기
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, BorderStyle, WidthType, ShadingType } = require('docx');

const REF = path.resolve(__dirname, '..');            // loop/references
const LOOP = path.resolve(REF, '..');                 // loop
const date = process.argv[2];
if (!date) { console.error('YYYYMMDD 인자 필요'); process.exit(1); }
const outPath = process.argv[3] || path.join(LOOP, `관심모멘텀_파일럿_v2_${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}.docx`);

const NAVY='1F3864', HDRTXT='FFFFFF', GRIDCLR='BFBFBF', ALT='F2F5FA', GREENBG='E2EFDA', GREENTX='1E7B34', REDTX='C00000';
const FONT='맑은 고딕';

function readCSV(p){ if(!fs.existsSync(p)) return []; const L=fs.readFileSync(p,'utf8').trim().split(/\r?\n/); const h=L[0].split(','); return L.slice(1).filter(x=>x.length).map(r=>{const c=r.split(','); const o={}; h.forEach((k,i)=>o[k.trim()]=(c[i]||'').trim()); return o;}); }
function readJSON(p){ if(!fs.existsSync(p)) return null; try{ return JSON.parse(fs.readFileSync(p,'utf8')); }catch(e){ return null; } }

const themes = readCSV(path.join(REF,'attention_pilot_themes.csv'));
const picksAll = readCSV(path.join(REF,'attention_pilot_v2_picks.csv'));
const resAll = readCSV(path.join(REF,'attention_pilot_v2_results.csv'));
const raw = readCSV(path.join(REF,`raw_${date}.csv`));
const yt20detail = readJSON(path.join(REF,`yt20_detail_${date}.json`));

const picks = picksAll.filter(r=>r.date===date);
const usesV3 = picks.length>0 && picks[0].composite_ver === 'v3';
const scoreDates = [...new Set(resAll.map(r=>r.score_date))].sort();
const lastScoreDate = scoreDates[scoreDates.length-1] || '';
const lastRes = resAll.find(r=>r.score_date===lastScoreDate);

let successDays=0, hitSlots=0, n=resAll.length;
resAll.forEach(r=>{ successDays += Number(r.success)||0; hitSlots += Number(r.top3_hits)||0; });
const dayRows = resAll.map(r=>[r.score_date, r.top3_hits+'/3', r.success==='1'?'SUCCESS':'FAIL', r.top3_sectors, r.picks]);

const fmtd = s=> s? `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}` : '—';

function title(t){ return new Paragraph({ spacing:{after:80}, children:[new TextRun({text:t, bold:true, size:32, color:NAVY, font:FONT})] }); }
function subtitleLine(t){ return new Paragraph({ spacing:{after:200}, border:{bottom:{style:BorderStyle.SINGLE,size:12,color:NAVY,space:2}}, children:[new TextRun({text:t, size:18, color:'404040', font:FONT})] }); }
function section(n,t){ return new Paragraph({ spacing:{before:240,after:120}, children:[new TextRun({text:`${n}. ${t}`, bold:true, size:26, color:NAVY, font:FONT})] }); }
function para(t,opts={}){ return new Paragraph({ spacing:{after:opts.after??80}, children:[new TextRun({text:t, size:opts.size??19, font:FONT, color:opts.color||'000000', bold:!!opts.bold})] }); }
function bullet(t){ return new Paragraph({ spacing:{after:40}, indent:{left:360,hanging:200}, children:[new TextRun({text:'• '+t, size:18, font:FONT})] }); }

const B={style:BorderStyle.SINGLE,size:1,color:GRIDCLR};
const BORD={top:B,bottom:B,left:B,right:B};
function cell(text,opts){
  opts = opts||{};
  const w=opts.w, head=opts.head||false, fill=opts.fill, align=opts.align||'left', bold=opts.bold||false, color=opts.color;
  return new TableCell({ borders:BORD, width:{size:w,type:WidthType.DXA},
    shading: head?{fill:NAVY,type:ShadingType.CLEAR}:(fill?{fill,type:ShadingType.CLEAR}:undefined),
    margins:{top:50,bottom:50,left:90,right:90},
    children:[new Paragraph({ alignment: align==='center'?AlignmentType.CENTER:(align==='right'?AlignmentType.RIGHT:AlignmentType.LEFT),
      children:[new TextRun({text:String(text), size:16, font:FONT, bold: head||bold, color: head?HDRTXT:(color||'000000')})]})]});
}
function table(cols, headers, rows){
  const total=cols.reduce((a,b)=>a+b,0);
  const headRow=new TableRow({tableHeader:true, children:headers.map((h,i)=>cell(h,{w:cols[i],head:true,align:'center'}))});
  const bodyRows=rows.map((r,ri)=> new TableRow({children:r.map((c,i)=>{
    const spec = typeof c==='object'? c : {text:c};
    return cell(spec.text,{w:cols[i], align:spec.align||(i===0?'left':'center'), fill: ri%2?ALT:undefined, bold:spec.bold, color:spec.color});
  })}));
  return new Table({width:{size:total,type:WidthType.DXA}, columnWidths:cols, rows:[headRow,...bodyRows]});
}

const kids=[];
kids.push(title(`관심 모멘텀 파일럿 ${usesV3?'v2.3':'v2.0'} — 데일리 리포트`));
kids.push(subtitleLine(`기준일 ${fmtd(date)} · Attention-Momentum Forward Pilot (섹터 추천) · 정보 제공 목적(투자 자문 아님)`));

kids.push(section(1,`파일럿 개요 (${usesV3?'v2.3, 2026-07-14 yt20 반영':'v2.0, 2026-07-09 확정'})`));
kids.push(para('가격이 아닌 장전(전일 16:00→금일 09:00) 정성 관심 신호(뉴스 매수/매도 감성·데이터랩 검색 모멘텀·유튜브 매수/매도 순)로 15개 섹터 중 상위 5개 섹터를 매일 사전에 선정하고, 그날 종가 기준 실제 상위3위 섹터가 추천 5개 안에 전부 포함되는지(SUCCESS) 검증하는 전방(forward) 페이퍼 파일럿.'));
if (usesV3) {
  kids.push(para('composite_v3 = z(sent_news) + z(search_mom) + z(yt_net) + z(yt20_net). 상위 5개 섹터의 대표 ETF를 관심 픽으로 기록.', {after:60, color:'404040', size:18}));
} else {
  kids.push(para('composite_v2 = z(sent_news) + z(search_mom) + z(yt_net). 상위 5개 섹터의 대표 ETF를 관심 픽으로 기록.', {after:60, color:'404040', size:18}));
}
kids.push(para('채점 기준: 15개 섹터 ETF 유니버스 내 당일 종가수익률 상위 3위가 추천 5개 안에 전부 포함되면 SUCCESS(무작위 기대 약 2.2%, 매우 어려운 목표). 보조지표로 top3 중 적중 슬롯 수(0~3)도 함께 추적.', {color:'404040', size:18}));

kids.push(section(2, `직전 픽 채점 (${fmtd(lastScoreDate)} 종가 기준)`));
if(lastRes){
  const hit=Number(lastRes.top3_hits), success=lastRes.success==='1';
  kids.push(para(`섹터 유니버스 ${lastRes.sector_N}개 · 실제 TOP3 = ${lastRes.top3_sectors.split('|').join(', ')} · 추천 픽 = ${lastRes.picks.split('|').join(', ')}`, {bold:true, after:60}));
  kids.push(para(`top3 적중 ${hit}/3 → ${success?'SUCCESS':'FAIL'}`, {bold:true, color: success?GREENTX:REDTX, after:100}));
  const prevPicks = picksAll.filter(r=>r.date===lastScoreDate);
  const ranks = lastRes.pick_ranks.split('|');
  const rows = prevPicks.map((p,i)=>{
    const top3set = new Set(lastRes.top3_sectors.split('|'));
    const inTop3 = top3set.has(p.theme);
    return [
      {text:p.theme, align:'left'},
      {text:p.etf, align:'left'},
      {text: ranks[i] || '—'},
      {text: inTop3?'TOP3 적중':'미적중', bold:true, color: inTop3?GREENTX:REDTX}
    ];
  });
  kids.push(table([1800,3600,1600,2360],['테마','대표 ETF','당일 순위','판정'],rows));
  if (lastScoreDate === '20260714') {
    kids.push(para('원인분석(2026-07-14, FAIL 0/3):', {bold:true, after:40, size:19}));
    kids.push(para('7/14 추천 픽(태양광·원자력·은행금융·자동차·방산)은 전일(7/13 급락 당일) 저녁까지의 관심 신호를 반영한 것으로, 7/13 급락 이후 순환매·저가매수 기대가 실린 업종들이었다. 그러나 실제 상위3위(반도체·AI전력·금귀금속)는 모두 장중에 새로 터진 재료로 움직였다: 반도체는 SK하이닉스 ADR 급등(+27%)과 Barclays 목표주가 상향 리포트가 7/14 장중부터 장전 막판에 확산되며 반등을 주도했고, AI전력은 전력인프라 투자 확대 관련 개별 호재(삼성SDI UPS배터리 인증 등)가 같은 날 부각됐으며, 금귀금속은 국제 금현물 3% 급등이라는 당일 지정학 이벤트성 가격 움직임이었다. 세 업종 모두 파일럿의 관심 신호 수집 윈도(전일 16:00부터 금일 09:00) 종료 이후, 즉 장 시작 직후부터 장중에 본격화된 재료였다는 공통점이 있다.', {after:60}));
    kids.push(para('구조적 시사점: 이번 FAIL은 룩어헤드 위반이 아니라 신호 윈도의 구조적 한계(장중 발생 재료를 장전 신호로는 원천적으로 포착 불가)로 설명된다. 특히 반도체와 AI전력은 7/9부터 7/13 기간에도 composite 상위권에 반복 등장한 상시 관심 테마였음에도 7/14 픽에서는 순위가 밀려났는데, 이는 은행금융·자동차·방산 등 급락 후 순환매 기대 테마의 관심 신호(뉴스 감성·검색 모멘텀)가 일시적으로 더 강하게 관측됐기 때문이다. 아울러 유튜브(YT50) 신호가 반도체·증권·AI전력·건설 4개 테마에만 존재하는 커버리지 한계, 데이터랩 검색 API의 약 1~2일 랙도 신호 대표성을 낮추는 요인으로 계속 작용하고 있다.', {size:18, color:'404040'}));
  } else if (lastScoreDate === '20260721') {
    kids.push(para('원인분석(2026-07-21, FAIL 2/3):', {bold:true, after:40, size:19}));
    kids.push(para('7/21 코스피는 전일 미국 증시의 AI·반도체 강세(엔비디아 등)가 이어지며 전일 대비 +3.56% 급등해 6747선을 회복했다. 삼성전자·SK하이닉스가 지수 상승을 주도해 반도체(+4.18%)·AI전력(+3.75%)이 실제 상위3위에 들며 파일럿 픽(반도체 1위·AI전력 2위)이 정확히 적중했다. 그러나 실제 3위는 건설(+2.64%)이었는데, 건설은 파일럿 관심 신호(뉴스 감성·검색·유튜브) 기준으로는 15개 섹터 중 13위(컴포짓 하위권)로 전날 밤 특별한 화제성이 없던 섹터였다. 당일 보도(초이스경제 7/21 16:22)에 따르면 건설주 상승은 삼성E&A(+5.36%)·현대건설(+3.08%) 등 대형주가 반도체발 지수 급등과 함께 동반 상승한 결과로, 건설 업종 자체의 개별 재료보다는 반도체 랠리에 따른 코스피 전반 상승(외국인·기관 순매수 확대)에 대형주가 동반 편승한 베타성 상승에 가깝다.', {after:60}));
    kids.push(para('구조적 시사점: 이번 FAIL도 룩어헤드 위반은 없다(픽은 7/20 16:00~7/21 09:00 장전 신호만 사용). 다만 "관심(주목) 신호"는 특정 테마에 대한 사전 화제성을 포착하는 데는 강하지만(반도체·AI전력 적중), 장중 지수 전반 급등에 따른 대형주 동반 상승(베타 편승형 상승)은 장전 시점에 원천적으로 예측하기 어려운 유형의 미스라는 점이 재확인됐다. 은행금융·자동차·태양광·우주항공 등 픽 후순위 테마의 관심 신호가 실제로는 약했던 반면, shadow 트랙의 inter 변형(뉴스감성 방향으로 관심신호를 조건화)은 이날 3/3 SUCCESS를 기록해(2차전지를 픽5에 포함) 참고할 만한 신호다 — 다만 20영업일 누적 전까지는 단일일 우열로 방법을 교체하지 않는다는 원칙을 유지한다.', {size:18, color:'404040'}));
  } else if (lastScoreDate === '20260713') {
    kids.push(para('원인분석(2026-07-13, FAIL 1/3):', {bold:true, after:40, size:19}));
    kids.push(para('7/13은 SK하이닉스 ADR 상장 재료 소멸과 미국-이란 군사충돌 격화가 겹치며 코스피가 -8.95% 급락(서킷브레이커·사이드카 발동)한 날이었다. 파일럿이 추천한 AI전력·반도체·은행금융·로봇·원자력 5종은 전일까지의 관심(뉴스·검색·유튜브) 모멘텀을 반영한 것이었으나, 정작 반도체는 이날 급락의 진앙이었고(삼성전자 -10.7%, SK하이닉스 -15%) 회복 탄력은 없었다. 반면 실제 상위3위(태양광·은행금융·2차전지)는 대부분 반도체 약세에도 견조하거나 차별화됐다고 보도된 순환매 수혜 업종으로, 전일 관심이 뜨거웠던 테마(반도체·AI전력)에서 자금이 빠져나와 상대적으로 소외됐던 업종으로 이동하는 로테이션 패턴이었다. 은행금융만 픽과 TOP3에 동시 포함되며 1/3 적중했다.', {after:60}));
    kids.push(para('구조적 시사점: 관심(attention) 신호는 본질적으로 후행적(전일까지 이미 화제였던 테마)이라 급락 후 순환매처럼 어제까지 안 오르던 업종이 오늘 뜨는 반전 국면 포착에는 약하다. 룩어헤드 위반은 없음(신호 수집과 픽 기록은 장전 윈도만 사용, 종가는 채점에만 사용). 다만 데이터랩 검색량 API가 약 2일 랙(latest=7/12)이 있어 7/13 급락 당일의 실제 검색 급증을 이번 검색모멘텀 신호가 반영하지 못한 점, 유튜브(50채널) 테마 태그가 반도체·증권·AI전력·건설 4개 테마에만 존재해 나머지 11개 테마는 구조적으로 yt_net=0인 점은 신호 커버리지의 알려진 한계다.', {size:18, color:'404040'}));
  }
} else {
  kids.push(para('아직 채점된 v2 픽이 없습니다.', {color:'808080'}));
}

kids.push(section(3, `오늘(${fmtd(date)}) 관심 신호 수집 — 장전 윈도 전일 16:00→금일 09:00`));
if(raw.length){
  const pickThemes = new Set(picks.map(p=>p.theme));
  const hasYt20Col = raw[0].yt20_total !== undefined;
  const cols = hasYt20Col ? [1700,1100,1700,1200,1000,1700,1000,1700] : [2200,1300,1900,1400,1400,1900];
  const headers = hasYt20Col
    ? ['테마','뉴스건수','뉴스매수/매도/중립','검색모멘텀','YT50건수','YT50매수/매도/중립','YT20건수','YT20매수/매도/중립']
    : ['테마','뉴스 건수','뉴스 매수/매도/중립','검색 모멘텀','유튜브 건수','유튜브 매수/매도/중립'];
  const rows = raw.map(r=>{
    const base = [
      {text: r.theme + (pickThemes.has(r.theme)?' ★':''), align:'left', bold:pickThemes.has(r.theme), color: pickThemes.has(r.theme)?GREENTX:undefined},
      {text: r.news_total},
      {text: `${r.news_buy}/${r.news_sell}/${r.news_neutral}`},
      {text: Number(r.search).toFixed(3)},
      {text: r.yt_total},
      {text: `${r.yt_buy}/${r.yt_sell}/${r.yt_neutral}`}
    ];
    if (hasYt20Col) {
      base.push({text: r.yt20_total});
      base.push({text: `${r.yt20_buy}/${r.yt20_sell}/${r.yt20_neutral}`});
    }
    return base;
  });
  kids.push(table(cols, headers, rows));
  kids.push(para('뉴스=네이버뉴스 윈도 내 발행 건수(상한 60), 매수/매도/중립은 기사 제목과 요약 논조 3분류. 검색 모멘텀=데이터랩 최신 검색비율 나누기 직전 5일 평균(API 특성상 약 2일 랙 존재). YT50=대표 50채널(youtube_channels_config.py) 한정 윈도 내 신규영상수(채널 테마 태그가 반도체·증권·AI전력·건설 4개뿐이라 그 외 테마는 구조적으로 0). YT20=Playboard 주식투자 카테고리 상위 20채널 한정, 영상 제목의 종목명 언급을 섹터 매핑해 집계(복수섹터 종목은 0.5/0.5 분할). 별표는 오늘 관심 픽 선정 테마.', {size:15, color:'606060', after:40}));
} else {
  kids.push(para(`raw_${date}.csv 없음 — 신호 원자료 누락. (참고: 2026-07-15는 뉴스 15테마 수동 감성분류 및 데이터랩 검색모멘텀으로 raw csv를 구성했으며, yt20 신호는 미수집으로 composite_v2 폴백 적용)`, {color:'808080'}));
}

if (yt20detail) {
  kids.push(section('3b', 'YT20 상위 언급 종목 상세 (Playboard 상위20채널)'));
  const sectorsWithData = Object.keys(yt20detail).filter(s=>yt20detail[s].length>0);
  if (sectorsWithData.length) {
    sectorsWithData.forEach(sector=>{
      const items = yt20detail[sector].slice(0,5);
      const line = items.map(it=>`${it.stock} ${it.count}회(매수${it.buy}/매도${it.sell}/중립${it.neutral}, ${it.channels.join('·')})`).join('; ');
      kids.push(bullet(`${sector}: ${line}`));
    });
  } else {
    kids.push(para('오늘 상위20채널 윈도 내 종목 언급 없음.', {color:'808080'}));
  }
}

kids.push(section(4, `오늘(${fmtd(date)}) 관심 픽 5종`));
if(picks.length){
  const rows = picks.map(p=>{
    const compVal = Number(p.composite_v2).toFixed(2);
    const zline = usesV3 ? `z(s/q/y/y20) ${p.sent_z}/${p.search_z}/${p.yt_z}/${p.yt20_z}` : `z(s/q/y) ${p.sent_z}/${p.search_z}/${p.yt_z}`;
    return [
      {text:p.rank, align:'center', bold:true},
      {text:p.theme, align:'left'},
      {text:p.etf, align:'left'},
      {text:p.code},
      {text:compVal},
      {text:`sent ${p.sent_news}`},
      {text:zline},
      {text:`N +${p.news_buy}/-${p.news_sell} · Y +${p.yt_buy}/-${p.yt_sell}${usesV3?` · Y20 +${p.yt20_buy}/-${p.yt20_sell}`:''}`}
    ];
  });
  kids.push(table([600,1200,2200,700,700,1300,2000,2600],['순위','테마','대표 ETF','코드','comp','감성비율','z(뉴스/검색/YT'+(usesV3?'/YT20':'')+')','매수/매도'],rows));
  kids.push(para(`${usesV3?'composite_v3 = z(sent_news) + z(search_mom) + z(yt_net) + z(yt20_net).':'composite_v2 = z(sent_news) + z(search_mom) + z(yt_net) (오늘은 yt20 미수집으로 v2 폴백).'} sent_news=(뉴스매수-뉴스매도) 나누기 뉴스총건수. 채점은 당일 종가로 15개 섹터 중 실제 상위3위 전부 포함 여부(SUCCESS/FAIL)로 수행.`, {size:15, color:'606060'}));
} else {
  kids.push(para(`${fmtd(date)} 기록된 픽 없음.`, {color:'808080'}));
}

kids.push(section(5,'누적 현황'));
kids.push(para(`채점 영업일 ${n}일 · SUCCESS(top3 전부 포함) ${successDays}/${n} · top3 슬롯 적중 ${hitSlots}/${3*n} (무작위 기대 SUCCESS율 약 2.2%)`, {bold:true, after:100}));
if(dayRows.length){
  kids.push(table([1800,1200,1400,3000,2400],['채점일','슬롯적중','판정','실제 TOP3','추천 픽'], dayRows.map(d=>[
    {text:fmtd(d[0]),align:'left'},{text:d[1]},{text:d[2],bold:true,color:d[2]==='SUCCESS'?GREENTX:REDTX},
    {text:d[3].split('|').join(', ')},{text:d[4].split('|').join(', ')}
  ])));
} else {
  kids.push(para('누적 채점 이력 없음.', {color:'808080'}));
}

kids.push(section(6,'참고 및 주의'));
kids.push(bullet('룩어헤드 금지: 픽 기록은 장전(전일 종가와 장전 신호)까지만 사용, 결과 수익률은 채점 전용.'));
kids.push(bullet('신호 수집은 매일 동일 절차와 동일 키워드로 진행(사후 편향 방지). 키워드 변경 시 로그에 명시.'));
kids.push(bullet('조선, 금 등 일부 테마 키워드는 뉴스 검색 시 동음이의어 결과가 다수 섞여 news_total이 실제 업종 관련도와 다를 수 있음(정성 판단 보조 지표 한계).'));
kids.push(bullet('매수/매도/중립 분류는 기사와 영상 제목, 요약 논조 기준 정성 판단 보조 지표이며, 분류자 주관이 개입될 수 있음.'));
kids.push(bullet('유튜브(YT50) 신호는 채널 테마 태그가 반도체, 증권, AI전력, 건설 4개 테마에만 존재해 나머지 11개 테마는 구조적으로 0으로 집계됨(2026-07-14 확인, 채널 설정 파일 한계).'));
kids.push(bullet('데이터랩 검색 API는 약 1~2일 랙이 있어, 전일 급락이나 급등 당일의 실제 검색 스파이크를 검색모멘텀 신호가 반영하지 못할 수 있음 — 알려진 데이터 병목.'));
kids.push(bullet('2026-07-15는 yt20(상위20채널 종목언급) 신호를 수집하지 못해 composite_v2(3항목)로 폴백해 픽을 산출함. yt20 수집은 다음 실행에서 재시도.'));
kids.push(bullet('판정 기준: 20영업일 내외 누적 후 SUCCESS율이 무작위 기대(약 2.2%)를 유의하게 상회하면 정식 후보로 승격 검토, 미달이면 기각.'));
kids.push(bullet('본 리포트는 파일럿 검증 기록으로 정보 제공 목적이며 투자 자문이 아님.'));

const doc = new Document({
  styles:{ default:{ document:{ run:{ font:FONT, size:19 } } } },
  sections:[{ properties:{ page:{ size:{width:12240,height:15840}, margin:{top:1080,right:1080,bottom:1080,left:1080} } }, children:kids }]
});
Packer.toBuffer(doc).then(buf=>{ fs.writeFileSync(outPath, buf); console.log('생성 완료:', outPath); });
