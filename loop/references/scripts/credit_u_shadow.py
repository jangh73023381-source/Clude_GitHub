#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""credit_u_shadow.py — Rule CRU shadow (2026-10-22 사용자 승인 등록, 조회 전용).

Rule CRU = 신용융자잔고 '상대 수준' U자 노출 규칙(KODEX200 보유 기준).
  z = (신용잔고 − 직전 250거래일 평균) / 표준편차. 데이터일 D 판단에는 **D−2 거래일 신용**만 쓴다(결제 기준·공개 지연).
  z 가 과거 분포(2010 이후 확장창, 직전일까지)의 하위 20% 이하 또는 상위 20% 이상이면 노출 100%, 그 사이면 50%.
  수익 = 노출 × (D→D+1 KODEX200 종가 수익). 현금 0 · 비용 0(v2.8).
근거(2010-01~2026-10, 코스피 기준, `backtest/credit_20261022/ushape.py`): CAGR 9.5 / MDD −27.2 / Sh 0.63 / 평균노출 0.70
  vs 보유 7.8 / −43.9 / 0.46 · 같은 평균노출 상수 Sh 0.46 · 시차이동 대조 p=0.030 · ΔSh fold 3/3.
  약점: 코스피 자체 U자(대조)도 Sh 0.50~0.58 → 신용 고유 몫은 그 차이 · R1 z120/z500 에서 fold 1개씩 0/음수 ·
  연도별 U자 존재 7/16 · 강세장 비용(2017 −13.2 · 2025 −14.1%p) · **Rule LV 에 얹으면 열위(2026-10-22 기각)**.

판정(CLAUDE.md §5 Rule CRU): `judge_ready.py references/credit_u_shadow.csv cru_minus_bench` 판정 가능 + **기록 120거래일 이상**일 때
(a) 누적 MDD 가 KODEX200 보유 대비 개선 (b) Sharpe 개선 (c) 누적 수익 격차 −5%p 이내. **2회 연속 미달이면 종결.**
**동결**: z 창 250 · 하위/상위 20% · 중간 노출 50% · D−2 신용 · KODEX200 종가. 백필 금지(START 이후만 기록).
선정·브리핑·Rule CB·트랙 A~D·Rule LV 에 반영하지 않는다.

열 — 한 행 = 데이터일 D: credit_date(사용한 신용일) · credit_z · q_lo · q_hi · bucket(하위/중간/상위) · expo
  · kodex_day(D→D+1 %) · cru_day = expo × kodex_day · cru_minus_bench = cru_day − kodex_day
데이터: 네이버 stock.naver.com/api/domestic/market/trendDeposit (고객예탁금·신용융자, 억원, 코스피+코스닥) → references/credit_cache.csv 멱등 보충.

사용: python3 credit_u_shadow.py --record --score --report   (멱등, 빠진 날 자동 회수)
"""
import argparse, csv, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE)
LOOP = os.path.dirname(REF)
sys.path.insert(0, HERE)
TRACK = os.path.join(REF, 'credit_u_shadow.csv')
CACHE = os.path.join(REF, 'credit_cache.csv')
PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
START = '20261022'
CODE = '069500'; ZW = 250; LO = .2; HI = .8; MID = .5; LAG = 2; MINQ = 500
FIELDS = ['date', 'credit_date', 'credit_z', 'q_lo', 'q_hi', 'bucket', 'expo', 'kodex_day', 'cru_day', 'cru_minus_bench']


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
    """최근 200건만 받아 캐시에 합친다. 실패해도 캐시로 진행."""
    try:
        import requests
        H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.naver.com/sise/sise_deposit.naver'}
        j = requests.get('https://stock.naver.com/api/domestic/market/trendDeposit?startIdx=0&pageSize=200', headers=H, timeout=15).json()
        new = {x['bizdate']: (int(x['customerDeposit']), int(x['creditLoan'])) for x in (j.get('content') or [])}
    except Exception as e:
        print(f'  [cru] 신용 갱신 실패 — 캐시 사용 ({type(e).__name__})'); return False
    old = {r['date']: (int(r['deposit']), int(r['credit'])) for r in csv.DictReader(open(CACHE, encoding='utf-8'))}
    add = {d: v for d, v in new.items() if d not in old}
    if add:
        import safe_io
        old.update(add)
        tmp = CACHE + '.tmp'
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f); w.writerow(['date', 'deposit', 'credit'])
            for d in sorted(old): w.writerow([d, *old[d]])
        if os.path.exists(CACHE):
            safe_io.safe_replace(tmp, CACHE)  # 2026-11-01: 생 os.replace 대신 §6 safe_replace
        else:
            os.rename(tmp, CACHE)
    return True


def zseries():
    rows = list(csv.DictReader(open(CACHE, encoding='utf-8')))
    ds = [r['date'] for r in rows]; c = [float(r['credit']) for r in rows]
    z = {}
    for i in range(ZW - 1, len(c)):
        w = c[i - ZW + 1:i + 1]; m = statistics.mean(w); s = statistics.stdev(w)
        z[ds[i]] = (c[i] - m) / s if s > 0 else 0.0
    return z


def quant(vals, q):
    v = sorted(vals); k = (len(v) - 1) * q; f = int(k); c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def bars():
    out = {}
    if os.path.exists(PANEL):
        for r in csv.DictReader(open(PANEL, encoding='utf-8')):
            if r.get('code') == CODE:
                try: out[r['date']] = float(r['close'])
                except (ValueError, KeyError): pass
    return out


def cmd_record():
    refresh()
    B = bars(); ds = sorted(B)
    try:
        import ensure_data
        ds = [d for d in ds if ensure_data.settled(d)]
    except Exception:
        pass
    z = zseries(); zd = sorted(d for d in z if d >= '20100101')
    rows = load(); have = {r['date'] for r in rows}; new = 0
    for i, d in enumerate(ds):
        if d < START or d in have or i < LAG:
            continue
        cd = ds[i - LAG]
        if cd not in z:
            print(f'  [cru] {d}: 신용 {cd} 미공개 — 다음 실행에서 회수'); continue
        hist = [z[x] for x in zd if x < cd]          # 판단 시점 이전 분포(확장창)
        if len(hist) < MINQ:
            continue
        ql, qh, x = quant(hist, LO), quant(hist, HI), z[cd]
        b = '하위' if x <= ql else ('상위' if x >= qh else '중간')
        e = 1.0 if b != '중간' else MID
        rows.append(dict(date=d, credit_date=cd, credit_z=f'{x:.4f}', q_lo=f'{ql:.4f}', q_hi=f'{qh:.4f}', bucket=b, expo=f'{e:.2f}'))
        have.add(d); new += 1
    if new:
        save(rows)
    print(f'  [cru] 기록 {new}행 추가 (누적 {len(rows)}행)'); return 0


def cmd_score():
    B = bars(); ds = sorted(B); rows = load(); n = 0
    for r in rows:
        if r.get('kodex_day') or r['date'] not in B:
            continue
        i = ds.index(r['date'])
        if i + 1 >= len(ds):
            continue
        try:
            import ensure_data
            if not ensure_data.settled(ds[i + 1]): continue
        except Exception:
            pass
        k = (B[ds[i + 1]] / B[r['date']] - 1) * 100; e = float(r['expo'])
        r['kodex_day'] = f'{k:.4f}'; r['cru_day'] = f'{e * k:.4f}'; r['cru_minus_bench'] = f'{e * k - k:.4f}'; n += 1
    if n:
        save(rows)
    print(f'  [cru] 채점 {n}행'); return 0


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
        print(f"  [cru] 최근 {l['date']} (신용 {l['credit_date']}) z {float(l['credit_z']):+.2f} · 경계 {float(l['q_lo']):+.2f}/{float(l['q_hi']):+.2f} → {l['bucket']} · 노출 {float(l['expo'])*100:.0f}%")
    rows = [r for r in allr if r.get('kodex_day')]
    if len(rows) < 3:
        print(f'  [cru] 채점 {len(rows)}일 — 성과 집계 보류'); return 0
    a = perf([float(r['cru_day']) for r in rows]); b = perf([float(r['kodex_day']) for r in rows])
    print(f'  [cru] {len(rows)}일 · CRU 누적 {a[0]:+.2f}% MDD {a[1]:.2f}% Sh {a[2]:.2f} | KODEX200 누적 {b[0]:+.2f}% MDD {b[1]:.2f}% Sh {b[2]:.2f}')
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
