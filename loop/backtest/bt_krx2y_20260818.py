#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_krx2y_20260818.py — 2026-08-18 기각된 KRX 파생 축 전부를 **2년(604일) 표본**에서 재검정.

배경
  이날 오전(BRD·TVQ·TAL·CWS·BTL) · 오후(TVQ재검·EFF·LIS·SRV·ADP) · 3차(SBR)에서 KRX 데이터로
  만든 축이 전부 기각됐는데, **공통 한계가 표본 113~114일**이었다. 8/13 절차("후보는 반드시 더
  긴 별도 패널에서 재검정한다")를 KRX 축에는 적용할 수 없었던 이유가 이것이다.
  KRX OPEN API 가 2024년치까지 정상 응답하므로 **604거래일(20240221~20260814)** 로 확장해
  이 한계를 정면으로 없앤다. ETF 2년 가격패널(`panel_ohlc_2y.csv`)과 구간이 정확히 일치한다.

검정 대상 — 113일에서 '가드 통과' 또는 '최선'이었던 변형들, 그리고 그 부호 대조군
  SBR  업종 참여율(하위/상위) — dart2 · yf 두 분류
  SRV  업종지수 5일 강세/약세 틸트
  EFF  ETF 설정/환매(상장좌수 변화) — 유출종목 배제 · 유입상위
  BRD  시장 등락 breadth 게이트 · TVQ 거래대금 집중도 분위수 · LIS 레버·인버스 점유율

전부 **[D-1]**(실전 조달 가능)만 돌린다 — [D] 는 KRX D+1 공개 지연으로 재현 불가(§4-5).

한계(보고서에 명시할 것)
  · 업종 매핑은 **현재 상장 종목** 기준이라 2024~2025 중 상장폐지된 종목은 매핑이 없다.
    **생존편의 미통제** — breadth 분모가 최근으로 올수록 촘촘해진다.
  · ETF 유니버스도 현재 상장분 기준이다(가격패널 자체가 그렇다).
"""
import csv, os, statistics, sys
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))
from universe_filters import eligible                 # noqa: E402

P2Y = os.path.join(HERE, 'panel_ohlc_2y.csv')
STK = os.path.join(HERE, 'krx_stock_panel.csv')
ETFP = os.path.join(HERE, 'krx_etf_panel.csv')
IDXP = os.path.join(HERE, 'krx_sector_idx.csv')
MAP_D = os.path.join(HERE, 'stock_sector_dart.csv')
MAP_Y = os.path.join(HERE, 'stock_sector_yf.csv')
BENCH, NPICK, MOM, COST = '069500', 5, 20, 0.0
SECTOR_IDX = ['KRX 자동차', 'KRX 반도체', 'KRX 헬스케어', 'KRX 은행', 'KRX 에너지화학',
              'KRX 철강', 'KRX 방송통신', 'KRX 건설', 'KRX 증권', 'KRX 기계장비',
              'KRX 보험', 'KRX 운송', 'KRX 경기소비재', 'KRX 필수소비재', 'KRX K콘텐츠',
              'KRX 정보기술', 'KRX 유틸리티']


# ─────────────────────────────────────────── 로드

def load_etf():
    px, names = defaultdict(dict), {}
    r = csv.reader(open(P2Y, encoding='utf-8'))
    next(r)
    for code, name, date, o, h, l, c, v in r:
        try:
            px[code][date] = float(c)
        except ValueError:
            continue
        names[code] = name
    return px, names


def load_stock_axes(smaps):
    """일자별: 전체 breadth · 거래대금 집중도 · 업종별 참여율(분류별) · 업종 등가중 수익률."""
    day_all = defaultdict(lambda: [0, 0, []])          # [n, up, values]
    day_sec = {k: defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0]))
               for k in smaps}                          # tag -> date -> sec -> [n, up, sumret]
    r = csv.reader(open(STK, encoding='utf-8'))
    hdr = next(r)
    i_d, i_c, i_chg, i_val = (hdr.index(x) for x in ('date', 'code', 'chg_pct', 'value'))
    for row in r:
        d, code = row[i_d], row[i_c]
        try:
            chg = float(row[i_chg]); val = float(row[i_val] or 0)
        except ValueError:
            continue
        a = day_all[d]
        a[0] += 1
        a[1] += (chg > 0)
        a[2].append(val)
        for tag, m in smaps.items():
            s = m.get(code)
            if s:
                z = day_sec[tag][d][s]
                z[0] += 1
                z[1] += (chg > 0)
                z[2] += chg
    brd, conc = {}, {}
    for d, (n, up, vals) in day_all.items():
        brd[d] = up / n
        tot = sum(vals) or 1.0
        conc[d] = sum(sorted(vals, reverse=True)[:20]) / tot
    return brd, conc, day_sec


def load_etf_krx():
    rec, mkt = defaultdict(dict), defaultdict(lambda: [0.0, 0.0, []])
    r = csv.reader(open(ETFP, encoding='utf-8'))
    hdr = next(r)
    i_d, i_c, i_n, i_v, i_s = (hdr.index(x) for x in
                               ('date', 'code', 'name', 'value', 'list_shrs'))
    for row in r:
        d, c = row[i_d], row[i_c]
        try:
            shrs = float(row[i_s] or 0); val = float(row[i_v] or 0)
        except ValueError:
            continue
        rec[c][d] = shrs
        m = mkt[d]
        m[0] += val
        if not eligible(row[i_n]):
            m[1] += val
        m[2].append(val)
    lev = {d: (v[1] / v[0] if v[0] else 0.0) for d, v in mkt.items()}
    return rec, lev


def load_sector_idx():
    out = defaultdict(dict)
    keep = set(SECTOR_IDX)
    for r in csv.DictReader(open(IDXP, encoding='utf-8')):
        if r['name'] in keep:
            try:
                out[r['date']][r['name']] = float(r['chg_pct'])
            except ValueError:
                pass
    return out


def load_maps():
    dart, yf = {}, {}
    for r in csv.DictReader(open(MAP_D, encoding='utf-8')):
        ic = (r['induty_code'] or '').strip()
        if len(ic) >= 2:
            dart[r['code']] = 'D' + ic[:2]
    for r in csv.DictReader(open(MAP_Y, encoding='utf-8')):
        s = (r['sector'] or '').strip()
        if s:
            yf[r['code']] = 'Y' + s
    return {'dart2': dart, 'yf': yf}


# ─────────────────────────────────────────── 채점 틀 (bt_breadth 와 동일 규약)

def mom(px, code, d, dates, k=MOM):
    i = dates.index(d)
    if i < k:
        return None
    a, b = px[code].get(dates[i - k]), px[code].get(d)
    return None if not (a and b) else (b / a - 1) * 100


def rule_h(px, code, d, dates):
    i = dates.index(d)
    if i < 3:
        return False
    c0, c1, c3 = px[code].get(d), px[code].get(dates[i - 1]), px[code].get(dates[i - 3])
    if not (c0 and c1 and c3):
        return False
    return (c0 / c1 - 1) * 100 > 10 or (c0 / c3 - 1) * 100 > 20


def build_cands(px, names, dates):
    """날짜별 mom20 내림차순 후보를 미리 만들어 둔다(604일 × 반복 호출 회피)."""
    pos = {d: i for i, d in enumerate(dates)}
    out = {}
    for i, d in enumerate(dates):
        if i < MOM:
            continue
        lst = []
        for code in px:
            if not eligible(names.get(code, '')):
                continue
            a, b = px[code].get(dates[i - MOM]), px[code].get(d)
            if not (a and b):
                continue
            c1, c3 = px[code].get(dates[i - 1]), px[code].get(dates[i - 3])
            if c1 and c3 and ((b / c1 - 1) * 100 > 10 or (b / c3 - 1) * 100 > 20):
                continue
            lst.append(((b / a - 1) * 100, code))
        lst.sort(reverse=True)
        out[d] = lst
    return out, pos


def fwd(px, code, d, nxt):
    a, b = px[code].get(d), px[code].get(nxt)
    return None if not (a and b) else (b / a - 1) * 100


def run(select, px, dates, cands):
    res = []
    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        bm = fwd(px, BENCH, d, nxt)
        cd = cands.get(d)
        if bm is None or not cd or len(cd) < NPICK:
            continue
        picks = select(cd, d)
        rs = [fwd(px, c, d, nxt) for c in picks]
        rs = [x for x in rs if x is not None]
        if len(rs) < NPICK:
            continue
        res.append((d, sum(rs) / len(rs) - COST - bm))
    return res


def stat(res, label):
    v = [x for _, x in res]
    if not v:
        return None
    n = len(v)
    m = sum(v) / n
    sd = statistics.stdev(v) if n > 1 else 0.0
    h = n // 2
    tr = sum(x for _, x in res[:h]) / h
    te = sum(x for _, x in res[h:]) / (n - h)
    jk = min((sum(v) - x) / (n - 1) for x in v)
    f3 = [sum(x for _, x in res[i * n // 3:(i + 1) * n // 3]) /
          max(1, len(res[i * n // 3:(i + 1) * n // 3])) for i in range(3)]
    return {'label': label, 'n': n, 'mean': m, 't': m / (sd / n ** 0.5) if sd else 0.0,
            'train': tr, 'test': te, 'win': sum(1 for x in v if x > 0) / n * 100,
            'jk': jk, 'f3': f3}


def show(s, base=None):
    d = '' if base is None else f'  Δ{s["mean"] - base["mean"]:+.4f}'
    g = ''
    if base is not None:
        pass3 = (s['mean'] > base['mean'] and s['train'] > base['train']
                 and s['test'] > base['test'] and s['jk'] > 0)
        okf = sum(1 for i in range(3) if s['f3'][i] > base['f3'][i])
        g = f'  {"✔" if pass3 else " "}가드 fold{okf}/3'
    print(f'  {s["label"]:42s} n={s["n"]:3d} full{s["mean"]:+.4f} train{s["train"]:+.4f} '
          f'test{s["test"]:+.4f} 승률{s["win"]:4.1f}% jk{s["jk"]:+.4f} t{s["t"]:+.2f}{d}{g}')


# ─────────────────────────────────────────── 규칙

def sel_base(cd, d):
    return [c for _, c in cd[:NPICK]]


def lagged(d, lag, keys):
    ds = [x for x in keys if x <= d]
    return ds[max(len(ds) - 1 - lag, 0)] if ds else None


def main():
    px, names = load_etf()
    dates = sorted({d for c in px for d in px[c]})
    print(f'ETF 2년 패널 {len(dates)}일 {dates[0]}~{dates[-1]} · 종목 {len(px)}')
    maps = load_maps()
    brd, conc, day_sec = load_stock_axes(maps)
    rec, lev = load_etf_krx()
    sec_ret = load_sector_idx()
    kdates = sorted(brd)
    print(f'KRX 개별종목 {len(kdates)}일 · ETF패널 {len({d for c in rec for d in rec[c]})}일 · '
          f'업종지수 {len(sec_ret)}일')
    cands, pos = build_cands(px, names, dates)
    base = stat(run(sel_base, px, dates, cands), 'BASE mom20+RuleH (2년)')
    show(base)
    print(f'  fold {base["f3"][0]:+.4f} {base["f3"][1]:+.4f} {base["f3"][2]:+.4f}\n')

    # ETF→업종 배정: 60일 롤링 상관 argmax (SBR 과 동일 방법)
    codes = sorted(px)
    R = np.full((len(dates), len(codes)), np.nan)
    for j, c in enumerate(codes):
        s = px[c]
        for i in range(1, len(dates)):
            a, b = s.get(dates[i - 1]), s.get(dates[i])
            if a and b:
                R[i, j] = (b / a - 1) * 100
    idx_etf = {c: j for j, c in enumerate(codes)}

    built = {}
    for tag in maps:
        secs = sorted({s for d in day_sec[tag] for s in day_sec[tag][d]
                       if day_sec[tag][d][s][0] >= 5})
        sret = np.full((len(kdates), len(secs)), np.nan)
        sbrd = np.full((len(kdates), len(secs)), np.nan)
        for i, d in enumerate(kdates):
            row = day_sec[tag].get(d, {})
            for j, s in enumerate(secs):
                z = row.get(s)
                if z and z[0] >= 5:
                    sbrd[i, j] = z[1] / z[0]
                    sret[i, j] = z[2] / z[0]
        built[tag] = (secs, sret, sbrd)
        print(f'[{tag}] 업종 {len(secs)}개')

    kpos = {d: i for i, d in enumerate(kdates)}
    assign_cache = {}

    def assign(tag, d):
        i = kpos.get(d)
        if i is None:
            return None
        key = (tag, i // 20)
        if key in assign_cache:
            return assign_cache[key]
        secs, sret, _ = built[tag]
        lo = max(1, i - 59)
        A = R[max(1, lo):i + 1] if i + 1 <= len(dates) else None
        Bm = sret[lo:i + 1]
        m = min(len(A) if A is not None else 0, len(Bm))
        if m < 20:
            assign_cache[key] = None
            return None
        A, Bm = A[-m:], Bm[-m:]
        ok = ~np.isnan(Bm).any(1)
        A, Bm = A[ok], Bm[ok]
        if A.shape[0] < 20:
            assign_cache[key] = None
            return None
        valid = (~np.isnan(A)).sum(0)
        mu, sd = np.nanmean(A, axis=0), np.nanstd(A, axis=0)
        Az = np.nan_to_num((A - mu) / (sd + 1e-9), nan=0.0)
        Bz = (Bm - Bm.mean(0)) / (Bm.std(0) + 1e-9)
        out = np.nanargmax(Az.T @ Bz / A.shape[0], axis=1)
        out[valid < 20] = -1
        assign_cache[key] = out
        return out

    def sbr(tag, pool, direction, lag=1):
        _, _, sbrd = built[tag]

        def f(cd, d):
            ref = lagged(d, lag, kdates)
            a = assign(tag, ref) if ref else None
            if a is None:
                return sel_base(cd, d)
            row = sbrd[kpos[ref]]
            sc = []
            for _, c in cd[:pool]:
                j = idx_etf.get(c)
                if j is None or a[j] < 0:
                    continue
                v = row[a[j]]
                if not np.isnan(v):
                    sc.append((v, c))
            if len(sc) < NPICK:
                return sel_base(cd, d)
            sc.sort(reverse=(direction == 'high'))
            return [c for _, c in sc[:NPICK]]
        return f

    def srv(pool, direction, span=5, lag=1):
        sdates = sorted(sec_ret)

        def f(cd, d):
            ref = lagged(d, lag, sdates)
            if ref is None:
                return sel_base(cd, d)
            win = [x for x in sdates if x <= ref][-span:]
            a = assign('dart2', lagged(d, lag, kdates))
            sc = []
            for _, c in cd[:pool]:
                nm = names.get(c, '')
                s = etf_sector_token(nm)
                if not s:
                    continue
                vs = [sec_ret[x].get(s) for x in win]
                vs = [v for v in vs if v is not None]
                if vs:
                    sc.append((sum(vs), c))
            if len(sc) < NPICK:
                return sel_base(cd, d)
            sc.sort(reverse=(direction == 'strong'))
            return [c for _, c in sc[:NPICK]]
        return f

    def eff(mode, pool=15, lag=1):
        rd = {c: sorted(rec[c]) for c in rec}

        def flow(c, ref):
            s = rec.get(c)
            if not s:
                return None
            ds = [x for x in rd[c] if x <= ref]
            if len(ds) < 2:
                return None
            a, b = s[ds[-2]], s[ds[-1]]
            return None if not (a and b) else (b / a - 1) * 100

        def f(cd, d):
            ref = lagged(d, lag, kdates)
            if ref is None:
                return sel_base(cd, d)
            if mode == 'exclude':
                keep = [c for _, c in cd if (flow(c, ref) is None or flow(c, ref) >= 0)]
                return keep[:NPICK] if len(keep) >= NPICK else sel_base(cd, d)
            fl = [(flow(c, ref), c) for _, c in cd[:pool]]
            fl = [x for x in fl if x[0] is not None]
            if len(fl) < NPICK:
                return sel_base(cd, d)
            fl.sort(reverse=(mode == 'top'))
            return [c for _, c in fl[:NPICK]]
        return f

    def gate_series(series, q, lag=1, win=60, above=True):
        keys = sorted(series)

        def f(cd, d):
            ref = lagged(d, lag, keys)
            if ref is None:
                return sel_base(cd, d)
            i = keys.index(ref)
            hist = [series[x] for x in keys[max(0, i - win):i]]
            if len(hist) < 20:
                return sel_base(cd, d)
            p = sum(1 for x in hist if x <= series[ref]) / len(hist)
            hit = (p > q) if above else (p < 1 - q)
            return [c for _, c in (cd[-NPICK:] if hit else cd[:NPICK])]
        return f

    tests = []
    for tag in ('dart2', 'yf'):
        for pool in (8, 10, 12, 15):
            tests.append((f'SBR[{tag}] 참여율하위5 pool{pool} [D-1]', sbr(tag, pool, 'low')))
        tests.append((f'SBR[{tag}] 참여율상위5 pool10 [D-1](대조)', sbr(tag, 10, 'high')))
    tests += [
        ('SRV 업종강세5 pool15 5일 [D-1]', srv(15, 'strong')),
        ('SRV 업종강세5 pool10 5일 [D-1]', srv(10, 'strong')),
        ('EFF 환매(유출)종목 배제 [D-1]', eff('exclude')),
        ('EFF 상위15중 유입상위5 [D-1]', eff('top')),
        ('BRD 전체breadth<0.40 역전 [D-1]', gate_series(brd, 0.0, 1, above=False)),
        ('TVQ 집중도 롤링p80 초과 역전 [D-1]', gate_series(conc, 0.80)),
        ('TVQ 집중도 롤링p70 초과 역전 [D-1]', gate_series(conc, 0.70)),
        ('LIS 레버인버스점유 롤링p80 초과 역전 [D-1]', gate_series(lev, 0.80)),
    ]

    print(f'\n=== 2년(604일) 재검정 — {len(tests)}변형 · 전부 [D-1] 실전 가능 ===')
    rows = []
    for label, f in tests:
        s = stat(run(f, px, dates, cands), label)
        if s:
            show(s, base)
            rows.append(s)

    print('\n--- 3분할 가드 + fold 3/3 ---')
    ok = [s for s in rows if s['mean'] > base['mean'] and s['train'] > base['train']
          and s['test'] > base['test'] and s['jk'] > 0
          and all(s['f3'][i] > base['f3'][i] for i in range(3))]
    if ok:
        for s in ok:
            show(s, base)
    else:
        print('  통과 0건.')
    return 0


NAME2SEC = [
    (('반도체', '메모리', '팹리스'), 'KRX 반도체'),
    (('자동차', '모빌리티', '자율주행'), 'KRX 자동차'),
    (('바이오', '헬스케어', '제약', '의료', '헬스'), 'KRX 헬스케어'),
    (('은행', '금융', '지주'), 'KRX 은행'), (('증권',), 'KRX 증권'), (('보험',), 'KRX 보험'),
    (('건설', '건자재', '리츠', '부동산'), 'KRX 건설'),
    (('조선', '기계', '방산', '우주', '항공', '로봇', '휴머노이드', '중공업'), 'KRX 기계장비'),
    (('철강', '비철', '금속', '소재'), 'KRX 철강'),
    (('2차전지', '배터리', '화학', '에너지', '태양광', '수소', '풍력', 'ESS'), 'KRX 에너지화학'),
    (('통신', '미디어', '방송'), 'KRX 방송통신'),
    (('게임', '엔터', 'K팝', '콘텐츠', '웹툰'), 'KRX K콘텐츠'),
    (('AI', '소프트웨어', 'IT', '플랫폼', '인터넷', '클라우드', '데이터센터'), 'KRX 정보기술'),
    (('원자력', '전력', '유틸리티', '가스'), 'KRX 유틸리티'),
    (('운송', '물류', '해운'), 'KRX 운송'),
    (('화장품', '식품', '음식료', '유통', '소비재'), 'KRX 필수소비재'),
    (('여행', '레저', '호텔'), 'KRX 경기소비재'),
]


def etf_sector_token(name):
    for toks, sec in NAME2SEC:
        if any(t in name for t in toks):
            return sec
    return None


if __name__ == '__main__':
    sys.exit(main())
