#!/usr/bin/env python3
"""3차 — 목록(list) 단위 검정 + R3 정의 교체 (조회 전용, 2026-09-11).
목록: 브리핑일 T 아침에 '최근 H 거래일 안(D ∈ [T-H, T-1])에 신호가 난 종목'을 매수 금지로 싣는다.
목록 성과: 금지 종목의 T 종가→T+1 종가 수익 − 같은 날 유니버스 평균(일별 초과). 연속 일별 계열이라
NW(lag=H) t 와 R5(유리한 상위 k일 제거)를 그대로 적용할 수 있다.
"""
import os, json
import numpy as np, pandas as pd
import engine as E, signals as SG
d = E.load(); I = E.indicators(d); C = I['C']; M, N = C.shape; dates = d['dates']
S = SG.build(I)
H = 20
R1 = E.sh(C, -1) / C - 1                      # T 종가 → T+1 종가
mu = np.nanmean(R1, axis=0); X1 = R1 - mu[None, :]
validT = ~np.isnan(X1)


def ban_state(sig, h=H):
    """T 아침 목록 = D∈[T-h, T-1] 신호. (T 당일 신호는 T 종가 확정이므로 T+1 목록부터)"""
    s = pd.DataFrame(sig.T.astype(float)).rolling(h, min_periods=1).max().shift(1).fillna(0).values.T > 0
    return s


def list_stats(sig, h=H, label=''):
    B = ban_state(sig, h) & validT
    cnt = B.sum(axis=0)
    e = np.where(cnt > 0, np.where(B, X1, 0).sum(axis=0) / np.maximum(cnt, 1), np.nan)
    days = ~np.isnan(e); y = e[days] * 100
    srt = np.sort(y)
    n = len(y); thirds = np.array_split(y, 3)
    o = dict(label=label, days=int(n), avg_list=float(cnt[days].mean()), med_list=float(np.median(cnt[days])),
             share=float(cnt[days].mean() / validT[:, days].sum(axis=0).mean() * 100),
             mean_bp=float(y.mean() * 100), med_bp=float(np.median(y) * 100), win=float((y < 0).mean() * 100),
             t=float(E.nw_t(y, h)), ann=float(y.mean() * 250),
             folds_bp=[float(z.mean() * 100) for z in thirds],
             r5_bp={k: float(srt[k:].mean() * 100) for k in (1, 3, 5, 10, 20)},
             top3_share=float(srt[:3].sum() / y.sum() * 100) if y.sum() < 0 else None)
    return o


if __name__ == '__main__':
    out = {}
    for name in ['F14 역배열 진입', 'F3c 데드크로스 20/60', 'F4b MA60 이탈+MA60 하락', 'F12 mom20 하위 10% 진입']:
        out[name] = list_stats(S[name], H, name)
    # 금지 기간 민감도(F14)
    for h in (10, 15, 25, 30):
        out[f'F14 H={h}'] = list_stats(S['F14 역배열 진입'], h, f'F14 H={h}')

    # R3 정의 교체 ① EMA ② 주봉(주말 종가 기준 2·4·12주 이평, 금지 4주=20거래일)
    def ema(x, w):
        return pd.DataFrame(x.T).ewm(span=w, adjust=False, min_periods=w).mean().values.T
    e5, e20, e60 = ema(C, 5), ema(C, 20), ema(C, 60)
    sig_ema = np.nan_to_num(SG.cross((e5 < e20) & (e20 < e60)), nan=0).astype(bool)
    wk = pd.to_datetime(pd.Series(dates.astype(str))).dt.to_period('W').values
    last = np.r_[wk[1:] != wk[:-1], True]           # 주의 마지막 거래일
    Cw = C[:, last]
    mw = lambda w: pd.DataFrame(Cw.T).rolling(w, min_periods=w).mean().values.T
    sw = np.nan_to_num(SG.cross((mw(2) < mw(4)) & (mw(4) < mw(12))), nan=0).astype(bool)
    sig_wk = np.zeros_like(C, dtype=bool); sig_wk[:, np.where(last)[0]] = sw
    out['R3 EMA 5/20/60'] = list_stats(sig_ema, H, 'R3 EMA 5/20/60')
    out['R3 주봉 2/4/12주'] = list_stats(sig_wk, H, 'R3 주봉 2/4/12주')
    # 이벤트 기준도 함께
    R, X = E.fwd(C, H)
    for k, sg in [('F14', S['F14 역배열 진입']), ('R3 EMA', sig_ema), ('R3 주봉', sig_wk)]:
        st = E.stats(sg, X, H, N=N)
        out[f'event {k}'] = {kk: (float(v) * 100 if kk in ('mean', 'med', 'f1', 'f2', 'f3', 'r5_3', 'dmean') else float(v))
                             for kk, v in st.items() if kk in ('n', 'mean', 'neg', 't', 'f1', 'f2', 'f3', 'r5_3')}
    for k, v in out.items():
        print(k, json.dumps(v, ensure_ascii=False, default=float))
    json.dump(out, open(os.path.join(E.HERE, 'list_level.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
