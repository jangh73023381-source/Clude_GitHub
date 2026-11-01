# -*- coding: utf-8 -*-
"""loop10 중기(20거래일+) 엔진 (2026-09-26).
평가 틀 — 20거래일 겹침 트랜치 포트폴리오(Jegadeesh-Titman):
  매 거래일 d 종가에 규칙의 5종을 자본 1/H 로 매수(종가 단일가 = Rule CB 집행과 같은 시점),
  H 거래일 뒤 d+H 종가에 매도. 포트폴리오 일수익 = 살아 있는 H 개 트랜치의 동일가중 평균.
  → 모든 포지션이 정확히 H 거래일 보유된다(사용자 선호 '20일 이상 보유'를 그대로 구현).
보조: 비중복 오프셋(H 간격 독립 시점) 평균 초과 · 양수 오프셋 수 (2026-07-29 mid_engine 과 같은 틀).
선정은 d 종가까지의 정보만 쓴다. 비용 0(v2.8).
"""
import numpy as np, pandas as pd
from engine import load, Engine, prof, tstat, r5, folds

P, dates, codes, names = load()
E = Engine(P, dates, codes, names)
C = E.C; T, N = C.shape; bi = E.bi


def lag(X, k):
    return np.vstack([np.full((k, N), np.nan), X[:-k]])


MOM = {k: (C / lag(C, k) - 1) * 100 for k in (20, 60, 120, 150, 200, 250)}
okH = E.elig[None, :] & ~(((C / lag(C, 1) - 1) > .10) | ((C / lag(C, 3) - 1) > .20))  # Rule H
Rd = E.R  # 일간 수익률(%)
START = 250  # 250일 지표까지 가용한 시점부터 공통 시작(모든 규칙 동일 표본)


def top(score, i, n=5, mask=None):
    s = score[i]
    m = okH[i] & ~np.isnan(s) & ~np.isnan(C[i])
    if mask is not None:
        m &= mask
    idx = np.where(m)[0]
    if len(idx) < n:
        return None
    return idx[np.argsort(-s[idx], kind='stable')[:n]]


def base_sel(i):
    return top(MOM[150], i)


def tranche(sel, H=20, lagd=0, weight=None):
    """sel(i) -> 인덱스 배열(또는 None=현금). weight(i)->0~1 (트랜치 투자비중, 나머지 현금).
    반환 DataFrame(date, port, bench, excess) — 날짜 t 의 일수익."""
    picks = {}
    for i in range(START, T - 1):
        p = sel(i)
        picks[i] = (p, 1.0 if weight is None else weight(i))
    port = np.full(T, np.nan)
    for t in range(START + 1 + lagd, T):
        vals = []
        for s in range(t - H, t):          # 트랜치 시작(매수 종가) s: t 일 수익은 (s, t] 구간에 포함
            i = s - lagd
            if i < START or i not in picks:
                continue
            p, w = picks[i]
            if p is None or len(p) == 0:
                vals.append(0.0); continue
            r = Rd[t, p]
            r = r[~np.isnan(r)]
            vals.append(w * (r.mean() if len(r) else 0.0))
        if len(vals) == H:
            port[t] = np.mean(vals)
    df = pd.DataFrame({'date': dates, 'port': port, 'bench': Rd[:, bi]})
    df = df.dropna().reset_index(drop=True)
    df['ex'] = df.port - df.bench
    return df


def offsets(sel, H=20):
    """비중복: 오프셋 o 마다 시작일 START+o, +H, ... 의 H일 보유수익 − 벤치. 평균·양수 오프셋 수."""
    res = []
    for o in range(H):
        ex = []
        for i in range(START + o, T - H, H):
            p = sel(i)
            if p is None or len(p) == 0:
                ex.append(-(C[i + H, bi] / C[i, bi] - 1) * 100); continue
            r = (C[i + H, p] / C[i, p] - 1) * 100
            ex.append(np.nanmean(r) - (C[i + H, bi] / C[i, bi] - 1) * 100)
        res.append(np.mean(ex))
    res = np.array(res)
    return res.mean(), (res > 0).sum(), res


BASE = None


def report(name, sel, H=20, weight=None, ref=None, quiet=False, lagd=0):
    global BASE
    df = tranche(sel, H, lagd, weight)
    p = prof(df.port); b = prof(df.bench)
    om, opos, _ = offsets(sel, H) if weight is None else (np.nan, -1, None)
    out = dict(name=name, cagr=p['cagr'], mdd=p['mdd'], sh=p['sharpe'], exm=df.ex.mean(), ext=tstat(df.ex),
               om=om, opos=opos, f3=folds(df.ex.values), bcagr=b['cagr'], bmdd=b['mdd'], bsh=b['sharpe'], n=len(df))
    line = (f"[{name}] n={len(df)} CAGR{p['cagr']:+6.1f} MDD{p['mdd']:6.1f} Sh{p['sharpe']:5.2f} | vs KODEX200 일{df.ex.mean():+.4f} t{tstat(df.ex):+.2f} "
            f"fold{['%+.3f' % x for x in out['f3']]} | 비중복20일 {om:+.3f}%p 양수 {opos}/{H}")
    if ref is not None:
        j = df.merge(ref[['date','port']], on='date', suffixes=('', '_r'))
        d = j.port - j.port_r
        rr = r5(d.values); pr = prof(j.port_r)
        out.update(dcagr=p['cagr'] - pr['cagr'], dmdd=p['mdd'] - pr['mdd'], dsh=p['sharpe'] - pr['sharpe'],
                   dm=d.mean(), dt=tstat(d), df3=folds(d.values), dmed=rr['median'], ddrop3=rr['drop3'])
        line += (f"\n    vs 기준 ΔCAGR{out['dcagr']:+5.1f} ΔMDD{out['dmdd']:+5.1f} ΔSh{out['dsh']:+.2f} | Δ일{d.mean():+.4f} t{tstat(d):+.2f} "
                 f"fold{['%+.3f' % x for x in out['df3']]} 중앙{rr['median']:+.4f} 상위3제거{rr['drop3']:+.4f}")
    if not quiet:
        print(line)
    return out, df
