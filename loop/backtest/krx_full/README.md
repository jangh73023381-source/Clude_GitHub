# 생존편의 없는 개별주 일별 패널 (2026-10-22 구축)
- 출처: KRX Open API `sto/stk_bydd_trd`·`sto/ksq_bydd_trd` — 그날 상장된 전 종목 스냅샷(이후 상장폐지·합병 종목 포함). 수집 `collect.py`(멱등, done.txt), 변환 `build.py`.
- 범위: 2012-01-02 ~ 2026-10-21 · 3,635거래일 · 3,501종목(중도 소멸 739) · 일 1,907~2,789종목.
- 파일: `YYYY.csv`(원본) · `P_<col>.npy`(거래일×종목, float32: chg_pct·close·open·high·low·value·mktcap·shares) · `dates.npy` · `codes.npy` · `codes_meta.csv`(이름·시장·첫/마지막 거래일).
- **수익률은 `P_chg_pct`(KRX 등락률, 기준가 대비 = 분할·증자 조정)를 쓴다. `P_close` 는 비수정 종가**(종가로 만든 수익률과 5%p 이상 다른 셀 3,329개 = 기업행위일).
- 검증: 네이버 수정주가 패널(sjh, 2019~)과 일별 수익률 478만 셀 대조 — 99.48% 가 |차|<0.05%p, 중앙 0.0025%p.
- KRX 는 D 일자를 D+1 장중 공개 → 연장은 `python3 collect.py <시작> <끝> 10` 후 `build.py`(P_*.npy 는 지우고 재생성, 셸 180초 제한으로 여러 번).
