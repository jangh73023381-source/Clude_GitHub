# -*- coding: utf-8 -*-
"""데일리 브리핑 [1-5] 외국인 수급 전환 확률표 — 생성기 (2026-10-21 신설, fable/CLAUDE.md 28번).

무엇: 코스피 외국인 '직전 20거래일 누적 순매수'가 플러스로 돌아서는 첫 주가 언제일지, 주별 확률(앞으로 40거래일).
방법: 과거 일별 외국인 순매수(현재 지수 수준으로 규모 환산)를 10일 블록으로 이어 붙인 경로 N개 시뮬레이션.
      두 표본의 평균 = (7년 중 순매도 국면이던 날) + (2026년). 7년 전체 표본은 매수기까지 섞여 낙관적이라 참고로만 낸다.
성격: **참고 전용 — 선정 로직 반영 금지.** 예측 신호로 검정한 적이 없다.
데이터: 네이버 모바일 index trend API(코스피 투자자별, 억원) · 네이버 siseJson(코스피 지수). 조회 전용, 무인증.
캐시: _foreign_turn_investor.csv · _foreign_turn_kospi.csv (멱등 보충), 실패 시 캐시만 쓰고 stale=true.

    python3 foreign_turn_ref.py --json
"""
import os, sys, json, re, datetime as dt
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
INV = os.path.join(HERE, '_foreign_turn_investor.csv')
KOS = os.path.join(HERE, '_foreign_turn_kospi.csv')
UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.naver.com/'}
HOLIDAYS = {'20261225', '20261231', '20270101', '20270208', '20270209', '20270301'}  # 2027 설 연휴는 추정
N_SIM, BLOCK, SEED = 6000, 10, 42
HORIZON = 40   # 앞으로 몇 거래일까지 볼지 (사용자 지시 2026-10-21)

FOOTNOTE = ("※ **참고 전용 — 선정에 반영하지 않습니다.** '전환'은 하루 순매수가 아니라 외국인 **20거래일 누적 순매수가 "
            "플러스**로 바뀌는 것입니다. 과거 수급 패턴만으로 만든 통계 추정이며 예측이 아닙니다(금리·환율 등 거시 조건은 "
            "7년 검정에서 시점 예측력이 없어 넣지 않았습니다).")


def _today():
    return dt.datetime.utcnow() + dt.timedelta(hours=9)


def refresh():
    """캐시에 없는 날짜만 보충. 성공 여부 반환."""
    import requests
    ok = True
    try:
        t = requests.get('https://api.finance.naver.com/siseJson.naver?symbol=KOSPI&requestType=1'
                         '&startTime=20190101&endTime=20991231&timeframe=day', headers=UA, timeout=20).text
        rows = []
        for rr in re.findall(r"\[([^\[\]]*)\]", t)[1:]:
            p = [x.strip().strip("'\"") for x in rr.split(',')]
            if p[0].isdigit():
                rows.append((p[0], float(p[4])))
        if len(rows) > 1000:
            pd.DataFrame(rows, columns=['date', 'kospi']).to_csv(KOS + '.tmp', index=False)
            os.replace(KOS + '.tmp', KOS)
    except Exception:
        ok = False
    k = pd.read_csv(KOS, dtype={'date': str})
    inv = pd.read_csv(INV, dtype={'date': str})
    now = _today()
    todo = [d for d in k.date if d not in set(inv.date)]
    # 오늘 날짜는 16:00 이후에만(장중 미확정 수치 유입 방지)
    todo = [d for d in todo if d < now.strftime('%Y%m%d') or now.hour >= 16]
    new = []
    for d in todo[-40:]:
        try:
            j = requests.get('https://m.stock.naver.com/api/index/KOSPI/trend?bizdate=' + d, headers=UA, timeout=10).json()
            if j.get('bizdate') != d:
                continue
            f = lambda s: int(str(s).replace(',', '').replace('+', ''))
            new.append((d, f(j['personalValue']), f(j['foreignValue']), f(j['institutionalValue'])))
        except Exception:
            ok = False
    if new:
        inv = pd.concat([inv, pd.DataFrame(new, columns=['date', 'indiv', 'foreign', 'inst'])])
        inv.drop_duplicates('date').sort_values('date').to_csv(INV + '.tmp', index=False)
        os.replace(INV + '.tmp', INV)
    return ok


def compute():
    inv = pd.read_csv(INV, dtype={'date': str})
    inv = inv[(inv[['indiv', 'foreign', 'inst']] != 0).any(axis=1)]
    k = pd.read_csv(KOS, dtype={'date': str})
    d = inv.merge(k, on='date').sort_values('date').reset_index(drop=True)
    K = d.kospi.iloc[-1]
    d['f'] = d.foreign * (K / d.kospi)
    d['s20'] = d.f.rolling(20).sum()
    asof = d.date.iloc[-1]
    last20 = list(d.foreign.values[-20:])
    s20 = int(sum(last20))
    # 연속 순매도 국면 일수(정규화 20일 누적 < 0)
    neg = (d.s20 < 0).values
    run = 0
    for v in neg[::-1]:
        if v: run += 1
        else: break
    # 앞으로 HORIZON 거래일(2026-10-21 사용자 지시: +40거래일 롤링)
    start = pd.Timestamp(asof) + pd.Timedelta(days=1)
    days = [x for x in pd.bdate_range(start, start + pd.Timedelta(days=90)) if x.strftime('%Y%m%d') not in HOLIDAYS][:HORIZON]
    wk = [(x - pd.Timedelta(days=x.weekday())) for x in days]
    H = len(days)
    pools = {'regime': d.f.values[neg], 'y2026': d.f.values[(d.date >= f'{asof[:4]}0101').values], 'all': d.f.values}
    rng = np.random.default_rng(SEED)
    first = {}
    for nm, pool in pools.items():
        pool = pool[~np.isnan(pool)]
        n = len(pool); fs = np.full(N_SIM, -1)
        for s in range(N_SIM):
            path = []
            while len(path) < H:
                st = rng.integers(0, n - BLOCK); path += list(pool[st:st + BLOCK])
            w = np.array(last20 + path[:H], float)
            c = np.convolve(w, np.ones(20), 'valid')[1:]      # t 일째 끝나는 20일 합
            hit = np.where(c > 0)[0]
            fs[s] = hit[0] if len(hit) else -1
        first[nm] = fs
    W = list(dict.fromkeys(wk))
    wkarr = np.array(wk)
    rows, cum = [], 0.0
    for w in W:
        idx = np.where(wkarr == w)[0]
        p = {nm: float(np.isin(fs, idx).mean()) * 100 for nm, fs in first.items()}
        pb = (p['regime'] + p['y2026']) / 2; cum += pb
        lo, hi = days[idx[0]], days[idx[-1]]
        rows.append(dict(week=f"{lo.month}/{lo.day}~{hi.month}/{hi.day}", ndays=int(len(idx)), prob=round(pb, 1), cum=round(cum, 1),
                         regime=round(p['regime'], 1), y2026=round(p['y2026'], 1), all=round(p['all'], 1)))
    # 같은 금액을 매일 순매수할 때 t 일째 전환에 필요한 하루 평균(억원)
    need = [dict(t=t, date=days[t - 1].strftime('%m/%d'), eok=int(round(-sum(last20[t:]) / t)))
            for t in (5, 10, 15) if t <= H]
    # 이번 주(asof 가 속한 주) 누적과 주간 순매수 확률 기저
    d['dt'] = pd.to_datetime(d.date); d['wk'] = d.dt.dt.to_period('W')
    g = d.groupby('wk').agg(f=('foreign', 'sum'), s=('s20', 'first'), y=('date', 'first'))
    wk_now = int(d[d.wk == d.wk.iloc[-1]].foreign.sum())
    weekly_base = dict(regime=round(float((g[g.s < 0].f > 0).mean()) * 100, 0),
                       y2026=round(float((g[g.y >= f'{asof[:4]}0101'].f > 0).mean()) * 100, 0))
    last5 = [dict(date=r.date, foreign=int(r.foreign), inst=int(r.inst), indiv=int(r.indiv)) for r in d.tail(5).itertuples()]
    yr_end = rows[-1]['cum'] if rows else 0
    peak = max(rows, key=lambda r: r['prob']) if rows else None
    summary = (f"외국인 20일 누적 {s20/1e4:+.1f}조 · 순매도 국면 {run}일째 → 20일 누적 플러스 전환 확률: "
               f"가장 높은 주 {peak['week']} {peak['prob']:.0f}% · 40거래일({days[-1].month}/{days[-1].day})까지 누적 {yr_end:.0f}%"
               if peak else '')
    return dict(horizon=HORIZON, horizon_end=days[-1].strftime('%Y%m%d'), asof=asof, s20_eok=s20, regime_days=run, rows=rows, need=need, last5=last5, week_now_eok=wk_now,
                weekly_base=weekly_base, yr_end_cum=yr_end, summary=summary, footnote=FOOTNOTE,
                n_sim=N_SIM, block=BLOCK, kospi=float(K))


def main():
    stale = False
    try:
        stale = not refresh()
    except Exception:
        stale = True
    out = compute()
    out['stale'] = stale
    out['stale_days'] = (pd.Timestamp(_today().date()) - pd.Timestamp(out['asof'])).days
    if '--json' in sys.argv:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(out['summary'])
        for r in out['rows']:
            print(f"{r['week']:12s} {r['ndays']}일 {r['prob']:5.1f}% 누적 {r['cum']:5.1f}%  (국면 {r['regime']} · 2026 {r['y2026']} · 7년 {r['all']})")
        print('필요 일평균', out['need'], '이번 주', out['week_now_eok'], 'stale', stale)


if __name__ == '__main__':
    main()
