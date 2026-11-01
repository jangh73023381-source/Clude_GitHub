#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nhi_shadow.py — Rule NHI shadow (2026-09-17 사용자 승인 등록, 조회 전용).

Rule NHI = [신고가 근접: 종가 ≥ 250일 최고가(고가 기준)×0.95] ∩ [KODEX200 종가 > MA20 게이트]
  → 그 집합 안에서 현행 선정기(mom20+Rule H → pool30 → σ20 하위 5종, Rule LV v2.9)를 그대로 돌린다.
  게이트 OFF 날은 현금(수익 0).
근거: `유튜브_종목선정기법_백테스트_2026-08-25.docx` · `backtest/bt_yt_lv_20260825.py` (7년 ETF)
  2×2 상호작용 +0.062 · fold 3/3 · R3 재현 · R4 p=0.000 · R5 중앙 +0.1388≈평균 +0.1392.
  약점: R1 게이트 축 MA40↑ 붕괴 · LV 위 복리 +31.2%→+24.6%(MDD −25.4%→−16.2% 개선).
→ LV 처럼 **위험 축**이라 일평균 %p 하나로 판정하지 않는다. LV·NHI 페어로 기록한다.

판정(CLAUDE.md §5 Rule NHI 절): `judge_ready.py references/nhi_shadow.csv nhi_minus_lv` 가
판정 가능을 내면 (a) 누적 MDD 가 LV 대비 개선 (b) Sharpe 가 LV 대비 개선 (c) 누적 수익 격차가
LV 대비 −5%p 이내. **2회 연속 미달이면 종결.** 3회 연속 기록 결손도 종결 후보.
**파라미터 동결**: 0.95 · 250일 · MA20 · pool30 · σ20 · 5종. 백테스트 백필 금지(START 이후만).

사용: python3 nhi_shadow.py --record --score --report   (record 는 START 이후 빠진 날을 자동 회수, 멱등)
"""
import argparse, csv, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE); LOOP = os.path.dirname(REF)
sys.path.insert(0, HERE)
import morning_run as mr          # noqa: E402  같은 선정기를 그대로 쓴다(두 곳에서 계산하지 않기 위해)
TRACK = os.path.join(REF, 'nhi_shadow.csv')
START = '20260916'                # 등록일 직전 데이터일(9/17 브리핑의 선정 D). 이전 날짜는 기록하지 않는다.
BENCH = '069500'; NEAR = 0.95; HI_WIN = 250; GATE_MA = 20
FIELDS = ['date', 'gate', 'near_n', 'nhi_picks', 'lv_picks', 'nhi_ret', 'lv_ret', 'bench_ret',
          'nhi_minus_lv', 'nhi_minus_bench']


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


def highs():
    hi = {}
    for r in csv.DictReader(open(os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv'), encoding='utf-8')):
        try:
            hi.setdefault(r['code'], {})[r['date']] = float(r['high'])
        except (ValueError, KeyError):
            continue
    return hi


def compute(px, nm, dates, hi, D):
    i = dates.index(D)
    b = px.get(BENCH, {})
    bw = [b.get(d) for d in dates[i - GATE_MA + 1:i + 1]]
    gate = all(bw) and b[D] > sum(bw) / GATE_MA
    lv = mr.compute_picks(px, nm, dates, D)
    lv5 = [r['code'] for r in lv['short10'][:5]]
    near = {}
    for c, v in px.items():
        h = hi.get(c)
        if not h or D not in v:
            continue
        hs = [x for d, x in h.items() if d <= D]
        if len(hs) < 60:
            continue
        hs = [h[d] for d in sorted(d for d in h if d <= D)[-HI_WIN:]]
        if v[D] >= max(hs) * NEAR:
            near[c] = v
    nhi5 = []
    if gate and near:
        nhi5 = [r['code'] for r in mr.compute_picks(near, nm, dates, D)['short10'][:5]]
    return dict(date=D, gate=int(gate), near_n=len(near), nhi_picks=','.join(nhi5), lv_picks=','.join(lv5))


def cmd_record():
    _, px, nm, dates = mr.load_panel()
    rows = load(); have = {r['date'] for r in rows}
    todo = [d for d in dates if d >= START and d not in have and dates.index(d) >= 60][-30:]
    if not todo:
        print('  [nhi] 기록할 새 날짜 없음 (멱등)'); return 0
    hi = highs()
    for D in todo:
        if D not in hi.get(BENCH, {}):
            print(f'  [nhi] {D}: 2y OHLC 패널에 없음 — 건너뜀(다음 실행에서 회수)'); continue
        r = compute(px, nm, dates, hi, D); rows.append(r)
        print(f"  [nhi] {D} 게이트 {'ON' if r['gate'] else 'OFF(현금)'} · 신고가근접 {r['near_n']}종 · "
              f"NHI [{r['nhi_picks'] or '-'}] | LV [{r['lv_picks']}]")
    save(rows); return 0


def cmd_score():
    _, px, _, dates = mr.load_panel()
    rows = load(); n = 0
    for r in rows:
        if r.get('lv_ret') or r['date'] not in dates:
            continue
        i = dates.index(r['date'])
        if i + 1 >= len(dates):
            continue
        d, nx = r['date'], dates[i + 1]

        def ew(codes):
            cs = [c for c in codes.split(',') if c]
            v = [(px[c][nx] / px[c][d] - 1) * 100 for c in cs if d in px.get(c, {}) and nx in px.get(c, {})]
            return (sum(v) / len(v) if len(v) == len(cs) else None) if cs else 0.0
        lv, nh, bm = ew(r['lv_picks']), ew(r['nhi_picks']), ew(BENCH)
        if lv is None or nh is None or bm is None:
            continue
        r.update(nhi_ret=f'{nh:.4f}', lv_ret=f'{lv:.4f}', bench_ret=f'{bm:.4f}',
                 nhi_minus_lv=f'{nh - lv:.4f}', nhi_minus_bench=f'{nh - bm:.4f}')
        n += 1
    if n:
        save(rows)
    print(f'  [nhi] 채점 {n}행 · 누적 {sum(1 for r in rows if r.get("lv_ret"))}일'); return 0


def _curve(v):
    x, pk, w = 1.0, 1.0, 0.0
    for a in v:
        x *= 1 + a / 100; pk = max(pk, x); w = min(w, x / pk - 1)
    return w * 100, (x - 1) * 100


def cmd_report():
    rows = [r for r in load() if r.get('lv_ret')]
    if len(rows) < 3:
        print(f'  Rule NHI shadow — 누적 {len(rows)}일 (표본 부족)'); return 0
    out = {}
    for k in ('nhi', 'lv', 'bench'):
        v = [float(r[k + '_ret']) for r in rows]
        m, c = _curve(v)
        sh = statistics.mean(v) / statistics.stdev(v) * 252 ** 0.5 if statistics.stdev(v) else 0
        out[k] = (m, c, sh)
        print(f'  {k:5s} 누적 {c:+7.2f}% · MDD {m:7.2f}% · Sharpe {sh:5.2f}')
    on = sum(int(r['gate']) for r in rows)
    print(f'  게이트 ON {on}/{len(rows)}일 · (a) MDD {"개선" if out["nhi"][0] > out["lv"][0] else "미달"}'
          f' · (b) Sharpe {"개선" if out["nhi"][2] > out["lv"][2] else "미달"}'
          f' · (c) 누적격차 {out["nhi"][1] - out["lv"][1]:+.2f}%p')
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
