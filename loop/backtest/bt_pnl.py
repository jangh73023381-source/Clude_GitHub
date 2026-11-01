# -*- coding: utf-8 -*-
"""손익(P&L) 기반 성과 백테스트 — 2026-07-16 (사용자 요청: 채점기준을 손익으로 교체 검토)

질문: '매일 추천 5종 전부 매수'를 실제로 했다면 돈이 얼마나 벌리거나 잃었는가?
- 전략: mom20+RuleH 상위5 동일가중 (bt_ruleCC.py의 sel_baseline 재구현과 동일 로직)
- 보유기간 N ∈ {1,2,3,5,10} 거래일 (N일마다 전량 교체 리밸런스)
- 비용 시나리오: 왕복 0bp / 10bp / 30bp per 리밸런스 (수수료+호가스프레드+슬리피지)
- 벤치마크: KODEX200(069500) 단순 보유 (동일 구간)
룩어헤드 없음: 선정은 D 종가까지 정보만, 수익은 D종가 매수→(D+N)종가 매도.
"""
import csv, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_close_0715.csv')
BENCH = '069500'

def load():
    px = defaultdict(dict); name = {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            c = r['code']
            try:
                px[c][r['date']] = float(r['close'])
            except (ValueError, KeyError):
                continue
            name[c] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, name, dates

def is_spot(nm):
    n = (nm or '').replace(' ', '')
    return not ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper()
                or '2배' in n or '숏' in n)

def mom20(px, c, d, dates, k=20):
    i = dates.index(d)
    if i < k: return None
    a = px[c].get(dates[i-k]); b = px[c].get(d)
    return (b/a - 1.0) if (a and b) else None

def ret_window(px, c, d, dates, k):
    i = dates.index(d)
    if i < k: return None
    a = px[c].get(dates[i-k]); b = px[c].get(d)
    return (b/a - 1.0) if (a and b) else None

def rule_h_ok(px, c, d, dates):
    s = ret_window(px, c, d, dates, 1)
    c3 = ret_window(px, c, d, dates, 3)
    if s is not None and s > 0.10: return False
    if c3 is not None and c3 > 0.20: return False
    return True

def sel_baseline(px, name, d, dates, n=5, minp=10000):
    cand = []
    for c in px:
        pc = px[c].get(d)
        if not pc or pc < minp or not is_spot(name.get(c, '')): continue
        m = mom20(px, c, d, dates)
        if m is None: continue
        if not rule_h_ok(px, c, d, dates): continue
        cand.append((c, m))
    cand.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in cand[:n]]

def port_ret(px, picks, d_buy, d_sell):
    rs = []
    for c in picks:
        a = px[c].get(d_buy); b = px[c].get(d_sell)
        if a and b: rs.append(b/a - 1.0)
    return sum(rs)/len(rs) if rs else 0.0

def max_dd(curve):
    peak = curve[0]; mdd = 0.0
    for v in curve:
        peak = max(peak, v)
        mdd = min(mdd, v/peak - 1.0)
    return mdd

def run(px, name, dates, hold, cost_rt):
    """hold일 보유·전량 교체. cost_rt = 왕복비용(소수, 리밸런스마다 차감)."""
    start = 20  # mom20 필요
    i = start
    curve = [1.0]; trades = []
    while i + hold < len(dates):
        d = dates[i]; d_sell = dates[i + hold]
        picks = sel_baseline(px, name, d, dates)
        gross = port_ret(px, picks, d, d_sell)
        net = gross - cost_rt
        curve.append(curve[-1] * (1.0 + net))
        trades.append(net)
        i += hold
    total = curve[-1] - 1.0
    win = sum(1 for t in trades if t > 0)
    # 벤치마크: 동일 구간 단순 보유(비용 0 가정 — 보수적 비교)
    b0 = px[BENCH].get(dates[start]); b1 = px[BENCH].get(dates[i]) or px[BENCH].get(dates[-1])
    bench_total = (b1/b0 - 1.0) if (b0 and b1) else None
    return {
        'hold': hold, 'cost_bp': round(cost_rt*1e4),
        'n_trades': len(trades), 'total': total,
        'avg_trade': sum(trades)/len(trades) if trades else 0.0,
        'win_rate': win/len(trades) if trades else 0.0,
        'mdd': max_dd(curve), 'bench_total': bench_total,
        'excess': total - bench_total if bench_total is not None else None,
        'trades': trades, 'span': (dates[start], dates[i]),
    }

def main():
    px, name, dates = load()
    print(f"패널: {len(px)}종 × {len(dates)}일 ({dates[0]}~{dates[-1]})")
    d0, d1 = dates[20], dates[-1]
    b = px[BENCH]
    print(f"평가구간(결정 시작 {d0} → 종료 {d1}), KODEX200 {b.get(d0):,.0f} → {b.get(d1):,.0f} "
          f"({b.get(d1)/b.get(d0)-1:+.2%})\n")
    hdr = f"{'보유':>4} {'비용bp':>6} {'회전수':>5} {'누적수익':>9} {'평균/회':>8} {'승률':>6} {'MDD':>8} {'벤치':>8} {'초과':>9}"
    for cost in (0.0, 0.0010, 0.0030):
        print(f"=== 왕복비용 {cost*1e4:.0f}bp ===")
        print(hdr)
        for hold in (1, 2, 3, 5, 10):
            r = run(px, name, dates, hold, cost)
            print(f"{r['hold']:>4} {r['cost_bp']:>6} {r['n_trades']:>5} {r['total']:>+9.2%} "
                  f"{r['avg_trade']:>+8.3%} {r['win_rate']:>6.0%} {r['mdd']:>8.2%} "
                  f"{r['bench_total']:>+8.2%} {r['excess']:>+9.2%}")
        print()
    # 1일 보유(실제 매매 방식) 상세: 최악의 날 5개
    r1 = run(px, name, dates, 1, 0.0010)
    idx_dates = dates[20:20+len(r1['trades'])+1]
    day_rets = list(zip(idx_dates[:-1], r1['trades']))
    worst = sorted(day_rets, key=lambda x: x[1])[:5]
    best = sorted(day_rets, key=lambda x: x[1], reverse=True)[:5]
    print("1일 보유(10bp) 최악 5일:", [(d, f"{t:+.2%}") for d, t in worst])
    print("1일 보유(10bp) 최선 5일:", [(d, f"{t:+.2%}") for d, t in best])
    neg_sum = sum(t for _, t in worst)
    print(f"최악 5일 합계 기여: {neg_sum:+.2%} (전체 누적 {r1['total']:+.2%})")

if __name__ == '__main__':
    main()
