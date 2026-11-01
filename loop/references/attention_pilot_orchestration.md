# 관심 모멘텀 파일럿 — 멀티모델 수동 오케스트레이션 런북

> 목적: 관심 모멘텀 파일럿(`references/attention_pilot.md` v2.2)을 **자동 Workflow가 아니라
> 오케스트레이터(메인 에이전트)가 단계별로 직접 지휘**하는 방식으로 실행한다. 각 단계는 성격에
> 맞는 모델(Fable 5 / Haiku 4.5 / Sonnet 5)을 배정하고, 필요 시 Agent 도구의 `model` 오버라이드로
> 서브에이전트에 위임한다. 단계 간 게이트(특히 Phase 0의 조기종료)를 반드시 통과한 뒤 다음 단계로
> 넘어간다.
>
> 설정일: 2026-07-11 (사용자 지시 "관심 모멘텀 파일럿을 멀티모델 수동 오케스트레이션으로 설정").
> 참조 정본: 절차·채점 규칙은 `references/attention_pilot.md`(v2.2)를 따르고, 이 문서는 그 절차에
> **모델 배정과 수동 지휘 방식**을 덧붙인 실행 런북이다. 절차가 상충하면 attention_pilot.md가 우선.

## 자동 Workflow와의 차이 (왜 "수동")
- `loop-engineering-multimodel`은 스크립트가 phase/agent를 자동 실행하지만, 이 런북은 **사람의
  "실행" 요청 시 오케스트레이터가 Phase 0부터 순서대로 직접 돌린다.** 각 Phase 종료 후 결과를
  확인하고 다음 Phase로 진행할지(또는 조기종료할지) 판단한다.
- 데이터 수집(뉴스·검색량·유튜브)은 MCP 호출과 정성 감성분류가 필요해 완전 배치 자동화가 어렵다 →
  수동 오케스트레이션이 적합.

## 공통 가드레일 (모든 Phase·서브에이전트 필수 준수)
- `C:\agent\Claude\loop\`의 `46238499_appkey.txt`, `46238499_secretkey.txt`, `.kiwoom_token.json`,
  `xai_apikey.txt`는 **절대 읽거나 참조하지 않는다**(자격증명 파일).
- 어떤 스크립트로도 **주문·매매·송금 기능은 호출 금지.** 시세 조회(읽기 전용: `kiwoom_api.py info/daily`
  등)만 허용.
- 실행 환경 주의: 사용자 PC(Windows)에서는 `python`/`node`, 샌드박스(Linux)에서는 `python3`/`node`.
- 신호 수집 윈도는 **전일 거래일 16:00 → 금일 거래일 09:00**를 엄격 적용(룩어헤드 금지). 윈도 밖
  기사·영상은 집계 제외.
- 트위터/X(xAI `x_search`)는 결제 크레딧 미등록으로 **미가동** — 크레딧 등록 확인 전에는
  `fetch_twitter_signals.py` 등으로 호출하지 않는다. composite는 news+search+youtube 3항만 사용.
- 파일 인코딩 UTF-8. 로그·정본 파일 수정 시 기존 문체·표 형식을 유지하고 기존 내용을 삭제·재작성하지
  않고 필요한 절만 append.
- 정보 제공 목적이며 투자 자문 아님.

## 모델 배정 요약
| Phase | 단계 | 모델 | 위임 방식 |
|---|---|---|---|
| 0 | 대상 확인 (조기종료 게이트) | **Fable 5** | 간단하면 오케스트레이터 직접, 아니면 Agent(model:fable) |
| 1 | 지난 픽 채점 | **Haiku 4.5** | Agent(model:haiku) 또는 직접 bash |
| 2 | 오늘 관심 신호 수집 + 감성분류 | **Sonnet 5** | 오케스트레이터 직접(MCP 호출·정성판단) |
| 3 | 오늘 픽 기록 | **Haiku 4.5** | Agent(model:haiku) 또는 직접 bash |
| 4 | 누적 현황 + 원인/판정 분석 | **Sonnet 5** | 오케스트레이터 직접 |
| 5 | 리포트(docx) 생성·공유 | **Sonnet 5** | 오케스트레이터 직접 |

> 배정 원칙: 기계적·결정적 단계(채점·기록)는 Haiku, 정성 판단·MCP 오케스트레이션·서술이 필요한
> 단계(신호 감성분류·원인분석·리포트)는 Sonnet, 값싼 존재/데이터 유무 판별(Phase 0)은 Fable.

---

## Phase 0 — 대상 확인 (모델: Fable 5) · **조기종료 게이트**
목적: 오늘 실제로 할 일이 있는지 판정한다. 없으면 **아무 파일도 건드리지 않고 종료**한다.

절차:
1. `references/attention_pilot_v2_picks.csv`(마지막 `date`)와 `attention_pilot_v2_results.csv`
   (마지막 `score_date`)를 읽어 마지막 기록·마지막 채점 일자를 확인.
2. **채점 대기 판정**: 마지막 기록일(picks) > 마지막 채점일(results)이고, 그 기록일의 **당일 종가가
   존재**하면(벤치마크 `python kiwoom_api.py daily 069500 <YYYYMMDD>`에 해당일 종가 행 존재) →
   채점 대상 있음(Phase 1로).
3. **신규 픽 기록 판정**: 오늘이 **거래일**(주말·공휴일 아님)이고 장전 윈도(전일16:00~금일09:00)가
   유효하면 → 신호 수집 대상 있음(Phase 2로).
4. 둘 다 아니면 `found=false`로 조기종료:
   - 오늘이 주말/공휴일 → reason="비거래일 — 신규 채점/기록 대상 없음".
   - 채점일 종가 아직 없음(장 마감 전) → reason="채점일 종가 아직 없음".
   조기종료 시 산출물은 "실행 없음(사유)" 한 줄 보고. loop-log에 남길 필요는 없음(no-op).

출력(JSON): `found`(bool), `reason`, `score_target`(YYYYMMDD|null), `record_target`(YYYYMMDD|null).

## Phase 1 — 지난 픽 채점 (모델: Haiku 4.5)
- `score_target`의 당일 종가 패널(`prices_*.csv`)이 있으면 재사용, 없으면 키움으로 유니버스 수집.
- 실행: `python references/scripts/attention_pilot_v2.py score --date <score_target> --prices <prices csv>`
- 결과: `attention_pilot_v2_results.csv`에 `score_date,picks,top3_sectors,top3_hits,success,pick_ranks,sector_N`
  append. top3_hits(0~3)와 success(0/1) 확인.
- **[shadow A/B 병행 채점]** v2 채점 직후 같은 prices로 shadow도 채점(기존 파일 무손상, 신규 파일에만 기록):
  `python references/scripts/attention_pilot_shadow.py score --date <score_target> --prices <prices csv>`
  → `attention_shadow_results.csv`에 base/clean/contra/inter 변형별 top3_hits·rank-IC append. 20영업일
  누적 후 판정(단일일 우열로 방법 교체 금지, context-notes §4·§6).
- **[ns2 전방검증 병행 채점]** (2026-07-23 정보소스 백테스트로 채택된 후보) 유튜브를 뺀 '뉴스감성+검색'
  2축 변형을 별도 파일에 병행 채점:
  `python references/scripts/attention_pilot_shadow_ns2.py score --date <score_target> --prices <prices csv>`
  → `attention_shadow_ns2_results.csv`에 ns2의 top3_hit·rank-IC·픽5바스켓수익·시장초과 append.
  기존 shadow/v2 파일 무손상. **20영업일(≈2026-08-20경) 누적 후 base 대비 rank-IC·바스켓수익·시장초과로
  판정(G_ns2)**; 우위 입증 시에만 analysis-method 정식 교체 검토.
- **[INTER vs KODEX200 일일 트래커]** (2026-07-23 사용자 요청) shadow 채점 직후, INTER(순수 관심·감성
  조건화) 상위 5섹터 픽의 KODEX200 대비 초과수익을 한 줄씩 누적:
  `python3 references/scripts/inter_vs_kodex_tracker.py`
  → `references/inter_vs_kodex_tracker.csv`에 date별 pick5수익·KODEX200수익·초과수익 append(멱등: 이미
  기록된 date 건너뜀, 데이터는 키움 일봉 자체 조회라 prices 인자 불필요). 개념검증(9일)에서 INTER가
  섹터평균 대비 +0.13%p·KODEX200 대비 +0.42%p(4/9 승)로 나왔으나 표본이 작아, **20영업일(≈2026-08-20경)
  누적 후 KODEX200 대비 유의 초과일 때만 루프 ETF 선정에 섹터 오버레이로 편입 검토**. 근거·설계는
  `references/combo_concept_note.md` 참조. 가격(mom20) 결합은 개념검증에서 열위 확인 → 미채택.

## Phase 2 — 오늘 관심 신호 수집 + 감성분류 (모델: Sonnet 5)
15테마(`references/attention_pilot_themes.csv`) 각각, 윈도 전일16:00~금일09:00:
- **news**: 네이버 `search_news`(sort=date) 테마 키워드 기사 중 윈도 내 발행 건수. **[B1 수정]**
  `display`를 100까지 올려 **윈도 내 실제 발행 전량**을 세고, 30/60에서 잘렸으면(마지막 페이지가
  꽉 참) `news_capped=1`을 기록한다. 과거 raw는 news_total이 30 근처에서 포화(15중 13이 30)해 뉴스
  '양' 변별력이 죽어 있었다 — 실제 총량을 담아 순감성 분모 압축을 푼다. 제목·요약을 매수/매도/중립
  3분류 → `news_total,news_buy,news_sell,news_neutral`(+선택 `news_capped`).
- **[B4 감성 검수용]** 분류한 기사 제목·판정을 `references/news_audit_<YYYYMMDD>.csv`
  (`theme,title,label`)로 함께 저장한다. 주 1회 무작위 20건을 수기 재검토해 오분류율을 기록
  (감성축 신뢰도 점검). raw 카운트만으로는 소급 검수가 불가하므로 이 저장은 전방(going-forward)으로만.
- **search**: `datalab_search` 테마 키워드 최신 검색비율 ÷ 직전 5일 평균(모멘텀). 감성분류 없음.
- **youtube**: 대표 50채널(`youtube_channels_config.py`) 한정. `fetch_youtube_signals_final.py`로
  윈도 내 영상만 남기고 제목을 매수/매도/중립 3분류 → `yt_total,yt_buy,yt_sell,yt_neutral`.
  **[B2 주의]** yt/yt20 수집이 **실패**한 날(예: 채널 수집 오류)과 **진짜 0**을 구분하라 — 실패면
  해당 셀을 빈값으로 비워 두고(0으로 채우지 말 것) shadow의 liveness 게이트가 모달리티를 자동 제외한다.
- 15행 raw CSV 저장: `references/raw_<YYYYMMDD>.csv`
  (`theme,news_total,news_buy,news_sell,news_neutral,search,yt_total,yt_buy,yt_sell,yt_neutral`;
  선택 컬럼 `news_capped`, yt20_* 허용 — v2/shadow 모두 컬럼명 기반이라 추가 컬럼 무해).

## Phase 3 — 오늘 픽 기록 (모델: Haiku 4.5)
- 실행: `python references/scripts/attention_pilot_v2.py record --date <record_target> --raw references/raw_<YYYYMMDD>.csv`
- composite_v2 = z(sent_news) + z(search_mom) + z(yt_net) 상위 5테마 → 대표 ETF를
  `attention_pilot_v2_picks.csv`에 append.
- **[shadow A/B 병행 기록]** v2 기록 직후 같은 raw로 shadow도 기록(15섹터 전량·4변형):
  `python references/scripts/attention_pilot_shadow.py record --date <record_target> --raw references/raw_<YYYYMMDD>.csv`
  → `attention_shadow_picks.csv`에 base/clean/contra/inter 컴포짓·랭크 append.
- **[ns2 전방검증 병행 기록]** 유튜브 제외 '뉴스감성+검색' 2축:
  `python references/scripts/attention_pilot_shadow_ns2.py record --date <record_target> --raw references/raw_<YYYYMMDD>.csv`
  → `attention_shadow_ns2_picks.csv`에 comp_ns2=z(sent)+z(search) 컴포짓·랭크 append(멱등: 같은 date 재기록 안 함).

## Phase 4 — 누적 현황 + 원인/판정 분석 (모델: Sonnet 5)
- 실행: `python references/scripts/attention_pilot_v2.py status`
- Phase 1 채점 결과(top3_hits·success)를 그날 실제 상위3 섹터와 대조해 적중/미달 원인을 1~2문단으로
  정리(무작위 기대 top3 3/3 ≈ 2.2%, 보조지표 슬롯 적중수 추적). 룩어헤드·데이터 병목 여부 명시.

## Phase 5 — 리포트(docx) 생성·공유 (모델: Sonnet 5) · **필수 종료 단계**
- 실행: `node references/scripts/gen_attention_report_v2.js <YYYYMMDD>`
  → `관심모멘텀_파일럿_v2_YYYY-MM-DD.docx` 생성(loop 폴더).
- 생성 파일을 `present_files`로 사용자에게 공유해야 그날 실행이 "완료"된 것으로 본다(docx 생략 금지).

---

## 수동 실행 트리거
사용자가 "관심 모멘텀 파일럿 (멀티모델) 실행/돌려줘"라고 하면 이 런북의 Phase 0부터 순서대로 지휘한다.
Phase 0에서 조기종료 조건이면 사유만 보고하고 종료. 정상 실행이면 Phase 1~5를 모두 마치고 docx 공유로
끝낸다.


---

## [2026-07-26 개정] Phase 2 신호 수집 절차 — v2.3 소스 개편 반영

`attention_pilot.md` "v2.3 — 정보 소스 개편" 절이 정본이다. Phase 2 실행 시 아래로 대체한다.

1. **유튜브 수집 단계 삭제.** `fetch_youtube_signals*.py`·`_yt_fetch_*_parallel.py`·yt20 상세 수집을
   호출하지 않는다. raw CSV의 yt 관련 열은 하위호환을 위해 남기되 전부 공란(또는 0)으로 기록하고
   composite 산식에서 제외한다. → Phase 2 소요시간이 가장 크게 줄어드는 변경이다.
2. **데이터랩 검색**(NaverSearch datalab) — 기존과 동일하게 수집. **이 신호가 랭킹 축이다.**
3. **뉴스** — 테마명 단독 쿼리 대신 **이벤트 키워드 쿼리 5종**(`공급계약`·`수주`·`정부 지원`·`증설`·
   `규제`)을 테마별로 수집한다. 감성은 **악재 배제필터(z < -0.15)** 용도로만 산출하고 랭킹에 더하지 않는다.
4. **DART 공시(주 1회, 매주 첫 거래일만)** — opendart MCP `search_disclosures`로
   `references/attention_dart_watchlist.csv`의 45종목을 최근 7일 창으로 스캔해 테마별
   `dart_event` 점수를 산출, 5거래일간 캐리한다. **초기에는 기록 전용(랭킹 미반영).**
5. **픽 산출** — 조합8 SEARCH-LED 규칙으로 shadow 기록:
   `python3 references/scripts/combo_shadow_tracker.py` (멱등 누적, 인자 없으면 전체 스캔).
6. **채점 지표** — 1차: 코스피 지수(^KS11) 대비 초과수익, 병기: KODEX200 대비. 기존 top3 적중·
   rank-IC는 보조로 계속 기록한다.

> 유의: 조합8은 **shadow 전용**이다. 20영업일 누적·판정 전까지 데일리 브리핑의 단기 ETF 추천
> 로직(mom20+RuleH 확정방법)은 변경하지 않는다.
