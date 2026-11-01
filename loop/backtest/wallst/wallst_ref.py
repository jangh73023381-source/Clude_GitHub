#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wallst_ref.py — 브리핑 [2-1] 미국장 전이 참고표 + 발표 일정 캘린더.

**참고 전용이다. 종목 선정 로직에 반영하지 않는다**(trade_ref.py·sector_levels.py 와 같은 취급).
근거: backtest/wallst/ 7년(1,822 한국거래일) 실측 — 상세는
loop/월가정보_이벤트캘린더_검토_20260908.md.

사용: python3 wallst_ref.py [--json]
"""
import json, os, sys, csv, datetime, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
SYMS = {'SOX': '%5ESOX', 'GSPC': '%5EGSPC', 'IXIC': '%5EIXIC', 'TNX': '%5ETNX', 'VIX': '%5EVIX'}

# 7년 실측 전이표: 전일 SOX 구간 → 익일 한국 섹터 평균 수익률(%) / 상승확률(%)
BUCKETS = ['SOX≤-2%', '-2~-1%', '-1~+1%', '+1~+2%', 'SOX≥+2%']
TRANSFER = {  # 섹터: (평균 5개, 상승확률 5개)
    '반도체':      ([-1.69, -0.65, 0.20, 0.81, 1.47], [19.6, 32.9, 55.2, 69.4, 77.7]),
    'AI':          ([-2.43, -0.85, 0.27, 1.18, 1.90], [12.0, 26.2, 59.1, 82.9, 88.7]),
    'AI전력인프라': ([-2.54, -0.37, 0.49, 1.14, 1.84], [19.8, 37.8, 61.9, 70.7, 78.3]),
    'IT테크':      ([-1.24, -0.42, 0.20, 0.61, 1.02], [26.3, 38.9, 57.1, 70.9, 78.3]),
    '로봇':        ([-1.76, -0.42, 0.21, 0.66, 1.33], [22.4, 40.3, 52.3, 63.8, 76.7]),
    '2차전지':     ([-1.01, -0.27, 0.14, 0.43, 0.73], [30.7, 41.7, 51.4, 60.8, 67.3]),
    '원자력':      ([-1.06, -0.27, 0.23, 0.77, 0.95], [34.0, 45.6, 52.3, 63.2, 67.4]),
    '방산우주':    ([-1.06, -0.20, 0.22, 0.74, 0.91], [32.8, 44.9, 54.2, 61.0, 63.5]),
    '국내지수':    ([-1.04, -0.32, 0.15, 0.45, 0.84], [25.6, 40.7, 58.4, 67.2, 73.1]),
    '증권':        ([-1.04, -0.25, 0.15, 0.44, 0.80], [27.8, 41.7, 52.1, 57.5, 67.0]),
    '은행금융':    ([-0.67, -0.03, 0.23, 0.36, 0.53], [37.4, 49.2, 53.8, 55.2, 67.7]),
    '자동차':      ([-0.88, -0.00, 0.17, 0.28, 0.55], [31.1, 46.3, 51.4, 59.3, 60.9]),
    '바이오':      ([-0.83, -0.13, 0.01, 0.34, 0.47], [32.1, 44.0, 48.1, 56.8, 59.8]),
    '건설':        ([-0.74, -0.22, 0.13, 0.34, 0.57], [39.3, 39.4, 52.1, 58.2, 58.4]),
    '배당':        ([-0.79, -0.25, 0.13, 0.33, 0.65], [28.9, 42.6, 59.0, 65.3, 72.5]),
    '귀금속':      ([-0.34,  0.06, 0.07, 0.29, 0.28], [43.7, 51.9, 52.4, 54.5, 54.1]),
    '채권':        ([-0.12, -0.05, 0.04, 0.08, 0.12], [45.2, 48.6, 56.7, 58.6, 57.2]),
}
NDAYS = [270, 216, 741, 268, 327]

# 발표 일정(확정 공개분). 연 1회 갱신한다 — 출처는 검토 문서 §4.
CALENDAR = [
    ('2026-09-11', '미국 8월 CPI',            '美 22:30 KST', '높으면 금리↑ → 반도체·AI 약세 / 낮으면 강세'),
    ('2026-09-16', 'FOMC 결정 + 점도표',       '美 익일 03:00', '변동폭이 평소의 1.1배. 방향은 전이표대로'),
    ('2026-10-01', '한국 9월 수출입동향(산업부)', '한 09:00',     '참고 전용 — 선행성 없음(2026-09-02 검정)'),
    ('2026-10-02', '미국 9월 고용보고서',       '美 21:30 KST', '강하면 금리↑ / 약하면 침체 우려 — 양방향'),
    ('2026-10-14', '미국 9월 CPI',            '美 21:30 KST', '위와 같음'),
    ('2026-10-22', '한국 금통위 기준금리',      '한 10:00',     '은행금융·건설·리츠에 직접'),
    ('2026-10-28', 'FOMC 결정',               '美 익일 03:00', ''),
    ('2026-11-06', '미국 10월 고용보고서',      '美 22:30 KST', ''),
    ('2026-11-10', '미국 10월 CPI',           '美 22:30 KST', ''),
    ('2026-11-18', '엔비디아 실적(예상·미확정)',  '美 익일 06:00', '반도체·AI·AI전력에 최대 단일 이벤트'),
    ('2026-11-26', '한국 금통위 기준금리',      '한 10:00',     ''),
    ('2026-12-04', '미국 11월 고용보고서',      '美 22:30 KST', ''),
    ('2026-12-09', 'FOMC 결정 + 점도표',       '美 익일 03:00', ''),
    ('2026-12-10', '미국 11월 CPI',           '美 22:30 KST', ''),
]

FOOTNOTE = (
    "이 표는 **예측 신호가 아니라 국면 대응 참고표**입니다. 7년(2019-04~2026-09, 한국 1,822거래일) "
    "실측한 '전일 미국 반도체지수(SOX) 구간 → 익일 한국 섹터 평균 수익률'이며, 발표 결과가 좋을지 "
    "나쁠지는 알려주지 않습니다. 알려주는 것은 **결과가 나온 뒤 어느 섹터가 얼마나 받는가**뿐입니다. "
    "충격은 한국 개장 첫날(D+1)에 전부 반영되고 D+2·D+3에는 반등도 추가하락도 없습니다"
    "(반도체 SOX≤-2% 후 D+2 +0.32%p·D+3 -0.08%p). 종목 선정에는 사용하지 않습니다."
)


def _fetch(sym, q):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{q}"
         f"?range=10d&interval=1d")
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25))
    r = d['chart']['result'][0]
    cl = [c for c in r['indicators']['quote'][0]['close'] if c is not None]
    ts = r['timestamp']
    dt = datetime.datetime.utcfromtimestamp(ts[-1]).strftime('%Y-%m-%d')
    return cl[-1], (cl[-1] / cl[-2] - 1) * 100, dt


def bucket_idx(sox_pct):
    if sox_pct <= -2: return 0
    if sox_pct <= -1: return 1
    if sox_pct < 1:   return 2
    if sox_pct < 2:   return 3
    return 4


def main():
    us = {}
    for name, q in SYMS.items():
        try:
            us[name] = _fetch(name, q)
        except Exception as e:
            us[name] = None
            print(f"[warn] {name} 조회 실패: {e}", file=sys.stderr)
    sox = us.get('SOX')
    out = {'us': {k: (None if v is None else {'close': round(v[0], 2), 'chg': round(v[1], 2), 'date': v[2]})
                  for k, v in us.items()}}
    if sox:
        bi = bucket_idx(sox[1])
        out['bucket'] = BUCKETS[bi]
        out['bucket_n'] = NDAYS[bi]
        out['rows'] = [{'sector': s, 'exp': v[0][bi], 'win': v[1][bi]}
                       for s, v in sorted(TRANSFER.items(), key=lambda kv: -kv[1][0][bi])]
    today = datetime.date.today().isoformat()
    out['calendar'] = [{'date': d, 'event': e, 'time': t, 'note': n,
                        'dday': (datetime.date.fromisoformat(d) - datetime.date.today()).days}
                       for d, e, t, n in CALENDAR if d >= today][:6]
    out['footnote'] = FOOTNOTE

    if '--json' in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1)); return
    print("■ 전일 미국장")
    for k in ['SOX', 'GSPC', 'IXIC', 'TNX', 'VIX']:
        v = us.get(k)
        if v: print(f"  {k:5s} {v[0]:10,.2f}  {v[1]:+6.2f}%   ({v[2]})")
    if sox:
        print(f"\n■ 오늘 참고 반응 — 구간 [{BUCKETS[bucket_idx(sox[1])]}] (과거 {NDAYS[bucket_idx(sox[1])]}일)")
        for r in out['rows']:
            print(f"  {r['sector']:12s} 평균 {r['exp']:+5.2f}%   상승확률 {r['win']:4.1f}%")
    print("\n■ 다가오는 발표 일정")
    for c in out['calendar']:
        print(f"  D{c['dday']:+3d}  {c['date']}  {c['event']:22s} {c['time']:14s} {c['note']}")
    print("\n" + FOOTNOTE)


if __name__ == '__main__':
    main()
