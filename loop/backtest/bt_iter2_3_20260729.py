# -*- coding: utf-8 -*-
"""2026-07-29 루프 iteration 2·3 — distinct 2축 백테스트.

iteration 2 (축 ②) Rule RS — 코스피/코스닥 상대강도 로테이션
  KODEX200(069500) vs KODEX 코스닥150(229200)의 최근 k일 상대강도로 그날의
  '주도 시장'을 판정하고, 그 시장 계열 ETF만 후보로 남긴 뒤 mom20 상위5.
  ※ 기각된 Rule R'(regime 게이팅)는 지수 절대수익 기반이고, 본 축은
    두 시장 간 '횡단면 상대강도'라 구별된다.

iteration 3 (축 ③) Rule X — 외국인·기관 수급 프록시
  ETF 자체의 외국인 보유비중 변화(foreign_trend_panel)·기관 순매수
  (institution_trend_panel)를 D까지 누적해 랭킹에 반영.
  ※ 2026-07-11 잠정 등록 후 백테스트 미실행 축.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유, 무비용 - KODEX200), 평균 %p/일.  # 2026-08-14 비용 0
가드: full·train·test 3개 모두 baseline 초과일 때만 후보 승격.
룩어헤드 금지 — 선정은 D 종가·D까지 수급 정보만 사용.
"""
import csv
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANEL = os.path.join(HERE, 'panel_close_0728.csv')
FOR = os.path.join(ROOT, 'references', 'foreign_trend_panel.csv')
INS = os.path.join(ROOT, 'references', 'institution_trend_panel.csv')
BENCH, KQ = '069500', '229200'
COST, MINP = 0.0, 10000  # 2026-08-14 사용자 지시 — 왕복비용 없음(무료 수수료·ETF 거래세 면제, 겹치는 종목은 계속 보유하고 교체분만 거래). 종전값 0.0010(왕복 10bp)

CASH_KW = ['머니마켓', 'CD금리', 'CD1년', '초단기채', 'KOFR', '국고채', '통안',
           '금리액티브', '금리플러스', '금리투자']
KQ_KW = ['코스닥']
KS_KW = ['200', '코스피']


def load_panel():
    px, name = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError):
            continue
        name[r['code']] = r['name']
    return px, name, sorted({d for c in px for d in px[c]})


def load_flow():
    fo, ins = defaultdict(dict), defaultdict(dict)
    try:
        for r in csv.DictReader(open(FOR, encoding='utf-8')):
            try:
                fo[r['code']][r['date']] = float(str(r['wght']).replace('+', ''))
            except (ValueError, KeyError):
                continue
    except OSError:
        pass
    try:
        for r in csv.DictReader(open(INS, encoding='utf-8')):
            for key in ('orgn_net_qty', 'chg_qty', 'netprps_qty'):
                if key in r:
                    try:
                        ins[r['code']][r['date']] = float(str(r[key]).replace('+', ''))
                    except (ValueError, TypeError):
                        pass
                    break
    except OSError:
        pass
    return fo, ins


def is_spot(nm):
    n = (nm or '').replace(' ', '')
    return not ('인버스' in n or '곱버스' in n or '레버리지' in n
                or '2X' in n.upper() or '2배' in n or '숏' in n)


def is_cash(nm):
    n = (nm or '').replace(' ', '')
    return any(k in n for k in CASH_KW)


def mom(px, c, d, di, dates, k):
    i = di[d]
    if i < k:
        return None
    a, b = px[c].get(dates[i - k]), px[c].get(d)
    return (b / a - 1.0) if (a and b) else None


def rule_h_ok(px, c, d, di, dates):
    s, c3 = mom(px, c, d, di, dates, 1), mom(px, c, d, di, dates, 3)
    if s is not None and s > 0.10:
        return False
    if c3 is not None and c3 > 0.20:
        return False
    return True


def build_cand(px, name, d, di, dates):
    out = []
    for c in px:
        pc = px[c].get(d)
        if not pc or pc < MINP or not is_spot(name.get(c, '')) or is_cash(name.get(c, '')):
            continue
        m = mom(px, c, d, di, dates, 20)
        if m is None or not rule_h_ok(px, c, d, di, dates):
            continue
        out.append({'code': c, 'mom': m, 'name': name.get(c, '')})
    return out


def base_sel(cand, **_):
    return [x['code'] for x in sorted(cand, key=lambda x: -x['mom'])[:5]]


def rs_sel(cand, px=None, d=None, di=None, dates=None, k=5, **_):
    """Rule RS — 코스피/코스닥 상대강도로 주도시장 계열만 남긴다."""
    a1, b1 = None, None
    i = di[d]
    if i >= k:
        pa, pb = px[BENCH].get(dates[i - k]), px[BENCH].get(d)
        qa, qb = px[KQ].get(dates[i - k]), px[KQ].get(d)
        if pa and pb and qa and qb:
            a1, b1 = pb / pa - 1.0, qb / qa - 1.0
    if a1 is None:
        return base_sel(cand)
    lead_kq = b1 > a1
    keep = []
    for x in cand:
        n = x['name'].replace(' ', '')
        is_kq = any(w in n for w in KQ_KW)
        is_ks = any(w in n for w in KS_KW) and not is_kq
        if lead_kq and is_ks:
            continue
        if (not lead_kq) and is_kq:
            continue
        keep.append(x)
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def flow_score(tbl, c, d, di, dates, k, mode='level'):
    """mode='level' 보유비중(수준) → 구간 변화량 / mode='flow' 순매수량 → 구간 합계."""
    i = di[d]
    if i < k:
        return None
    vals = [tbl[c][dates[j]] for j in range(i - k + 1, i + 1)
            if dates[j] in tbl.get(c, {})]
    if len(vals) < max(2, k // 2):
        return None
    return (vals[-1] - vals[0]) if mode == 'level' else sum(vals)


def x_sel(cand, px=None, d=None, di=None, dates=None, fo=None, ins=None,
          src='fo', pool=15, **_):
    """Rule X — mom20 상위 pool 안에서 수급 스코어 상위5."""
    tbl, mode = (fo, 'level') if src == 'fo' else (ins, 'flow')
    top = sorted(cand, key=lambda x: -x['mom'])[:pool]
    sc = []
    for x in top:
        s = flow_score(tbl, x['code'], d, di, dates, 5, mode)
        if s is not None:
            sc.append((s, x['code']))
    if len(sc) < 5:
        return base_sel(cand)
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


def x_filter(cand, px=None, d=None, di=None, dates=None, fo=None, ins=None,
             src='fo', **_):
    """Rule X2 — 수급 악화(스코어<0) 종목 사전제외 후 mom20 상위5."""
    tbl, mode = (fo, 'level') if src == 'fo' else (ins, 'flow')
    keep = []
    for x in cand:
        s = flow_score(tbl, x['code'], d, di, dates, 5, mode)
        if s is not None and s < 0:
            continue
        keep.append(x)
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def run(fn, px, name, dates, di, fo, ins, lo=None, hi=None, **kw):
    recs = []
    rng = range(21, len(dates) - 1)
    for i in rng:
        d, nxt = dates[i], dates[i + 1]
        if lo and d < lo:
            continue
        if hi and d > hi:
            continue
        cand = build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        picks = fn(cand, px=px, d=d, di=di, dates=dates, fo=fo, ins=ins, **kw)
        rets = [px[c][nxt] / px[c][d] - 1.0 for c in picks
                if px[c].get(d) and px[c].get(nxt)]
        if not rets:
            continue
        ba, bb = px[BENCH].get(d), px[BENCH].get(nxt)
        if not (ba and bb):
            continue
        recs.append(100 * ((sum(rets) / len(rets) - COST) - (bb / ba - 1.0)))
    return recs


def report(title, variants, px, name, dates, di, fo, ins, lo=None, hi=None):
    print(f'\n=== {title} ===')
    base = None
    print(f"{'변형':38s} {'전체':>9s} {'train':>9s} {'test':>9s}  판정")
    print('-' * 80)
    for label, fn, kw in variants:
        r = run(fn, px, name, dates, di, fo, ins, lo=lo, hi=hi, **kw)
        if not r:
            print(f'{label:38s} — 표본 없음')
            continue
        h = len(r) // 2
        full, tr, te = statistics.mean(r), statistics.mean(r[:h]), statistics.mean(r[h:])
        if base is None:
            base, v = (full, tr, te), f'기준선 (n={len(r)}일)'
        else:
            v = '후보승격' if (full > base[0] and tr > base[1] and te > base[2]) \
                else '기각(가드 미통과)'
        print(f'{label:38s} {full:+9.4f} {tr:+9.4f} {te:+9.4f}  {v}')


def main():
    px, name, dates = load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = load_flow()
    print(f'패널 {len(dates)}일 ({dates[0]}~{dates[-1]}) · {len(px)}종')
    print(f'수급: 외국인 {len(fo)}종 · 기관 {len(ins)}종')

    report('iteration 2 — Rule RS (코스피/코스닥 상대강도 로테이션)', [
        ('baseline (mom20+RuleH)', base_sel, {}),
        ('RS1 상대강도 5일', rs_sel, {'k': 5}),
        ('RS2 상대강도 10일', rs_sel, {'k': 10}),
        ('RS3 상대강도 20일', rs_sel, {'k': 20}),
    ], px, name, dates, di, fo, ins)

    # 수급 패널은 20260710까지만 존재 → 해당 구간으로 한정
    fdates = sorted({d for c in fo for d in fo[c]})
    hi = fdates[-1] if fdates else None
    report(f'iteration 3 — Rule X (외국인·기관 수급 프록시, ~{hi})', [
        ('baseline (mom20+RuleH)', base_sel, {}),
        ('X1 상위15풀 → 외국인비중증가 상위5', x_sel, {'src': 'fo', 'pool': 15}),
        ('X2 외국인비중 감소종목 제외', x_filter, {'src': 'fo'}),
        ('X3 상위15풀 → 기관순매수 상위5', x_sel, {'src': 'ins', 'pool': 15}),
        ('X4 기관 순매도 종목 제외', x_filter, {'src': 'ins'}),
    ], px, name, dates, di, fo, ins, hi=hi)


if __name__ == '__main__':
    main()
