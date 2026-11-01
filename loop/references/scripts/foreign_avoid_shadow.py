#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""foreign_avoid_shadow.py — Rule FIA shadow (2026-10-22 사용자 승인 등록, 조회 전용).

Rule FIA = 외국인 대량 순매도 다음 날 KODEX200 '장중 회피'.
  데이터일 D 의 코스피 외국인 순매수(**장 마감 후 최종 집계**, 억원) ÷ 코스피 종가 가 2019 이후 확장창 분포(직전일까지)의
  하위 20% 이하이면 신호 → D+1 **시가에 매도하고 같은 날 종가에 재매수**(D+1 시가→종가 구간만 현금).
  수익(종가 기준): 신호 없음 = D→D+1 종가 수익 / 신호 = D 종가→D+1 시가(갭)만. 현금 0 · 비용 0(v2.8, 스프레드 미반영).
근거(2019-06~2026-09, 7년 ETF 패널, `backtest/intraday_flow/use.py`, 신호 461일): KODEX200 시가→시가 보유 Sh 0.87·CAGR 22.3·MDD −39.9
  → 회피 Sh 1.26·30.9·−32.2 · 무작위 같은 일수 대조 p=0.014 · 3분할 Sharpe 3/3 개선 · R5 상위3일 제거 +0.006.
  약점: 신호일 장중 차 t −1.34 · R5 상위5일 제거 −0.002 · 다중검정 미달 · 연 약 60회 왕복 · 지수 시가 착시 제거 후 효과 절반.
  **[6-1] LV 픽 적용은 기각(2026-10-22).** 장중 잠정 수급으로 판단하지 말 것(10/22: 15:00 −2,319억 → 최종 +592억).

판정(CLAUDE.md §5 Rule FIA): `judge_ready.py references/foreign_avoid_shadow.csv fia_minus_bench --event sig` 판정 가능 + **기록 120거래일 이상**일 때
(a) 누적 MDD 가 KODEX200 보유 대비 개선 (b) Sharpe 개선 (c) 누적 수익 격차 −5%p 이내. **2회 연속 미달이면 종결.**
**동결**: 하위 20% · 확장창 · 최종 집계 · KODEX200 시가 매도/종가 재매수. 백필 금지(START 이후만 기록).
선정·브리핑·Rule CB·트랙 A~D·Rule LV 에 반영하지 않는다.

열 — 한 행 = 데이터일 D: foreign(억원) · fn(=foreign/코스피) · thr · sig(1/0)
  · kodex_day(D→D+1 종가 %) · gap_day(D 종가→D+1 시가 %) · fia_day · fia_minus_bench
사용: python3 foreign_avoid_shadow.py --record --score --report   (멱등, 빠진 날 자동 회수)
"""
import argparse, csv, os, re, statistics, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE)
LOOP = os.path.dirname(REF)
sys.path.insert(0, HERE)
TRACK = os.path.join(REF, 'foreign_avoid_shadow.csv')
CACHE = os.path.join(REF, 'foreign_flow_cache.csv')
PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
START = '20261022'
CODE = '069500'; Q = 0.2; MINQ = 120
FIELDS = ['date', 'foreign', 'fn', 'thr', 'sig', 'kodex_day', 'gap_day', 'fia_day', 'fia_minus_bench']
UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.naver.com/'}


def load():
    return list(csv.DictReader(open(TRACK, encoding='utf-8'))) if os.path.exists(TRACK) else []


def save(rows):
    import safe_io
    tmp = TRACK + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for r in sorted(rows, key=lambda x: x['date']):
            w.writerow({k: r.get(k, '') for k in FIELDS})
    if os.path.exists(TRACK):
        safe_io.safe_replace(tmp, TRACK)
    else:
        os.rename(tmp, TRACK)


def refresh():
    """코스피 종가(네이버 siseJson)와 외국인 최종 순매수(네이버 index trend)를 캐시에 멱등 보충. 당일은 16:30 이후만."""
    try:
        import requests
    except Exception:
        return
    cache = {r['date']: r for r in csv.DictReader(open(CACHE, encoding='utf-8'))}
    now = dt.datetime.utcnow() + dt.timedelta(hours=9); today = now.strftime('%Y%m%d')
    try:
        start = (now - dt.timedelta(days=40)).strftime('%Y%m%d')
        t = requests.get(f'https://api.finance.naver.com/siseJson.naver?symbol=KOSPI&requestType=1&startTime={start}&endTime={today}&timeframe=day',
                         headers=UA, timeout=15).text
        kos = {}
        for rr in re.findall(r"\[([^\[\]]*)\]", t)[1:]:
            p = [x.strip().strip("'\"") for x in rr.split(',')]
            if p[0].isdigit(): kos[p[0]] = p[4]
    except Exception as e:
        print(f'  [fia] 코스피 조회 실패 — 캐시 사용 ({type(e).__name__})'); return
    add = 0
    for d in sorted(kos):
        if d in cache or (d == today and (now.hour, now.minute) < (16, 30)):
            continue
        try:
            j = requests.get('https://m.stock.naver.com/api/index/KOSPI/trend?bizdate=' + d, headers=UA, timeout=10).json()
            if j.get('bizdate') != d: continue
            fv = int(str(j['foreignValue']).replace(',', '').replace('+', ''))
            if fv == 0 and int(str(j['personalValue']).replace(',', '').replace('+', '')) == 0: continue
            cache[d] = {'date': d, 'foreign': str(fv), 'kospi': kos[d]}; add += 1
        except Exception:
            continue
    if add:
        tmp = CACHE + '.tmp'
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['date', 'foreign', 'kospi']); w.writeheader()
            for d in sorted(cache): w.writerow(cache[d])
        os.replace(tmp, CACHE)


def quant(v, q):
    v = sorted(v); k = (len(v) - 1) * q; f = int(k); c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def bars():
    out = {}
    if os.path.exists(PANEL):
        for r in csv.DictReader(open(PANEL, encoding='utf-8')):
            if r.get('code') == CODE:
                try: out[r['date']] = (float(r['open']), float(r['close']))
                except (ValueError, KeyError): pass
    return out


def cmd_record():
    refresh()
    rows_c = sorted(csv.DictReader(open(CACHE, encoding='utf-8')), key=lambda r: r['date'])
    fn = [(r['date'], int(r['foreign']), float(r['foreign']) / float(r['kospi'])) for r in rows_c]
    rows = load(); have = {r['date'] for r in rows}; new = 0
    for i, (d, fv, x) in enumerate(fn):
        if d < START or d in have:
            continue
        hist = [v for (dd, _, v) in fn[:i]]
        if len(hist) < MINQ: continue
        th = quant(hist, Q); s = 1 if x <= th else 0
        rows.append(dict(date=d, foreign=str(fv), fn=f'{x:.4f}', thr=f'{th:.4f}', sig=str(s))); new += 1
    if new: save(rows)
    print(f'  [fia] 기록 {new}행 추가 (누적 {len(rows)}행)'); return 0


def cmd_score():
    B = bars(); ds = sorted(B); rows = load(); n = 0
    for r in rows:
        if r.get('kodex_day') or r['date'] not in B: continue
        i = ds.index(r['date'])
        if i + 1 >= len(ds): continue
        try:
            import ensure_data
            if not ensure_data.settled(ds[i + 1]): continue
        except Exception:
            pass
        c0 = B[r['date']][1]; o1, c1 = B[ds[i + 1]]
        k = (c1 / c0 - 1) * 100; g = (o1 / c0 - 1) * 100; fia = g if r['sig'] == '1' else k
        r['kodex_day'] = f'{k:.4f}'; r['gap_day'] = f'{g:.4f}'; r['fia_day'] = f'{fia:.4f}'; r['fia_minus_bench'] = f'{fia - k:.4f}'; n += 1
    if n: save(rows)
    print(f'  [fia] 채점 {n}행'); return 0


def perf(xs):
    eq = peak = 1.0; mdd = 0.0
    for x in xs:
        eq *= 1 + x / 100; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    sh = (statistics.mean(xs) / statistics.stdev(xs) * 245 ** .5) if len(xs) > 2 and statistics.stdev(xs) > 0 else float('nan')
    return (eq - 1) * 100, mdd * 100, sh


def cmd_report():
    allr = load()
    if allr:
        l = allr[-1]
        msg = '★신호 — 다음 거래일 시가 매도·종가 재매수(참고)' if l['sig'] == '1' else '신호 없음 — 그대로 보유'
        print(f"  [fia] {l['date']} 외국인 {int(l['foreign']):+,}억 · 기준선 {float(l['thr'])*float(l['foreign'])/float(l['fn']) if float(l['fn']) else 0:+,.0f}억 → {msg}")
    rows = [r for r in allr if r.get('kodex_day')]
    if len(rows) < 3:
        print(f'  [fia] 채점 {len(rows)}일 — 성과 집계 보류'); return 0
    a = perf([float(r['fia_day']) for r in rows]); b = perf([float(r['kodex_day']) for r in rows])
    ns = sum(r['sig'] == '1' for r in rows)
    print(f'  [fia] {len(rows)}일(신호 {ns}) · FIA 누적 {a[0]:+.2f}% MDD {a[1]:.2f}% Sh {a[2]:.2f} | KODEX200 누적 {b[0]:+.2f}% MDD {b[1]:.2f}% Sh {b[2]:.2f}')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', action='store_true'); ap.add_argument('--score', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args(); rc = 0
    if a.record: rc |= cmd_record()
    if a.score: rc |= cmd_score()
    if a.report or not (a.record or a.score): rc |= cmd_report()
    return rc


if __name__ == '__main__':
    sys.exit(main())
