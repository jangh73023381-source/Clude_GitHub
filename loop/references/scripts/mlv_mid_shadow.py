#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mlv_mid_shadow.py — Rule MLV shadow (2026-09-26 사용자 승인 등록, 조회 전용).

Rule MLV = [6-3] 중기 선정의 저변동 정렬판.
  mom150 상위 pool 30 (Rule MM 과 같은 계산 = mid_momentum_shadow.pick_mom150(n=30)) 중
  최근 20거래일 실현변동성(표본표준편차, 수익률 6개 이상) 하위 5종. σ 산출 5종 미만이면 mom150 순서로 폴백.
  각 선정일 D 종가에 매수해 **정확히 20거래일 보유**하는 겹침 트랜치(매일 1/20)로 기록한다.
근거: `루프엔지니어링_2026-09-26_중기20일_10회_opus.docx` 4절 · `backtest/loop10_20260926/gA*.py`
  (2020-04~2026-09 1,568일, 20일 트랜치) mom150 CAGR +35.0/MDD −51.3/Sharpe 1.00 →
  MLV +34.3/−37.4/1.32. R1 21점 Sharpe 21/21↑ · R2 MDD·Sharpe 6분할 6/6 · R3 재현 ·
  R4 무작위·지속형 무작위 MDD/Sharpe p=0.000(CAGR p=0.315) · R5 부분(5일 대체 MDD −46.2 유지, 10일에서 Sharpe 우위 소멸).
→ Rule LV 처럼 **위험 축**이라 일평균 %p 하나로 판정하지 않는다. mom150 트랜치와 **페어**로 기록한다.

판정(CLAUDE.md §5 Rule MLV 절): `judge_ready.py references/mlv_mid_shadow.csv mlv_minus_mom` 이
판정 가능을 내고 **트랜치가 20개로 찬 날(n_tr=20)이 60일 이상**일 때 (a) 누적 MDD 가 mom150 대비 개선
(b) Sharpe 개선 (c) 누적 수익 격차 −5%p 이내. **2회 연속 미달이면 종결.** 3회 연속 기록 결손도 종결 후보.
**파라미터 동결**: pool 30 · σ20 · 최소 수익률 6 · 5종 · 20거래일. 백테스트 백필 금지(START 이후만).
선정·브리핑·Rule CB·Rule MM 에 반영하지 않는다.

열 설명 — 한 행 = 데이터일 D.
  mlv_picks / mom_picks : D 종가 매수 트랜치 5종(Rule MLV / Rule MM mom150 상위 5)
  mlv_day / mom_day / bench_day : D→D+1 트랜치 포트폴리오 일수익(%) — D 이전 20개 선정일(D 포함) 중
      기록된 트랜치의 동일가중. n_tr = 그날 살아 있는 트랜치 수(등록 직후 20일은 20 미만 = 적립 구간).
  mlv_minus_mom : mlv_day − mom_day (%p/일, 비중복 일별) — judge_ready 대상.

사용: python3 mlv_mid_shadow.py --record --score --report   (record 는 START 이후 빠진 날을 자동 회수, 멱등)
"""
import argparse, csv, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mid_momentum_shadow as mms   # noqa: E402  mom150 pool 을 같은 계산으로 받는다(두 곳에서 계산하지 않기 위해)

TRACK = os.path.join(REF, 'mlv_mid_shadow.csv')
START = '20260923'   # 등록일(9/26) 직전 데이터일. 이전 날짜는 기록하지 않는다(백필 금지).
BENCH = '069500'; POOL = 30; K = 20; MINRET = 6; NPICK = 5; HOLD = 20
FIELDS = ['date', 'mlv_picks', 'mom_picks', 'n_tr', 'mlv_day', 'mom_day', 'bench_day',
          'mlv_minus_mom', 'mlv_minus_bench']


def load():
    return list(csv.DictReader(open(TRACK, encoding='utf-8'))) if os.path.exists(TRACK) else []


def save(rows):
    import safe_io
    tmp = TRACK + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for r in sorted(rows, key=lambda x: x['date']):
            w.writerow({k: r.get(k, '') for k in FIELDS})
    safe_io.safe_replace(tmp, TRACK)


def sigma(px, dates, i, c):
    v = px.get(c, {}); rs = []
    for a, b in zip(dates[i - K:i], dates[i - K + 1:i + 1]):
        if a in v and b in v and v[a]:
            rs.append((v[b] / v[a] - 1) * 100)
    return statistics.stdev(rs) if len(rs) >= MINRET else None


def compute(px, nm, dates, D):
    i = dates.index(D)
    pool = mms.pick_mom150(px, nm, dates, i, n=POOL)
    mom5 = pool[:NPICK]
    sc = [(s, c) for c in pool for s in [sigma(px, dates, i, c)] if s is not None]
    if len(sc) < NPICK:
        mlv5 = mom5
    else:
        sc.sort(key=lambda x: x[0]); mlv5 = [c for _, c in sc[:NPICK]]
    return dict(date=D, mlv_picks=','.join(mlv5), mom_picks=','.join(mom5))


def cmd_record():
    px, nm, dates = mms.load_panel()
    if not dates:
        print('  [mlv] 2y 패널 없음 — 건너뜀'); return 0
    rows = load(); have = {r['date'] for r in rows}
    todo = [d for d in dates if d >= START and d not in have and dates.index(d) >= 150][-30:]
    if not todo:
        print('  [mlv] 기록할 새 날짜 없음 (멱등)'); return 0
    for D in todo:
        r = compute(px, nm, dates, D); rows.append(r)
        name = lambda cs: ', '.join(nm.get(c, c) for c in cs.split(',') if c)
        print(f"  [mlv] {D} MLV [{name(r['mlv_picks'])}] | mom150 [{name(r['mom_picks'])}]")
    save(rows); return 0


def cmd_score():
    px, _, dates = mms.load_panel()
    rows = load(); by = {r['date']: r for r in rows}; n = 0
    for r in rows:
        if r.get('mlv_day') or r['date'] not in dates:
            continue
        i = dates.index(r['date'])
        if i + 1 >= len(dates):
            continue
        d, nx = r['date'], dates[i + 1]
        act = [by[s] for s in dates[max(0, i - HOLD + 1):i + 1] if s in by]   # D 이전 20 선정일(D 포함)

        def ew(codes):
            cs = [c for c in codes.split(',') if c]
            v = [(px[c][nx] / px[c][d] - 1) * 100 for c in cs if d in px.get(c, {}) and nx in px.get(c, {})]
            return sum(v) / len(v) if cs and len(v) == len(cs) else None
        m1 = [ew(a['mlv_picks']) for a in act]; m2 = [ew(a['mom_picks']) for a in act]; bm = ew(BENCH)
        if bm is None or not act or any(x is None for x in m1 + m2):
            continue
        a1, a2 = sum(m1) / len(m1), sum(m2) / len(m2)
        r.update(n_tr=str(len(act)), mlv_day=f'{a1:.4f}', mom_day=f'{a2:.4f}', bench_day=f'{bm:.4f}',
                 mlv_minus_mom=f'{a1 - a2:.4f}', mlv_minus_bench=f'{a1 - bm:.4f}')
        n += 1
    if n:
        save(rows)
    print(f'  [mlv] 채점 {n}행 · 누적 {sum(1 for r in rows if r.get("mlv_day"))}일'); return 0


def _curve(v):
    x, pk, w = 1.0, 1.0, 0.0
    for a in v:
        x *= 1 + a / 100; pk = max(pk, x); w = min(w, x / pk - 1)
    return w * 100, (x - 1) * 100


def cmd_report():
    rows = [r for r in load() if r.get('mlv_day')]
    full = sum(1 for r in rows if r.get('n_tr') == str(HOLD))
    if len(rows) < 3:
        print(f'  Rule MLV shadow — 누적 {len(rows)}일 (표본 부족 · 트랜치 적립 중)'); return 0
    out = {}
    for k in ('mlv', 'mom', 'bench'):
        v = [float(r[k + '_day']) for r in rows]
        m, c = _curve(v)
        sd = statistics.stdev(v)
        sh = statistics.mean(v) / sd * 252 ** 0.5 if sd else 0
        out[k] = (m, c, sh)
        print(f'  {k:5s} 누적 {c:+7.2f}% · MDD {m:7.2f}% · Sharpe {sh:5.2f}')
    print(f'  누적 {len(rows)}일(트랜치 20개 완비 {full}일 — 판정은 완비 60일 이후) · (a) MDD '
          f'{"개선" if out["mlv"][0] > out["mom"][0] else "미달"} · (b) Sharpe '
          f'{"개선" if out["mlv"][2] > out["mom"][2] else "미달"} · (c) 누적격차 {out["mlv"][1] - out["mom"][1]:+.2f}%p')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for f in ('record', 'score', 'report'):
        ap.add_argument('--' + f, action='store_true')
    a = ap.parse_args(); rc = 0
    if a.record: rc |= cmd_record()
    if a.score: rc |= cmd_score()
    if a.report or not (a.record or a.score): rc |= cmd_report()
    sys.exit(rc)
