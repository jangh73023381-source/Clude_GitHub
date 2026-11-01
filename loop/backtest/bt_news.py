# -*- coding: utf-8 -*-
"""뉴스(네이버 데이터랩 검색량) 신호 Rule J 백테스트 (2026-07-05).
베이스라인 = 현행 확정(v1.2+v1.9+RuleH). 여기에 뉴스 신호를 얹었을 때 비악화/개선 여부 검증.
- J1 (테마 과열 컷): 선정일 D의 테마 검색량 s(D) / 직전 5일 평균 >= 2.0 이면 해당 테마 ETF를
  top5에서 제외하고 차순위 충원 (검색 스파이크 = 대중 관심 피크 = 익일 평균회귀 위험 가설).
- J2 (지속 관심 가점): 테마 검색량 5일이동평균이 3일 전 대비 상승 중이면 mom20 백분위에 +0.05 가점.
- J3 = J1+J2 동시.
룩어헤드 금지: 선정일 D까지의 검색량만 사용(저녁 브리핑 시점 D일 데이터 가용 가정, 캐비앳 명시).
데이터: 검색량 2026-03-23~07-03 (16테마, datalab_raw.txt), 가격 85일 (prices_long+july).
"""
import csv, math, statistics as st, datetime as dt
from collections import defaultdict

LOOP = '/sessions/lucid-keen-gauss/mnt/loop/backtest'
OUTD = '/sessions/lucid-keen-gauss/mnt/outputs'
BENCH = '069500'

# ---- 가격 로드 ----
def load_px():
    px = defaultdict(dict); name = {}
    for fp in (LOOP + '/prices_long.csv', OUTD + '/prices_july.csv'):
        for r in csv.DictReader(open(fp, encoding='utf-8')):
            try: px[r['code']][r['date']] = float(r['close'])
            except: pass
            name[r['code']] = r['name']
    dates = sorted({d for c in px for d in px[c]})
    return px, name, dates

def is_spot(nm):
    n = nm.replace(' ', '')
    return not ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n)

px, name, dates = load_px()
DIDX = {d: i for i, d in enumerate(dates)}

# ---- 테마 매핑 & 검색량 로드 ----
theme_of = {}
for r in csv.DictReader(open(OUTD + '/theme_map.csv', encoding='utf-8')):
    if r['theme']: theme_of[r['code']] = r['theme']

search = {}  # theme -> {'20260323': ratio}
for line in open(OUTD + '/datalab_raw.txt', encoding='utf-8'):
    line = line.strip()
    if not line: continue
    theme, rest = line.split('|', 1)
    d = {}
    for kv in rest.split(','):
        k, v = kv.split('=')
        d['2026' + k] = float(v)
    search[theme] = d

def cal_prev_days(dstr, n):
    """달력 기준 직전 n일 (dstr 제외)."""
    d0 = dt.date(int(dstr[:4]), int(dstr[4:6]), int(dstr[6:]))
    return [(d0 - dt.timedelta(days=i)).strftime('%Y%m%d') for i in range(1, n + 1)]

def theme_signals(theme, dstr):
    """(spike여부, 상승추세여부). 데이터 부족 시 (False, False) = 중립."""
    s = search.get(theme)
    if not s: return False, False
    cur = s.get(dstr)
    prev5 = [s.get(x) for x in cal_prev_days(dstr, 5)]
    prev5 = [x for x in prev5 if x is not None]
    spike = False
    if cur is not None and len(prev5) >= 4:
        m = st.mean(prev5)
        if m > 0.02 and cur / m >= 2.0: spike = True
    # 5일 MA(오늘 포함) vs 3일 전 5일 MA
    def ma5(end):
        days = [end] + cal_prev_days(end, 4)
        vals = [s.get(x) for x in days]
        vals = [x for x in vals if x is not None]
        return st.mean(vals) if len(vals) >= 4 else None
    d0 = dt.date(int(dstr[:4]), int(dstr[4:6]), int(dstr[6:]))
    d3 = (d0 - dt.timedelta(days=3)).strftime('%Y%m%d')
    a, b = ma5(dstr), ma5(d3)
    rising = a is not None and b is not None and a > b * 1.05
    return spike, rising

# ---- 채점 ----
def ret(c, d, k):
    i = DIDX[d]
    if i < k: return None
    a = px[c].get(dates[i - k]); b = px[c].get(d)
    return (b / a - 1.0) if (a and b) else None

def score(d, dnext, picks):
    u = []
    for c in px:
        pc = px[c].get(d); nc = px[c].get(dnext)
        if pc and nc and pc >= 10000: u.append((c, nc / pc - 1.0))
    if not u: return None
    u.sort(key=lambda x: x[1], reverse=True)
    N = len(u); cutoff = max(1, math.ceil(N * 0.10))
    rank = {c: i + 1 for i, (c, _) in enumerate(u)}
    r = dict(u); bench = r.get(BENCH, 0.0)
    hit = 0; pcts = []; ex = []
    for c in picks:
        if c in rank:
            hit += 1 if rank[c] <= cutoff else 0
            pcts.append((rank[c] - 1) / N * 100); ex.append(r[c] - bench)
    if not pcts: return None
    return hit, st.mean(pcts), st.mean(ex)

def pctile_map(vals):
    s = sorted(vals.items(), key=lambda x: x[1]); n = len(s)
    return {c: (i + 1) / n for i, (c, _) in enumerate(s)}

def candidates(d):
    return [c for c in px if px[c].get(d) and px[c][d] >= 10000 and is_spot(name[c])]

def sel(d, method, n=5):
    cs = candidates(d)
    f = {c: dict(m20=ret(c, d, 20), m1=ret(c, d, 1), m3=ret(c, d, 3)) for c in cs}
    def okH(c):
        m1, m3 = f[c]['m1'], f[c]['m3']
        if m1 is not None and m1 > 0.10: return False
        if m3 is not None and m3 > 0.20: return False
        return True
    sig = {}
    def get_sig(c):
        t = theme_of.get(c)
        if not t: return False, False
        if t not in sig: sig[t] = theme_signals(t, d)
        return sig[t]
    if method == 'base':      # 확정: mom20 + RuleH
        sc = [(c, f[c]['m20']) for c in cs if f[c]['m20'] is not None and okH(c)]
    elif method == 'J1':      # + 테마 과열 컷
        sc = [(c, f[c]['m20']) for c in cs if f[c]['m20'] is not None and okH(c) and not get_sig(c)[0]]
    elif method == 'J2':      # + 지속 관심 가점 (백분위 +0.05)
        p20 = pctile_map({c: f[c]['m20'] for c in cs if f[c]['m20'] is not None})
        sc = [(c, p20[c] + (0.05 if get_sig(c)[1] else 0.0)) for c in cs if c in p20 and okH(c)]
    elif method == 'J3':      # J1 + J2
        p20 = pctile_map({c: f[c]['m20'] for c in cs if f[c]['m20'] is not None})
        sc = [(c, p20[c] + (0.05 if get_sig(c)[1] else 0.0)) for c in cs
              if c in p20 and okH(c) and not get_sig(c)[0]]
    else: raise ValueError(method)
    sc.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in sc[:n]]

def daily(method, lo, hi):
    out = []
    for i in range(max(20, lo), min(hi, len(dates) - 1)):
        d, dn = dates[i], dates[i + 1]
        if d < '20260331': continue  # 검색량 가용 시작(3/23)+5일 룩백 확보
        p = sel(d, method)
        if len(p) < 5: continue
        s = score(d, dn, p)
        if s: out.append((d, dn, s[0], s[1], s[2] * 100, p))
    return out

def summ(rows):
    H = [r[2] for r in rows]; E = [r[4] for r in rows]; P = [r[3] for r in rows]
    return dict(days=len(H), hit=st.mean(H), pct=st.mean(P), ex=st.mean(E),
                ge1=100 * sum(1 for h in H if h >= 1) / len(H),
                ge3=100 * sum(1 for h in H if h >= 3) / len(H),
                p55=100 * sum(1 for h in H if h == 5) / len(H))

if __name__ == '__main__':
    n = len(dates)
    res = {m: daily(m, 20, n - 1) for m in ('base', 'J1', 'J2', 'J3')}
    # train/test 분할 (채점일 기준 절반)
    days_all = [r[0] for r in res['base']]
    mid_d = days_all[len(days_all) // 2]
    lab = {'base': '확정(v1.9+RuleH)', 'J1': '+J1 테마과열컷', 'J2': '+J2 지속관심가점', 'J3': '+J1+J2'}
    print(f"검증 구간: {days_all[0]}~{days_all[-1]} 선정, {len(days_all)}일 (train/test 경계 {mid_d})\n")
    print(f"{'방법':<20}{'tr적중':>7}{'tr초과':>7}{'te적중':>7}{'te초과':>7}{'전체':>6}{'초과%':>7}{'>=3%':>6}{'5/5%':>6}")
    for m in res:
        tr = [r for r in res[m] if r[0] < mid_d]; te = [r for r in res[m] if r[0] >= mid_d]
        a, b, f = summ(tr), summ(te), summ(res[m])
        print(f"{lab[m]:<20}{a['hit']:>7.2f}{a['ex']:>7.2f}{b['hit']:>7.2f}{b['ex']:>7.2f}"
              f"{f['hit']:>6.2f}{f['ex']:>7.2f}{f['ge3']:>6.0f}{f['p55']:>6.1f}")
    # 페어 비교 + 신호 발동일 분석
    print()
    dB = {r[0]: r for r in res['base']}
    for m in ('J1', 'J2', 'J3'):
        dM = {r[0]: r for r in res[m]}
        common = sorted(set(dB) & set(dM))
        diff = [dM[d][2] - dB[d][2] for d in common]
        act = [d for d in common if dM[d][5] != dB[d][5]]
        actdiff = [dM[d][2] - dB[d][2] for d in act]
        w = sum(1 for x in diff if x > 0); l = sum(1 for x in diff if x < 0)
        print(f"{lab[m]} vs 확정: 승{w}/무{len(diff)-w-l}/패{l}, 평균차 {st.mean(diff):+.3f} | "
              f"신호로 선정 변경 {len(act)}일, 변경일 평균차 {st.mean(actdiff):+.3f}" if act else
              f"{lab[m]} vs 확정: 승{w}/무{len(diff)-w-l}/패{l}, 평균차 {st.mean(diff):+.3f} | 선정 변경 0일")
    # 변경일 상세 (J3)
    print("\n== J3 선정 변경일 상세 ==")
    dM = {r[0]: r for r in res['J3']}
    for d in sorted(set(dB) & set(dM)):
        if dM[d][5] != dB[d][5]:
            outs = [name[c][:12] for c in dB[d][5] if c not in dM[d][5]]
            ins = [name[c][:12] for c in dM[d][5] if c not in dB[d][5]]
            print(f"{d}: 적중 {dB[d][2]}→{dM[d][2]} | 제외 {outs} → 편입 {ins}")
