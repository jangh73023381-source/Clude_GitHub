#!/usr/bin/env python3
"""4차 — 실용성 보정 2변형(사전 선언) · 목록 크기 구간별 성과 (조회 전용, 2026-09-11).
동기: 2026-09-10 기준 목록이 102/187 종 — 8월 말 전반 조정으로 동시 발생했고 상당수는 이미 역배열이 해소됐다.
 V0 고정 20일(기준) / V1 역배열이 풀리면 조기 해제(20일 이내라도 T-1 종가 기준 MA5<MA20<MA60 불성립이면 목록 제외)
 V2 V1 + MA5<MA20 만 유지돼도 금지 유지(완화된 해제 조건)
"""
import json
import numpy as np, pandas as pd
import engine as E, signals as SG
from list_level import list_stats, ban_state, X1, validT, H
d = E.load(); I = E.indicators(d); C = I['C']; M, N = C.shape
S = SG.build(I); sig = S['F14 역배열 진입']
st = (I['MA5'] < I['MA20']) & (I['MA20'] < I['MA60'])
st1 = np.zeros_like(st); st1[:, 1:] = st[:, :-1]             # T-1 상태
half = (I['MA5'] < I['MA20']); half1 = np.zeros_like(half); half1[:, 1:] = half[:, :-1]


def stats_from_ban(B, label):
    B = B & validT; cnt = B.sum(axis=0)
    e = np.where(cnt > 0, np.where(B, X1, 0).sum(axis=0) / np.maximum(cnt, 1), np.nan)
    days = ~np.isnan(e); y = e[days] * 100; srt = np.sort(y); th = np.array_split(y, 3)
    return dict(label=label, avg_list=float(cnt[days].mean()), med_list=float(np.median(cnt[days])),
                p90_list=float(np.percentile(cnt[days], 90)), mean_bp=float(y.mean() * 100),
                t=float(E.nw_t(y, H)), win=float((y < 0).mean() * 100),
                folds_bp=[float(z.mean() * 100) for z in th], r5_3=float(srt[3:].mean() * 100),
                r5_20=float(srt[20:].mean() * 100), ann=float(y.mean() * 250)), cnt, e


B0 = ban_state(sig, H)
out = {}
for lab, B in [('V0 고정 20일', B0), ('V1 역배열 해소 시 해제', B0 & st1), ('V2 MA5<MA20 유지 시만', B0 & half1)]:
    o, cnt, e = stats_from_ban(B, lab)
    # 목록 크기(유니버스 대비 비중) 3구간별 일평균 초과
    share = cnt / np.maximum(validT.sum(axis=0), 1)
    ok = ~np.isnan(e)
    q = pd.qcut(share[ok], 3, labels=['소', '중', '대'])
    o['by_size_bp'] = {str(k): [round(float(v.mean() * 1e4), 2), int(len(v))] for k, v in pd.Series(e[ok]).groupby(q.codes)}
    o['size_cut'] = [float(x) for x in np.percentile(share[ok], [33.3, 66.7])]
    out[lab] = o
    print(json.dumps(o, ensure_ascii=False))
# 오늘(D=마지막 날) 다음 브리핑일 목록 크기 — V1/V2
lastB0 = pd.DataFrame(sig.T.astype(float)).rolling(H, min_periods=1).max().values.T[:, -1] > 0
print('today list V0', int(lastB0.sum()), 'V1', int((lastB0 & st[:, -1]).sum()), 'V2', int((lastB0 & half[:, -1]).sum()))
json.dump(out, open('refine.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
