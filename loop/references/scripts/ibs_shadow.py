#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ibs_shadow.py — Rule IBS shadow (2026-10-21 사용자 승인 등록, 조회 전용).

Rule IBS = KODEX200(069500) 하루 단위 역추세 타이밍. IBS = (종가−저가)/(고가−저가).
  데이터일 D 의 IBS < 0.2 이면 D 종가에 진입(보유 상태로 전환), IBS > 0.8 이면 D 종가에 청산(현금 전환).
  그 사이에는 상태를 유지한다. 포지션 수익 = 상태 × (D→D+1 KODEX200 종가 수익). 현금 수익 0, 비용 0(v2.8).
출처: GitHub 퀀트 고전 규칙(IBS mean reversion) — 검정 `backtest/github_skills_20261020/README_GitHub추가검정_2026-10-21.md` 3절.
근거(2020-04~2026-09 1,621일): CAGR 28.3 / MDD −22.5 / Sharpe 1.25 / 노출 46%  vs 보유 27.2 / −40.8 / 0.97.
  같은 노출·같은 보유 블록 무작위 타이밍 1,000회 p=0.021 · R1 15칸 중 13칸 Sharpe>보유 · R2 3분할 Sharpe 3/3 우위
  · R3 TIGER200·RISE200·200IT·반도체·코스닥150 재현(미국나스닥100·은행 열위) · R5 상위 10일 제거 시 보유일 평균=무조건 평균.
→ Rule LV·MLV 처럼 **위험 축**(MDD 절반, CAGR 동률)이다. 이득의 77%가 밤사이 갭이다.

판정(CLAUDE.md §5 Rule IBS 절): `judge_ready.py references/ibs_shadow.csv ibs_minus_bench` 가 판정 가능을 내고
**기록 120거래일 이상**일 때 (a) 누적 MDD 가 KODEX200 보유 대비 개선 (b) Sharpe 개선 (c) 누적 수익 격차 −5%p 이내.
**2회 연속 미달이면 종결.** 3회 연속 기록 결손도 종결 후보.
**파라미터 동결**: 진입 0.2 · 청산 0.8 · KODEX200 · 종가 집행. 백테스트 백필 금지(START 이후만 기록).
선정·브리핑·Rule CB·트랙 A~D 에 반영하지 않는다. 실전 근사(15:20 가격 IBS)는 장중알림 참고 알림으로만 낸다.

열 — 한 행 = 데이터일 D.
  ibs : D 의 IBS · pos : D 종가 이후 상태(1 보유 / 0 현금) · kodex_day : D→D+1 KODEX200 종가 수익(%)
  ibs_day = pos × kodex_day · ibs_minus_bench = ibs_day − kodex_day (judge_ready 대상)
상태 초기값: START 이전 패널 구간(최대 60거래일)에서 같은 규칙을 돌려 정한다(상태 계산일 뿐 기록하지 않는다).

사용: python3 ibs_shadow.py --record --score --report   (멱등, 빠진 날 자동 회수)
"""
import argparse, csv, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE)
LOOP = os.path.dirname(REF)
sys.path.insert(0, HERE)
TRACK = os.path.join(REF, 'ibs_shadow.csv')
PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
START = '20261021'   # 등록일 데이터일. 이전 날짜는 기록하지 않는다(백필 금지).
CODE = '069500'; LO = 0.2; HI = 0.8; WARM = 60
FIELDS = ['date', 'ibs', 'pos', 'kodex_day', 'ibs_day', 'ibs_minus_bench']


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


def bars():
    out = {}
    if not os.path.exists(PANEL):
        return out
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r.get('code') != CODE:
                continue
            try:
                out[r['date']] = (float(r['high']), float(r['low']), float(r['close']))
            except (ValueError, KeyError):
                continue
    return out


def ibs_of(b):
    h, l, c = b
    return (c - l) / (h - l) if h > l else 0.5


def step(prev, x):
    if prev == 0 and x < LO:
        return 1
    if prev == 1 and x > HI:
        return 0
    return prev


def cmd_record():
    B = bars(); ds = sorted(B)
    try:
        import ensure_data
        ds = [d for d in ds if ensure_data.settled(d)]
    except Exception:
        pass
    if not ds:
        print('  [ibs] 2y 패널에 KODEX200 없음 — 건너뜀'); return 0
    rows = load(); have = {r['date']: r for r in rows}
    pre = [d for d in ds if d < START][-WARM:]
    st = 0
    for d in pre:
        st = step(st, ibs_of(B[d]))
    new = 0
    for d in [d for d in ds if d >= START]:
        x = ibs_of(B[d]); st = step(st, x)
        if d in have:
            st = int(have[d]['pos']); continue   # 기록된 상태를 우선(재현성)
        rows.append(dict(date=d, ibs=f'{x:.4f}', pos=str(st))); have[d] = rows[-1]; new += 1
    if new:
        save(rows)
    print(f'  [ibs] 기록 {new}행 추가 (누적 {len(rows)}행)'); return 0


def cmd_score():
    B = bars(); ds = sorted(B); rows = load(); n = 0
    for r in rows:
        if r.get('kodex_day'):
            continue
        d = r['date']
        if d not in ds:
            continue
        i = ds.index(d)
        if i + 1 >= len(ds):
            continue
        try:
            import ensure_data
            if not ensure_data.settled(ds[i + 1]):
                continue
        except Exception:
            pass
        k = (B[ds[i + 1]][2] / B[d][2] - 1) * 100; pos = int(r['pos'])
        r['kodex_day'] = f'{k:.4f}'; r['ibs_day'] = f'{pos * k:.4f}'; r['ibs_minus_bench'] = f'{pos * k - k:.4f}'; n += 1
    if n:
        save(rows)
    print(f'  [ibs] 채점 {n}행'); return 0


def perf(xs):
    eq = 1.0; peak = 1.0; mdd = 0.0
    for x in xs:
        eq *= 1 + x / 100; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    sh = (statistics.mean(xs) / statistics.stdev(xs) * 245 ** .5) if len(xs) > 2 and statistics.stdev(xs) > 0 else float('nan')
    return (eq - 1) * 100, mdd * 100, sh


def cmd_report():
    rows = [r for r in load() if r.get('kodex_day')]
    last = load()[-1] if load() else None
    if last:
        print(f"  [ibs] 최근 {last['date']} IBS {float(last['ibs']):.2f} → 상태 {'보유' if last['pos'] == '1' else '현금'}")
    if len(rows) < 3:
        print(f'  [ibs] 채점 {len(rows)}일 — 성과 집계 보류'); return 0
    a = perf([float(r['ibs_day']) for r in rows]); b = perf([float(r['kodex_day']) for r in rows])
    expo = sum(int(r['pos']) for r in rows) / len(rows) * 100
    print(f'  [ibs] {len(rows)}일 · 노출 {expo:.0f}% · IBS 누적 {a[0]:+.2f}% MDD {a[1]:.2f}% Sh {a[2]:.2f} | '
          f'KODEX200 누적 {b[0]:+.2f}% MDD {b[1]:.2f}% Sh {b[2]:.2f}')
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
