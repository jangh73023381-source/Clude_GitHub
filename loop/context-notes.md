<!-- 단기 ETF 추천 루프 개선을 위한 근거 기반 리서치 결정·근거 기록 (deep-research 산출) -->

# Context Notes — 근거 기반 신호 리서치

작성일: 2026-07-17
출처: deep-research 워크플로우 (검색 5각도 → 16소스 → 75주장 추출 → 3표 적대적 검증)
검증 상태: 신호 4건 패널 확정(confirmed), 나머지는 월 지출 한도로 검증 미완(도메인 지식으로 보증). 한도 상향 후 재검증 가능.

이 문서는 루프 선정 로직(analysis-method) 개선의 **근거와 결정 이유**를 남기는 노트다. 방법 정본을 대체하지 않으며, 다음 회차가 신호를 설계할 때 참고한다.

---

## 1. 패널 검증으로 확정된 신호 (3표 적대적 투표 통과)

핵심 방향 하나로 수렴한다 — **한국 단기는 "많이 오른 것 추종(모멘텀)"보다 "비펀더멘털 과잉반응의 반전"이 더 근거 있다.**

### C1. 줄다리기(tug of war) 강도가 횡단면 수익을 예측 — 투표 3-0
- 밤사이(overnight) 상승 → 장중(daytime) 반전이 한 달 내 반복되는 강도가 셀수록 이후 수익이 높다.
- 인용: "a more intense daily tug of war predicts higher future returns in the cross section"
- 출처: JFE, https://www.sciencedirect.com/science/article/abs/pii/S0304405X21004116
- **함의**: 종가-종가 단일 수익률로 뭉치지 말고 오버나이트/장중을 분해해 신호를 만든다.

### C2. 한국 시장 오버나이트-장중은 음(-)의 비선형 관계 — 투표 2-1
- 밤사이 과잉반응 → 장중 반전. 단 뉴스가 좋으면 연속, 나쁘면 반전으로 부호가 뒤집힌다(비선형).
- 인용: "A negative relationship exists between overnight and daytime returns on the Korean equity market... positively (negatively) and nonlinearly associated... when the overnight news is relatively good (bad)."
- 출처: https://www.sciencedirect.com/science/article/abs/pii/S1544612323001526
- **주의**: 1명이 반대표. "항상 반전"으로 단정하지 말고 뉴스 조건부로 다룬다.

### C3. 오전=정보 주도(연속), 오후=유동성 주도(반전) — 투표 3-0
- 인용: "trades in the morning are mostly information driven and trades in the afternoon are mostly liquidity driven"
- 출처: https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/f360fb42-445c-433b-8d78-0059bcf604ca.pdf
- **함의**: 종가 근처(오후) 급등은 유동성 주도라 익일 반전 위험. 추천을 종가에 확정한다면 감점 요인으로 둔다.

### C4. 단기 반전은 "비펀더멘털" 가격변동에만 유효 — 투표 2-0 (이번 리서치의 최대 실무 정제)
- 단기 반전 수익은 4개 요소로 분해되는데, 뉴스·펀더멘털로 설명 안 되는 잔차(residual) 성분만 유의미하게 양(+)이다.
- 인용: "Only the residual component, which isolates reaction to recent 'nonfundamental' price changes, is significant and positive"
- 출처: NY Fed Staff Report 513, https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr513.pdf
- **함의**: 반전 신호는 "그냥 급등한 것"이 아니라 실적·공시로 설명 안 되는 급등에만 건다. 급등이 뉴스 기인이면 반전 베팅에서 제외.

---

## 2. 검증 미완이나 도메인 지식으로 보증되는 것

패널 투표는 못 끝냈지만 확립된 문헌·공식 문서 기반이라 결론이 바뀔 가능성은 낮다.

### 레버리지/인버스 ETF — 변동성 끌림(volatility decay)
- 일간 배수 상품이라 횡보·반전 잦은 장에서 다일 보유 시 구조적 손실. 예시(KCMI): +/-5% 5일 상승 후 5일 하락이면 2배 레버리지 -4.90%, 인버스 -1.24%(단리 0%인데도 손실).
- 갭(손실폭)은 변동성·반전빈도·음의 자기상관이 클수록 커진다(KCI 실증).
- 출처: KCMI https://www.kcmi.re.kr/kcmifile/oldfiledata/weekly_6_10_923.pdf , KCI https://journal.kci.go.kr/capm/archive/articlePdf?artiId=ART002343619
- **함의**: 원시 상승률 순위는 레버리지 ETF에 유리하게 왜곡된다. **변동성 조정 수익률로 비교**하거나 레버리지 버킷을 분리한다.

### 수급 — 기관 추종 유효 / 외국인 추종 역효과 (반직관적)
- 2004-2010 일간 데이터에서 국내 기관 순매수 추종은 KOSPI·베타조정 요구수익 초과, 외국인 추종은 둘 다 미달.
- 출처: KCI, https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001728636
- **주의**: 표본이 2004-2010으로 오래됨. 방향성(투자주체별 부호 차이)만 참고하고 최신 데이터로 재확인한다. (loop에 이미 institution_trend_panel.csv / foreign_trend_panel.csv 수집 파이프라인 있음 — 재검증에 활용 가능.)

### 데이터 파이프라인 — pykrx 무료 수집 (보조 수단)
- 괴리율: get_etf_price_deviation / OHLCV+NAV: get_etf_ohlcv_by_date, get_etf_ohlcv_by_ticker / 수급: get_market_trading_value_by_investor.
- 출처: https://github.com/sharebook-kr/pykrx
- **주의**: 함수 시그니처는 버전마다 다름 — 구현 전 dir()로 확인. 본 프로젝트는 키움 REST API가 1순위(CLAUDE.md)이므로 pykrx는 키움으로 안 되는 항목의 보조로만.

---

## 3. 루프 방법에 반영할 실행안

1. **오버나이트/장중 분해 신호 도입** (C1, C2) — 종가-종가 단일 모멘텀 축소.
2. **반전 신호는 비펀더멘털 급등에만** (C4) — 실적·공시 기인 급등은 반전 후보에서 제외.
3. **오후 급등 종목 감점** (C3) — 유동성 주도라 익일 반전 위험.
4. **레버리지 ETF는 변동성 조정 후 비교** — 순위 왜곡 제거.
5. **수급 신호는 투자주체별 부호 구분** — 기관/외국인을 한 덩어리로 합치지 않는다.

---

## 4. 【중요】 루프 구조 자체의 과최적화 위험 — 설계 긴장

리서치에서 가장 강하게 뒷받침된 경고(Bailey & Lopez de Prado 계열, 검증 미완이나 계량금융 확립 사실).

- N번 시도하면 실력이 0이어도 최고 성과가 부풀려진다. 5년 일간 데이터로 45개 변형만 시도해도 최고가 우연히 샤프>=1일 확률이 절반을 넘는다.
- 홀드아웃·교차검증도 **반복 적용하면** 무력화된다(약 20회면 거짓양성이 기본). **익일 채점 자체가 반복되는 홀드아웃**이라, 익일 통과만으로는 검증이 안 된다.
- 메모리(평균회귀) 있는 실제 시계열에서 과최적화는 0이 아니라 음(-)의 미래 성과를 낸다.
- "백테스트의 올바른 용도는 나쁜 모델을 버리는 것이지 개선하는 게 아니다."
- 출처: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 , https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf , https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html

**본 루프와의 긴장**: CLAUDE.md [2026-07-08] 규칙은 5/5 적중까지 최대 5회 반복 개선을 강제한다. 이는 목표 달성에는 좋지만, 통계적으로는 다중검정·과최적화를 구조적으로 유발한다. 즉 "5회 반복해 상위10% 5/5를 맞춘 방법"이 진짜 실력인지 우연인지 구분이 안 될 수 있다.

**권장 보정** (규칙을 뒤집지 말고 보강):
- **누적 시행횟수(N) 로깅** — loop-log.md에 회차별 시도한 규칙 변형 수를 누적 기록. 성과를 N으로 할인해서 판단(Deflated Sharpe 사고방식).
- **워크포워드 채점** — 규칙을 고친 날 이후의 미래 구간에서만 성과를 인정. 규칙을 튜닝한 과거 구간의 적중률은 신뢰하지 않는다.
- **거래비용·슬리피지·괴리율 차감** — 익일 수익에서 빼야 "종이 위 적중"과 "실현 적중"의 괴리가 드러난다.
- **생존편향 점검** — 상장폐지·합병 ETF 제외한 현재 목록만 백테스트하면 성과 과대평가.

---

## 5. 재검증 방법 (한도 상향 후)

- 월 지출 한도 상향 후(claude.ai/settings/usage) deep-research 워크플로우를 캐시에서 이어받아 검증만 재실행하면 §2·§4 주장들도 3표 투표로 확정/반박 판정 가능.
- 이어받기: Workflow({ scriptPath: "...deep-research-wf_b9c9014b-1d3.js", resumeFromRunId: "wf_b9c9014b-1d3", args: "<동일 질문>" }) — 검색·수집은 캐시 재사용, 검증만 라이브.

---

## 6. 관심모멘텀 파일럿 진단 (2026-07-17)

실행 정본: `references/scripts/collect_attention.py` + `dual_score.py` **트랙 B = SEARCH-LED**(검색 랭킹 + mom20 하방필터 + 악재감성 배제; 동결 파라미터 MOM_CUT=10 / SENT_CUT=−0.15 / NPICK=5). ~~v2.3 composite = z(sent_news)+z(search)+z(yt_net)+z(yt20_net)~~ 는 **v2.4(2026-07-27) 유튜브 전면 폐지로 폐기**(rank-IC −0.128, yt20 15테마 중 절반 결측·7/24 미수집 → 결측이 0으로 둔갑). 아래 진단 (c)가 그 근거다. 유튜브 항이 포함된 7/09~7/24 표본은 이후 표본과 합산하지 않는다. 채점 = 15섹터 중 당일수익 TOP3가 픽5에 전부 포함 시 SUCCESS. 전방 5일(7/9~7/15) 성공 1일(7/15). **개선 체크리스트 정본: `관심모멘텀_파일럿_개선_checklist.md`.**

**진단 요지**:
- **수집**: (a) 뉴스 40 상한 → 순감성 분모 압축. (b) 소표본 테마(news_total<5)의 감성비율 z가 노이즈(7/14 태양광 n≈2). (c) 유튜브 3일 연속 0(수집실패를 0으로 취급, log 1063). (d) 감성 분류 정확도 미검증(중립 버킷 최대).
- **관심 4종은 서로 겹치는 지연 모멘텀** — 관심은 대개 "이미 오른 것"을 뒤따르므로 사실상 mom20의 변형. 정작 익일 최대 드라이버인 오버나이트/US(§1 C1·C2)는 입력에 없음.
- **방법 방향 의심**: 본인 7/9 관찰(매수감성 상위 ↔ 당일수익 역상관) + §1 C4(비펀더멘털 과잉반응 반전)가 **컨트래리언/조건부**를 지지. 현행은 매수감성·관심에 +가중(추종).
- **덧셈 ≠ 조건부**: §1 C2는 비선형(뉴스 호재→연속, 악재→반전). 현행은 4z 단순합. 수정은 데이터 추가가 아니라 **조합을 `search_z·sign(sent_news)` 상호작용으로** 바꾸는 것(US 없이 가능).
- **채점**: 연속값 top3_hits(0~3) 이미 있음 → 이진 대신 연속+rank-IC로 판정, 무작위·mom20·컨트래리언 병렬 베이스라인 병기 필요. **n=5는 노이즈 구간**(본인 설계 20일 후 판정). 지금 세게 튜닝하면 §4 과최적화 함정.

**결정**: 방법 즉시 교체 안 함. shadow 변형(base/contra/inter) 병렬 append로 20일 누적 → 베이스라인 대비·N할인 후 판정. 근거 보강용 focused deep-research 실행 중(run wf_14b0a40e-8c7, 질문: 관심/검색이 익일 섹터수익을 예측하는가·부호·조건·독립성).

### 6-1. deep-research 결과 (run wf_14b0a40e-8c7, 2026-07-17, 2차 재개까지 66/102 완료 — 3차 재개 진행 중)
25개 주장 투표: **확정 7건·반박 6건·미확정 12건**(세션 한도 반복, 23:10 KST 리셋 후 3차 재개함). synthesize 미완.

**확정(투표 통과)**:
1. [3-0] 한국 고관심 종목 = 유의한 음(−)의 모멘텀(컨트래리언). 출처 sciencedirect S0275531921000258.
2. [3-0] KOSDAQ 검색량 급증 → 당주·익주 +, 2~3주뒤 반전(−). 출처 researchgate 305671289.
3. [2-1] 한국 오버나이트→장중 수익 **전반적으로 음(−)의 관계**(반전이 기본값). 출처 S1544612323001526.
4. **[3-0] 오버나이트→장중 관계는 뉴스 질에 조건부** — 좋은 뉴스=연속(+), 나쁜 뉴스=반전(−). "Good overnight news: positively associated... Bad overnight news: negatively associated". 출처 동일(S1544612323001526). **→ 이게 정확히 shadow `inter` 변형(attention×sign(sent_news))의 설계 근거를 문헌으로 확정함.**
5. [2-1] 반전은 **장중(intraday) 내에서 소멸** — 시가 프리미엄이 그날 장중에 되돌아감(다음날까지 안 감). 출처 SSRN 1625495.
6. [2-1] 오버나이트 수익은 firm-specific 리테일 관심의 프록시(관심유발 이벤트→다음 시가 근처 수요집중→시가 프리미엄→장중 반전). 출처 UCLA Anderson JFQA2018.
7. **[2-1] attention(오버나이트) 신호는 표준 가격모멘텀과 구별됨** — 모멘텀으로 파티션 통제해도 효과 잔존(1.27~1.87pp 유의). **→ "관심=지연된 가격모멘텀일 뿐"이라는 우려는 기각. 관심 자체가 고유 정보 보유.**

**반박(내 초기 가설 중 틀린 것)**:
- "관심 효과는 항상 순수 컨트래리언(모멘텀 전혀 없음)" — **0-3 반박**.
- "관심 신호는 주간 모멘텀으로 w+2~w+4까지 지속" — **1-2 반박**(그렇게 오래 안 감).
- "장기(12개월) 가면 부호가 반전" — **1-2 반박**(그 정도로 느리게 반전하는 게 아님).
- "관심은 평균적으론 +, 나쁜뉴스일 때만 −로 flip" — **0-3 반박**(④의 조건부 구조와는 다른 프레이밍 — 반전이 '평균 기준선+예외'가 아니라 애초에 뉴스질 조건부 자체가 구조).
- 이 외 한국 PEAD 가속·검색량 단순 컨트래리언 등 2건 추가 반박.

**함의(shadow 설계 재확인)**: `contra`(무조건 부호반전)는 **문헌 근거 약함** — "항상 반전"·"몇 주 지속 모멘텀" 둘 다 반박됨. `inter`(뉴스감성 방향 조건화)가 확정④·⑦과 정확히 정합하는 **정답 방향**. 반전은 장중 내 소멸(⑤)하므로 **다음날 아침 픽 스킴 자체(종가~개장전 신호→익일 채점)가 이 메커니즘의 호라이즌과 잘 맞음**(장중 반전이 아니라 익일 채점이라 다른 메커니즘일 수 있음 — 유니버스가 개별종목이 아니라 섹터ETF라는 것도 차이, 100% 동일시 금지).
- 미확정 12건(중국 실증·attention이 반전을 증폭하는지 등) 확정/반박 대기 — 3차 재개 진행 중.

### 6-2. shadow A/B 6일 소급 결과 (n=6, 판정 아님)
base(현행) mean rank-IC=−0.101(6일 중 4일 IC<0) / clean −0.092(B2+B3 적용해도 거의 동일) / contra +0.101 / inter −0.002. top3_hit: base 1.17·clean 1.17·contra 1.00·inter 1.33·random 1.00.
- **현행 관심추종 방향의 IC가 음** → deep-research 확정①과 정합(고관심=반전). 단 단순부호반전(contra)은 top3_hit=무작위와 동일(저관심주가 승자는 아님). inter가 승자포착 최고이나 IC 평탄. **데이터 수리(clean)는 방향 문제를 못 고침** — 핵심은 노이즈가 아니라 부호/조합. **n=6 노이즈 구간, 20일 누적 후 판정.**
- 산출물: `references/scripts/attention_pilot_shadow.py`, `references/attention_shadow_picks.csv`, `references/attention_shadow_results.csv`. status로 누적 확인(전 변형 자동 표시).
- Track B(수집수리)·Track A6(매일 자동 축적, 런북+배치 연결) 완료. 세부는 `관심모멘텀_파일럿_개선_checklist.md`.

### 6-3. mom20 섹터 베이스라인 (n=5, 2026-07-17, `attention_pilot_mom20_baseline.py`)
15섹터 ETF 20거래일 모멘텀(panel_close 기준) → mean top3_hit=**0.80**(무작위 1.00보다 낮음), mean rank-IC=−0.053.
- **섹터 로테이션 단위에서는 mom20도 안 먹힘** — 종목단위 mom20(v1.9 baseline, analysis-method 정본)이 유효했던 것과 대비. 이 15섹터·일 단위 호라이즌 자체가 어떤 단순 베이스라인으로도 잘 안 잡히는 구간임을 시사(과최적화보다 "쉬운 정답이 없는 문제"일 가능성).
- **갭**: panel_close가 정적 스냅샷이라 daily job에 mom20 자동 연결 미완 — 롤링 갱신 방식 결정 필요(다음 세션).
