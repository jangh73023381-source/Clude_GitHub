export const meta = {
  name: 'loop-engineering-multimodel',
  description: '단기 추천 ETF 루프 엔지니어링을 fable(대상확인)/haiku(채점)/sonnet(분석·기록·보고서)/opus(가설검토·검증관) 단계별 모델 배정으로 실행. 신규 미평가 브리핑이 없으면 조기 종료.',
  phases: [
    { title: '대상 확인', detail: '신규 미평가 브리핑 감지 + 픽 추출', model: 'fable' },
    { title: '채점', detail: '가격 패널 구축 및 rank_etf.py 채점', model: 'haiku' },
    { title: '분석', detail: '불가항력/학습가능 분류', model: 'sonnet' },
    { title: '검증 루프', detail: '가설 검토(opus) + loop-goal-verifier(opus), 최대 5회', model: 'opus' },
    { title: '기록', detail: '운영 파일(current-holdings.md·loop-log.md·analysis-method.md) 갱신', model: 'sonnet' },
    { title: '보고서', detail: '표준 양식(report-format.md) md+docx 생성', model: 'sonnet' },
  ],
}

const ROOT_LOOP = 'C:\\agent\\Claude\\loop'
const ROOT_FABLE = 'C:\\agent\\Claude\\fable'

const GUARDRAILS = `
[공통 주의사항 — 반드시 준수]
- ${ROOT_LOOP}\\ 안의 46238499_appkey.txt, 46238499_secretkey.txt, .kiwoom_token.json, xai_apikey.txt 는
  절대 읽거나 참조하지 마라(자격증명 파일).
- kiwoom_api.py 등 어떤 스크립트로도 주문·매매·송금 관련 기능은 절대 호출하지 마라. 시세 조회
  (읽기 전용: info/daily 등)만 허용.
- 이 환경(Windows)에서는 python3 이 아니라 python, node.js 스크립트는 node 명령을 사용하라.
- 브리핑 원본은 ${ROOT_FABLE}\\, 분석방법·로그·백테스트·스크립트 정본은 ${ROOT_LOOP}\\ 이다.
- 파일 인코딩은 UTF-8. 기존 파일을 수정할 때는 기존 문서의 문체·표 형식을 그대로 따르고, 기존 내용을
  삭제·재작성하지 말고 필요한 절만 追加(append)하라(SKILL.md 원칙 3 — 과적합 금지·서술 방식 일관성).
`

phase('대상 확인')
const target = await agent(`
${GUARDRAILS}

[임무] 새로 채점할 대상이 있는지 판정하라.

절차:
1. ${ROOT_LOOP}\\current-holdings.md 를 읽어 "최신 평가 완료: \`데일리브리핑_YYYY-MM-DD.docx\`" 줄에서
   마지막으로 평가된 브리핑 날짜(이하 last_evaluated)를 확인하라.
2. ${ROOT_FABLE}\\ 폴더(하위 _보관 폴더 제외, 최상위만) 의 데일리브리핑_YYYY-MM-DD.docx 파일들을 날짜순으로
   나열하고, last_evaluated보다 날짜가 큰 파일 중 가장 이른 것을 후보로 삼아라(여러 버전 파일이 있으면
   가장 최근 수정된 것 하나만).
3. 후보가 없으면 found=false, reason="신규 브리핑 없음"으로 종료.
4. 후보가 있으면: 이 브리핑 파일명의 날짜 자체가 "채점일(scoring date, D+1)"이고, 문서 내 단기 추천 ETF
   표의 "전일종가" 열이 참조하는 날짜가 "선정일(entry date, D)"이다(현재 관행: 브리핑은 D 종가까지
   정보로 D+1에 대해 추천하고, D+1 종가로 채점한다).
5. 채점일(D+1)의 종가가 실제로 존재하는지 확인하라 — 다음 명령으로 벤치마크 종목(069500, KODEX 200)의
   일봉을 조회: \`python "${ROOT_LOOP}\\kiwoom_api.py" daily 069500 <D+1을 YYYYMMDD로>\`. 출력에 그
   날짜의 종가 행이 있으면 존재(found=true), 없으면(주말·공휴일·아직 미마감) found=false,
   reason="채점일 종가 아직 없음(주말/공휴일/장마감 전)"으로 종료.
6. found=true이면, python-docx로 해당 브리핑의 단기 추천 ETF 표(헤더 '순위'·'매수상단' 포함)를 열어
   상위 5종의 코드(원문 그대로, 영숫자 혼합 코드 훼손 금지)·종목명·전일종가를 추출하라. 문서 내 각주에
   "채점 대상 단기 상위5(picks)"가 있으면 그 값과 대조해 일치를 확인하라.

JSON으로 found(boolean), reason(string), entry_date(YYYY-MM-DD|null, D), scoring_date(YYYY-MM-DD|null, D+1),
source_docx(string|null), picks(배열|null, 각 code/name/prev_close)를 반환하라.
`, {
  label: 'find-new-target',
  model: 'fable',
  schema: {
    type: 'object',
    required: ['found', 'reason'],
    properties: {
      found: { type: 'boolean' },
      reason: { type: 'string' },
      entry_date: { type: ['string', 'null'] },
      scoring_date: { type: ['string', 'null'] },
      source_docx: { type: ['string', 'null'] },
      picks: { type: ['array', 'null'], items: { type: 'object', properties: { code: {type:'string'}, name:{type:'string'}, prev_close:{type:'number'} } } },
    },
  },
})

if (!target?.found) {
  log(`신규 채점 대상 없음: ${target?.reason ?? '알 수 없음'}. 워크플로우를 조기 종료합니다.`)
  return { status: 'no_new_target', target }
}

phase('채점')
const score = await agent(`
${GUARDRAILS}

[임무] 아래 대상을 채점하라. 선정일(D)=${target.entry_date}, 채점일(D+1)=${target.scoring_date}.
픽: ${JSON.stringify(target.picks)}

절차:
1. ${ROOT_LOOP}\\panel_close.csv (긴 유니버스 종가 패널)가 이미 D+1=${target.scoring_date}까지의
   데이터를 포함하는지 확인하라. 포함하면 그 데이터를 재사용해도 좋다.
2. 포함하지 않으면 새로 가격 CSV를 만들어야 한다. ${ROOT_LOOP}\\ 안의 기존 _fetch_*.py 파일(예:
   _fetch_0709_0710.py) 중 하나를 템플릿으로 읽고, kiwoom_api.py를 이용해 ${ROOT_LOOP}\\etf_universe.csv
   의 전체 유니버스에 대해 D 종가(prev_close)와 D+1 종가(next_close)를 조회하는 스크립트를 작성해
   실행하라. 조회 실패 종목은 1회 재시도, 계속 실패하면 제외하고 결과에 명시하라. 결과를
   \`${ROOT_LOOP}\\prices_${target.entry_date}_to_${target.scoring_date}.csv\` (헤더:
   code,name,type,prev_close,next_close)로 저장하고, 가능하면 panel_close.csv에도 이번 날짜 행을
   추가하라(향후 백테스트 재사용, 기존 스키마와 동일한 형식 유지).
3. \`python "${ROOT_FABLE}\\loop-engineering\\skills\\loop-engineering\\references\\scripts\\rank_etf.py"
   --prices "${ROOT_LOOP}\\prices_${target.entry_date}_to_${target.scoring_date}.csv" --picks <5개 코드>
   --min-price 10000 --top-pct 10\` 를 실행해 채점하라.

JSON으로 universe_n, cutoff_rank, cutoff_return_pct, results(배열: code/name/rank/percentile/return_pct/hit),
hits, achieved, prices_csv_path 를 반환하라.
`, {
  label: 'rank-score',
  model: 'haiku',
  schema: {
    type: 'object',
    required: ['universe_n', 'cutoff_rank', 'results', 'hits', 'achieved', 'prices_csv_path'],
    properties: {
      universe_n: { type: 'number' },
      cutoff_rank: { type: 'number' },
      cutoff_return_pct: { type: 'number' },
      results: { type: 'array', items: { type: 'object', properties: { code:{type:'string'}, name:{type:'string'}, rank:{type:'number'}, percentile:{type:'number'}, return_pct:{type:'number'}, hit:{type:'boolean'} } } },
      hits: { type: 'number' },
      achieved: { type: 'boolean' },
      prices_csv_path: { type: 'string' },
    },
  },
})

phase('분석')
let analysis = await agent(`
${GUARDRAILS}

[임무] 채점 결과를 보고 미적중 종목별로 "불가항력" 또는 "학습가능"으로 분류하라. ${ROOT_LOOP}\\analysis-method.md
의 "루프 판정·검증 강화 기준(v2.2)" 절(A.1~A.4)을 반드시 그대로 적용하라(읽기만, 수정 금지):
- 시장 급락/등락 자체는 불가항력 아님(상대순위 채점이므로 상위10%는 항상 존재).
- 선정일(D=${target.entry_date}) 저녁에 급락게이트·금리인상조짐·리밸런싱 경고 중 하나라도 발동
  중이었으면 불가항력 불인정(학습가능 강제). WebSearch로 그날 실제 시장 상황(코스피/코스닥 등락,
  주요 이벤트)을 확인하고, 게이트 발동 여부는 ${ROOT_LOOP}\\loop-log.md 최근 기록의 판정 관행과
  일관되게 적용하라.
- 종목별 개별 판정 필수(일괄 "전부 불가항력" 금지). 불가항력 주장은 뉴스·공시 출처 2개 이상 필요.
- 최근 10회 중 불가항력 3회 이상이면 반복충격은 불가항력 아님(loop-log.md 최근 10회 기록 확인).

채점 결과: ${JSON.stringify(score)}

D+1(${target.scoring_date}) 유니버스 상위권을 차지한 종목·섹터 특성(winner_profile)도 정리하라
(가격 CSV의 상위권 데이터 직접 확인, 필요시 WebSearch로 원인 뉴스 확인).

JSON으로 classification(종목별 code/category/reasoning), overall("달성"|"미달"), winner_profile을 반환하라.
`, {
  label: 'cause-analysis',
  model: 'sonnet',
  schema: {
    type: 'object',
    required: ['classification', 'overall', 'winner_profile'],
    properties: {
      classification: { type: 'array', items: { type: 'object', properties: { code:{type:'string'}, category:{type:'string'}, reasoning:{type:'string'} } } },
      overall: { type: 'string' },
      winner_profile: { type: 'string' },
    },
  },
})

phase('검증 루프')
let verifier = null
let iteration = 0
let bestPicks = target.picks
let bestScore = score
let bannedList = []
const MAX_ITER = 5

if (analysis.overall !== '달성') {
  while (iteration < MAX_ITER) {
    iteration++
    const hyp = await agent(`
${GUARDRAILS}

[임무] iteration ${iteration}/${MAX_ITER}. 현재 미달 상태(적중 ${bestScore.hits}/5)를 개선할 "구별되는
(distinct)" 신규 가설을 도출하고, 가능하면 실제로 백테스트해 검증하라.

1. ${ROOT_LOOP}\\loop-log.md 와 ${ROOT_LOOP}\\analysis-method.md 전체에서 이미 "기각"·"채택 보류" 표시된
   규칙 계열을 전부 확인하라(Rule A~X 등, 읽기만). 이번 iteration에서 그 목록과 중복되지 않는 축을
   1개 지정하라(일반 규칙으로 표현, 특정 종목 하드코딩 금지).
2. ${ROOT_LOOP}\\backtest\\ 폴더의 기존 백테스트 스크립트(bt_engine.py 등)와 ${ROOT_LOOP}\\panel_close.csv
   를 참고해, 가능하면 이 가설을 실제로 in-sample(오늘 D=${target.entry_date} 시점 정보만 사용,
   룩어헤드 금지) 재선정 → rank_etf.py로 D+1(${target.scoring_date}) 채점까지 실행하라. 시간·데이터
   제약으로 전체 백테스트가 불가능하면 그 사유를 명시하고 "검증 대기(백테스트 미실행)"로 잠정 등록만 하라.
3. 현재까지 이번 실행에서 이미 지정·기각된 금지(중복) 목록: ${JSON.stringify(bannedList)}

분석 결과: ${JSON.stringify(analysis)}

JSON으로 hypothesis(string), rationale(string), duplicate_check(string), backtest_attempted(boolean),
insample_picks(배열|null, 재선정 5종 code/name), insample_hits(number|null), insample_achieved(boolean|null)
를 반환하라.
`, { label: `hypothesis-iter${iteration}`, phase: '검증 루프', model: 'opus', schema: {
      type: 'object',
      required: ['hypothesis', 'rationale', 'duplicate_check', 'backtest_attempted'],
      properties: {
        hypothesis: { type: 'string' },
        rationale: { type: 'string' },
        duplicate_check: { type: 'string' },
        backtest_attempted: { type: 'boolean' },
        insample_picks: { type: ['array', 'null'] },
        insample_hits: { type: ['number', 'null'] },
        insample_achieved: { type: ['boolean', 'null'] },
      },
    } })

    const verify = await agent(`
${GUARDRAILS}

너는 loop-goal-verifier다(정의: ${ROOT_LOOP}\\.claude\\agents\\loop-goal-verifier.md, 읽고 절차를 그대로
따르라). iteration ${iteration}/${MAX_ITER}.

V1. 이번 회차의 채점(원래 픽, 그리고 있다면 재선정 픽)을 rank_etf.py로 독립 재계산하라(가격 CSV:
${score.prices_csv_path}). 룩어헤드(D+1 데이터가 재선정 입력에 섞였는지) 점검.
V2. 조기종료 방지 게이트(v2.2 A) 재적용 — 시장급락 불인정·게이트발동중 불인정·종목별 개별판정·
    10회중 3회 상한.
V3. PASS = 5/5 그리고(신규 채택 시) 교차검증 게이트 통과. FAIL = 그 외 전부.
V4. FAIL이면 다음 iteration을 위해 이번에 기각/보류된 것을 banned_list에 추가하고, 그날 승자 특성과
    아직 시도 안 된 신규 가설 방향을 지정하라.
V5. 종료 조건 결론.

원래 채점: ${JSON.stringify(bestScore)}
분석: ${JSON.stringify(analysis)}
이번 iteration 가설: ${JSON.stringify(hyp)}

JSON으로 v1_recheck({hits,cutoff_rank,lookahead_suspected}), v2_gate({violations:[string]}),
v3_verdict("PASS"|"FAIL"), v4_reassignment({banned_list:[string],winner_profile:string,new_hypothesis:string}|null),
v5_conclusion(string)을 반환하라.
`, { label: `verifier-iter${iteration}`, phase: '검증 루프', model: 'opus', schema: {
      type: 'object',
      required: ['v1_recheck', 'v2_gate', 'v3_verdict', 'v5_conclusion'],
      properties: {
        v1_recheck: { type: 'object' },
        v2_gate: { type: 'object' },
        v3_verdict: { type: 'string' },
        v4_reassignment: { type: ['object', 'null'] },
        v5_conclusion: { type: 'string' },
      },
    } })

    verifier = { iteration, hypothesis: hyp, verdict: verify }
    bannedList.push(...(verify.v4_reassignment?.banned_list ?? []), hyp.hypothesis)
    if (hyp.insample_achieved && verify.v3_verdict === 'PASS') {
      bestPicks = hyp.insample_picks
      bestScore = { ...bestScore, hits: hyp.insample_hits, achieved: true }
      break
    }
  }
} else {
  verifier = { iteration: 0, note: '3단계에서 이미 달성 판정 — 검증 루프 생략' }
}

phase('기록')
const record = await agent(`
${GUARDRAILS}

[임무] 이번 실행 결과를 운영 파일 3개에 반영하라(기존 문체·형식 그대로, 새 절만 추가):

1. ${ROOT_LOOP}\\current-holdings.md — "## 현재 대상" 절을 이번 실행 결과로 갱신하고, 기존 "현재 대상"
   내용은 "## 직전 대상 (${target.scoring_date}, 평가 완료 — 멀티모델 루프)" 절로 이동시켜라(기존
   파일의 다른 "직전 대상"/"과거 대상" 절들은 그대로 둔다).
2. ${ROOT_LOOP}\\loop-log.md — 파일 하단(실행 이력 마지막)에 "## ${target.scoring_date} 실행 (멀티모델)"
   절을 새로 추가하라. 기존 기록 형식(유니버스·채점표·분석·검증 루프·결과)을 그대로 따르고, 검증관
   판정(${JSON.stringify(verifier)})을 포함하라.
3. ${ROOT_LOOP}\\analysis-method.md — 이번 회차 검증관이 PASS 판정(정식 채택)을 승인한 새 규칙이 있으면
   "확정" 절로 승격하고 "변경 이력(버전 로그)"에 새 버전을 추가하라. PASS가 아니면(대부분의 경우) 이
   파일은 건드리지 마라(잠정 등록은 "검증 루프" 단계에서 이미 hypothesis로만 언급, 실제 채택은 없음).

채점 결과: ${JSON.stringify(score)}
분석: ${JSON.stringify(analysis)}
검증 결과: ${JSON.stringify(verifier)}
최종 픽/스코어: ${JSON.stringify({ bestPicks, bestScore })}

수정한 파일 목록과 각 파일에서 실제로 추가한 절의 제목을 반환하라.
`, {
  label: 'record-results',
  model: 'sonnet',
  schema: {
    type: 'object',
    required: ['files_modified'],
    properties: {
      files_modified: { type: 'array', items: { type: 'object', properties: { path: {type:'string'}, section_added: {type:'string'} } } },
    },
  },
})

phase('보고서')
const report = await agent(`
${GUARDRAILS}

[임무] ${ROOT_LOOP}\\report-format.md 표준 양식대로 이번 실행 보고서를 작성하라.

1. ${ROOT_LOOP}\\report-format.md 를 읽고, ${ROOT_LOOP}\\references\\scripts\\build_report_docx.js 하단
   주석의 JSON 스키마를 확인하라(참고 예시: ${ROOT_LOOP}\\references\\scripts\\report_2026-07-10.json).
2. \`${ROOT_LOOP}\\references\\scripts\\report_${target.scoring_date}.json\` 을 그 스키마대로 작성하라
   (referenceTop5 절 필수 포함 — 유니버스 상위 1~5위 참고용 표). 실행 모델은 "멀티모델(fable/haiku/
   sonnet/opus)"로 부제에 명시하라.
3. \`node "${ROOT_LOOP}\\references\\scripts\\build_report_docx.js"
   "${ROOT_LOOP}\\references\\scripts\\report_${target.scoring_date}.json"
   "${ROOT_LOOP}\\루프엔지니어링_${target.scoring_date}_multimodel.docx"\` 를 실행하라. 동일 파일명이
   이미 있으면 _v2, _v3로 넘버링하라(기존 파일 덮어쓰기 금지).
4. 같은 내용으로 \`${ROOT_LOOP}\\루프엔지니어링_${target.scoring_date}_multimodel.md\` 도 작성하라.
5. 두 파일이 실제로 생성됐는지 확인하라.

채점: ${JSON.stringify(score)}
분석: ${JSON.stringify(analysis)}
검증 루프: ${JSON.stringify(verifier)}
기록 결과: ${JSON.stringify(record)}

JSON으로 md_path, docx_path, summary를 반환하라.
`, {
  label: 'final-report',
  model: 'sonnet',
  schema: {
    type: 'object',
    required: ['md_path', 'docx_path', 'summary'],
    properties: {
      md_path: { type: 'string' },
      docx_path: { type: 'string' },
      summary: { type: 'string' },
    },
  },
})

return { status: 'executed', target, score, analysis, verifier, record, report }
