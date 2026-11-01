# amflow/ — 글로벌 자산운용사 '포지션' 축 검정 (2026-09-22, 3축 전부 기각)

판정 전문: `loop/글로벌운용사_포지션_활용검토_2026-09-22.md`
기각 기록: `analysis-method_rejected.md` 상단 "글로벌 자산운용사 '포지션' 3축"

## 스크립트
```
collect_etf_extend.py <시작> <끝> [예산초]   # krx_etf_panel.csv 기간 연장 (멱등·재개, rc=3이면 재실행)
flow_gates.py                                # ETF 설정/환매 → 익일 초과수익 + R2/R5/대조군
collect_dart_holders.py <시작> <끝> [예산초] # DART 지분공시 전수 (멱등, 월 단위, rc=3이면 재실행)
fetch_majorstock.py                          # 대상 corp_code 보유비율 증감 이력 (최근 2년만 제공)
dart_gates.py                                # 공시 이벤트 → 초과수익 + 방향별/연도fold/R5/지속형 대조군
```

## 산출 데이터
- `_dart_disc.csv` — 지분공시 전수 201,530건 (2019-04~2026-09, 90개월)
- `_dart_fx.csv` — 글로벌 운용사 대량보유 1,709건 · 310종
- `_majorstock.csv` — 보유비율 증감 이력 (2024-09~, API 제한)

## 주의
- **ETF 횡단면 검정은 `universe_filters.eligible` 적용이 선행이다.** 필터 전 Q5-Q1 +0.220%p(t=3.12)
  → 필터 후 +0.088%p. 효과의 60%가 레버리지·인버스에서 왔다.
- **KRX ETF API 필드명**: `ISU_CD`(코드) · `INVSTASST_NETASST_TOTAMT`(순자산) · `LIST_SHRS`(상장좌수).
  `ISU_SRT_CD`·`NETASST_TOTAMT` 는 **없는 필드**다 — 2026-09-22 이 오기로 빈 420,683행이 패널에
  유입되는 사고가 있었다. 필드 매핑은 `collect_krx_etf_idx_20260818.py` 가 정본이다.
- **이벤트 축에는 지속형 무작위 대조군이 필수다.** DART 축에서 같은 종목 무작위 날짜의 귀무 평균이
  **+0.542%**(0이 아니다)였고, 관측 +1.080%(t=3.15)가 그 90% 구간 안이었다.
- `majorstock.json` 은 최근 2년치만 준다. 7년 방향별 검정은 공시 원문(document.xml) 파싱이 필요하다.
