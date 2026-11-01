# -*- coding: utf-8 -*-
"""Rule FF 정식 백테스트 — 해외벤치마크 역행 하향 (2026-07-16 조건부 관찰 등록분).
정의: 후보 ETF가 추종하는 해외 벤치마크의 '가장 최근 완결 세션' 수익률이 -2% 이하면
mom20 순위와 무관하게 하향(차순위 대체). 룩어헤드 금지:
- 미국 벤치마크(SOXX,^GSPC,^NDX): KR 선정일 D 기준, 미국 캘린더일 <= D 의 최근 세션
  (D 세션은 KST D+1 05:00 종료 -> D+1 장전 가용).
- 홍콩(3033.HK): 캘린더일 <= D 의 최근 세션(당일 17:00 KST 종료 -> D 저녁 가용).
"""
import csv, math
from collections import defaultdict
import bt_ruleCC as H  # harness: load/score/mom20/rule_h/is_spot/candidate_pool 등

BASE = '/sessions/hopeful-affectionate-cerf/mnt/loop'
THR = -0.02

def load_panel():
    px = defaultdict(dict); name = {}
    with open(BASE + '/backtest/panel_close_0720.csv', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try: px[r['code']][r['date']] = float(r['close'])
            except ValueError: continue
            name[r['code']] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, name, dates

def load_bench():
    b = defaultdict(dict)
    for r in csv.DictReader(open(BASE + '/backtest/bench_close.csv')):
        b[r['bench']][r['date']] = float(r['close'])
    return {k: sorted(v.items()) for k, v in b.items()}

def bench_ret_asof(series, d):
    """가장 최근 완결 세션(캘린더일 <= d)의 수익률."""
    prev = None; last = None
    for dt, cl in series:
        if dt <= d:
            prev, last = last, (dt, cl)
        else: break
    if last is None or prev is None: return None
    return last[1] / prev[1] - 1.0

def bench_of(nm):
    n = (nm or '').replace(' ', '')
    if any(k in n for k in ['국채','회사채','머니마켓','초단기','채권혼합','금리']): return None
    if any(k in n for k in ['차이나','중국','항셍']): return '3033.HK'
    if '반도체' in n and any(k in n for k in ['미국','글로벌','필라델피아','HBM','메모리']): return 'SOXX'
    if any(k in n for k in ['나스닥','빅테크','미국테크','우주','양자','글로벌AI','미국AI']): return '^NDX'
    if any(k in n for k in ['S&P500','미국배당','다우존스']): return '^GSPC'
    return None

def sel_ruleFF(px, name, d, dates, bench, n=5):
    pool = H.candidate_pool(px, name, d, dates, pool_n=n + 15)
    picks = []
    for c, _ in pool:
        b = bench_of(name.get(c, ''))
        if b:
            r = bench_ret_asof(bench[b], d)
            if r is not None and r <= THR:
                continue  # 하향(차순위 대체)
        picks.append(c)
        if len(picks) >= n: break
    return picks

def main():
    px, name, dates = load_panel()
    bench = load_bench()
    H_load_px = px  # for score() reuse we pass px/name directly
    res = []
    for i in range(21, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        base = H.sel_baseline(px, name, d, dates)
        ff = sel_ruleFF(px, name, d, dates, bench)
        sb = H.score(px, name, d, dn, base)
        sf = H.score(px, name, d, dn, ff)
        if sb is None or sf is None: continue
        res.append((d, dn, base, ff, sb, sf))
    days = len(res)
    act = [r for r in res if r[2] != r[3]]
    def agg(rs, k):
        return sum(r[k]['hit'] for r in rs) / len(rs) if rs else float('nan')
    def aggx(rs, k, f):
        v = [r[k][f] for r in rs if r[k][f] is not None]
        return sum(v)/len(v) if v else float('nan')
    half = days // 2
    tr, te = res[:half], res[half:]
    print(f'전체 {days}일 | 발동(선정변경) {len(act)}일')
    print(f'baseline 평균적중 {agg(res,4):.3f} | FF {agg(res,5):.3f}')
    print(f'train: base {agg(tr,4):.3f} FF {agg(tr,5):.3f} | test: base {agg(te,4):.3f} FF {agg(te,5):.3f}')
    print(f'평균백분위: base {aggx(res,4,"avg_pct"):.1f} FF {aggx(res,5,"avg_pct"):.1f} | 초과수익: base {aggx(res,4,"avg_excess")*100:.2f}% FF {aggx(res,5,"avg_excess")*100:.2f}%')
    print(f'발동일만: base {agg(act,4):.3f} FF {agg(act,5):.3f} | 발동일 초과수익 base {aggx(act,4,"avg_excess")*100:.2f}% FF {aggx(act,5,"avg_excess")*100:.2f}%')
    print('발동일 상세:')
    for d, dn, b, f, sb, sf in act:
        chg_out = [c for c in b if c not in f]; chg_in = [c for c in f if c not in b]
        print(f'  {d}->{dn}: base hit {sb["hit"]} -> FF hit {sf["hit"]} | 제외 {chg_out} 편입 {chg_in}')
    return res

if __name__ == '__main__':
    main()
