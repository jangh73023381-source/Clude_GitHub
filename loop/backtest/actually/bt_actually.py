#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_actually.py — 「사실은 이렇습니다」(정부의 언론보도 반박) 축 7년 검정. 조회 전용.

선등록 설계(korea.kr 검토문서 §4, 2026-09-08):
  · 이벤트 = 반박일 D(반박일이 휴장이면 다음 거래일) · 대상 = 매핑된 테마 섹터
  · 지표 = 그 섹터 ETF 등가중 D→D+1 초과수익(vs KODEX200) − 같은 섹터 전체기간 평균(섹터 고정효과 제거)
  · 가설 방향 = 음(-)  · 보수 가정: D 종가에 이미 공개된 것으로 보고 D+1만 거래(룩어헤드 없음)
  · 관문 R1 강도 고원 · R2 3-fold(fold3 필수) · R5 꼬리·중앙값 · ★ 매핑 셔플 대조군
"""
import csv, json, os, sys, statistics, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.dirname(HERE); LOOP = os.path.dirname(BT)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import eligible          # noqa
import etf_sector_map as sm                    # noqa
import themes                                  # noqa

BENCH = '069500'

def load_px():
    px, names = collections.defaultdict(dict), {}
    r = csv.reader(open(os.path.join(BT, 'panel_ohlc_long.csv'), encoding='utf-8')); h = next(r)
    ic, inm, idt, icl = h.index('code'), h.index('name'), h.index('date'), h.index('close')
    for row in r:
        try: px[row[ic]][row[idt]] = float(row[icl])
        except ValueError: continue
        names[row[ic]] = row[inm]
    return px, names

def sector_excess(px, names):
    """{date: {sector: 그날→익일 초과수익%p}}  (date 는 '보유 시작일')"""
    dates = sorted({d for c in px for d in px[c]})
    out = {}
    for i, d in enumerate(dates[:-1]):
        n = dates[i + 1]
        b0, b1 = px[BENCH].get(d), px[BENCH].get(n)
        if not (b0 and b1): continue
        bm = (b1 / b0 - 1) * 100
        agg = {}
        for c in px:
            nm = names.get(c, '')
            if not eligible(nm): continue
            a, b = px[c].get(d), px[c].get(n)
            if not (a and b): continue
            agg.setdefault(sm.sector(nm), []).append((b / a - 1) * 100)
        out[d] = {s: sum(v) / len(v) - bm for s, v in agg.items() if len(v) >= 2}
    return dates, out

def main():
    px, names = load_px()
    dates, exc = sector_excess(px, names)
    tset = sorted(exc)
    # 섹터 고정효과 = 전체기간 평균
    base = collections.defaultdict(list)
    for d in tset:
        for s, v in exc[d].items(): base[s].append(v)
    smean = {s: statistics.mean(v) for s, v in base.items()}

    def next_td(d):
        import bisect
        i = bisect.bisect_left(tset, d)
        return tset[i] if i < len(tset) else None

    rows = [json.loads(L) for L in open(os.path.join(HERE, 'actually2.jsonl'), encoding='utf-8')]
    ev = []
    for r in rows:
        t = themes.theme(r['title'] + ' ' + r['lead'])
        if not t: continue
        d = next_td(r['date'])
        if not d or t not in exc.get(d, {}): continue
        ev.append({'d': d, 'sec': t, 'raw': exc[d][t], 'adj': exc[d][t] - smean[t]})
    print(f"매핑 1,536건 중 패널 기간·섹터 매칭 이벤트 **{len(ev)}건** "
          f"({min(e['d'] for e in ev)}~{max(e['d'] for e in ev)})")
    a = [e['adj'] for e in ev]
    def t_(v): return statistics.mean(v) / (statistics.stdev(v) / len(v) ** .5)
    print(f"\n■ 전체 — 섹터조정 초과수익 평균 {statistics.mean(a):+.4f}%p · t={t_(a):+.2f} · "
          f"중앙 {statistics.median(a):+.4f} · 승률 {sum(1 for x in a if x>0)/len(a)*100:.1f}%")
    print(f"  (조정 전 raw 평균 {statistics.mean([e['raw'] for e in ev]):+.4f}%p)")
    # R2 3-fold (시간순)
    ev.sort(key=lambda e: e['d']); n = len(ev); t3 = n // 3
    f = [statistics.mean([e['adj'] for e in ev[s:e2]]) for s, e2 in [(0,t3),(t3,2*t3),(2*t3,n)]]
    print(f"  R2 3-fold: {f[0]:+.4f} / {f[1]:+.4f} / {f[2]:+.4f}")
    s = sorted(a)
    print(f"  R5 하위3제거 {statistics.mean(s[3:]):+.4f} · 상위3제거 {statistics.mean(s[:-3]):+.4f}")
    # R1 — 같은 날 같은 섹터 반박 건수(강도)
    cnt = collections.Counter((e['d'], e['sec']) for e in ev)
    print("\n■ R1 강도 고원 — 같은 날 같은 섹터 반박 건수별")
    g = collections.defaultdict(list)
    for e in ev: g[min(cnt[(e['d'], e['sec'])], 4)].append(e['adj'])
    for k in sorted(g):
        lbl = f"{k}건" + ("+" if k == 4 else "")
        print(f"  {lbl:<5} n={len(g[k]):>5}  평균 {statistics.mean(g[k]):+.4f}%p  "
              f"중앙 {statistics.median(g[k]):+.4f}  t={t_(g[k]) if len(g[k])>2 else float('nan'):+.2f}")
    # 섹터별
    print("\n■ 섹터별 (n>=30)")
    bysec = collections.defaultdict(list)
    for e in ev: bysec[e['sec']].append(e['adj'])
    for s2, v in sorted(bysec.items(), key=lambda x: statistics.mean(x[1])):
        if len(v) < 30: continue
        print(f"  {s2:<12} n={len(v):>4}  평균 {statistics.mean(v):+.4f}%p  중앙 {statistics.median(v):+.4f}  t={t_(v):+.2f}")
    json.dump(ev, open(os.path.join(HERE, '_events.json'), 'w'))

if __name__ == '__main__':
    main()
