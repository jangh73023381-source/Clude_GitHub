#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""breadth_shadow.py — Rule BRD shadow (2026-10-27 사용자 승인 등록, 조회 전용).

Rule BRD = 시장 폭(breadth) KODEX200 타이밍. 출처: tradermonty/claude-trading-skills market-breadth-analyzer 정량화.
  폭(D) = 유동 개별주(종가>=1,000원 · 20일 평균 거래대금>=10억) 중 종가 > 자기 200일 이동평균 비율(%).
  원안 B(판정 대상): 폭 >= 50% 이면 보유, 아니면 현금.  원안 A(병기): 폭의 8일 평균 > 200일 평균이면 보유.
  KRX 일별매매는 D+1 공개 → **실전 집행 = D 신호를 D+1 종가에 반영, 수익 = D+1→D+2 KODEX200 종가**(1일 지연).
근거(2020-10~2026-09, 비용 0): 폭>=50% 지연1일 CAGR 33.4 / MDD -20.6 / Sharpe 1.59 vs 보유 27.1 / -40.8 / 0.96,
  같은 노출 무작위 타이밍 p 0.012. R1 격자 10/10 · R5 상위 10일 제거 1.31 vs 0.46 · 가격추세(KODEX200>MA200) p 0.23.
  미통과: R2 중간 구간(2022-10~2024-10) Sharpe 0.23 < 보유 0.75. → 위험 축. 보고 backtest/github_skills_20261027/.

판정(CLAUDE.md §5 Rule BRD 절): `judge_ready.py references/breadth_shadow.csv b50_minus_bench` 판정 가능 + 기록 120거래일 이상일 때
  (a) 누적 MDD 개선 (b) Sharpe 개선 (c) 누적 수익 격차 -5%p 이내. 2회 연속 미달이면 종결. 3회 연속 기록 결손도 종결 후보.
파라미터 동결: MA200 · 문턱 50% · 유동 기준 · 1일 지연. 백테스트 백필 금지(START 이후 데이터일만 기록).
선정·브리핑·Rule CB·트랙 A~D 에 반영하지 않는다.

데이터: 종가 이력은 backtest/breadth_px.csv(date,code,close,value) — krx_api.call 로 빠진 날짜만 채운다(멱등, 조회 전용).
  키는 krx_api 가 읽고 출력하지 않는다. KODEX200 종가는 backtest/panel_ohlc_2y.csv(069500).
열 — 한 행 = 데이터일 D: n(유동·MA200 산출 종목 수) · breadth · b8 · b200 · pos_b50 · pos_a ·
  kodex_next(D+1→D+2 %) · b50_day · b50_minus_bench · a_day · a_minus_bench
사용: python3 breadth_shadow.py --fetch --record --score --report  (--backfill YYYYMMDD 로 이력 최초 구축)
"""
import argparse, csv, os, sys, time, statistics
from datetime import datetime, timedelta
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE)
LOOP = os.path.dirname(REF)
sys.path.insert(0, HERE); sys.path.insert(0, LOOP)
TRACK = os.path.join(REF, 'breadth_shadow.csv')
PX = os.path.join(LOOP, 'backtest', 'breadth_px.csv')
PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
START = '20261027'
MA, TH, LIQ_PX, LIQ_VAL, KEEP = 200, 50.0, 1000.0, 1e9, 520
FIELDS = ['date', 'n', 'breadth', 'b8', 'b200', 'pos_b50', 'pos_a', 'kodex_next', 'b50_day', 'b50_minus_bench', 'a_day', 'a_minus_bench']


def px_dates():
    if not os.path.exists(PX):
        return set()
    with open(PX, encoding='utf-8') as f:
        return {r['date'] for r in csv.DictReader(f)}


def fetch(since, until, budget=150):
    """빠진 평일을 KRX 에서 받아 PX 에 덧붙인다. 휴장일은 0행. 예산(초) 초과 시 다음 호출에서 이어받는다."""
    import krx_api as K
    have = px_dates(); t0 = time.time(); add = 0
    d = datetime.strptime(since, '%Y%m%d'); end = datetime.strptime(until, '%Y%m%d')
    new = not os.path.exists(PX)
    with open(PX, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['date', 'code', 'close', 'value'])
        while d <= end:
            ds = d.strftime('%Y%m%d'); d += timedelta(days=1)
            if datetime.strptime(ds, '%Y%m%d').weekday() >= 5 or ds in have:
                continue
            if time.time() - t0 > budget:
                print(f'  [brd] 예산 초과 — {ds} 부터 다음 호출에서 이어받음'); break
            rows = []
            for path in ('sto/stk_bydd_trd', 'sto/ksq_bydd_trd'):
                st, data = K.call(path, basDd=ds)
                if st != 'ok':
                    print(f'  [brd] {ds} {path} {st} — 중단'); return add
                rows += K.rows(data)
            if not rows:
                continue                      # 휴장일 또는 미공개(D+1 전) — 기록하지 않아 다음에 다시 시도
            for r in rows:
                code = r.get('ISU_SRT_CD') or r.get('ISU_CD'); c = r.get('TDD_CLSPRC'); v = r.get('ACC_TRDVAL')
                if code and c not in (None, '', '-'):
                    w.writerow([ds, code, c, v]); add += 1
            f.flush()
    print(f'  [brd] 종가 이력 +{add}행'); return add


def series():
    """날짜별 폭(%) — 유동 종목 중 종가>MA200 비율. 반환: [(date, n, breadth)]"""
    hist = {}
    with open(PX, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                hist.setdefault(r['code'], {})[r['date']] = (float(r['close']), float(r['value'] or 0))
            except ValueError:
                continue
    ds = sorted({d for h in hist.values() for d in h})[-KEEP:]
    pos = {d: i for i, d in enumerate(ds)}
    import numpy as np
    Cm = np.full((len(ds), len(hist)), np.nan); Vm = np.full_like(Cm, np.nan)
    for j, h in enumerate(hist.values()):
        for d, (c, v) in h.items():
            i = pos.get(d)
            if i is not None:
                Cm[i, j] = c; Vm[i, j] = v
    out = []
    for i in range(MA - 1, len(ds)):
        w = Cm[i - MA + 1:i + 1]; full = np.isfinite(w).all(0)
        v20 = np.nanmean(Vm[max(i - 19, 0):i + 1], 0)
        ok = full & (Cm[i] >= LIQ_PX) & (v20 >= LIQ_VAL)
        if ok.sum() < 100:
            continue
        ma = w[:, ok].mean(0)
        out.append((ds[i], int(ok.sum()), float((Cm[i, ok] > ma).mean() * 100)))
    return out


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


def cmd_record():
    if not os.path.exists(PX):
        print('  [brd] 종가 이력 없음 — --backfill 먼저'); return 0
    S = series()
    if not S:
        print('  [brd] MA200 산출 불가(이력 부족)'); return 0
    br = [b for _, _, b in S]
    rows = load(); have = {r['date'] for r in rows}; new = 0
    for i, (d, n, b) in enumerate(S):
        if d < START or d in have:
            continue
        b8 = statistics.mean(br[max(i - 7, 0):i + 1]) if i >= 7 else None
        b200 = statistics.mean(br[i - 199:i + 1]) if i >= 199 else None
        rows.append(dict(date=d, n=n, breadth=f'{b:.2f}', b8='' if b8 is None else f'{b8:.2f}',
                         b200='' if b200 is None else f'{b200:.2f}', pos_b50=str(int(b >= TH)),
                         pos_a='' if b200 is None else str(int(b8 > b200))))
        new += 1
    if new:
        save(rows)
    print(f'  [brd] 기록 {new}행 추가 (누적 {len(rows)}행)'); return 0


def kodex():
    out = {}
    if os.path.exists(PANEL):
        with open(PANEL, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r.get('code') == '069500':
                    try:
                        out[r['date']] = float(r['close'])
                    except (ValueError, KeyError):
                        pass
    return out


def cmd_score():
    K = kodex(); ds = sorted(K); rows = load(); n = 0
    try:
        import ensure_data
        ds = [d for d in ds if ensure_data.settled(d)]
    except Exception:
        pass
    for r in rows:
        if r.get('kodex_next'):
            continue
        later = [d for d in ds if d > r['date']]
        if len(later) < 2:
            continue
        k = (K[later[1]] / K[later[0]] - 1) * 100                 # D+1 종가 → D+2 종가 (1일 지연 집행)
        r['kodex_next'] = f'{k:.4f}'
        p = int(r['pos_b50']); r['b50_day'] = f'{p * k:.4f}'; r['b50_minus_bench'] = f'{p * k - k:.4f}'
        if r.get('pos_a') not in (None, ''):
            a = int(r['pos_a']); r['a_day'] = f'{a * k:.4f}'; r['a_minus_bench'] = f'{a * k - k:.4f}'
        n += 1
    if n:
        save(rows)
    print(f'  [brd] 채점 {n}행'); return 0


def perf(xs):
    eq = 1.0; peak = 1.0; mdd = 0.0
    for x in xs:
        eq *= 1 + x / 100; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    sh = (statistics.mean(xs) / statistics.stdev(xs) * 245 ** .5) if len(xs) > 2 and statistics.stdev(xs) > 0 else float('nan')
    return (eq - 1) * 100, mdd * 100, sh


def cmd_report():
    allr = load()
    if allr:
        L = allr[-1]
        print(f"  [brd] 최근 {L['date']} 폭 {float(L['breadth']):.1f}% (유동 {L['n']}종) → 원안B {'보유' if L['pos_b50'] == '1' else '현금'}"
              + (f" · 원안A {'보유' if L['pos_a'] == '1' else '현금'}" if L.get('pos_a') else ''))
    rows = [r for r in allr if r.get('kodex_next')]
    if len(rows) < 3:
        print(f'  [brd] 채점 {len(rows)}일 — 성과 집계 보류'); return 0
    a = perf([float(r['b50_day']) for r in rows]); b = perf([float(r['kodex_next']) for r in rows])
    expo = sum(int(r['pos_b50']) for r in rows) / len(rows) * 100
    print(f'  [brd] {len(rows)}일 · 노출 {expo:.0f}% · 폭≥50% 누적 {a[0]:+.2f}% MDD {a[1]:.2f}% Sh {a[2]:.2f} | '
          f'KODEX200 누적 {b[0]:+.2f}% MDD {b[1]:.2f}% Sh {b[2]:.2f}')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backfill', metavar='YYYYMMDD', help='종가 이력 최초 구축 시작일(예산 단위로 이어받기)')
    ap.add_argument('--fetch', action='store_true'); ap.add_argument('--record', action='store_true')
    ap.add_argument('--score', action='store_true'); ap.add_argument('--report', action='store_true')
    ap.add_argument('--budget', type=float, default=60)
    a = ap.parse_args(); today = datetime.now().strftime('%Y%m%d')
    if a.backfill:
        fetch(a.backfill, today, a.budget)
    if a.fetch:
        last = max(px_dates() or {'20241101'})
        fetch((datetime.strptime(last, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d'), today, a.budget)
    if a.record: cmd_record()
    if a.score: cmd_score()
    if a.report or not (a.record or a.score or a.fetch or a.backfill): cmd_report()
    return 0


if __name__ == '__main__':
    sys.exit(main())
