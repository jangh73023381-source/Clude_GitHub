"""2026-10-27 유튜브 미검정 매매법 6종 — 자막(PC에서 수집)의 규칙을 일봉으로 재현. 개별주 dense 7.7년(비수정 종가).
비수정 가격 보정: 보유 구간에 |일간 수익|>31%(가격제한 초과 = 권리락·병합) 이 끼면 그 건 제외.
지표: 건별 수익 − 같은 날 유동 유니버스(종가≥1,000·20일 평균 거래대금≥10억) 같은 구간 평균(%), 신호일 평균 → NW t, 3분할, 앞/뒤(2023-06-30),
상위 5% 신호일 제거, 승률, 절대 평균. 단기 매매는 왕복 비용(세금·수수료 약 0.25%) 차감 후 절대 수익도 병기(참고).
Y1 주도주 양봉 종가베팅 · Y2 음봉 종가베팅 · Y3 BNF 이격도 · Y4 상한가 종가 매수 · Y5 래리 윌리엄스 변동성 돌파 · Y6 바닥권 거래량 10배 윗꼬리 장대양봉."""
import numpy as np, pandas as pd
from gh_stats import nw_se
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); O, H, L, C, V = (Z[k].astype(float) for k in 'OHLCV'); bench = Z['bench'].astype(float)
T, N = C.shape
VAL = C * V
cs = np.cumsum(np.nan_to_num(VAL), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
SPLIT = 20230630; COST = 0.25
D = lambda A: pd.DataFrame(A)
sh = lambda A, d: np.vstack([np.full((d, N), np.nan), A[:-d]])
fw = lambda A, d: np.vstack([A[d:], np.full((d, N), np.nan)])
with np.errstate(all='ignore'):
    r1 = C / sh(C, 1) - 1
    bad = np.abs(r1) > 0.31                                    # 비수정 이벤트
    badf = {h: D(bad.astype(float))[::-1].rolling(h, min_periods=1).max()[::-1].values > 0 for h in (1, 2, 5, 20, 60)}
    # 보유 구간 [t+1, t+h] 에 bad 가 있으면 제외
    badw = {h: fw(badf[h], 1) > 0 for h in badf}
    # 수익 정의 (%)
    R = {
        '익일시가': (fw(O, 1) / C - 1) * 100,
        '익일종가': (fw(C, 1) / C - 1) * 100,
        '2일종가': (fw(C, 2) / C - 1) * 100,
        '5일': (fw(C, 5) / C - 1) * 100,
        '20일': (fw(C, 20) / C - 1) * 100,
        '60일': (fw(C, 60) / C - 1) * 100,
    }
    HZ = {'익일시가': 1, '익일종가': 1, '2일종가': 2, '5일': 5, '20일': 20, '60일': 60}
    for k in R:
        R[k][badw[HZ[k]]] = np.nan
    UM = {k: np.nanmean(np.where(LIQ & np.isfinite(R[k]), R[k], np.nan), 1) for k in R}
rows = []


def event(name, sig, keys=('익일시가', '익일종가', '5일', '20일'), short=True):
    sig = sig & LIQ; sig[:260] = False
    for k in keys:
        F = R[k]; t, j = np.where(sig & np.isfinite(F))
        if len(t) < 100:
            rows.append(dict(전략=name, 보유=k, 건수=len(t))); continue
        ex = F[t, j] - UM[k][t]
        d = pd.DataFrame({'t': t, 'ex': ex, 'raw': F[t, j]}).groupby('t').mean().sort_index()
        x = d.ex.values; n = len(x); k3 = n // 3; srt = np.sort(x)[::-1]; lag = max(HZ[k] - 1, 0)
        tr, te = d[dates[d.index] <= SPLIT], d[dates[d.index] > SPLIT]
        o = dict(전략=name, 보유=k, 신호일=n, 건수=len(t), 종목_일=round(len(t) / n, 1), 초과=x.mean(), t=x.mean() / nw_se(x, lag),
                 fold='/'.join(f'{x[i*k3:(i+1)*k3].mean():.2f}' for i in range(3)), 앞=tr.ex.mean(), 뒤=te.ex.mean(),
                 뒤_t=te.ex.mean() / nw_se(te.ex.values, lag) if len(te) > 10 else np.nan, 상위5pct제거=srt[max(1, int(n * .05)):].mean(),
                 절대평균=F[t, j].mean(), 승률=(F[t, j] > 0).mean() * 100, 중앙=np.median(F[t, j]))
        if short and k in ('익일시가', '익일종가', '2일종가'):
            o['비용후절대'] = F[t, j].mean() - COST
        rows.append(o)


with np.errstate(all='ignore'):
    body = C - O; rng = H - L; upw = H - np.fmax(O, C)
    chg = r1 * 100
    hi20 = sh(D(H).rolling(20).max().values, 1)
    long_bull = (body > 0) & (body >= 0.6 * rng) & (chg >= 5)
    short_wick = upw <= 0.25 * rng
    big = VAL >= 3e10                                          # 거래대금 300억
    # ---- Y1 주도주 양봉 종가베팅
    y1 = big & long_bull & short_wick & (C > hi20)
    event('Y1 종가베팅(300억·장대양봉≥5%·윗꼬리짧음·20일고점돌파)', y1)
    event('Y1b 종가베팅 강도↑(상승≥10%)', y1 & (chg >= 10))
    vrank = D(VAL).rank(axis=1, ascending=False).values
    event('Y1c 종가베팅 거래대금 상위20 ∩ 상승≥5% ∩ 윗꼬리짧음', (vrank <= 20) & (chg >= 5) & short_wick)
    # ---- Y2 음봉 종가베팅: 최근 5일(오늘 제외) 안에 300억 장대양봉 기준봉, 오늘 음봉 · 거래량 < 기준봉 거래량 · 전일보다 감소 · 종가 ≥ MA5
    base = big & long_bull
    bvol = np.where(base, V, np.nan)
    last_bvol = D(bvol).ffill(limit=5).values; last_bvol = sh(last_bvol, 1)
    base5 = D(sh(base.astype(float), 1)).rolling(5, min_periods=1).max().values > 0
    ma5 = D(C).rolling(5).mean().values
    y2 = base5 & (C < O) & (V < last_bvol) & (V < sh(V, 1)) & (C >= ma5 * 0.97)
    event('Y2 음봉 종가베팅(5일내 300억 장대양봉 → 거래량 감소 음봉)', y2)
    ma120 = D(C).rolling(120).mean().values
    event('Y2b 음봉 종가베팅 + 120일선 근처(±5%)', y2 & (np.abs(C / ma120 - 1) <= .05))
    # ---- Y3 BNF 이격도 (25일 이평 대비)
    ma25 = D(C).rolling(25).mean().values; ema25 = D(C).ewm(span=25, adjust=False).mean().values
    gap = (C / ma25 - 1) * 100
    first = lambda m: m & ~sh(m, 1).astype(bool)
    for th in (20, 25, 30, 35):
        event(f'Y3 BNF 이격도 ≤ −{th}% (첫날)', first(gap <= -th), keys=('익일종가', '5일', '20일'))
    bigcap = D(VAL).rank(axis=1, ascending=False).values <= 200
    event('Y3b BNF 대형(거래대금 상위200) 이격 ≤ −20%', first(gap <= -20) & bigcap, keys=('익일종가', '5일', '20일'))
    dC = C - sh(C, 1); up = D(np.fmax(dC, 0)).ewm(alpha=1 / 14, adjust=False).mean().values; dn = D(np.fmax(-dC, 0)).ewm(alpha=1 / 14, adjust=False).mean().values
    rsi = 100 - 100 / (1 + up / dn)
    e12 = D(C).ewm(span=12, adjust=False).mean().values; e26 = D(C).ewm(span=26, adjust=False).mean().values
    macd = e12 - e26; sig9 = D(macd).ewm(span=9, adjust=False).mean().values; hist = macd - sig9
    gape = (C / ema25 - 1) * 100
    bnf2 = (D(((gape <= -20)).astype(float)).rolling(5, min_periods=1).max().values > 0) & (rsi < 30) & (hist > sh(hist, 1)) & (sh(hist, 1) <= sh(hist, 2))
    event('Y3c BNF 박한결판(EMA25 이격≤−20%·RSI<30·MACD 히스토그램 반등)', first(bnf2), keys=('익일종가', '5일', '20일'))
    # BNF 청산형: 이격 ≤ −20% 첫날 종가 매수 → 종가 ≥ MA25 회복 또는 20일 만기
    t_, j_ = np.where(first(gap <= -20) & LIQ); t_, j_ = t_[t_ > 260], j_[t_ > 260]
    trades = []
    for t, j in zip(t_, j_):
        e = None
        for u in range(t + 1, min(t + 21, T)):
            if bad[u, j] or not np.isfinite(C[u, j]): e = None; break
            e = u
            if C[u, j] >= ma25[u, j]: break
        if e is None: continue
        rr = (C[e, j] / C[t, j] - 1) * 100; uu = np.nanmean(np.where(LIQ[t], C[e] / C[t] - 1, np.nan)) * 100
        trades.append((t, rr, rr - uu, e - t))
    tr = pd.DataFrame(trades, columns=['t', 'r', 'ex', 'hold'])
    dd = tr.groupby('t').ex.mean(); x = dd.values
    rows.append(dict(전략='Y3d BNF 이격≤−20% → MA25 회복/20일 청산', 보유=f'평균 {tr.hold.mean():.1f}일', 신호일=len(x), 건수=len(tr), 초과=x.mean(),
                     t=x.mean() / nw_se(x, 10), 앞=dd[dates[dd.index] <= SPLIT].mean(), 뒤=dd[dates[dd.index] > SPLIT].mean(),
                     절대평균=tr.r.mean(), 승률=(tr.r > 0).mean() * 100, 중앙=tr.r.median()))
    # ---- Y4 상한가 종가 매수
    lu = (r1 >= 0.295) & (C == H)
    event('Y4 상한가(종가=고가·+29.5%↑) 종가 매수', lu, keys=('익일시가', '익일종가', '2일종가', '5일', '20일'))
    event('Y4b 상한가 + 거래대금 300억↑', lu & big, keys=('익일시가', '익일종가', '2일종가', '5일', '20일'))
    # D+1 시가 매수 → D+1 종가 (상한가 다음날 시가 매매 근사)
    with np.errstate(all='ignore'):
        oc = (fw(C, 1) / fw(O, 1) - 1) * 100; oc[badw[1]] = np.nan
        R['다음날시가→종가'] = oc; HZ['다음날시가→종가'] = 1
        UM['다음날시가→종가'] = np.nanmean(np.where(LIQ & np.isfinite(oc), oc, np.nan), 1)
    event('Y4c 상한가 다음날 시가 매수 → 종가 매도', lu, keys=('다음날시가→종가',))
    # ---- Y5 래리 윌리엄스 변동성 돌파: 진입가 = 시가 + k×(전일 고가−저가), 고가가 닿으면 진입, 다음날 시가 매도
    for k in (0.5, 0.3, 0.7):
        trig = O + k * sh(rng, 1); hit = (H >= trig) & (trig > O)
        with np.errstate(all='ignore'):
            vb = (fw(O, 1) / trig - 1) * 100; vb[~hit] = np.nan; vb[badw[1]] = np.nan
        key = f'VB{k}'; R[key] = vb; HZ[key] = 1
        base_on = (fw(O, 1) / O - 1) * 100; base_on[badw[1]] = np.nan
        UM[key] = np.nanmean(np.where(LIQ & np.isfinite(base_on), base_on, np.nan), 1)   # 기준: 같은 날 유동 종목 '시가→익일시가'
        event(f'Y5 변동성돌파 k={k} (진입가→익일 시가, 기준=유동 시가→익일시가)', hit.copy(), keys=(key,))
    ma5_ok = C > ma5
    # ---- Y6 바닥권 거래량 10배 + 10%↑ 윗꼬리 장대양봉
    low250 = D(L).rolling(250, min_periods=200).min().values
    ma20 = D(C).rolling(20).mean().values; ma60 = D(C).rolling(60).mean().values
    conv = (np.fmax(np.fmax(ma5, ma20), ma60) / np.fmin(np.fmin(ma5, ma20), ma60) - 1) <= 0.10
    y6 = (V >= 10 * sh(V, 1)) & (chg >= 10) & (upw >= 0.3 * rng) & (C <= low250 * 1.5) & conv
    event('Y6 바닥권(250일저점×1.5 이내·이평 수렴) 거래량10배·+10%·윗꼬리 장대양봉', y6, keys=('익일시가', '5일', '20일', '60일'))
    event('Y6b 거래량10배·+10%·윗꼬리 (바닥·수렴 조건 없음)', (V >= 10 * sh(V, 1)) & (chg >= 10) & (upw >= 0.3 * rng), keys=('익일시가', '5일', '20일', '60일'))
o = pd.DataFrame(rows); pd.set_option('display.width', 330); pd.set_option('display.max_columns', 25); pd.set_option('display.max_colwidth', 60)
print('기간', dates[260], '~', dates[-2]); print(o.round(3).to_string(index=False)); o.to_csv('yt_rules.csv', index=False)
