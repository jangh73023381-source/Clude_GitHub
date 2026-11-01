# -*- coding: utf-8 -*-
"""bt_chb_etf_20260826.py — Rule CHB **ETF 트랙** 승격 검정 (iteration 10 지정 가설).

2026-08-25 로그가 지정한 distinct 축을 그대로 수행한다:
  "업종별 구성종목 채널위치 분포 점수를 ETF 랭킹으로 전이한다."

원자료
  개별주  : backtest/stk500_ohlc.csv  (시총 상위 500 · 키움 ka10081 수정주가 · 조회 전용)
  업종    : backtest/stock_sector_dart.csv  (DART induty 2자리)
  ETF 버킷: backtest/etf_sector_map.csv     (기초지수명 키워드 → 19버킷, 신규 API 호출 0회)
  ETF 가격: backtest/panel_ohlc_2y.csv      (601거래일)

★ 타 taxonomy 교차 — 사전 등록 크로스워크(R3 정의 교체 재현의 대상)
  ETF 버킷(19종)과 DART induty(2자리)는 다른 분류 체계다. 아래 CROSSWALK 는 이 검정을
  위해 **한 번 정의하고 스윕하지 않는다**. 이 매핑에 성능이 의존하면 그것이 곧 과적합이며
  R3 에서 걸러야 한다.

★ 하네스 함정 (2026-08-22 실측) — 동점 타이브레이크가 룩어헤드가 된다.
  정렬 키를 반드시 지표만으로 명시한다. 수익률을 튜플에 넣고 sorted() 하지 않는다.

채점: v2.3 P&L 1차 지표 — 픽5 동일가중 D→D+1 종가, 비용 0(v2.8), **KODEX200 대비 %p/일**.
"""
import csv
import os
import random
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import eligible  # noqa: E402

STK = os.path.join(HERE, 'stk500_ohlc.csv')
SEC = os.path.join(HERE, 'stock_sector_dart.csv')
EMAP = os.path.join(HERE, 'etf_sector_map.csv')
PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')

BENCH = '069500'          # KODEX 200
LOOKBACK = 120            # 채널 룩백 (8/22 고원 확인값)
HIGH_BANDS = ((0.75, 0.85), (0.95, 1.00))   # 8/22 고원 구간
NPICK = 5
MOM = 20

# ETF 버킷 → DART induty 2자리 (사전 등록·스윕 금지)
CROSSWALK = {
    '반도체':    {'26'},
    'IT':        {'26', '58', '62', '63'},
    '바이오':    {'21'},
    '은행금융':  {'64'},
    '증권':      {'66'},
    '2차전지':   {'20', '28'},
    '건설':      {'41'},
    '자동차':    {'30'},
    '조선':      {'31'},
    '방산우주':  {'25', '31'},
    '철강소재':  {'24'},
    '화장품':    {'20'},
    '전력':      {'28', '35'},
    '원자력':    {'28', '35'},
    '신재생':    {'28'},
    '금속귀금속': {'24'},
    '로봇':      {'29'},
    '소비재':    {'10', '47'},
}
# '지수' 버킷(365종)은 특정 업종이 없으므로 제외한다.


def load_stocks():
    sec = {}
    for r in csv.DictReader(open(SEC, encoding='utf-8')):
        sec[r['code']] = (r['induty_code'] or '')[:2]
    px = {}
    for r in csv.DictReader(open(STK, encoding='utf-8')):
        s = sec.get(r['code'], '')
        if not s:
            continue
        try:
            px.setdefault(r['code'], []).append(
                (r['date'], float(r['high']), float(r['low']), float(r['close'])))
        except ValueError:
            continue
    for c in px:
        px[c].sort()
    return px, sec


def load_panel():
    px, name = {}, {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            px.setdefault(r['code'], {})[r['date']] = float(r['close'])
        except ValueError:
            continue
        name[r['code']] = r['name']
    return px, name


def sector_scores(stk, sec):
    """날짜 → induty2 → 고채널 비중(breadth)."""
    ch = {}                                   # date -> induty -> [0/1,...]
    for code, bars in stk.items():
        s = sec.get(code, '')
        if not s:
            continue
        n = len(bars)
        for i in range(LOOKBACK, n):
            win = bars[i - LOOKBACK + 1:i + 1]
            hi = max(b[1] for b in win)
            lo = min(b[2] for b in win)
            if hi <= lo:
                continue
            pos = (bars[i][3] - lo) / (hi - lo)
            hit = any(a <= pos <= b for a, b in HIGH_BANDS)
            ch.setdefault(bars[i][0], {}).setdefault(s, []).append(1 if hit else 0)
    out = {}
    for d, m in ch.items():
        out[d] = {s: sum(v) / len(v) for s, v in m.items() if len(v) >= 3}
    return out


def etf_bucket():
    b = {}
    for r in csv.DictReader(open(EMAP, encoding='utf-8')):
        s = r['sector']
        if s and s in CROSSWALK:
            b[r['code']] = s
    return b


_CACHE = {}


def prep():
    if not _CACHE:
        stk, sec = load_stocks()
        _CACHE['scores'] = sector_scores(stk, sec)
        _CACHE['bucket0'] = etf_bucket()
        px, name = load_panel()
        _CACHE['px'], _CACHE['name'] = px, name
        _CACHE['dates'] = sorted(set(px.get(BENCH, {})))
    return _CACHE


def run(shuffle_seed=None):
    c = prep()
    scores, px, name, dates = c['scores'], c['px'], c['name'], c['dates']
    bucket = dict(c['bucket0'])

    if shuffle_seed is not None:                  # R4 플라시보 — 라벨 셔플
        rnd = random.Random(shuffle_seed)
        ks = list(bucket)
        vs = [bucket[k] for k in ks]
        rnd.shuffle(vs)
        bucket = dict(zip(ks, vs))

    rows = []
    for i in range(MOM + 1, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        sc = scores.get(d)
        if not sc:
            continue
        d20 = dates[i - MOM]
        cand = []
        for code, bk in bucket.items():
            if not eligible(name.get(code, "")):
                continue
            p = px.get(code)
            if not p or d not in p or nxt not in p or d20 not in p or p[d20] <= 0:
                continue
            vals = [sc[s] for s in CROSSWALK[bk] if s in sc]
            if not vals:
                continue
            cand.append({
                'code': code,
                'chb': sum(vals) / len(vals),
                'mom': p[d] / p[d20] - 1.0,
                'ret': (p[nxt] / p[d] - 1.0) * 100.0,
            })
        if len(cand) < NPICK * 3:
            continue
        # 정렬 키를 지표만으로 명시 — 수익률을 키에 넣지 않는다(룩어헤드 방지).
        cand.sort(key=lambda x: (-x['chb'], -x['mom'], x['code']))
        pick = cand[:NPICK]
        bp = px[BENCH]
        if d not in bp or nxt not in bp:
            continue
        bench = (bp[nxt] / bp[d] - 1.0) * 100.0
        rows.append((d, sum(x['ret'] for x in pick) / NPICK - bench))
    return rows


def stats(v):
    if len(v) < 2:
        return 0.0, 0.0, 0
    m = st.mean(v)
    sd = st.stdev(v)
    t = m / (sd / len(v) ** 0.5) if sd else 0.0
    return m, t, len(v)


def report(rows, label):
    v = [x[1] for x in rows]
    m, t, n = stats(v)
    print(f'{label:<28} n={n:4d}  평균 {m:+.4f}%p  t={t:+.2f}  '
          f'승률 {sum(1 for x in v if x > 0) / len(v) * 100:.1f}%')
    return m, t, n


if __name__ == '__main__':
    rows = run()
    print('=== Rule CHB ETF 트랙 (iteration 10) ===')
    m, t, n = report(rows, '전체')
    k = len(rows) // 2
    report(rows[:k], '  train(전반)')
    report(rows[k:], '  test(후반)')
    f = len(rows) // 3
    _, _, _ = report(rows[:f], '  fold1')
    report(rows[f:2 * f], '  fold2')
    m3, t3, _ = report(rows[2 * f:], '  fold3(최근)')

    v = [x[1] for x in rows]
    sv = sorted(v, reverse=True)
    for kk in (1, 3, 5, 10):
        rest = sv[kk:]
        print(f'  R5 상위{kk:2d}일 제거 후 평균 {st.mean(rest):+.4f}%p')
    print(f'  R5 중앙값 {st.median(v):+.4f}%p')

    print('  R4 플라시보(라벨 셔플 200회) 실행...')
    obs, ge = m, 0
    for s in range(200):
        r = run(shuffle_seed=s)
        if r and st.mean([x[1] for x in r]) >= obs:
            ge += 1
    print(f'  R4 경험적 p = {ge / 200:.4f}  (관측 {obs:+.4f}%p)')
