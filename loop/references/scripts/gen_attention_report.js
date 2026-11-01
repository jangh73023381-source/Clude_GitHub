// gen_attention_report.js — 관심 모멘텀 파일럿 데일리 리포트(docx) 생성기
// 사용법: node gen_attention_report.js <YYYYMMDD> [출력경로.docx]
//   - 오늘 픽: references/attention_pilot_picks.csv 의 date==YYYYMMDD 행
//   - 직전 채점: references/attention_pilot_results.csv 의 가장 최근 score_date 행
//   - 오늘 raw 신호: references/raw_YYYYMMDD.csv (있으면)
//   - 누적 현황: results.csv 전체 집계
// 서식: 맑은 고딕, 네이비(1F3864) 제목, 표 헤더 네이비 음영+흰 굵은 글씨 (fable 데일리브리핑 양식 준용)
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, BorderStyle, WidthType, ShadingType, HeadingLevel } = require('docx');

const REF = path.resolve(__dirname, '..');            // loop/references
const LOOP = path.resolve(REF, '..');                 // loop
const date = process.argv[2];
if (!date) { console.error('YYYYMMDD 인자 필요'); process.exit(1); }
const outPath = process.argv[3] || path.join(LOOP, `관심모멘텀_파일럿_${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}.docx`);

const NAVY='1F3864', HDRTXT='FFFFFF', GRIDCLR='BFBFBF', ALT='F2F5FA', GREENBG='E2EFDA', GREENTX='1E7B34', REDTX='C00000';
const FONT='맑은 고딕';

function readCSV(p){ if(!fs.existsSync(p)) return []; const L=fs.readFileSync(p,'utf8').trim().split(/\r?\n/); const h=L[0].split(','); return L.slice(1).filter(x=>x.length).map(r=>{const c=r.split(','); const o={}; h.forEach((k,i)=>o[k.trim()]=(c[i]||'').trim()); return o;}); }

const themes = readCSV(path.join(REF,'attention_pilot_themes.csv'));
const picksAll = readCSV(path.join(REF,'attention_pilot_picks.csv'));
const resAll = readCSV(path.join(REF,'attention_pilot_results.csv'));
const raw = readCSV(path.join(REF,`raw_${date}.csv`));

const picks = picksAll.filter(r=>r.date===date);
const scoreDates = [...new Set(resAll.map(r=>r.score_date))].sort();
const lastScoreDate = scoreDates[scoreDates.length-1] || '';
const lastRes = resAll.filter(r=>r.score_date===lastScoreDate);

// 누적 집계
const byDay={}; resAll.forEach(r=>{ if(r.hit!=='') (byDay[r.score_date]=byDay[r.score_date]||[]).push(Number(r.hit)); });
let tot=0,cnt=0; const dayRows=[]; Object.keys(byDay).sort().forEach(d=>{const h=byDay[d].reduce((a,b)=>a+b,0),n=byDay[d].length; tot+=h;cnt+=n; dayRows.push([d,`${h}/${n}`, `${(h/n*100).toFixed(0)}%`]);});
const cumPct = cnt? (tot/cnt*100).toFixed(1) : '—';

const fmtd = s=> s? `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}` : '—';

// ---- 스타일 헬퍼 ----
function title(t){ return new Paragraph({ spacing:{after:80}, children:[new TextRun({text:t, bold:true, size:32, color:NAVY, font:FONT})] }); }
function subtitleLine(t){ return new Paragraph({ spacing:{after:200}, border:{bottom:{style:BorderStyle.SINGLE,size:12,color:NAVY,space:2}}, children:[new TextRun({text:t, size:18, color:'404040', font:FONT})] }); }
function section(n,t){ return new Paragraph({ spacing:{before:240,after:120}, children:[new TextRun({text:`${n}. ${t}`, bold:true, size:26, color:NAVY, font:FONT})] }); }
function para(t,opts={}){ return new Paragraph({ spacing:{after:opts.after??80}, children:[new TextRun({text:t, size:opts.size??19, font:FONT, color:opts.color||'000000', bold:!!opts.bold})] }); }
function bullet(t){ return new Paragraph({ spacing:{after:40}, indent:{left:360,hanging:200}, children:[new TextRun({text:'• '+t, size:18, font:FONT})] }); }

const B={style:BorderStyle.SINGLE,size:1,color:GRIDCLR};
const BORD={top:B,bottom:B,left:B,right:B};
function cell(text,{w,head=false,fill,align='left',bold=false,color}={}){
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

// ---- 본문 구성 ----
const kids=[];
kids.push(title('관심 모멘텀 파일럿 — 데일리 리포트'));
kids.push(subtitleLine(`기준일 ${fmtd(date)} · Attention-Momentum Forward Pilot · 정보 제공 목적(투자 자문 아님)`));

// 1. 개요
kids.push(section(1,'파일럿 개요'));
kids.push(para('가격이 아닌 장전(전일 16:00→금일 09:00) 정성 관심 신호로 익일 상위 종목을 사전 포착할 수 있는지 검증하는 전방(forward) 페이퍼 파일럿. 뉴스·유튜브는 과거 시계열 재구성이 불가해 백테스트 대신 매일 사전 기록→익일 채점 방식으로 약 20영업일 누적 후 알파 유무를 판정한다.'));
kids.push(para('신호 = 테마별 (뉴스 기사수 + 데이터랩 검색 모멘텀 + 유튜브 신규영상수)를 z-score 표준화·합산(composite) → 상위 5테마의 대표 ETF를 당일 관심 픽으로 기록. 대상은 15테마(숏·레버리지·인버스 제외).', {after:60}));
kids.push(para('v1.1(2026-07-09): 뉴스·유튜브는 매수(긍정)/매도(부정)/중립 논조를 함께 집계해 표기(선정 로직에는 미반영, 참고용). 유튜브는 대표 8채널(삼프로TV·슈카월드·815머니톡·김작가TV·키움증권 채널K·삼성증권POP·미래에셋증권 스마트머니·주코노미TV)로 한정.', {after:60, color:'404040', size:18}));
kids.push(para('채점 기준: 관심 픽 ETF의 익일 종가 수익률이 유니버스(전일 종가 ≥ 1만원, 숏선물 제외)의 상위 10% 컷오프 이상이면 적중. 판정선 = 무작위 기대 10%, 확정 mom20 베이스라인 ≈ 28%(1.4/5).', {color:'404040', size:18}));

// 2. 직전 픽 채점
kids.push(section(2, `직전 픽 채점 (${fmtd(lastScoreDate)} 종가 기준)`));
if(lastRes.length){
  const N = lastRes.find(r=>r.universe_N)?.universe_N||'—';
  const cut = lastRes.find(r=>r.cutoff_rank)?.cutoff_rank||'—';
  const hit = lastRes.filter(r=>r.hit==='1').length;
  const scored = lastRes.filter(r=>r.hit!=='').length;
  kids.push(para(`유니버스 ${N}종 · 상위10% 컷오프 = 상위 ${cut}위 · 적중 ${hit}/${scored} (채점 가능분)`, {bold:true, after:100}));
  const rows = lastRes.map(r=>{
    const scored = r.hit!=='';
    const ok = r.hit==='1';
    return [
      {text:r.theme, align:'left'},
      {text:r.etf, align:'left'},
      {text: r.rank? `${r.rank}/${r.universe_N}`:'—'},
      {text: r.ret? `${Number(r.ret)>0?'+':''}${r.ret}%`:'—', color: r.ret? (Number(r.ret)>=0?GREENTX:REDTX):'808080'},
      {text: scored? (ok?'적중':'미달') : (r.note||'—'), bold:scored, color: scored?(ok?GREENTX:REDTX):'808080'}
    ];
  });
  kids.push(table([1500,3200,1400,1500,1760],['테마','대표 ETF','순위','익일수익','판정'],rows));
} else {
  kids.push(para('아직 채점된 픽이 없습니다.', {color:'808080'}));
}

// 3. 오늘 raw 신호
kids.push(section(3, `오늘(${fmtd(date)}) 관심 신호 수집 — 장전 윈도 전일 16:00→금일 09:00`));
if(raw.length){
  const pickThemes = new Set(picks.map(p=>p.theme));
  const g = (r,...keys)=>{ for(const k of keys){ if(r[k]!==undefined && r[k]!=='') return r[k]; } return ''; };
  const rows = raw.map(r=>{
    const newsTotal = g(r,'news_total','news');
    const nb=g(r,'news_buy'), ns=g(r,'news_sell'), nn=g(r,'news_neutral');
    const ytTotal = g(r,'yt_total','youtube');
    const yb=g(r,'yt_buy'), ys=g(r,'yt_sell'), yn=g(r,'yt_neutral');
    const hasSent = nb!=='' || ns!=='';
    const hasYtSent = yb!=='' || ys!=='';
    return [
      {text: r.theme + (pickThemes.has(r.theme)?' ★':''), align:'left', bold:pickThemes.has(r.theme), color: pickThemes.has(r.theme)?GREENTX:undefined},
      {text: newsTotal},
      {text: hasSent? `${nb}/${ns}/${nn}` : '—'},
      {text: r.search!==undefined? Number(r.search).toFixed(3):''},
      {text: ytTotal},
      {text: hasYtSent? `${yb}/${ys}/${yn}` : '—'}
    ];
  });
  kids.push(table([2600,1400,1800,1400,1400,1480],['테마','뉴스 건수','뉴스 매수/매도/중립','검색 모멘텀','유튜브 건수(대표8채널)','유튜브 매수/매도/중립'],rows));
  kids.push(para('뉴스=네이버뉴스 윈도 내 발행 건수(상한 40), 매수/매도/중립은 기사 제목·요약 논조 3분류. 검색 모멘텀=데이터랩 최신 검색비율÷직전 5일 평균. 유튜브=대표 8채널(삼프로TV·슈카월드·815머니톡·김작가TV·키움증권 채널K·삼성증권POP·미래에셋증권 스마트머니·주코노미TV) 한정 윈도 내 신규영상수 및 매수/매도/중립. ★=오늘 관심 픽 선정 테마. composite(테마 선정)은 매수/매도 건수를 반영하지 않는 참고 지표.', {size:15, color:'606060', after:40}));
} else {
  kids.push(para(`raw_${date}.csv 없음 — 신호 원자료 누락.`, {color:'808080'}));
}

// 4. 오늘 관심 픽
kids.push(section(4, `오늘(${fmtd(date)}) 관심 픽 5종`));
if(picks.length){
  const rows = picks.map(p=>{
    const hasSent = p.news_buy!==undefined && p.news_buy!=='';
    const sentText = hasSent? `N +${p.news_buy}/-${p.news_sell} · Y +${p.yt_buy}/-${p.yt_sell}` : '—';
    return [
      {text:p.rank, align:'center', bold:true},
      {text:p.theme, align:'left'},
      {text:p.etf, align:'left'},
      {text:p.code},
      {text:Number(p.composite).toFixed(2)},
      {text:`n ${p.news_z} / s ${p.search_z} / y ${p.yt_z}`},
      {text: sentText},
      {text: p.entry_prevclose? Number(p.entry_prevclose).toLocaleString():'—', align:'right'}
    ];
  });
  kids.push(table([500,1100,2100,750,650,1600,1980,1400],['순위','테마','대표 ETF','코드','comp','z(news/search/yt)','매수/매도(뉴스·YT)','진입 전일종가'],rows));
  kids.push(para('composite = news_z + search_z + yt_z(매수/매도 건수는 선정에 미반영, 참고용). 매수/매도(뉴스·YT) = 해당 테마 신호의 매수의견 건수/매도의견 건수(N=뉴스, Y=유튜브 대표8채널). 진입 전일종가 = 기록 시점(장전)의 직전 거래일 종가(참고용). 채점은 익일 종가로 수행.', {size:15, color:'606060'}));
} else {
  kids.push(para(`${fmtd(date)} 기록된 픽 없음.`, {color:'808080'}));
}

// 5. 누적 현황
kids.push(section(5,'누적 현황'));
kids.push(para(`채점 영업일 ${dayRows.length}일 · 누적 적중 ${tot}/${cnt} = ${cumPct}% (무작위 기대 10% / mom20 베이스라인 ≈ 28%)`, {bold:true, after:100}));
if(dayRows.length){
  kids.push(table([3000,3000,3360],['채점일','적중/채점','적중률'], dayRows.map(d=>[{text:fmtd(d[0]),align:'left'},{text:d[1]},{text:d[2]}])));
} else {
  kids.push(para('누적 채점 이력 없음.', {color:'808080'}));
}

// 6. 참고·주의
kids.push(section(6,'참고 · 주의'));
kids.push(bullet('룩어헤드 금지: 픽 기록은 장전(전일 종가+장전 신호)까지만 사용, 결과 수익률은 채점 전용.'));
kids.push(bullet('신호 수집은 매일 동일 절차·동일 키워드(사후 편향 방지). 키워드 변경 시 로그에 명시.'));
kids.push(bullet('픽 ETF가 유니버스 필터(전일종가 ≥ 1만원)에 못 미치면 채점에서 "유니버스 없음" 처리될 수 있음.'));
kids.push(bullet('매수/매도/중립 분류는 기사·영상 제목·요약 논조 기준 정성 판단 보조 지표이며, 종목 선정(composite) 로직에는 반영되지 않음.'));
kids.push(bullet('유튜브 신호는 대표 8채널(삼프로TV·슈카월드·815머니톡·김작가TV·키움증권 채널K·삼성증권POP·미래에셋증권 스마트머니·주코노미TV) 외 결과는 집계하지 않음.'));
kids.push(bullet('본 리포트는 파일럿 검증 기록으로 정보 제공 목적이며 투자 자문이 아님. 매수/매도 집계도 투자 권유가 아닌 시장 논조 참고 지표.'));

const doc = new Document({
  styles:{ default:{ document:{ run:{ font:FONT, size:19 } } } },
  sections:[{ properties:{ page:{ size:{width:12240,height:15840}, margin:{top:1080,right:1080,bottom:1080,left:1080} } }, children:kids }]
});
Packer.toBuffer(doc).then(buf=>{ fs.writeFileSync(outPath, buf); console.log('생성 완료:', outPath); });
