# -*- coding: utf-8 -*-
"""2026-07-31 — 미국 섹터 → 한국 섹터 오버나잇 전이 검증 (사용자 제안).

가설: 미국장에서 오른 섹터가 다음 한국장에서도 오른다(사용자 관측: 7/30 SOX +8.19%
→ 7/31 한국 반도체 급등). 반도체 외 섹터도 같은지, 규칙화할 가치가 있는지 본다.

**핵심 설계 — 베타 제거**: 원시 수익률로 재면 "미국장이 오르면 한국장도 오른다"는
이미 알려진 시장 동조(2026-06-30 확정: 방향 상관 +0.35)를 섹터 전이로 오인한다.
그래서 양쪽 모두 **시장 대비 초과수익**으로 바꾼 뒤 횡단면 순위상관을 잰다.
  US 초과  = 섹터 - SPY          (미국 날짜 D_us)
  KR 초과  = 섹터 - KODEX200     (그 다음 한국 거래일 D_kr)

**핵심 설계 — 매매 가능성 분리**: 미국 종가는 D_kr 05:00 KST 에 확정되므로
D_kr-1 한국 종가에는 살 수 없다. 따라서 세 구간을 분리해 잰다.
  M1 종가→종가 : 신호를 알기 전에 사야 함 → **매매 불가**(동조 관측용)
  M2 시가→종가 : 신호를 보고 시초가 매수 → **매매 가능**(유일한 유효 검정)
  M3 갭(전일종가→시가) : 정보가 실제로 어디서 소화되는지 분해

정렬 규칙: 한국 거래일 D_kr 에 대응하는 미국 세션은 **D_kr 보다 이전인 마지막 미국
거래일**이다(D_us == D_kr 인 세션은 D_kr 한국 마감 뒤에 끝나므로 룩어헤드).
"""
import csv
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

# 한국 테마 → 미국 대응 ETF. 프로젝트의 15테마 정의(references/attention_pilot_themes.csv)를 따른다.
MAP = {
    '반도체': 'SOXX', '자동차': 'CARZ', '증권': 'IAI', '은행금융': 'XLF', '방산': 'ITA',
    '조선': 'XLI', '2차전지': 'LIT', '바이오': 'XBI', '원자력': 'URA', 'AI전력': 'GRID',
    '우주항공': 'ARKX', '로봇': 'BOTZ', '태양광': 'TAN', '건설': 'PAVE', '금귀금속': 'GDX',
}
# 대응이 느슨해 결과 해석에 주의가 필요한 쌍
WEAK = {'조선': 'XLI 산업재 — 미국에 조선 ETF가 없다', '건설': 'PAVE 인프라 — 주택건설(ITB)과 다름'}
# 한국 상장이지만 기초자산이 해외라 전이가 아니라 '같은 자산'인 테마 → 민감도에서 제외
FOREIGN = {'우주항공'}          # TIGER 미국우주테크
BENCH_US, BENCH_KR = 'SPY', '_BENCH'


def load_us():
    p = os.path.join(HERE, 'us_sector_close.csv')
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    key = 'Date' if 'Date' in rows[0] else list(rows[0])[0]
    out = {}
    for r in rows:
        d = str(r[key])[:10].replace('-', '')
        out[d] = {k: float(v) for k, v in r.items() if k != key and v not in ('', None)}
    return out


def load_kr():
    p = os.path.join(HERE, 'kr_sector_oc.csv')
    o, c = defaultdict(dict), defaultdict(dict)
    for r in csv.DictReader(open(p, encoding='utf-8')):
        o[r['theme']][r['date']] = float(r['open'])
        c[r['theme']][r['date']] = float(r['close'])
    return o, c


def spearman(xs, ys):
    n = len(xs)
    if n < 4:
        return None

    def rank(v):
        s = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:                       # 동점은 평균 순위
            j = i
            while j + 1 < n and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                r[s[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    da = sum((a - mx) ** 2 for a in rx) ** 0.5
    db = sum((b - my) ** 2 for b in ry) ** 0.5
    return None if da == 0 or db == 0 else num / (da * db)


def build(themes):
    us, (ko, kc) = load_us(), load_kr()
    us_days = sorted(us)
    kr_days = sorted(set(kc[BENCH_KR]))
    recs = []
    for dk in kr_days:
        prior = [d for d in us_days if d < dk]        # 룩어헤드 금지: 엄격히 이전 세션
        if not prior:
            continue
        du = prior[-1]
        ku = us_days[us_days.index(du) - 1] if us_days.index(du) > 0 else None
        if ku is None or BENCH_US not in us[du] or BENCH_US not in us.get(ku, {}):
            continue
        i = kr_days.index(dk)
        if i == 0:
            continue
        dprev = kr_days[i - 1]
        bo, bc = ko[BENCH_KR].get(dk), kc[BENCH_KR].get(dk)
        bpc = kc[BENCH_KR].get(dprev)
        if not (bo and bc and bpc):
            continue
        us_mkt = us[du][BENCH_US] / us[ku][BENCH_US] - 1
        b_cc, b_oc, b_gap = bc / bpc - 1, bc / bo - 1, bo / bpc - 1

        row = {'dk': dk, 'du': du, 'us_mkt': us_mkt, 'kr_mkt_cc': b_cc,
               'items': []}
        for th in themes:
            t = MAP[th]
            if t not in us[du] or t not in us.get(ku, {}):
                continue
            o, c, pc = ko[th].get(dk), kc[th].get(dk), kc[th].get(dprev)
            if not (o and c and pc):
                continue
            row['items'].append({
                'th': th,
                'us_x': (us[du][t] / us[ku][t] - 1) - us_mkt,
                'cc_x': (c / pc - 1) - b_cc,
                'oc_x': (c / o - 1) - b_oc,
                'gap_x': (o / pc - 1) - b_gap,
            })
        if len(row['items']) >= 6:
            recs.append(row)
    return recs


def report(title, recs):
    print(f'\n=== {title} — 표본 {len(recs)}일 '
          f'({recs[0]["dk"]}~{recs[-1]["dk"]}) ===')
    print(f'{"구간":28s}{"평균 rank IC":>13s}{"t":>8s}{"IC>0 비율":>10s}')
    print('-' * 60)
    out = {}
    for key, label in (('cc_x', 'M1 종가→종가 (매매 불가)'),
                       ('oc_x', 'M2 시가→종가 (매매 가능)'),
                       ('gap_x', 'M3 갭 구간 (전일종가→시가)')):
        ics = [ic for r in recs
               if (ic := spearman([x['us_x'] for x in r['items']],
                                  [x[key] for x in r['items']])) is not None]
        m = statistics.fmean(ics)
        sd = statistics.stdev(ics) if len(ics) > 1 else 0
        t = m / (sd / len(ics) ** 0.5) if sd else 0
        pos = sum(1 for x in ics if x > 0) / len(ics)
        out[key] = (m, t, pos, ics)
        print(f'{label:28s}{m:+13.4f}{t:+8.2f}{pos:10.1%}')
    return out


def theme_detail(recs):
    print(f'\n{"테마":8s}{"US 대응":8s}{"n":>5s}{"상관(M1)":>10s}{"상관(M2)":>10s}{"비고"}')
    print('-' * 72)
    for th in MAP:
        pair = [(x['us_x'], x['cc_x'], x['oc_x'])
                for r in recs for x in r['items'] if x['th'] == th]
        if len(pair) < 20:
            print(f'{th:8s}{MAP[th]:8s}{len(pair):5d}      표본 부족')
            continue
        u = [p[0] for p in pair]

        def corr(j):
            v = [p[j] for p in pair]
            mu, mv = statistics.fmean(u), statistics.fmean(v)
            num = sum((a - mu) * (b - mv) for a, b in zip(u, v))
            da = sum((a - mu) ** 2 for a in u) ** 0.5
            db = sum((b - mv) ** 2 for b in v) ** 0.5
            return 0.0 if da == 0 or db == 0 else num / (da * db)
        note = WEAK.get(th, '')
        if th in FOREIGN:
            note = '기초자산이 해외 — 전이 아님'
        print(f'{th:8s}{MAP[th]:8s}{len(pair):5d}{corr(1):+10.3f}{corr(2):+10.3f}  {note}')


if __name__ == '__main__':
    full = list(MAP)
    recs = build(full)
    report('전체 15테마', recs)
    theme_detail(recs)
    recs2 = build([t for t in full if t not in FOREIGN and t not in WEAK])
    report('민감도: 해외기초·느슨매핑 제외 12테마', recs2)
