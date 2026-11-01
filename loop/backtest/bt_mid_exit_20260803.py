# -*- coding: utf-8 -*-
"""2026-08-03 중기 트랙 청산 규칙 검정 (사용자 지적).

문제: Rule MM 승격 근거는 '보유 20거래일'(HOLD=20) 백테스트인데, 실제 집행 규칙
(fable CLAUDE.md 14번)은 '추천 탈락한 첫 브리핑일 종가 청산'이다. mom150 상위5의
연속 재추천 지속일수를 재보니 중앙값 3거래일 · 89.7%가 20일 전에 탈락한다.
즉 승격을 정당화한 숫자와 실제로 집행되는 전략이 다르다.

두 방식을 같은 600일 패널에서 나란히 돌려 어느 쪽이 나은지 측정한다.
 · A(탈락청산) — top5 진입일 종가 매수, top5에서 빠진 첫날 종가 매도.
 · B(20일고정) — top5 진입일 종가 매수, 정확히 20거래일 뒤 종가 매도.
   시계는 최초 진입일 기준 고정(사용자 확정 2026-08-03). 보유 중 재추천돼도
   시계는 재시작하지 않고, 매도 후 다시 top5에 들면 새 포지션으로 취급한다.

자본 배분: 매일 '보유 중인 포지션 전체'에 등가중(A는 상시 5종, B는 중첩으로 5종을
넘을 수 있다). 왕복 10bp를 진입일·청산일에 5bp씩 부과. 벤치는 KODEX200 보유.
룩어헤드 금지 — 선정은 D 종가까지 정보만, 체결도 D 종가.
"""
import collections
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))
from universe_filters import eligible  # noqa: E402

PANEL = os.path.join(HERE, 'panel_full.csv')
BENCH = '069500'
K = 150          # mom150 룩백
HOLD = 20        # B안 고정 보유
COST = 0.0005    # 편도 5bp (왕복 10bp)


def load():
    px, nm = collections.defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError):
            continue
        nm[r['code']] = r['name']
    return px, nm, sorted({d for c in px for d in px[c]})


def top5_series(px, nm, ds, di):
    sel = {}
    for d in ds[K:]:
        i = di[d]
        out = []
        for c in px:
            if not eligible(nm.get(c, '')):
                continue
            a, b = px[c].get(ds[i - K]), px[c].get(d)
            if a and b:
                out.append((b / a - 1.0, c))
        out.sort(reverse=True)
        sel[d] = [c for _, c in out[:5]]
    return sel


def simulate(px, ds, di, sel, mode):
    """일별 포트폴리오 수익률 시계열. mode='dropout' | 'fixed20'"""
    days = sorted(sel)
    open_pos = {}          # code -> {'entry_i': int}
    daily = []
    for n, d in enumerate(days[:-1]):
        i = di[d]
        cur = set(sel[d])
        # --- 청산 판정 (D 종가) ---
        for c in list(open_pos):
            if mode == 'dropout':
                out = c not in cur
            else:
                out = (i - open_pos[c]['entry_i']) >= HOLD
            if out:
                open_pos[c]['exit_today'] = True
        # --- 신규 진입 (D 종가) ---
        for c in cur:
            if c not in open_pos:
                open_pos[c] = {'entry_i': i, 'enter_today': True}
        # --- D → D+1 수익률 (청산 예정분은 오늘 종가에 팔았으므로 제외) ---
        held = [c for c in open_pos if not open_pos[c].get('exit_today')]
        dn = days[n + 1]
        rets, fees = [], []
        for c in held:
            a, b = px[c].get(d), px[c].get(dn)
            if a and b:
                rets.append(b / a - 1.0)
                fees.append(COST if open_pos[c].pop('enter_today', False) else 0.0)
        # 청산 수수료는 청산일 종가에 부과 → 당일 수익률에서 차감
        exit_fee = sum(COST for c in open_pos if open_pos[c].get('exit_today'))
        nheld = len(rets)
        if nheld:
            port = statistics.mean(rets) - (sum(fees) + exit_fee) / max(nheld, 1)
        else:
            port = 0.0
        a, b = px[BENCH].get(d), px[BENCH].get(dn)
        bench = (b / a - 1.0) if (a and b) else 0.0
        daily.append((d, port, bench, nheld))
        for c in [c for c in open_pos if open_pos[c].get('exit_today')]:
            open_pos.pop(c)
    return daily


def stats(name, daily):
    ex = [(p - b) * 100 for _, p, b, _ in daily]
    cum_p = cum_b = 1.0
    peak = mdd = 0.0
    for _, p, b, _ in daily:
        cum_p *= (1 + p)
        cum_b *= (1 + b)
        peak = max(peak, cum_p)
        mdd = min(mdd, cum_p / peak - 1)
    n = len(ex)
    h = n // 2
    jk = [statistics.mean(ex[:i] + ex[i + 1:]) for i in range(n)]
    nh = statistics.mean(x[3] for x in daily)
    print(f'{name:16s} 누적 {(cum_p-1)*100:+8.1f}%  벤치 {(cum_b-1)*100:+7.1f}%  '
          f'일평균초과 {statistics.mean(ex):+.4f}%p  이김 {sum(1 for x in ex if x>0)}/{n}  '
          f'MDD {mdd*100:.1f}%  평균보유 {nh:.1f}종  잭나이프하한 {min(jk):+.4f}')
    print(f'{"":16s} train {statistics.mean(ex[:h]):+.4f} / test {statistics.mean(ex[h:]):+.4f}')
    return ex


def main():
    px, nm, ds = load()
    di = {d: i for i, d in enumerate(ds)}
    print(f'패널 {len(ds)}거래일 {ds[0]}~{ds[-1]} · {len(px)}종')
    sel = top5_series(px, nm, ds, di)
    print(f'선정일 {len(sel)}일 (mom150 상위5, 파생·현금성 제외)\n')
    a = stats('A 탈락청산', simulate(px, ds, di, sel, 'dropout'))
    b = stats('B 20일고정', simulate(px, ds, di, sel, 'fixed20'))
    d = [x - y for x, y in zip(b, a)]
    n = len(d)
    jk = [statistics.mean(d[:i] + d[i + 1:]) for i in range(n)]
    print(f'\nB - A 일평균 차이 {statistics.mean(d):+.4f}%p · '
          f'잭나이프 하한 {min(jk):+.4f} · 상한 {max(jk):+.4f}')
    sd = statistics.pstdev(d)
    if sd:
        print(f'  sd {sd:.4f} · t {statistics.mean(d)/(sd/n**0.5):+.2f}')


if __name__ == '__main__':
    main()
