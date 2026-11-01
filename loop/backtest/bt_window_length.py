# -*- coding: utf-8 -*-
"""2026-07-31 — shadow 판정 기간(20영업일) 단축 가능성 검정 (사용자 요청).

질문: "20영업일은 길다. 줄여도 크게 이상 없으면 줄이자."

방법: 판정은 '일별 차이 시계열의 평균 > 0' 이다. 그러면 기간 N일 판정의 오류율은
그 시계열의 **평균 대비 잡음(mean/sd)** 으로 결정된다. 두 각도로 잰다.

  (1) 롤링 일치율 — 실제 시계열에서 길이 N 창을 전부 굴려, 전체표본 판정과 부호가
      일치하는 비율. '전체표본 = 진실'로 두는 근사이지만 가용한 최선이다.
  (2) 부트스트랩 — 관측된 (평균, 표준편차) 를 가진 분포에서 N일을 복원추출해
      P(판정이 맞을 확률). 창이 겹치지 않아 (1)의 자기상관 편향이 없다.

핵심 주의: Rule RG 처럼 **게이트가 가끔만 발동하는 규칙은 유효표본이 발동일뿐**이다.
20영업일이라도 발동일은 4~5일에 그친다. 달력 일수가 아니라 발동 일수로 세야 한다.
"""
import csv
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
random.seed(20260731)


def rolling_agree(x, n):
    """길이 n 창의 판정(평균>0)이 전체표본 판정과 일치하는 비율."""
    if len(x) < n + 1:
        return None
    truth = statistics.fmean(x) > 0
    wins = [x[i:i + n] for i in range(len(x) - n + 1)]
    return sum((statistics.fmean(w) > 0) == truth for w in wins) / len(wins)


def boot_agree(x, n, trials=4000):
    """관측 분포에서 n일 복원추출 → 판정이 전체표본과 일치할 확률."""
    truth = statistics.fmean(x) > 0
    ok = 0
    for _ in range(trials):
        s = [random.choice(x) for _ in range(n)]
        ok += (statistics.fmean(s) > 0) == truth
    return ok / trials


def need_n(x, target=0.80, cap=200):
    """목표 정확도에 도달하는 최소 N (부트스트랩 기준)."""
    for n in range(3, cap + 1):
        if boot_agree(x, n, 1500) >= target:
            return n
    return None


def describe(x):
    m, sd = statistics.fmean(x), (statistics.stdev(x) if len(x) > 1 else 0)
    t = m / (sd / len(x) ** 0.5) if sd else 0
    return m, sd, t


def report(name, x, note=''):
    if len(x) < 5:
        print(f'\n■ {name} — 표본 {len(x)}일로 부족, 판정 불가 {note}')
        return
    m, sd, t = describe(x)
    print(f'\n■ {name} — 표본 {len(x)}일 · 평균 {m:+.4f} · 표준편차 {sd:.4f} · t {t:+.2f} {note}')
    print(f'  {"N일":>6s}{"롤링 일치율":>12s}{"부트스트랩":>12s}')
    for n in (3, 5, 10, 15, 20, 30, 40, 60):
        if n > len(x):
            break
        r = rolling_agree(x, n)
        b = boot_agree(x, n)
        print(f'  {n:6d}{("—" if r is None else f"{r:.1%}"):>12s}{b:>12.1%}')
    for tgt in (0.80, 0.90):
        nn = need_n(x, tgt)
        print(f'  → 정확도 {tgt:.0%} 도달에 필요한 N: {nn if nn else ">200"}일')


def col(path, c, flt=None):
    out = []
    for r in csv.DictReader(open(os.path.join(LOOP, 'references', path), encoding='utf-8')):
        if flt and not flt(r):
            continue
        try:
            out.append(float(r[c]))
        except (ValueError, KeyError):
            pass
    return out


def rg_series():
    """Rule RG — 게이트 적용 시 baseline 대비 일별 개선(발동일만 비0)."""
    import bt_us_rule_20260731 as R
    import bt_us_kr_transfer as T
    px, nm, op, th, dates = R.load()
    di = {d: i for i, d in enumerate(dates)}
    us = T.load_us()
    ud = sorted(us)

    def spy(dk):
        pr = [d for d in ud if d < dk]
        if len(pr) < 2:
            return None
        return us[pr[-1]]['SPY'] / us[ud[ud.index(pr[-1]) - 1]]['SPY'] - 1

    allday, fired = [], []
    for d, v in R.run(R.base_sel, px, nm, op, th, dates, di, 'oc'):
        nxt = dates[dates.index(d) + 1]
        m = spy(nxt)
        if m is None:
            continue
        gain = (0.0 - 0.10) - v if m >= 0.008 else 0.0   # 발동일엔 벤치 보유
        allday.append(gain)
        if m >= 0.008:
            fired.append(gain)
    return allday, fired


if __name__ == '__main__':
    print('=' * 70)
    print('shadow 판정 기간 단축 검정 — 판정 = 일별 차이 평균 > 0')
    print('=' * 70)

    allday, fired = rg_series()
    report('Rule RG (전체 달력일 기준)', allday,
           '← 미발동일 0 이 섞여 잡음만 늘린다')
    report('Rule RG (발동일만)', fired, '← 유효표본은 이쪽')
    print(f'  ※ 발동 빈도 {len(fired)}/{len(allday)} = {len(fired)/len(allday):.1%}'
          f' → 달력 20영업일이면 발동일 기대값 {20*len(fired)/len(allday):.1f}일뿐')

    report('트랙 B 조합제 (코스피 대비 초과)', col('combo_shadow_tracker.csv',
                                          'excess_vs_kospi_pct'))
    report('Rule CB 종가베팅 (코스피 대비 초과)', col('close_bet_band_tracker.csv', 'excess'))
    report('Rule CB — 실매수일만', col('close_bet_band_tracker.csv', 'excess',
                                   lambda r: (r['n_buy'] or '').strip().isdigit()
                                   and int(r['n_buy']) > 0),
           '← 관망일 제외')

    # ---- 조기종료(적응형) 규칙 검정 --------------------------------------
    print('\n' + '=' * 70)
    print('조기종료 규칙 — "증거가 이미 뚜렷하면 일찍 끝내고, 아니면 계속"')
    print('=' * 70)
    print('  판정: N=early 시점에 |t| >= tcut 이면 즉시 확정, 아니면 N=late 까지 관측')

    def early_stop(x, early, late, tcut, trials=4000):
        truth = statistics.fmean(x) > 0
        ok, dur = 0, 0
        for _ in range(trials):
            s = [random.choice(x) for _ in range(late)]
            head = s[:early]
            m, sd = statistics.fmean(head), statistics.stdev(head)
            t = m / (sd / early ** 0.5) if sd else 0
            if abs(t) >= tcut:
                ok += (m > 0) == truth
                dur += early
            else:
                ok += (statistics.fmean(s) > 0) == truth
                dur += late
        return ok / trials, dur / trials

    for label, x in (('Rule CB', col('close_bet_band_tracker.csv', 'excess')),
                     ('트랙 B 조합제', col('combo_shadow_tracker.csv', 'excess_vs_kospi_pct')),
                     ('Rule RG(발동일)', fired)):
        if len(x) < 5:
            continue
        print(f'\n■ {label}')
        base_acc = boot_agree(x, 20)
        print(f'  {"방식":30s}{"정확도":>9s}{"평균 소요일":>12s}')
        print(f'  {"고정 20일 (현행)":30s}{base_acc:>9.1%}{20:>12.1f}')
        for early, tcut in ((8, 2.0), (10, 1.8), (10, 2.0), (12, 1.5)):
            acc, dur = early_stop(x, early, 20, tcut)
            mark = '  ← 현행보다 빠르고 정확' if (acc >= base_acc and dur < 20) else ''
            print(f'  {f"조기 {early}일 |t|>={tcut} → 아니면 20일":30s}'
                  f'{acc:>9.1%}{dur:>12.1f}{mark}')
