# -*- coding: utf-8 -*-
"""2026-09-05 — Rule CB 진입 밴드의 '비대칭' ATR 정규화 검정 (7년 패널).

배경: 2026-08-03 bt_atr_cb.py 는 상·하한을 '함께' ATR 배수로 스케일한 4변형만 재고
      전부 고정 밴드에 미달했다. 그러나 고정 %는 ATR 단위로 환산하면 고변동 종목에
      이미 더 빡빡하다(상단 +1.5% = ATR 6.24% 종목엔 0.24 ATR / 1.94% 종목엔 0.77 ATR).
      즉 대칭 ATR 스케일은 고변동 종목의 상단을 '넓혀주는' 방향이고, 매수상단 검정에서
      확인된 역선택(체결 장치를 넓히면 고변동 픽을 비싸게 잡는다)과 같은 실패로 보인다.
      → 상·하한을 다르게 다루는 비대칭 형태는 미검정 칸이다. 이 스크립트가 그 칸을 채운다.

선정 mom150 상위5 · 청산 탈락 첫날 종가(기간조건 없음) · 비용 0(v2.8) ·
벤치 KODEX200(069500) 대비 %p/일 · 패널 panel_ohlc_long.csv(7년).
ATR14 는 D 까지(15:20 시점에 당일 고저는 사실상 확정) — D-1 기준 민감도는 말미에 병기.
"""
import csv, os, sys, statistics, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import is_cash, is_deriv  # noqa: E402

PANEL = os.path.join(HERE, 'panel_ohlc_long.csv')
BENCH = '069500'
ATR_MED = 3.57   # 픽5 ATR14% 중앙값 (2026-08-03 실측) — 역스케일 기준점


def load():
    bar, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
        except (ValueError, KeyError):
            continue
        if min(o, h, l, c) <= 0:
            continue
        nm[r['code']] = r['name']
        bar[r['code']][r['date']] = (o, h, l, c)
    bar = {c: v for c, v in bar.items() if not is_deriv(nm[c]) and not is_cash(nm[c])}
    return bar, nm, sorted({d for v in bar.values() for d in v})


def build_atr(bar, dates, di, codes, n=14, lag=0):
    """atr[(code,date)] = ATR14/종가 *100. lag=1 이면 D-1 까지의 정보만."""
    out = {}
    for c in codes:
        v = bar[c]
        for d in v:
            i = di[d] - lag
            if i < n:
                continue
            trs = []
            ok = True
            for j in range(i - n + 1, i + 1):
                cur, prv = v.get(dates[j]), v.get(dates[j - 1])
                if not cur or not prv:
                    ok = False; break
                trs.append(max(cur[1] - cur[2], abs(cur[1] - prv[3]), abs(cur[2] - prv[3])))
            if ok and trs:
                out[(c, d)] = 100.0 * (sum(trs) / len(trs)) / v[d][3]
    return out


def top5_by_day(bar, dates, di, k=150):
    res = {}
    for i in range(k + 1, len(dates) - 1):
        d = dates[i]
        cs = []
        for c, v in bar.items():
            a, b = v.get(dates[i - k]), v.get(d)
            if a and b:
                cs.append((b[3] / a[3] - 1.0, c))
        cs.sort(reverse=True)
        res[i] = [c for _, c in cs[:5]]
    return res


def run(bar, dates, di, tops, atr, ok_fn):
    """ok_fn(chg_pct, atr_pct) -> bool. 반환 (일별초과 리스트, 날짜, 진입건수)"""
    held, daily, dd, nbuy = {}, [], [], 0
    for i in sorted(tops):
        d = dates[i]
        if d not in bar[BENCH] or dates[i - 1] not in bar[BENCH]:
            continue
        top = tops[i]
        if not top:
            continue
        rs = []
        for c in held:
            a, b = bar[c].get(dates[i - 1]), bar[c].get(d)
            if a and b:
                rs.append(b[3] / a[3] - 1)
        if rs:
            bch = bar[BENCH][d][3] / bar[BENCH][dates[i - 1]][3] - 1
            daily.append(100 * (sum(rs) / len(rs) - bch)); dd.append(d)
        for c in [c for c in held if c not in top]:
            del held[c]
        for c in top:
            if c in held or d not in bar[c]:
                continue
            prv = bar[c].get(dates[i - 1])
            if not prv:
                continue
            chg = 100 * (bar[c][d][3] / prv[3] - 1)
            a = atr.get((c, d))
            if a is None:
                continue
            if ok_fn(chg, a):
                held[c] = bar[c][d][3]; nbuy += 1
    return daily, dd, nbuy


def stat(v):
    if len(v) < 3:
        return None
    mu = statistics.mean(v); sd = statistics.stdev(v)
    t = mu / (sd / len(v) ** 0.5) if sd else 0.0
    return mu, sum(1 for x in v if x > 0) / len(v), t, len(v)


def rep(lab, v, nbuy=None):
    s = stat(v)
    if not s:
        print(f'  {lab:34s}  (표본 없음)'); return
    mu, wr, t, n = s
    extra = f'{nbuy:>7d}' if nbuy is not None else ' ' * 7
    print(f'  {lab:34s}{mu:+9.4f}{wr:8.1%}{t:8.2f}{n:7d}{extra}')


def main():
    bar, nm, dates = load()
    di = {d: i for i, d in enumerate(dates)}
    tops = top5_by_day(bar, dates, di)
    codes = {c for v in tops.values() for c in v}
    atr = build_atr(bar, dates, di, codes, lag=0)
    print(f'패널 {len(dates)}거래일 {dates[0]}~{dates[-1]} · 선정일 {len(tops)} · 픽 등장 종목 {len(codes)}')
    av = [atr[k] for k in atr]
    av.sort()
    print(f'ATR14% 분포(픽 등장 종목 전체 {len(av)}건): 중앙 {av[len(av)//2]:.2f} '
          f'하위10% {av[len(av)//10]:.2f} 상위10% {av[9*len(av)//10]:.2f}')
    print()
    hdr = f'  {"방식":34s}{"평균초과":>9s}{"승률":>8s}{"t":>8s}{"보유일":>7s}{"진입":>7s}'
    print('기준선 및 대칭(2026-08-03 재현)')
    print(hdr); print('  ' + '-' * 73)
    base = {}
    for lab, fn in [
        ('밴드 없음(전량 매수)', lambda c, a: True),
        ('고정 -0.5% ~ +1.5% (현행)', lambda c, a: -0.5 <= c <= 1.5),
        ('대칭 ATR -0.50 ~ +1.00', lambda c, a: -0.50 <= c / a <= 1.00),
        ('대칭 ATR -0.15 ~ +0.45', lambda c, a: -0.15 <= c / a <= 0.45),
    ]:
        v, dd, nb = run(bar, dates, di, tops, atr, fn)
        base[lab] = v; rep(lab, v, nb)
    print()
    print('비대칭 A — 하단만 ATR (상단 고정 +1.5%)')
    print(hdr); print('  ' + '-' * 73)
    res = {}
    for a_ in (0.10, 0.15, 0.20, 0.25, 0.30):
        lab = f'A: lo=-{a_:.2f}ATR, hi=+1.5%'
        v, dd, nb = run(bar, dates, di, tops, atr,
                        lambda c, a, a_=a_: -a_ <= c / a and c <= 1.5)
        res[lab] = v; rep(lab, v, nb)
    print()
    print('비대칭 B — 상단만 ATR (하단 고정 -0.5%)')
    print(hdr); print('  ' + '-' * 73)
    for b_ in (0.20, 0.30, 0.40, 0.50, 0.60):
        lab = f'B: lo=-0.5%, hi=+{b_:.2f}ATR'
        v, dd, nb = run(bar, dates, di, tops, atr,
                        lambda c, a, b_=b_: -0.5 <= c and c / a <= b_)
        res[lab] = v; rep(lab, v, nb)
    print()
    print('비대칭 C — 상단 역-ATR (고변동일수록 좁게, hi = U x 3.57/ATR)')
    print(hdr); print('  ' + '-' * 73)
    for u in (1.0, 1.25, 1.5, 1.75, 2.0):
        lab = f'C: lo=-0.5%, hi=+{u:.2f}x(3.57/ATR)'
        v, dd, nb = run(bar, dates, di, tops, atr,
                        lambda c, a, u=u: -0.5 <= c <= u * ATR_MED / a)
        res[lab] = v; rep(lab, v, nb)
    print()
    print('비대칭 D — 상단 min(고정 1.5%, b x ATR) (둘 중 빡빡한 쪽)')
    print(hdr); print('  ' + '-' * 73)
    for b_ in (0.20, 0.30, 0.40, 0.50, 0.60):
        lab = f'D: hi=min(1.5%, {b_:.2f}ATR)'
        v, dd, nb = run(bar, dates, di, tops, atr,
                        lambda c, a, b_=b_: -0.5 <= c <= min(1.5, b_ * a))
        res[lab] = v; rep(lab, v, nb)

    import json
    json.dump({k: v for k, v in list(base.items()) + list(res.items())},
              open(os.path.join(HERE, '_asym_daily.json'), 'w'))
    print('\n일별 시계열 저장: _asym_daily.json')


if __name__ == '__main__':
    main()
