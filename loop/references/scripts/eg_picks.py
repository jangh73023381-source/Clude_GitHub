#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eg_picks.py — 트랙 D (Rule EG 매수·매도 타점) 일별 스캔·기록. 조회 전용.

Rule EG = HTS 장악형 눌림목에서 과열배제(C<=MA20*1.10)만 제거한 규칙.
  C>=MA20 & MA20>MA20(1) & C>MA60 & MA60>=MA60(5)
  & lowest(L,5)<=MA20*1.02
  & C>=O(1) & C>O & C(1)<O(1) & C>=L+(H-L)*0.6
  & V>=avg(V,20)*1.3
청산 = 매수 후 20거래일 종가 고정(백테스트에서 40/60일은 R5 기각).

근거: 2026-08-31 루프 외 실행. 7년 1,820거래일 · 거래대금 상위 100 ETF · 신호 1,103건.
  20일 보유 +4.41% vs B1(추세전제) +3.13% = +1.28%p · 승률 64.3%
  R1 고원(상한 1.15~제거 평평) · R2 fold 3/3 · R3 정의교체 재현 · R4 플라시보 p=0.000
  R5 는 집행 방식에 따라 갈림(D종가 +0.0850 통과 / D+1 -0.0794 기각) — 미확정 상태.
**실제 매매 판단은 사용자 몫이며 확정 방법 v2.9 선정에 관여하지 않는다.**

사용: python3 references/scripts/eg_picks.py [--record] [--asof YYYYMMDD]
"""
import argparse
import csv
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import universe_filters as uf                      # noqa: E402
from etf_sector_map import sector                   # noqa: E402
from safe_io import safe_replace                   # noqa: E402

TRACKER = os.path.join(LOOP, 'references', 'eg_track_tracker.csv')
HDR = ['date', 'n_buy', 'buy_codes', 'buy_rep_codes', 'n_sell', 'sell_codes', 'sell_pnl_pct',
       'n_hold', 'hold_codes', 'hold_pnl_pct', 'n_watch', 'note']
HOLD_DAYS = 20
LIQ_MARK = 100      # 표시 전용 — 거래대금 상위 N 밖이면 신호에 '低' 를 붙인다(선정에는 미사용)
EXEC = '종가'          # 2026-08-31 사용자 확정 — 신호일 15:20~15:30 종가 단일가 매수

# ---- Rule EG v1.1 (2026-09-03 사용자 승인, 근거 fable/트랙D_RuleEG_매수매도타점_검토_2026-09-03.pdf) ----
K_SLOTS = 5            # 동시보유 상한 — 자본을 5슬롯(각 20%)으로 나눠 빈 슬롯만 채운다(7년 CAGR 28.8%·MDD -34.1%)
D1_MAX_CHG = 5.0       # 집행일(D+1) 당일 등락률이 +5% 이상이면 매수 포기(D+1 +5%↑ n=31 평균 -1.84%·승률 45%)
BEAR_HALF = True       # KODEX200 종가 < MA60 이면 종목당 비중을 평소의 1/2 (이 국면 20일 +2.65%·승률 59.6% vs 평소 +4.79%·65.3%)
# 재신호 연장 금지: 보유 중 같은 종목에 재신호가 나도 청산일(HOLD_DAYS)을 늘리지 않고 추가 매수도 하지 않는다
# (5슬롯 재현 CAGR 28.8% → 연장 시 21.3%). 손절 없음 유지(-3/-5/-7% 어느 선도 방치보다 열위).
BENCH = '069500'       # 국면 판정 기준(KODEX 200)

# ---- Rule EG v1.2 매수 수식 보완 (2026-09-03 사용자 승인) ----
PULL_WIN = 10          # 눌림 조건 lowest(L,N)<=MA20*1.02 의 N: 5 → 10. 7년 신호 2,542건 20일 +5.52% vs 현행 +4.42%
                       # (+1.10%p), 승률 66.5%, fold 3/3, R5 상위3일 제거 +0.29, N=10~20 동일(고원). 5슬롯 CAGR 28.8→32.6%.
PULL_EFFECTIVE = 20260904   # 이 날짜 이후 신호부터 N=10 적용. 이전 신호(보유·이력)는 종전 N=5 로 판정해 트래커 이력 불변.
FLOW_DAYS = 5          # 수급 조건: 기관+외국인 최근 5거래일 누적 순매수 수량 > 0 (키움 ka10045, 신호 종목만 조회)
                       # 2년(2024-02~2026-07) 신호 1,088건: 통과 +9.15%(승률 74.6%) vs 미달 +4.74% · 클러스터 t=2.43 ·
                       # 플라시보 p=0.027 · R5 +0.71. 외국인 단독은 무효(fold ---), 기관 또는 합산만 유효.
                       # 2년 표본이므로 '잠정' — 통과분을 우선 매수, 미달분은 후순위(슬롯 여유 시에만)로 적용한다.

# ---- 신뢰도 표시 (2026-09-11 사용자 요청 · 표시 전용 — 선정·우선순위·청산에 절대 쓰지 않는다) ----
OOS_START = 20260828   # 규칙 설계에 쓴 7년 패널(~20260827) 이후에 난 신호만 OOS 로 센다
RECENT_DAYS = 20000    # '최근 2년' = 날짜 정수(YYYYMMDD)에서 20000 을 뺀 날 이후
GRADE_WEAK, GRADE_OK = 5, 15   # 독립n 등급 경계: <5 판단불가 · 5~14 약함 · 15+ 보통

# 우선순위 z 정규화 상수 — 7년 1,925신호 표본(2026-08-31, 유니버스 187종 기준 재산출).
# 표본이 늘거나 유니버스가 바뀌면 반드시 재산출할 것.
CHG_MU, CHG_SD = 2.6991, 2.5062      # 신호일 당일 등락률(%)
OVER_MU, OVER_SD = 5.0991, 4.0508    # 신호일 MA20 이격도(%)


def flow_check(codes, asof):
    """수급 조건(v1.2) — 신호 종목만 키움 ka10045 로 최근 FLOW_DAYS 거래일 기관+외국인 순매수 합산. 조회 전용.
    반환 {code: (합산수량 or None, 통과여부 or None)}. 조회 실패는 None(통과 판정 보류·후순위 아님)."""
    out = {}
    if not codes:
        return out
    try:
        sys.path.insert(0, LOOP)
        import kiwoom_api as k
    except Exception as e:                                # noqa: BLE001
        print(f'  [eg] 수급 조회 불가(kiwoom_api): {e}')
        return {c: (None, None) for c in codes}
    import time
    from datetime import datetime, timedelta
    end = str(asof)
    start = (datetime.strptime(end, '%Y%m%d') - timedelta(days=20)).strftime('%Y%m%d')
    for c in codes:
        try:
            time.sleep(0.25)
            r = k.get_institution_trend(c, start, end)
            arr = [x for x in (r.get('stk_orgn_trde_trnsn') or []) if str(x.get('dt', '')) <= end]
            arr = sorted(arr, key=lambda x: x['dt'], reverse=True)[:FLOW_DAYS]
            f_ = lambda v: float(str(v).replace('+', '').replace(',', '') or 0)
            tot = sum(f_(x.get('orgn_daly_nettrde_qty')) + f_(x.get('for_daly_nettrde_qty')) for x in arr)
            out[c] = (tot, tot > 0) if arr else (None, None)
        except Exception as e:                            # noqa: BLE001
            print(f'  [eg] 수급 조회 실패 {c}: {e}')
            out[c] = (None, None)
    return out


def sector_reps(new):
    """섹터별 우선점수 최고 1종의 코드 리스트(점수 내림차순)."""
    best = {}
    for x in sorted(new, key=lambda z: -z['score']):
        best.setdefault(x['sec'], x)
    return [x['code'] for x in sorted(best.values(), key=lambda z: -z['score'])]


def prio(chg, over):
    """우선순위 점수. 상관 +0.135(당일등락) · +0.128(MA20이격), 둘 다 fold 3/3.
    거래량 배수(-0.007)·종가 위치(+0.006)는 순위 정보가 없어 제외한다(게이트 전용)."""
    return (chg - CHG_MU) / CHG_SD + (over - OVER_MU) / OVER_SD


def load_panel():
    lg = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_long.csv'), dtype={'code': str})
    t2 = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv'), dtype={'code': str})
    p = pd.concat([lg, t2[t2.date > lg.date.max()][lg.columns]], ignore_index=True)
    p = p.drop_duplicates(['code', 'date']).sort_values(['code', 'date'])
    return p[~p.name.map(lambda n: uf.is_deriv(n) or uf.is_cash(n))]


def universe(p, asof):
    """아침 루틴(morning_run.py)과 **동일한 유니버스** — universe_filters 만 적용한다.
    2026-08-31 사용자 지시로 종전 '거래대금 상위 100' 컷을 폐지했다.
    load_panel() 에서 파생·현금성이 이미 제외되므로 여기서는 전체를 그대로 쓴다."""
    return set(p[p.date <= asof].code.unique())


def liquid_top(p, asof, n=LIQ_MARK):
    """표시 전용 — 최근 거래대금 상위 n 종. 선정·우선순위에는 쓰지 않는다."""
    # date가 YYYYMMDD 정수라 asof-300 같은 단순 산술은 연/월 경계에서 깨진다
    # (예: asof=20260215 → 20259915는 실존하지 않는 날짜라 1~2월엔 룩백이 '올해 들어서부터'로
    # 쪼그라든다). 실제 달력일 기준 300일 전으로 계산한다.
    cutoff = int((pd.to_datetime(str(asof), format='%Y%m%d')
                  - pd.Timedelta(days=300)).strftime('%Y%m%d'))
    r = p[(p.date <= asof) & (p.date >= cutoff)]
    amt = r.groupby('code')[['volume', 'close']].apply(
        lambda d: (d.volume * d.close).mean()).sort_values(ascending=False)
    return set(amt.head(n).index)


def bench_maps(p, asof):
    """KODEX200 날짜→종가, 날짜→약세(종가<MA60) 사전. 신뢰도 표시(시장 대비·국면 기준선) 전용."""
    b = p[(p.code == BENCH) & (p.date <= asof)].sort_values('date')
    ds, c = b.date.astype(int).values, b.close.values
    m = b.close.rolling(60).mean().values
    return (dict(zip(ds, c)),
            {int(x): bool(y < z) for x, y, z in zip(ds, c, m) if not np.isnan(z)})


def signal_outcomes(C, L, eg, dt, bclose):
    """20거래일을 완주한 EG 신호 각각의 결과(%) — r=20일 수익률(신호일 종가→20일째 종가),
    mae=보유 20일 중 장중 최저가의 매수가 대비 낙폭(0 이하), ex=같은 20일 KODEX200 대비 초과."""
    n, out = len(C), []
    for k in np.where(eg.values)[0]:
        if k + HOLD_DAYS >= n:
            continue
        r = (C.iloc[k + HOLD_DAYS] / C.iloc[k] - 1) * 100
        b0, b1 = bclose.get(int(dt[k])), bclose.get(int(dt[k + HOLD_DAYS]))
        out.append(dict(k=int(k), date=int(dt[k]), r=float(r),
                        mae=min(0.0, float((L.iloc[k + 1:k + HOLD_DAYS + 1].min() / C.iloc[k] - 1) * 100)),
                        ex=float(r - (b1 / b0 - 1) * 100) if b0 and b1 else None))
    return out


def n_indep(ks):
    """20일 보유가 겹치지 않는 신호 수 — 앞서 센 신호의 보유가 끝난 뒤에 난 신호만 센다.
    겹친 신호는 사실상 같은 매매라 전체 n 은 표본을 부풀린다."""
    c, last = 0, None
    for k in sorted(ks):
        if last is None or k >= last + HOLD_DAYS:
            c, last = c + 1, k
    return c


def wilson(p, n, z=1.96):
    """승률 p(0~1)의 95% Wilson 구간(%). n 은 독립 표본 수."""
    if not n:
        return None, None
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h) * 100, min(1.0, c + h) * 100


def hist_stats(sigs, j_now, asof):
    """그 종목의 **과거 EG 신호** 20거래일 성적 (2026-09-04 사용자 요청, 표시 전용).

    j_now(오늘 신호·보유 종목은 매수 신호일)를 제외하고, 20거래일을 완주한 과거 신호만 센다.
    **선정·우선순위에 절대 쓰지 않는다** — 종목당 표본이 7년 전체에서 중앙값 12건에 불과해
    (min 1 · max 32, 2026-09-04 실측) 평균 차이는 대부분 잡음이다. 브리핑에는 반드시
    n 을 함께 표기하고 '참고 전용' 각주를 붙인다.
    2026-09-11 확장(사용자 요청 — 확신도 표시): 독립n · 승률 95% Wilson 구간(독립n 기준) · 하위10% ·
    손익비 · MAE 중앙/하위20% · KODEX200 초과 평균/승률 · 최근 2년. 보정기대(h_shr)는 main 에서 채운다.
    """
    s = [x for x in sigs if x['k'] < j_now]
    if not s:
        return dict(h_n=0, h_ind=0, h_avg=None, h_med=None, h_win=None, h_lo=None, h_hi=None,
                    h_p10=None, h_pf=None, h_nloss=0, h_mae_med=None, h_mae_p20=None,
                    h_maes=np.array([]), h_ex_avg=None, h_ex_win=None, h_n2y=0, h_avg2y=None)
    rs = np.array([x['r'] for x in s])
    mae = np.array([x['mae'] for x in s])
    ex = np.array([x['ex'] for x in s if x['ex'] is not None])
    ind, win = n_indep([x['k'] for x in s]), float((rs > 0).mean())
    lo, hi = wilson(win, ind)
    pos, neg = rs[rs > 0], rs[rs <= 0]
    r2 = np.array([x['r'] for x in s if x['date'] >= asof - RECENT_DAYS])
    return dict(h_n=len(rs), h_ind=ind, h_avg=float(rs.mean()), h_med=float(np.median(rs)),
                h_win=win * 100, h_lo=lo, h_hi=hi, h_p10=float(np.percentile(rs, 10)),
                h_pf=float(pos.mean() / -neg.mean()) if len(pos) and len(neg) and neg.mean() < 0 else None,
                h_nloss=len(neg), h_mae_med=float(np.median(mae)), h_mae_p20=float(np.percentile(mae, 20)),
                h_maes=mae, h_ex_avg=float(ex.mean()) if len(ex) else None,
                h_ex_win=float((ex > 0).mean() * 100) if len(ex) else None,
                h_n2y=len(r2), h_avg2y=float(r2.mean()) if len(r2) else None)


def base_line(rows):
    """신호 묶음의 기준선 — n·평균·중앙·승률·KODEX200 초과·MAE 분포."""
    if not rows:
        return None
    r = np.array([x['r'] for x in rows])
    ex = np.array([x['ex'] for x in rows if x['ex'] is not None])
    mae = np.array([x['mae'] for x in rows])
    return dict(n=len(r), avg=float(r.mean()), med=float(np.median(r)), win=float((r > 0).mean() * 100),
                ex_avg=float(ex.mean()) if len(ex) else None,
                ex_win=float((ex > 0).mean() * 100) if len(ex) else None,
                mae_med=float(np.median(mae)), mae_p20=float(np.percentile(mae, 20)), maes=mae)


def shrink_k(allsig):
    """보정 강도 K(경험적 베이즈). 종목별 평균의 흩어짐 가운데 표본오차(σ²/독립n)로 설명되지 않는 몫 τ² 를
    구해 K = σ²/τ². τ² ≤ 0 이면 종목 간 차이가 전부 잡음이라는 뜻이므로 상한 500 을 쓴다."""
    g = {}
    for x in allsig:
        g.setdefault(x['code'], []).append(x)
    means, ns, vs = [], [], []
    for ss in g.values():
        if len(ss) < 2:
            continue
        r = np.array([x['r'] for x in ss])
        means.append(r.mean()); ns.append(n_indep([x['k'] for x in ss])); vs.append(r.var(ddof=1))
    if len(means) < 5:
        return 500.0
    s2 = float(np.mean(vs))
    tau2 = float(np.var(means, ddof=1) - np.mean([s2 / n for n in ns]))
    return float(np.clip(s2 / tau2, 1, 500)) if tau2 > 0 else 500.0


def grade(x, base):
    if x['h_ind'] < GRADE_WEAK:
        return f'판단불가(독립n<{GRADE_WEAK})'
    g = '약함' if x['h_ind'] < GRADE_OK else '보통'
    if x['h_lo'] > base['win']:
        g += ' · 승률 기준선 우위 확인'
    elif x['h_hi'] < base['win']:
        g += ' · 승률 기준선 열위 확인'
    return g


def win_ci(x):
    return f"{x['h_win']:.0f}%({x['h_lo']:.0f}~{x['h_hi']:.0f})" if x['h_n'] else '—'


def print_detail(new, base, K):
    """매수 신호 신뢰도 상세(2026-09-11). 섹터 중복으로 비고로 밀린 신호까지 전부 싣는다."""
    rows = sorted(new, key=lambda z: -z['score'])
    print('\n■ 매수 신호 신뢰도 상세 — 그 종목의 과거 EG 신호 20거래일 성적 (참고 전용 · 선정·우선순위 미반영)')
    print(f"   [표본]           {'종목':28s} {'코드':6s} {'독립/전체n':>9s} {'평균':>7s} {'중앙':>7s} "
          f"{'보정기대':>8s} {'승률':>6s} {'95%구간':>9s} {'최근2년':>13s}  등급")
    for x in rows:
        head = f"                    {x['name'][:26]:28s} {x['code']:6s}"
        if not x['h_n']:
            print(f"{head} {'0/0':>9s}  과거 신호 없음 — 보정기대 = 전체 평균 {x['h_shr']:+.2f}%  판단불가")
            continue
        r2 = f"n{x['h_n2y']} {x['h_avg2y']:+.2f}%" if x['h_n2y'] else 'n0'
        ci = f"{x['h_lo']:.0f}~{x['h_hi']:.0f}%"
        print(f"{head} {str(x['h_ind']) + '/' + str(x['h_n']):>9s} {x['h_avg']:>+6.2f}% {x['h_med']:>+6.2f}% "
              f"{x['h_shr']:>+7.2f}% {x['h_win']:>5.1f}% {ci:>9s} {r2:>13s}  "
              f"{grade(x, base)}")
    print(f"   [흔들림·시장대비] {'종목':28s} {'코드':6s} {'MAE중앙':>7s} {'MAE하위20%':>9s} {'하위10%':>8s} "
          f"{'손익비':>7s} {'KODEX200초과':>11s} {'초과승률':>7s}")
    for x in rows:
        if not x['h_n']:
            continue
        pf = f"{x['h_pf']:.2f}" if x['h_pf'] is not None else ('손실0건' if x['h_nloss'] == 0 else '—')
        ea = f"{x['h_ex_avg']:+.2f}%p" if x['h_ex_avg'] is not None else '—'
        ew = f"{x['h_ex_win']:.1f}%" if x['h_ex_win'] is not None else '—'
        print(f"                    {x['name'][:26]:28s} {x['code']:6s} {x['h_mae_med']:>+6.1f}% "
              f"{x['h_mae_p20']:>+8.1f}% {x['h_p10']:>+7.2f}% {pf:>7s} {ea:>11s} {ew:>7s}")
    print(f"   ※ 기준선(전체 {base['n']:,}건): 평균 {base['avg']:+.2f}% · 중앙 {base['med']:+.2f}% · "
          f"승률 {base['win']:.1f}% · KODEX200 초과 {base['ex_avg']:+.2f}%p(초과승률 {base['ex_win']:.1f}%) · "
          f"MAE중앙 {base['mae_med']:+.1f}%(하위20% {base['mae_p20']:+.1f}%). **종목 수치는 반드시 이 줄과 대조할 것.**")
    print('   ※ 독립n = 20일 보유가 겹치지 않는 신호만 센 수. 겹친 신호는 사실상 같은 매매라 전체n 은 표본을 부풀린다. '
          '**승률 95% 구간(Wilson)은 독립n 기준**이며, 구간이 기준선 승률을 포함하면 "기준선과 다르다"고 말할 수 없다.')
    print(f'   ※ 보정기대 = (독립n×종목평균 + K×전체평균) ÷ (독립n + K), K={K:.0f}. 표본이 작을수록 전체 평균 쪽으로 '
          '당긴 값이다 — **종목 간 비교는 평균이 아니라 이 값으로 할 것.**')
    print(f'   ※ 등급: 독립n <{GRADE_WEAK} 판단불가 · {GRADE_WEAK}~{GRADE_OK - 1} 약함 · {GRADE_OK}+ 보통. '
          '"기준선 우위/열위 확인"은 95% 구간 전체가 기준선 승률 위/아래일 때만 붙는다.')
    print('   ※ MAE = 매수가(신호일 종가) 대비 보유 20거래일 중 장중 최저가 낙폭. **Rule EG 는 손절이 없으므로 '
          '이만큼 흔들리는 것이 과거의 보통 경로다.** 하위10% = 20일 수익률 하위 10% 값(꼬리 위험). '
          '손익비 = 평균 이익 ÷ |평균 손실|.')
    print('   ※ KODEX200 초과 = 같은 20거래일 KODEX200 수익률을 뺀 값(강세장에서 원승률이 부풀려지는 것을 걸러낸다). '
          '최근2년 = 최근 2년 안에 난 신호만(국면 변화 확인용).')


def print_hold_check(hold, base):
    """보유 종목 흔들림 점검(2026-09-11) — 지금까지의 낙폭이 과거 경로에서 어디쯤인지. 청산 규칙은 바꾸지 않는다."""
    print(f"   [흔들림 점검] {'종목':28s} {'코드':6s} {'독립/전체n':>9s} {'보정기대':>8s} {'승률(95%구간)':>13s} "
          f"{'MAE중앙':>7s} {'MAE하위20%':>9s} {'현재역행':>7s}  판정")
    for x in sorted(hold, key=lambda z: z['sig']):
        own = x['h_ind'] >= GRADE_WEAK
        med, p20, maes = ((x['h_mae_med'], x['h_mae_p20'], x['h_maes']) if own
                          else (base['mae_med'], base['mae_p20'], base['maes']))
        src = '그 종목 과거' if own else f'전체 기준선(독립n<{GRADE_WEAK})'
        deeper = float((maes <= x['cur_mae']).mean() * 100)
        lab = '보통 흔들림' if deeper >= 50 else ('정상 범위' if deeper >= 20 else '이례적 깊이 — 규칙상 보유 유지')
        print(f"                 {x['name'][:26]:28s} {x['code']:6s} {str(x['h_ind']) + '/' + str(x['h_n']):>9s} "
              f"{x['h_shr']:>+7.2f}% {win_ci(x):>13s} {med:>+6.1f}% {p20:>+8.1f}% {x['cur_mae']:>+6.1f}%  "
              f"{lab}({src} {deeper:.0f}%가 이만큼 이상 빠졌었다)")
    print('   ※ 현재역행 = 매수가 대비 매수 후 지금까지의 장중 최저가 낙폭(음수, 절대값이 클수록 깊다). '
          '잔여 기간에 더 깊어질 수 있고, 과거 MAE 는 20일 전체 기준이다.')
    print('   ※ **판정은 참고용이며 v1.1 청산 규칙(20거래일째 종가 고정·손절 없음)을 바꾸지 않는다.** '
          f'독립n<{GRADE_WEAK} 이면 전체 기준선 MAE 분포로 대조한다.')


def print_baseline(allsig, base, K, new, hold, bear, asof):
    """신뢰도 기준선(2026-09-11) — 종목 표본이 작을 때 기댈 곳. 오늘 신호·보유 종목의 섹터만 싣는다."""
    print(f'\n■ 신뢰도 기준선 — D={asof} 기준 재계산 · 20거래일 완주 신호 전체 (참고 전용 · 선정·우선순위 미반영)')
    print(f"   {'구분':30s} {'n':>6s} {'평균':>7s} {'중앙':>7s} {'승률':>6s} {'KODEX200초과':>11s} "
          f"{'초과승률':>7s} {'MAE중앙':>7s}")

    def row(label, b):
        if not b:
            print(f"   {label:30s} {0:>6d}  표본 없음")
            return
        ea = f"{b['ex_avg']:+.2f}%p" if b['ex_avg'] is not None else '—'
        ew = f"{b['ex_win']:.1f}%" if b['ex_win'] is not None else '—'
        print(f"   {label:30s} {b['n']:>6,d} {b['avg']:>+6.2f}% {b['med']:>+6.2f}% {b['win']:>5.1f}% "
              f"{ea:>11s} {ew:>7s} {b['mae_med']:>+6.1f}%")

    row(f"전체({str(min(x['date'] for x in allsig))[:4]}~)", base)
    row('최근 2년', base_line([x for x in allsig if x['date'] >= asof - RECENT_DAYS]))
    row('국면 약세(KODEX200<MA60)' + (' ◀오늘' if bear else ''),
        base_line([x for x in allsig if x['bear'] is True]))
    row('국면 정상' + ('' if bear else ' ◀오늘'), base_line([x for x in allsig if x['bear'] is False]))
    for sc in sorted({x['sec'] for x in new + hold}):
        row(f'섹터 {sc}', base_line([x for x in allsig if x['sec'] == sc]))
    oh = [x for x in hold if x['sig'] >= OOS_START]
    row(f'OOS 청산분(신호일 {OOS_START}~)', base_line([x for x in allsig if x['date'] >= OOS_START]))
    print('   ※ 국면 약세 = v1.1 규칙 ④ 발동 조건과 같은 **KODEX200 종가 < MA60 단독** 기준(신호일 판정). '
          '9절 각주의 "약세 +2.65%·승률 59.6%"는 MA20·MA60 동시 하회(n=146) 기준이라 값이 다르다.')
    print(f'   ※ OOS = 규칙 설계에 쓴 7년 패널(~{OOS_START - 1}) 이후에 난 신호. 보유 중 {len(oh)}건'
          + (f" 평균 {np.mean([x['pnl'] for x in oh]):+.2f}%(미실현)" if oh else '')
          + ' — 백테스트 기대치와의 대조 판정은 N* 도달 후(judge_ready.py)에만 한다.')
    cnt = pd.Series([x['code'] for x in allsig]).value_counts()
    print(f'   ※ 종목당 전체n 중앙값 {cnt.median():.0f}건(최소 {cnt.min()}·최대 {cnt.max()}) — '
          '**n 을 보지 않고 평균만 비교하지 말 것.**')
    print(f'   ※ 보정 강도 K={K:.0f}: 독립n 이 {K:.0f}건이면 종목 평균과 전체 평균을 반반 믿는다. 종목 간 평균 차이 중 '
          '표본오차로 설명되지 않는 몫으로 매번 재추정한다(K 가 클수록 종목별 차이가 대부분 잡음이라는 뜻).')


def scan(p, asof, allsig=None):
    """반환: (신규 신호, 보유중, 대기). allsig 에 list 를 넘기면 20거래일 완주한 전 신호의 결과를
    채워 준다(신뢰도 기준선 · 보정 강도 추정용, 2026-09-11)."""
    new, hold, watch, sell = [], [], [], []
    bclose, bbear = bench_maps(p, asof)
    for code, d in p.groupby('code'):
        d = d[d.date <= asof].reset_index(drop=True)
        if len(d) < 300 or int(d.date.iloc[-1]) != asof:
            continue
        H, L, C, O, V = d.high, d.low, d.close, d.open, d.volume
        M = C.rolling(20).mean(); M1 = M.shift(1)
        M6 = C.rolling(60).mean(); VA = V.rolling(20).mean()
        core = (C >= M) & (M > M1) & (C > M6) & (M6 >= M6.shift(5))
        eff = d.date.astype(int) >= PULL_EFFECTIVE
        pull = np.where(eff, L.rolling(PULL_WIN).min() <= M * 1.02, L.rolling(5).min() <= M * 1.02)
        trend = core & pd.Series(pull, index=d.index).fillna(False)
        eg = (trend & (C >= O.shift(1)) & (C > O) & (C.shift(1) < O.shift(1))
              & (C >= L + (H - L) * 0.6) & (V >= VA * 1.3)).fillna(False)
        i = len(d) - 1
        nm = d.name.iloc[0]
        sec_ = sector(nm)
        sigs = signal_outcomes(C, L, eg, d.date.astype(int).values, bclose)
        if allsig is not None:
            allsig.extend(dict(x, code=code, sec=sec_, bear=bbear.get(x['date'])) for x in sigs)
        for j in np.where(eg.values)[0]:
            age = i - j
            if age == 0:
                chg = (C.iloc[j] / C.iloc[j - 1] - 1) * 100
                over = (C.iloc[j] / M.iloc[j] - 1) * 100
                new.append(dict(code=code, name=nm, sec=sector(nm),
                                close=float(C.iloc[j]), over=over,
                                chg=chg, vr=float(V.iloc[j] / VA.iloc[j]),
                                score=prio(chg, over), ma20=float(M.iloc[j]),
                                resig=bool(eg.iloc[max(0, j - HOLD_DAYS):j].any()),
                                **hist_stats(sigs, j, asof)))
            elif 0 < age <= HOLD_DAYS:
                rec_ = dict(code=code, name=nm, sec=sec_, sig=int(d.date.iloc[j]),
                            buy=float(C.iloc[j]), cur=float(C.iloc[i]), held=age,
                            pnl=(C.iloc[i] / C.iloc[j] - 1) * 100, remain=HOLD_DAYS - age,
                            cur_mae=min(0.0, float((L.iloc[j + 1:i + 1].min() / C.iloc[j] - 1) * 100)),
                            **hist_stats(sigs, j, asof))
                (sell if age == HOLD_DAYS else hold).append(rec_)
        if bool(trend.fillna(False).iloc[i]) and not bool(eg.iloc[i]):
            # ready = 오늘이 음봉 → 내일 조건8(C(1)<O(1))이 충족되므로 내일 신호 가능.
            # (2026-08-31 수정: 종전 bear1 은 '어제 음봉'이라 전방 정보가 아니었다.)
            watch.append(dict(code=code, name=nm, sec=sector(nm), close=float(C.iloc[i]),
                              over=(C.iloc[i] / M.iloc[i] - 1) * 100,
                              vr=float(V.iloc[i] / VA.iloc[i]),
                              ready=bool(C.iloc[i] < O.iloc[i])))
    return new, sell, hold, watch


def record(asof, new, sell, hold, watch):
    rows, hdr = [], HDR
    if os.path.exists(TRACKER):
        with open(TRACKER, encoding='utf-8') as f:
            rd = list(csv.reader(f))
        hdr, rows = rd[0], [r for r in rd[1:] if r and r[0] != str(asof)]
    rows.append([str(asof),
                 len(new), '|'.join(x['code'] for x in new),
                 '|'.join(sector_reps(new)),
                 len(sell), '|'.join(x['code'] for x in sell),
                 f"{np.mean([x['pnl'] for x in sell]):.4f}" if sell else '',
                 len(hold), '|'.join(x['code'] for x in hold),
                 f"{np.mean([x['pnl'] for x in hold]):.4f}" if hold else '',
                 len(watch), ''])
    rows.sort(key=lambda r: r[0])
    tmp = TRACKER + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(hdr); w.writerows(rows)
    safe_replace(tmp, TRACKER)
    print(f'  [eg] {asof} 기록 → {os.path.basename(TRACKER)} (누적 {len(rows)}일)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', action='store_true')
    ap.add_argument('--asof', type=int, default=None)
    ap.add_argument('--catchup', action='store_true',
                    help='트래커 마지막 기록일 이후 빠진 거래일을 전부 회수한다(멱등)')
    a = ap.parse_args()
    p = load_panel()
    if a.catchup:
        dates = sorted(int(x) for x in p.date.unique())
        last = 0
        if os.path.exists(TRACKER):
            with open(TRACKER, encoding='utf-8') as f:
                rr = [r for r in csv.reader(f)][1:]
            last = max((int(r[0]) for r in rr if r), default=0)
        todo = [d for d in dates if d > last][-30:]
        for dt in todo:
            q = p[p.code.isin(universe(p, dt))]
            record(dt, *scan(q, dt))
        print(f'  [eg] catchup {len(todo)}일 처리')
        return 0
    asof = a.asof or int(p.date.max())
    liq = liquid_top(p, asof)
    p = p[p.code.isin(universe(p, asof))]
    nu = p[p.date == asof].code.nunique()
    allsig = []
    new, sell, hold, watch = scan(p, asof, allsig)
    # ---- 신뢰도 표시(2026-09-11) — 기준선·보정 강도. 선정·우선순위·청산에는 쓰지 않는다 ----
    base, K = base_line(allsig), shrink_k(allsig)
    for x in new + sell + hold:
        x['h_shr'] = ((x['h_ind'] * x['h_avg'] + K * base['avg']) / (x['h_ind'] + K)
                      if x['h_n'] else base['avg'])
    for x in new + watch:
        x['liq'] = x['code'] in liq
    print(f'[트랙 D · Rule EG 매수·매도 타점] D={asof} · 유니버스 {nu}종'
          f'(아침루틴 동일 필터) · 집행 {EXEC}')

    # ---- v1.2: 수급 조건 (2026-09-03) — 통과분 우선, 미달분 후순위 ----
    fl = flow_check([x['code'] for x in new], asof)
    for x in new:
        x['flow'], x['flow_ok'] = fl.get(x['code'], (None, None))
        x['score'] = x['score'] + (0 if x['flow_ok'] is not False else -100)   # 미달분은 정렬상 맨 뒤(점수 표시는 원값 유지)
        x['score0'] = x['score'] + (100 if x['flow_ok'] is False else 0)

    # ---- v1.1: 국면 · 슬롯 (2026-09-03) ----
    bear = False
    bp = p[(p.code == BENCH) & (p.date <= asof)].sort_values('date')
    if len(bp) >= 60:
        bm60 = float(bp.close.tail(60).mean()); bear = float(bp.close.iloc[-1]) < bm60
        print(f'   국면: KODEX200 {float(bp.close.iloc[-1]):,.0f} vs MA60 {bm60:,.0f} → '
              + ('**약세 — 종목당 비중 평소의 1/2**' if bear else '정상 비중'))
    free = max(0, K_SLOTS - len(hold))
    print(f'   슬롯: {K_SLOTS} 중 보유 {len(hold)} → 여유 {free}. '
          + (f'신호 {len(new)}건 > 여유 → 우선점수·섹터대표 순 상위 {free}건만 매수'
             if len(new) > free else '신호 전부 동일가중(각 자본의 20%)'))

    # 섹터 중복 정리 — 같은 섹터는 우선점수 최고 1종만 행으로 내고 나머지는 비고로 넘긴다.
    bysec = {}
    for x in sorted(new, key=lambda z: -z['score']):
        bysec.setdefault(x['sec'], []).append(x)
    reps = [x for x in sorted(new, key=lambda z: -z['score'])
            if x['code'] in set(sector_reps(new))]
    dup = len(new) - len(reps)
    print(f'\n■ 매수 — 신호 {len(new)}건'
          + (f' · 섹터 대표 {len(reps)}건(중복 {dup}건은 비고)' if dup else '')
          + ('  (우선순위 순)' if len(reps) > 1 else ''))
    if reps:
        print(f"   {'순':>2s} {'섹터':10s} {'종목':28s} {'코드':6s} {'매수가':>10s} {'당일등락':>7s} "
              f"{'MA20이격':>8s} {'거래량':>6s} {'점수':>6s} {'수급5일':>12s} "
              f"{'독립/전체n':>9s} {'보정기대':>8s} {'승률(95%구간)':>13s} {'MAE중앙':>7s}  비고")
        for k, x in enumerate(reps, 1):
            others = bysec[x['sec']][1:]
            note = ('같은 섹터 ' + ', '.join(
                f"{o['name'][:18]}({o['code']}"
                + ('' if o.get('flow_ok') is None else ('·수급통과' if o['flow_ok'] else '·수급미달'))
                + (f"·과거 n{o['h_ind']}/{o['h_n']} 보정 {o['h_shr']:+.2f}%" if o.get('h_n')
                   else f"·과거 n0 보정 {o['h_shr']:+.2f}%") + ')'
                for o in others)) if others else ''
            if not x['liq']:
                note = ('低유동 · ' + note) if note else '低유동'
            if x['resig']:
                note = ('보유 중 재신호 — 연장·추가매수 없음 · ' + note) if note else '보유 중 재신호 — 연장·추가매수 없음'
            fs = ('조회불가' if x['flow_ok'] is None else
                  f"{x['flow']:>+9,.0f}{'통과' if x['flow_ok'] else '미달'}")
            if x['flow_ok'] is False:
                note = ('**수급 미달 — 후순위(슬롯 여유 시에만)** · ' + note) if note else '**수급 미달 — 후순위(슬롯 여유 시에만)**'
            hs = (f"{str(x['h_ind']) + '/' + str(x['h_n']):>9s} {x['h_shr']:>+7.2f}% {win_ci(x):>13s} "
                  + (f"{x['h_mae_med']:>+6.1f}%" if x['h_n'] else f"{'—':>7s}"))
            print(f"   {k:>2d} {x['sec']:10s} {x['name'][:26]:28s} {x['code']:6s} {x['close']:>9,.0f}원 "
                  f"{x['chg']:+6.2f}% {x['over']:+7.1f}% {x['vr']:5.2f}배 {x['score0']:+6.2f} {fs:>12s} "
                  f"{hs}  {note}")
        print(f'   ※ 집행(v1.1) = 브리핑일 15:20~15:30 종가 단일가(D+1 종가 진입 20일 +4.36% ≈ D종가 +4.42%).'
              f' **당일 등락 +{D1_MAX_CHG:.0f}% 이상이거나 종가가 MA20 아래면 매수 포기.**')
        for x in reps:
            print(f"      {x['name'][:26]:28s} 포기 상단가 {x['close'] * (1 + D1_MAX_CHG / 100):>9,.0f}원 / MA20 {x['ma20']:>9,.0f}원")
        print(f'   ※ **독립/전체n·보정기대·승률(95%구간)·MAE중앙 = 그 종목이 과거 EG 신호로 잡혔을 때의 20거래일 성적**'
              f'(오늘 신호 제외, 20일 완주분만). **참고 전용 — 선정·우선순위에 쓰지 않는다.** 상세는 아래 ■ 매수 신호 신뢰도 상세.')
        print('   ※ **표본이 작다 — n 을 보지 않고 평균만 비교하지 말 것.** 전체 기준선·종목당 n 분포는 ■ 신뢰도 기준선.')
        print(f'   ※ 수급(v1.2) = 기관+외국인 최근 {FLOW_DAYS}거래일 누적 순매수 수량 > 0 (2년 검정: 통과 +9.15% vs 미달 +4.74%, '
              f't=2.43·p=0.027). 통과분을 먼저 담고 미달분은 슬롯이 남을 때만. 눌림 조건은 {PULL_EFFECTIVE} 부터 {PULL_WIN}일 저점 기준.')
        print('   ※ 섹터 대표 = 같은 섹터 신호 중 우선점수 최고 1종. 7년 검정에서 무작위 선택'
              '(+3.47%)보다 우위(+3.57%, p=0.005)다.')
        print('   ※ 자금이 되면 비고의 중복분까지 전부 동일가중이 최선이다'
              '(전부 +1.37%p vs 섹터대표만 +0.51%p). 섹터 대표는 종목 수를 줄여야 할 때 쓴다.')
        if any(not x['liq'] for x in new):
            print('   ※ 低유동 = 거래대금 상위 100 밖. 이 그룹은 7년 검정에서 일별 R5 가'
                  ' -0.5229 로 기각됐다(상위 100 은 +0.2396 통과). 비중을 낮추는 편이 안전하다.')
        print_detail(new, base, K)
    else:
        print('   없음')

    print(f'\n■ 매도 — 보유 {HOLD_DAYS}거래일 도래 {len(sell)}건 (v1.1: 손절·연장 없음, 20일째 종가 매도 고정)')
    for x in sorted(sell, key=lambda z: z['sig']):
        print(f"   {x['name'][:26]:28s} {x['code']:6s} 매수 {x['sig']} {x['buy']:>9,.0f} → "
              f"{x['cur']:>9,.0f}원  {x['pnl']:+6.1f}%  ← 오늘 종가 매도")
    if not sell:
        print('   없음')

    print(f'\n■ 보유 중 {len(hold)}건')
    for x in sorted(hold, key=lambda z: z['sig']):
        print(f"   {x['name'][:26]:28s} {x['code']:6s} 매수 {x['sig']} {x['buy']:>9,.0f} → "
              f"{x['cur']:>9,.0f}원  {x['pnl']:+6.1f}%  (잔여 {x['remain']}일)")
    if not hold:
        print('   없음')
    else:
        print_hold_check(hold, base)

    rdy = [x for x in watch if x['ready']]
    print(f'\n■ 대기 {len(watch)}건 — 추세 5조건 충족, 캔들·거래량 트리거만 미충족'
          f' (그중 내일 신호 가능 {len(rdy)}건)')
    for x in sorted(watch, key=lambda z: (not z['ready'], -z['over'])):
        f_ = ' ★내일 트리거 가능(오늘 음봉)' if x['ready'] else ''
        print(f"   {x['sec']:10s} {x['name'][:26]:28s} {x['code']:6s} {x['close']:>9,.0f}원  "
              f"MA20 {x['over']:+5.1f}%  거래량 {x['vr']:.2f}배"
              f"{'' if x['liq'] else ' 低유동'}{f_}")
    if not watch:
        print('   없음')
    if watch and not rdy:
        print('   ※ 오늘 전 종목이 양봉이라 내일 조건8(전일 음봉)이 성립하지 않는다 —'
              ' 이 목록에서 내일 신호가 날 종목은 없다.')

    print_baseline(allsig, base, K, new, hold, bear, asof)

    if a.record:
        record(asof, new, sell, hold, watch)
    return 0


if __name__ == '__main__':
    sys.exit(main())
