# 루프 엔지니어링 보고서 표준 양식

> 사용자 지시(2026-06-22): 앞으로 모든 루프 엔지니어링 보고서는 이 양식으로 통일한다.
> 기준 문서: `루프엔지니어링_2026-06-19_sonnet_확장187종.docx`

## 사용법

1. `references/scripts/report_YYYY-MM-DD.json`을 작성한다 (구조는
   `references/scripts/build_report_docx.js` 하단 주석 참조: title, subtitle, summary,
   universeNote, sectionA{heading,tableHeaders,tableRows,colWidths,notes},
   referenceTop5{heading,note,tableHeaders,tableRows,colWidths}, causeAnalysis,
   sectionB{heading,intro,tableHeaders,tableRows,colWidths,notes}, methodChange{heading,notes},
   finalAdoption, disclaimer).
   - `referenceTop5`은 **매 보고서마다 항상 포함**한다 — 그날 유니버스 전체에서 익일 상승률
     1~5위 ETF(코드·종목명·전일종가·익일종가·상승률)를 표로 싣는다. 추천 선정에는 사용하지
     않는(룩어헤드 금지) 순수 참고 정보이며, `rank_etf.py` 출력 상위 5행을 그대로 옮긴다.
   - `summary`는 **헤드라인만** 담는다(3~4개 불릿, 각 1문장). 본문 섹션(원인 분석/검증 루프/
     방법 변경/최종 채택)에서 이미 풀어서 설명하는 수치·근거를 요약에서 다시 길게 반복하지
     않는다 — 중복 서술 금지.
2. 실행: `node references/scripts/build_report_docx.js references/scripts/report_YYYY-MM-DD.json 루프엔지니어링_YYYY-MM-DD_sonnet.docx`
3. 결과 파일명 규칙: `루프엔지니어링_YYYY-MM-DD_sonnet.docx` (실행 모델명 반영, 예: `_opus`).

## 양식 구성 (고정 섹션 순서)

1. 제목(굵게, 15pt) + 부제(채점 기준·유니버스·확정방법·실행 모델 한 줄 요약)
2. 요약 (불릿 3~4개: 현 추천 채점 결과, 개선법 in-sample 결과, 확정 방법, 핵심 원인)
3. (유니버스 범위가 특이하면) 유니버스 범위 설명
4. (A) 현 추천 채점 — 표(순위/종목/코드/전일종가/당일종가/상승률/상위10%) + 컷오프·결론 문단
5. Reference — 유니버스 상위 1~5위 (항상 표시, 참고용 · 추천 선정에는 미사용)
6. 원인 분석 (불가항력 vs 학습가능)
7. (B) 신규 방법(잠정) 재산출 — 규칙 설명 + 표(종목/코드/전일종가/당일종가/상승률/순위·적중) + 결과·규칙충돌 문단
8. 방법 변경 요약 · 교차검증 게이트 (충족/미충족 명시)
9. 최종 채택 (확정 방법, 신규 잠정 등록, 결측데이터, 상태)
10. 확인 문구 · 면책 (룩어헤드 금지 확인 + 투자자문 아님 고지, 고정 문구)

표 스타일: 헤더 행 굵게 + 옅은 파란 배경(D5E8F0), 셀 테두리 연한 회색(CCCCCC), 표 전체 테두리는
검은색(auto) 얇은 선, 표 너비 9360 DXA(US Letter 1인치 여백 기준), 셀 패딩 top/bottom 80,
left/right 120 DXA.


---

## [2026-07-26 추가] (A2) 조합제 shadow 병기 섹션 (통합 루프 필수)

통합 루프(`references/integrated-loop-runbook.md`) 도입에 따라, 루프 보고서에는 (A) 다음에
**(A2) 조합제 shadow 병기** 섹션을 반드시 넣는다. JSON 스키마에는 `sectionA2`로 추가하고,
`build_report_docx.js`가 아직 이 키를 모르면 `sectionB`와 같은 표 구조로 만들어 `sectionA` 뒤에
오도록 배치하거나, 임시로 `sectionA.notes` 하단에 표를 이어 붙인다.

내용(고정):

1. 같은 채점일의 두 트랙 병기 표 — 트랙 A(확정방법, 실적용) / 트랙 B(조합제, shadow) /
   15섹터 등가중(기준선) 각각의 **코스피 대비**·**KODEX200 대비** 초과수익.
2. 트랙 B의 그날 픽 5종과 배제 사유(mom20 하방 / 악재감성).
3. 조합제 누적 현황 — 누적 일수 / 평균 초과(코스피) / 코스피 이김 / 잭나이프 하한 /
   **20영업일 판정까지 남은 일수** / 사후수집 일자 수.
4. 고정 문구: "트랙 B는 shadow 기록 전용이며 실제 추천에 반영되지 않습니다. 파라미터는 20영업일
   판정 전까지 동결됩니다."

수치는 전부 `python3 references/scripts/dual_score.py <YYYYMMDD> --picks <코드5>` 출력에서 그대로
옮긴다(수기 재계산 금지).
