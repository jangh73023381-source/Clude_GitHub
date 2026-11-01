#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_ag_recheck_20260901.py — Rule AG(상장연령 게이트) **7년 패널 재확인**.

왜 이 회차인가
  §10 진행중 과제에 "Rule AG — **보류**. t=+0.75, 730일 임계가 2년 패널 시작(20240219)과
  사실상 겹침. 7년 패널이 2026-08-28 최신화됐으므로 **다음 회차 우선 재확인 대상**,
  재현 안 되면 종결"로 등록돼 있다. 2026-09-01 이 8/31(경량 모드) 이후 첫 신규 채점
  대상일이므로 이 축을 먼저 수행한다.

무엇이 달라졌는가 (재검정 사유)
  ① 2026-08-10 AG, 2026-08-11 AGL 검정 당시 **판정 패널은 2년(panel_close_*)**이었고
     연령만 장기 패널에서 쟀다. 이번엔 **판정 패널 자체를 7년(panel_ohlc_long.csv,
     1,820거래일 20190401~)** 으로 옮긴다 — §4-5 "판정 패널의 기본은 7년".
  ② **관문 R5(꼬리 기여도)가 2026-08-18 에 신설**됐다. AG/AGL 은 그 이전 축이라
     R5 를 한 번도 통과한 적이 없다. 잭나이프는 대표본에서 이 결함을 못 잡는다.
  ③ 확정 방법이 **v2.9(Rule LV)** 로 바뀌었다. AG 를 현행 확정 방법 위에서도 잰다.

측정
  · 1차 지표 = v2.3 P&L, 픽5 동일가중 1일 보유, **비용 0(v2.8)**, KODEX200 대비 %p/일.
  · baseline 2종: MOM(mom20 상위5) / LV(mom20 상위 pool30 중 σ20 하위5, v2.9 확정방법).
  · 후보 = 각 baseline 의 **후보 리스트에 상장연령 게이트를 먼저 적용**한 뒤 동일 규칙 선정.
  · 관문 R1(임계 고원 5점) · R2(3-fold) · R4(플라시보 200회) · R5(꼬리) · 잭나이프 · t.

조회 전용. 룩어헤드 금지 — 선정은 D 종가까지의 정보만 쓴다.
"""
import csv
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))
from universe_filters import eligible                 # noqa: E402

LONG = os.path.join(HERE, 'panel_ohlc_long.csv')
BENCH, NPICK, MOM = '069500', 5, 20
LV_POOL, LV_K = 30, 20
AGES = [365, 545, 730, 912, 1095]          # R1 고원 격자


def load():
    px, names = defaultdict(dict), {}
    r = csv.reader(open(LONG, encoding='utf-8'))
    h = next(r)
    ic, inm, idt, icl = h.index('code'), h.index('name'), h.index('date'), h.index('close')
    for row in r:
        try:
            px[row[ic]][row[idt]] = float(row[icl])
        except ValueError:
            continue
        names[row[ic]] = row[inm]
    return px, names


def _d(s):
    from datetime import date
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def build_cands(px, names, dates):
    """일자별 (mom20, code, sigma20) 내림차순 후보 — Rule H 적용."""
    out = {}
    for i, d in enumerate(dates):
        if i < max(MOM, LV_K) + 1:
            continue
        lst = []
        for c in px:
            if not eligible(names.get(c, '')):
                continue
            a, b = px[c].get(dates[i - MOM]), px[c].get(d)
            if not (a and b):
                continue
            c1, c3 = px[c].get(dates[i - 1]), px[c].get(dates[i - 3])
            if not (c1 and c3):
                continue
            if (b / c1 - 1) * 100 > 10 or (b / c3 - 1) * 100 > 20:
                continue                                     # Rule H
            rets = []
            ok = True
            for k in range(LV_K):
                p0, p1 = px[c].get(dates[i - k - 1]), px[c].get(dates[i - k])
                if not (p0 and p1):
                    ok = False
                    break
                rets.append((p1 / p0 - 1) * 100)
            if not ok:
                continue
            lst.append(((b / a - 1) * 100, c, statistics.stdev(rets)))
        lst.sort(reverse=True)
        out[d] = lst
    return out


def fwd(px, c, d, n):
    a, b = px[c].get(d), px[c].get(n)
    return None if not (a and b) else (b / a - 1) * 100


def pick_mom(cand):
    return [c for _, c, _ in cand[:NPICK]]


def pick_lv(cand):
    pool = cand[:LV_POOL]
    if len(pool) < NPICK:
        return [c for _, c, _ in pool]
    return [c for _, c, _ in sorted(pool, key=lambda x: x[2])[:NPICK]]


def series(px, dates, cands, picker, first_seen=None, minage=None, agemap=None):
    """일별 (date, 초과%p) 시계열."""
    out = []
    for i, d in enumerate(dates[:-1]):
        n = dates[i + 1]
        bm = fwd(px, BENCH, d, n)
        cd = cands.get(d)
        if bm is None or not cd:
            continue
        if minage is not None:
            src = agemap if agemap is not None else first_seen
            dd = _d(d)
            cd = [x for x in cd
                  if src.get(x[1]) is not None and (dd - _d(src[x[1]])).days >= minage]
        if len(cd) < NPICK:
            continue
        rs = [fwd(px, c, d, n) for c in picker(cd)]
        rs = [x for x in rs if x is not None]
        if len(rs) < NPICK:
            continue
        out.append((d, sum(rs) / len(rs) - bm))
    return out


def jack(v):
    if len(v) < 3:
        return float('nan')
    m = [statistics.mean(v[:i] + v[i + 1:]) for i in range(len(v))]
    return min(m)


def tstat(v):
    if len(v) < 3:
        return float('nan')
    return statistics.mean(v) / (statistics.stdev(v) / len(v) ** 0.5)


def r5(v):
    s = sorted(v, reverse=True)
    n = len(v)
    o = {}
    for k in (1, 3, 5, 10):
        o[f'-top{k}'] = statistics.mean(s[k:]) if n > k else float('nan')
    o['median'] = statistics.median(v)
    q = int(n * 0.05)
    w = sorted(v)
    if q:
        w = [w[q]] * q + w[q:n - q] + [w[n - q - 1]] * q
    o['winsor'] = statistics.mean(w)
    return o


def report(tag, base, cand):
    """base·cand 는 [(date, ex%p)] — 공통 날짜로 페어 정렬."""
    bd = dict(base)
    cd = dict(cand)
    days = sorted(set(bd) & set(cd))
    b = [bd[d] for d in days]
    c = [cd[d] for d in days]
    diff = [x - y for x, y in zip(c, b)]
    n = len(days)
    third = n // 3
    folds = [(0, third), (third, 2 * third), (2 * third, n)]
    fs = [statistics.mean(diff[a:z]) for a, z in folds]
    half = n // 2
    print(f'\n--- {tag} (페어 {n}일 {days[0]}~{days[-1]}) ---')
    print(f'  후보 {statistics.mean(c):+.4f}%p/일 · baseline {statistics.mean(b):+.4f}%p/일 '
          f'· 차 {statistics.mean(diff):+.4f}%p (t={tstat(diff):+.2f}) '
          f'· 승 {sum(1 for x in diff if x > 0)}/{n}')
    print(f'  R2 반분  train {statistics.mean(diff[:half]):+.4f} / '
          f'test {statistics.mean(diff[half:]):+.4f}')
    print(f'  R2 3fold {fs[0]:+.4f} / {fs[1]:+.4f} / {fs[2]:+.4f} '
          f'→ {"3/3 통과" if all(x > 0 for x in fs) else "미통과"}')
    print(f'  잭나이프 하한 {jack(diff):+.4f}')
    t = r5(diff)
    print(f'  R5 꼬리  -top1 {t["-top1"]:+.4f} · -top3 {t["-top3"]:+.4f} · '
          f'-top5 {t["-top5"]:+.4f} · -top10 {t["-top10"]:+.4f}')
    print(f'          중앙값 {t["median"]:+.4f} · 윈저화(5%) {t["winsor"]:+.4f} '
          f'→ {"통과" if t["-top3"] > 0 else "**기각**(상위3일 제거 시 부호 반전)"}')
    return statistics.mean(diff), fs, t


def main():
    px, names = load()
    dates = sorted({d for c in px for d in px[c]})
    first_seen = {c: min(px[c]) for c in px}
    print(f'=== Rule AG 재확인 · 7년 패널 {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · {len(px)}종 ===')
    cands = build_cands(px, names, dates)

    base_mom = series(px, dates, cands, pick_mom)
    base_lv = series(px, dates, cands, pick_lv)
    print(f'\n[baseline] MOM {statistics.mean([x for _, x in base_mom]):+.4f}%p/일 '
          f'({len(base_mom)}일) · LV {statistics.mean([x for _, x in base_lv]):+.4f}%p/일 '
          f'({len(base_lv)}일)')

    print('\n########## R1 파라미터 고원 — 임계 5점 ##########')
    res = {}
    for a in AGES:
        for tag, bs, pk in (('MOM', base_mom, pick_mom), ('LV', base_lv, pick_lv)):
            cs = series(px, dates, cands, pk, first_seen=first_seen, minage=a)
            m, fs, t = report(f'AG {a}일↑ on {tag}', bs, cs)
            res[(a, tag)] = (m, fs, t)

    print('\n########## R4 플라시보 — 상장일 라벨 무작위 셔플 200회 (730일, LV) ##########')
    codes = sorted(first_seen)
    firsts = [first_seen[c] for c in codes]
    obs = res[(730, 'LV')][0]
    rnd = random.Random(20260901)
    null = []
    for it in range(200):
        sh = firsts[:]
        rnd.shuffle(sh)
        fake = dict(zip(codes, sh))
        cs = series(px, dates, cands, pick_lv, minage=730, agemap=fake)
        bd, cdd = dict(base_lv), dict(cs)
        days = sorted(set(bd) & set(cdd))
        if days:
            null.append(statistics.mean([cdd[d] - bd[d] for d in days]))
    if null:
        ge = sum(1 for x in null if x >= obs)
        print(f'  관측 {obs:+.4f} vs 귀무 평균 {statistics.mean(null):+.4f} '
              f'(sd {statistics.stdev(null):.4f}) · 경험적 p = {ge / len(null):.4f}')

    print('\n########## 요약 ##########')
    for tag in ('MOM', 'LV'):
        line = ' · '.join(f'{a}:{res[(a, tag)][0]:+.4f}' for a in AGES)
        print(f'  {tag}: {line}')


if __name__ == '__main__':
    main()
