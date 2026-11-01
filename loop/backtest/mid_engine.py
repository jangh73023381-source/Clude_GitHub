# -*- coding: utf-8 -*-
"""중기(다일 보유) · 비가격축 백테스트 공용 엔진.

핵심 설계 — 겹치지 않는(non-overlapping) 다중 오프셋 평가
------------------------------------------------------
보유 H일 전략을 매일 재구성하면 관측이 H배 겹쳐 t값이 부풀려진다.
그래서 오프셋 0..H-1 각각에 대해 H일 간격의 독립 시점만 뽑아 평가하고,
오프셋별 평균의 분산으로 안정성을 판단한다(오프셋 간 평균의 t = 겹침 없는 t).
"""
import csv, os, math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, os.environ.get('PANEL_FILE', 'panel_ohlc_2y.csv'))
BENCH = '069500'
MINP = 10000
NPICK = 5
COST = 0.0010


def is_excluded(nm):
    n = nm.replace(' ', '').upper()
    return ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n
            or '2배' in n or '숏' in n)


def is_cashlike(nm):
    n = nm.replace(' ', '')
    return any(kw in n for kw in ('머니마켓', 'CD금리', '초단기채', 'KOFR',
                                 '국고채', '통안', 'CP금리'))


def rsi_series(px, n=14):
    out = [None] * len(px)
    if len(px) <= n:
        return out

    def _r(ag, al):
        if al == 0:
            return 100.0 if ag > 0 else 50.0
        return 100 - 100 / (1 + ag / al)
    g = l = 0.0
    for i in range(1, n + 1):
        ch = px[i] - px[i - 1]; g += max(ch, 0.0); l += max(-ch, 0.0)
    ag = g / n; al = l / n
    out[n] = _r(ag, al)
    for i in range(n + 1, len(px)):
        ch = px[i] - px[i - 1]
        ag = (ag * (n - 1) + max(ch, 0.0)) / n
        al = (al * (n - 1) + max(-ch, 0.0)) / n
        out[i] = _r(ag, al)
    return out


def build():
    """code -> dict(지표 배열). 모든 지표는 인덱스 i에서 dates[0..i]만 사용."""
    raw = defaultdict(dict); name = {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                raw[r['code']][r['date']] = (
                    float(r['high']), float(r['low']),
                    float(r['close']), float(r['volume']))
            except Exception:
                continue
            name[r['code']] = r['name']
    all_dates = sorted({d for c in raw for d in raw[c]})
    cache = {}
    for code, s in raw.items():
        ds = sorted(s)
        hi = [s[d][0] for d in ds]; lo = [s[d][1] for d in ds]
        px = [s[d][2] for d in ds]; vol = [s[d][3] for d in ds]
        n = len(px)
        e = {'dates': ds, 'idx': {d: i for i, d in enumerate(ds)},
             'px': px, 'hi': hi, 'lo': lo, 'vol': vol}
        e['rsi14'] = rsi_series(px, 14)
        # 모멘텀
        for k in (5, 20, 60, 120):
            a = [None] * n
            for i in range(k, n):
                if px[i - k]:
                    a[i] = px[i] / px[i - k] - 1.0
            e[f'mom{k}'] = a
        # 볼린저 %B / MA
        ma = [None] * n; sd = [None] * n
        rs = rs2 = 0.0
        for i, v in enumerate(px):
            rs += v; rs2 += v * v
            if i >= 20:
                o = px[i - 20]; rs -= o; rs2 -= o * o
            if i >= 19:
                m = rs / 20; var = max(rs2 / 20 - m * m, 0.0)
                ma[i] = m; sd[i] = var ** 0.5
        pb = [None] * n
        for i in range(n):
            if ma[i] and sd[i]:
                pb[i] = 0.5 + (px[i] - ma[i]) / (4 * sd[i])
        e['pctb'] = pb
        # 피보나치 되돌림(L=60, UP국면만 값 부여) & 채널위치
        retr = [None] * n; chpos = [None] * n
        for i in range(59, n):
            H = max(hi[i - 59:i + 1]); L = min(lo[i - 59:i + 1])
            if H <= L:
                continue
            chpos[i] = (px[i] - L) / (H - L)
            iH = iL = i - 59
            for j in range(i - 59, i + 1):
                if hi[j] >= hi[iH]:
                    iH = j          # 동률이면 가장 최근
                if lo[j] <= lo[iL]:
                    iL = j
            retr[i] = (H - px[i]) / (H - L) if iH > iL else None
        e['retr60'] = retr; e['chpos60'] = chpos
        # 거래대금·거래량 급증
        amt = [px[i] * vol[i] for i in range(n)]
        e['amt'] = amt
        vs = [None] * n; asf = [None] * n; a60 = [None] * n
        for i in range(20, n):
            mv = sum(vol[i - 20:i]) / 20
            ma_ = sum(amt[i - 20:i]) / 20
            if mv > 0:
                vs[i] = vol[i] / mv
            if ma_ > 0:
                asf[i] = amt[i] / ma_
        for i in range(60, n):
            m6 = sum(amt[i - 60:i]) / 60
            if m6 > 0:
                a60[i] = amt[i] / m6
        e['volsurge'] = vs; e['amtsurge'] = asf; e['amtsurge60'] = a60
        # 거래대금 5일 평균(유동성 필터용)
        la = [None] * n
        for i in range(5, n):
            la[i] = sum(amt[i - 5:i + 1]) / 6
        e['amt5'] = la
        cache[code] = e
    return cache, name, all_dates


def eligible(cache, name, d, minp=MINP, min_amt=None):
    out = []
    for code, e in cache.items():
        nm = name[code]
        if is_excluded(nm) or is_cashlike(nm):
            continue
        i = e['idx'].get(d)
        if i is None or e['px'][i] < minp:
            continue
        if min_amt is not None:
            a = e['amt5'][i]
            if a is None or a < min_amt:
                continue
        out.append((code, i))
    return out


def rule_h_ok(e, i):
    if i < 3:
        return True
    p0, p1, p3 = e['px'][i], e['px'][i - 1], e['px'][i - 3]
    if p1 and p0 / p1 - 1.0 > 0.10:
        return False
    if p3 and p0 / p3 - 1.0 > 0.20:
        return False
    return True


# ---------------- 다중 오프셋 평가 ----------------
def run_h(cache, name, dates, picker, label, H=20, warm=140, min_amt=None):
    """오프셋 0..H-1 별로 H일 간격 독립 시점만 평가. 반환: (label, per_offset, all_obs)"""
    be = cache[BENCH]
    per = []; allobs = []
    for off in range(H):
        obs = []
        k = warm + off
        while k + H < len(dates):
            d = dates[k]; dn = dates[k + H]
            bi = be['idx'].get(d); bj = be['idx'].get(dn)
            if bi is None or bj is None:
                k += H; continue
            bench = be['px'][bj] / be['px'][bi] - 1.0
            univ = eligible(cache, name, d, min_amt=min_amt)
            picks = picker(cache, name, d, univ)
            rets = []
            for c in picks:
                e = cache[c]; i = e['idx'][d]; j = e['idx'].get(dn)
                if j is not None:
                    rets.append(e['px'][j] / e['px'][i] - 1.0)
            if rets:
                obs.append(sum(rets) / len(rets) - COST - bench)
            else:
                obs.append(0.0 - bench)
            k += H
        if obs:
            per.append(sum(obs) / len(obs))
            allobs += obs
    return label, per, allobs


def stat(per, allobs):
    n = len(per)
    m = sum(per) / n
    var = sum((x - m) ** 2 for x in per) / (n - 1) if n > 2 else 0
    se = math.sqrt(var / n) if var > 0 else 0
    t = m / se if se > 0 else 0
    win = sum(1 for x in allobs if x > 0) / len(allobs) * 100 if allobs else 0
    pos = sum(1 for x in per if x > 0)
    return {'mean': m * 100, 't': t, 'win': win, 'npos': pos, 'noff': n,
            'lo': min(per) * 100, 'hi': max(per) * 100, 'nobs': len(allobs)}


def show(rows):
    print(f'\n{"전략":<34}{"평균 H일초과%":>13}{"t(오프셋)":>10}{"승률%":>7}'
          f'{"오프셋 양수":>11}{"최저%":>9}{"최고%":>9}{"관측":>7}')
    print('-' * 102)
    for lbl, s in rows:
        print(f'{lbl:<34}{s["mean"]:>13.3f}{s["t"]:>10.2f}{s["win"]:>7.1f}'
              f'{(str(s["npos"])+"/"+str(s["noff"])):>11}{s["lo"]:>9.3f}'
              f'{s["hi"]:>9.3f}{s["nobs"]:>7}')


def mk_rank(key, reverse, cond=None, ruleh=True):
    def f(cache, name, d, univ):
        sc = []
        for code, i in univ:
            e = cache[code]
            v = e[key][i]
            if v is None:
                continue
            if ruleh and not rule_h_ok(e, i):
                continue
            if cond and not cond(e, i):
                continue
            sc.append((v, code))
        sc.sort(reverse=reverse)
        return [c for _, c in sc[:NPICK]]
    return f
