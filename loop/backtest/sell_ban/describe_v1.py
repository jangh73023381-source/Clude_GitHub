#!/usr/bin/env python3
"""V1 목록 종목을 '그래도 샀다면' 20거래일 성과(설명용) · 목록 비중 구간별 (조회 전용)."""
import json
import numpy as np, pandas as pd
import engine as E, signals as SG
from list_level import ban_state
d = E.load(); I = E.indicators(d); C = I['C']; M, N = C.shape
st = np.nan_to_num((I['MA5'] < I['MA20']) & (I['MA20'] < I['MA60']), nan=0).astype(bool)
prev = np.zeros_like(st); prev[:, 1:] = st[:, :-1]
B = ban_state(SG.cross(st), 20) & prev
R = E.sh(C, -20) / C - 1                     # T 종가 매수 → T+20 종가
mu = np.nanmean(R, axis=0); X = R - mu
ok = ~np.isnan(X)
share = (B & ok).sum(axis=0) / np.maximum(ok.sum(axis=0), 1)
bucket = np.where(share <= 0.054, '소(≤5.4%)', np.where(share <= 0.172, '중(5.4~17.2%)', '대(>17.2%)'))
out = {}
def desc(mask, lab):
    x = X[mask] * 100; r = R[mask] * 100
    out[lab] = dict(n=int(mask.sum()), excess=round(float(x.mean()), 2), under=round(float((x < 0).mean() * 100), 1),
                    raw=round(float(r.mean()), 2), loss=round(float((r < 0).mean() * 100), 1))
desc(B & ok, '금지 목록 전체')
desc(~B & ok, '목록 밖 종목')
for b in ['소(≤5.4%)', '중(5.4~17.2%)', '대(>17.2%)']:
    desc(B & ok & (bucket == b)[None, :], f'금지 목록 · 목록비중 {b}')
    desc(~B & ok & (bucket == b)[None, :], f'목록 밖 · 목록비중 {b}')
days = pd.Series(bucket[ok.any(axis=0)]).value_counts().to_dict()
out['days_by_bucket'] = days
for k, v in out.items():
    print(k, v)
json.dump(out, open('describe_v1.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
