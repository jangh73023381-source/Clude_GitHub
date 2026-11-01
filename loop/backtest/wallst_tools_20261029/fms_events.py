"""BofA FMS 현금 규칙 — 보도로 확인된 신호만(원자료는 유료). 발표일 다음 한국 거래일 종가 진입 → 20·60거래일 KODEX200 수익. 일화 수준(표본 8건)."""
import pandas as pd, numpy as np
Y = pd.read_csv('raw/y_069500.KS.csv', dtype={'date': str}); Y.index = pd.to_datetime(Y.date); c = Y.close[(Y.close > 0)]
EV = [('2020-12-15', '매도', '현금 4.0% (sell the vaccine)'), ('2021-02-17', '매도', '현금 규칙 매도'), ('2022-09-13', '매수', '현금 6.1%'),
      ('2024-12-17', '매도', '현금 3.9%'), ('2025-02-18', '매도', '현금 3.5%'), ('2025-12-16', '매도', '현금 3.3% 사상 최저'), ('2026-07-14', '매도', '현금 3.6%'), ('2026-08-18', '매도', '현금 3.5%')]
r20all = (c.shift(-20) / c - 1).dropna(); r60all = (c.shift(-60) / c - 1).dropna()
rows = []
for d, kind, note in EV:
    i = c.index.searchsorted(pd.Timestamp(d) + pd.Timedelta(days=1)); t = c.index[i]
    g = lambda n: (c.iloc[i + n] / c.iloc[i] - 1) * 100 if i + n < len(c) else np.nan
    rows.append((d, kind, note, str(t.date()), g(20), g(60)))
o = pd.DataFrame(rows, columns=['발표', '신호', '내용', '진입일', '20일%', '60일%']); print(o.round(2).to_string(index=False))
s = o[o.신호 == '매도']; print('매도 신호 평균 20일', round(s['20일%'].mean(), 2), '60일', round(s['60일%'].mean(), 2), '| 무조건 평균 20일', round(r20all[r20all.index >= '2019-01-01'].mean() * 100, 2), '60일', round(r60all[r60all.index >= '2019-01-01'].mean() * 100, 2))
o.to_csv('result_fms_events.csv', index=False)
