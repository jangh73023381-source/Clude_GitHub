# -*- coding: utf-8 -*-
"""Rule SU (v2.6) — 섹터 대표 개별종목 15종 유니버스 단기 픽 산출 (조회 전용).

데일리 브리핑 [7-1] 단기 단일종목 5종 선정에 사용한다.
선정 로직은 기존 확정 규칙과 동일: v1.9 mom20 상위 5종 + v2.1 Rule H 이중 과열필터.

사용법
    python3 stock15_picks.py                  # 최신 거래일 기준 픽
    python3 stock15_picks.py --date 20260724  # 특정 일자 기준 픽(백테스트/재현용)
    python3 stock15_picks.py --score 20260724 # 해당일 선정 → 익일 성과 채점 후 OOS 트래커 기록

주의: 키움 API는 조회 전용으로만 사용한다. 주문·매매 기능은 호출하지 않는다.
"""
import argparse
import csv
import math
import os
import sys


def _n_star(xs):
    """판정 필요 표본 수 — judge_ready.py 와 동일 식 (2026-07-31 규정, 고정 20일 폐지)."""
    if len(xs) < 3:
        return None
    m = sum(xs) / len(xs)
    if not m:
        return 60
    sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    return max(8, min(60, math.ceil((1.28 * sd / abs(m)) ** 2)))
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

TRACKER = os.path.join(LOOP, 'references', 'stock15_oos_tracker.csv')
BENCH = ('069500', 'KODEX 200')

# analysis-method.md "확정 — Rule SU" 표와 동일. 분기 1회 시총 재조회로 갱신.
UNIVERSE = [
    ('반도체',     '000660', 'SK하이닉스'),
    ('자동차',     '005380', '현대차'),
    ('증권',       '006800', '미래에셋증권'),
    ('은행금융',   '105560', 'KB금융'),
    ('방산',       '012450', '한화에어로스페이스'),
    ('조선',       '329180', 'HD현대중공업'),
    ('2차전지',    '373220', 'LG에너지솔루션'),
    ('바이오',     '207940', '삼성바이오로직스'),
    ('원자력',     '034020', '두산에너빌리티'),
    ('AI전력',     '010120', 'LS ELECTRIC'),
    ('화장품',     '090430', '아모레퍼시픽'),
    ('로봇',       '277810', '레인보우로보틱스'),
    ('태양광',     '009830', '한화솔루션'),
    ('건설',       '047040', '대우건설'),
    ('금속귀금속', '010130', '고려아연'),
]

NPICK = 5


def fetch_closes(code, need=40):
    """최근 need 거래일의 (date, close) 리스트를 오름차순으로 반환."""
    r = k.get_daily_chart(code, '00000000')
    arr = r.get('stk_dt_pole_chart_qry') or []
    out = []
    for d in arr:
        try:
            out.append((d['dt'], abs(float(d['cur_prc']))))
        except Exception:
            continue
    out.sort()
    out = [(d, c) for (d, c) in out if d <= _last_closed_session()]
    return out[-need:] if need else out


def _last_closed_session(_cache={}):
    """장 마감(16:00 KST) 전이면 오늘 날짜를 제외한다.

    키움 일봉은 장 시작 전에도 당일 행을 전일 종가로 채워 반환한다. 이를 그대로
    쓰면 '오늘 종가'가 전일과 같아져 수익률 0%짜리 가짜 채점 행이 트래커에
    쌓인다(2026-07-28 실측: 20260727→20260728 전 항목 0.00%). 마감 전에는
    당일을 아예 보지 않는다. 기준 16:00 KST는 fable CLAUDE.md 3번 규칙.
    """
    if 'v' not in _cache:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone(timedelta(hours=9)))
        cut = now if now.hour >= 16 else now - timedelta(days=1)
        _cache['v'] = cut.strftime('%Y%m%d')
    return _cache['v']


def load_panel(need=40):
    panel = {}
    for sector, code, name in UNIVERSE + [('BM', BENCH[0], BENCH[1])]:
        panel[code] = dict(fetch_closes(code, need))
        time.sleep(0.35)
    return panel


def pick(panel, asof=None):
    """asof(YYYYMMDD) 종가 기준 mom20 상위 5종 + Rule H. asof=None이면 최신일."""
    dates = sorted(set.intersection(*[set(v.keys()) for v in panel.values()]))
    if asof:
        dates = [d for d in dates if d <= asof]
    if len(dates) < 21:
        raise SystemExit('거래일 부족 — 데이터 수집 실패')
    d = dates[-1]
    i = len(dates) - 1

    def px(c, j):
        return panel[c].get(dates[j])

    cand = []
    for sector, code, name in UNIVERSE:
        p0, p20 = px(code, i), px(code, i - 20)
        if not (p0 and p20):
            continue
        mom20 = p0 / p20 - 1.0
        # Rule H — 전일 단일세션 +10% 초과 / 직전 3거래일 누적 +20% 초과 제외
        p1, p3 = px(code, i - 1), px(code, i - 3)
        if p1 and (p0 / p1 - 1.0) > 0.10:
            continue
        if p3 and (p0 / p3 - 1.0) > 0.20:
            continue
        cand.append({'sector': sector, 'code': code, 'name': name,
                     'close': p0, 'mom20': mom20,
                     'chg1': (p0 / p1 - 1.0) if p1 else None})
    cand.sort(key=lambda x: x['mom20'], reverse=True)
    return d, cand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', help='선정 기준일 YYYYMMDD (기본: 최신 거래일)')
    ap.add_argument('--score', help='해당일 선정 → 익일 성과 채점 후 트래커 기록')
    a = ap.parse_args()

    need = 60 if a.score else 40
    panel = load_panel(need)
    asof = a.score or a.date
    d, cand = pick(panel, asof)

    print(f'[Rule SU v2.6] 섹터 대표 개별종목 15종 — {d} 종가 기준')
    print(f"{'순위':>4s}  {'섹터':10s}{'종목':20s}{'코드':>8s}{'종가':>11s}{'mom20':>9s}{'전일%':>8s}")
    print('-' * 74)
    for n, c in enumerate(cand, 1):
        mark = '★' if n <= NPICK else ' '
        ch = f"{c['chg1']*100:+.2f}%" if c['chg1'] is not None else '   -  '
        print(f"{mark}{n:>3d}  {c['sector']:10s}{c['name']:20s}{c['code']:>8s}"
              f"{c['close']:>11,.0f}{c['mom20']*100:>8.2f}%{ch:>8s}")
    picks = cand[:NPICK]
    excluded = len(UNIVERSE) - len(cand)
    if excluded:
        print(f'\n※ Rule H 과열필터로 {excluded}종 제외됨')
    print('\n단기 추천 5종: ' + ', '.join(f"{c['name']}({c['code']})" for c in picks))

    if not a.score:
        return

    # ---- 채점: 선정일 d → 익일 dn ----
    dates = sorted(set.intersection(*[set(v.keys()) for v in panel.values()]))
    if d not in dates or dates.index(d) + 1 >= len(dates):
        print('\n익일 종가 미확보 — 채점 보류')
        return
    dn = dates[dates.index(d) + 1]

    def ret(c):
        return panel[c][dn] / panel[c][d] - 1.0

    port = sum(ret(c['code']) for c in picks) / len(picks)
    basket = sum(ret(c) for _, c, _ in UNIVERSE) / len(UNIVERSE)
    kodex = ret(BENCH[0])
    # 2026-08-14 사용자 지시 — 왕복비용 0. 종전값 0.0010(왕복 10bp).
    # 주의: 이 트랙은 ETF가 아니라 개별종목이다. ETF와 달리 매도 시 증권거래세가
    # 부과되므로 0 이 아닐 수 있다 — 실제 세율 확인 후 재조정 필요(미해결).
    COST = 0.0
    row = {
        'date': d, 'next_date': dn,
        'picks': '|'.join(c['code'] for c in picks),
        'port_ret': round(port * 100, 4),
        'basket_ret': round(basket * 100, 4),
        'kodex_ret': round(kodex * 100, 4),
        'excess_kodex': round((port - COST - kodex) * 100, 4),
        'excess_basket': round((port - COST - basket) * 100, 4),
        'note': '',
    }
    fields = list(row)
    exist = os.path.exists(TRACKER)
    prev = []
    if exist:
        with open(TRACKER, encoding='utf-8') as f:
            prev = [r for r in csv.DictReader(f)]
    if any(r['date'] == d for r in prev):
        print(f'\n트래커에 {d} 행이 이미 있음 — 멱등 처리(기록 생략)')
    else:
        with open(TRACKER, 'a', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            if not exist:
                w.writeheader()
            w.writerow(row)
        prev.append({k2: str(v) for k2, v in row.items()})
        print(f'\n트래커 기록 완료 → {TRACKER}')
    print(f"채점 {d}→{dn}: 픽 {port*100:+.2f}% / 바스켓 {basket*100:+.2f}% / "
          f"KODEX200 {kodex*100:+.2f}%")
    print(f"  초과(KODEX200 대비, 무비용) {row['excess_kodex']:+.4f}%p, "
          f"초과(바스켓 대비) {row['excess_basket']:+.4f}%p")
    n = len(prev)
    if n:
        eb = [float(r['excess_basket']) for r in prev]
        ek = [float(r['excess_kodex']) for r in prev]
        # 2026-08-06 시정 — 고정 20영업일 → N*(judge_ready 와 동일 식). Rule SU 의
        # 1차 판정 지표는 '바스켓 대비 초과'다(CLAUDE.md 2026-07-26·4차).
        ns = _n_star(eb)
        tail = ('표본 3일 미만' if ns is None else
                f'N*={ns}일 도달 — 판정 가능' if n >= ns else
                f'필요 표본 N*={ns}일, {ns-n}일 남음' +
                ('  ※ 잡음 상한(60) — 이 지표로는 판정이 어렵다' if ns >= 60 else ''))
        print(f'  누적 {n}일 평균: 바스켓초과 {sum(eb)/n:+.4f}%p, KODEX초과 {sum(ek)/n:+.4f}%p'
              f'  ({tail})')


if __name__ == '__main__':
    main()
