#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""데일리 브리핑 [1-3] 미국장 전이 참고표 + 발표 일정 생성기 (2026-09-08 신설).

성격: **참고 정보 전용 — 예측 신호 아님.** 선정 로직 반영 금지(fable/CLAUDE.md 19번).
근거: loop/월가정보_이벤트캘린더_검토_20260908.md · 데이터 loop/backtest/wallst/
      (7년 1,822 한국거래일 실측, 22섹터 전부 5구간 단조)

동작: 전일 미국 종가만 조회한다(Yahoo, 무인증). 실패 시 캐시를 쓰고 stale 플래그를 세운다.
      **User-Agent 헤더 필수** — 없으면 429가 온다.

사용:
    python3 wallst_ref.py           # 사람이 확인용
    python3 wallst_ref.py --json    # 브리핑 생성 스크립트가 읽을 JSON
"""
import os, sys, json, datetime, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '_wallst_ref_cache.json')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
TIMEOUT = 12
SYMS = [('SOX', '%5ESOX', '필라델피아 반도체'), ('IXIC', '%5EIXIC', '나스닥'),
        ('GSPC', '%5EGSPC', 'S&P500'), ('TNX', '%5ETNX', '미 10년물(%)'),
        ('VIX', '%5EVIX', 'VIX')]

BUCKETS = ['SOX ≤ -2%', '-2 ~ -1%', '-1 ~ +1%', '+1 ~ +2%', 'SOX ≥ +2%']
NDAYS = [270, 216, 741, 268, 327]
# 7년 실측: (익일 평균 수익률 5구간, 익일 상승확률 5구간, 전일 SOX 1%당 베타)
TRANSFER = {
    'AI':          ([-2.43, -0.85, 0.27, 1.18, 1.90], [12.0, 26.2, 59.1, 82.9, 88.7], 0.602),
    'AI전력인프라': ([-2.54, -0.37, 0.49, 1.14, 1.84], [19.8, 37.8, 61.9, 70.7, 78.3], 0.589),
    '반도체':      ([-1.69, -0.65, 0.20, 0.81, 1.47], [19.6, 32.9, 55.2, 69.4, 77.7], 0.441),
    '로봇':        ([-1.76, -0.42, 0.21, 0.66, 1.33], [22.4, 40.3, 52.3, 63.8, 76.7], 0.424),
    'IT테크':      ([-1.24, -0.42, 0.20, 0.61, 1.02], [26.3, 38.9, 57.1, 70.9, 78.3], 0.324),
    '원자력':      ([-1.06, -0.27, 0.23, 0.77, 0.95], [34.0, 45.6, 52.3, 63.2, 67.4], 0.317),
    '방산우주':    ([-1.06, -0.20, 0.22, 0.74, 0.91], [32.8, 44.9, 54.2, 61.0, 63.5], 0.299),
    '국내지수':    ([-1.04, -0.32, 0.15, 0.45, 0.84], [25.6, 40.7, 58.4, 67.2, 73.1], 0.271),
    '증권':        ([-1.04, -0.25, 0.15, 0.44, 0.80], [27.8, 41.7, 52.1, 57.5, 67.0], 0.269),
    '2차전지':     ([-1.01, -0.27, 0.14, 0.43, 0.73], [30.7, 41.7, 51.4, 60.8, 67.3], 0.243),
    '자동차':      ([-0.88, -0.00, 0.17, 0.28, 0.55], [31.1, 46.3, 51.4, 59.3, 60.9], 0.216),
    '배당':        ([-0.79, -0.25, 0.13, 0.33, 0.65], [28.9, 42.6, 59.0, 65.3, 72.5], 0.216),
    '바이오':      ([-0.83, -0.13, 0.01, 0.34, 0.47], [32.1, 44.0, 48.1, 56.8, 59.8], 0.189),
    '건설':        ([-0.74, -0.22, 0.13, 0.34, 0.57], [39.3, 39.4, 52.1, 58.2, 58.4], 0.207),
    '은행금융':    ([-0.67, -0.03, 0.23, 0.36, 0.53], [37.4, 49.2, 53.8, 55.2, 67.7], 0.174),
    '귀금속':      ([-0.34,  0.06, 0.07, 0.29, 0.28], [43.7, 51.9, 52.4, 54.5, 54.1], 0.106),
    '채권':        ([-0.12, -0.05, 0.04, 0.08, 0.12], [45.2, 48.6, 56.7, 58.6, 57.2], 0.041),
}

# 발표 일정 — 확정 공개분. **연 1회(12월) 수기 갱신**한다. 출처는 검토 문서 §4.
#   FOMC  federalreserve.gov/monetarypolicy/fomccalendars.htm
#   금통위 bok.or.kr/portal/singl/crncyPolicyDrcMtg/listYear.do?menuNo=200755&mtgSe=A
#   BLS(CPI·고용)는 봇 차단이라 브라우저로 확인 후 수기 입력한다.
CALENDAR = [
    ('2026-09-11', '미국 8월 CPI',              '22:30', '물가 재반등 시 11번 게이트 강화'),
    ('2026-09-16', 'FOMC 결정 + 점도표',         '익일 03:00', '변동폭이 평시의 1.1배 — 방향 효과는 없음'),
    ('2026-10-01', '한국 9월 수출입동향(산업부)',   '09:00', '참고 전용(2026-09-02 검정, 선행성 없음)'),
    ('2026-10-02', '미국 9월 고용보고서',          '21:30', '강해도 약해도 금리 경로로 반영 — 양방향'),
    ('2026-10-14', '미국 9월 CPI',              '21:30', ''),
    ('2026-10-22', '한국 금통위 기준금리',         '10:00', '은행금융·건설·리츠에 직접'),
    ('2026-10-28', 'FOMC 결정',                 '익일 03:00', ''),
    ('2026-11-06', '미국 10월 고용보고서',         '22:30', ''),
    ('2026-11-10', '미국 10월 CPI',             '22:30', ''),
    ('2026-11-18', '엔비디아 실적(추정·미확정)',    '익일 06:00', '반도체·AI·AI전력 최대 단일 이벤트'),
    ('2026-11-26', '한국 금통위 기준금리',         '10:00', ''),
    ('2026-12-04', '미국 11월 고용보고서',         '22:30', ''),
    ('2026-12-09', 'FOMC 결정 + 점도표',          '익일 03:00', ''),
    ('2026-12-10', '미국 11월 CPI',             '22:30', ''),
]

FOOTNOTE = (
    "이 표는 **예측 신호가 아니라 국면 대응 참고표**입니다. 발표 결과가 좋을지 나쁠지는 알려주지 "
    "않고, **결과가 나온 뒤 어느 섹터가 얼마나 받는지**만 알려줍니다. 7년(2019-04~2026-09, 한국 "
    "1,822거래일) 실측이며 22개 섹터 전부 5구간에서 단조입니다. **평균값을 '먹을 수 있는 수익'으로 "
    "읽으면 안 됩니다** — 이 크기는 한국 개장 갭에 상당 부분 이미 들어가 있습니다(A 지표 초과의 "
    "89.4%가 갭). 충격은 개장 첫날(D+1)에 전부 반영되고 **D+2·D+3에는 반등도 추가하락도 "
    "없습니다**(반도체 SOX≤-2% 후 D+2 +0.32%p·D+3 -0.08%p) — 폭락 다음날 저가매수의 근거가 "
    "데이터에 없습니다. 종목 선정에는 사용하지 않으며 비중·매수상단 판단에만 사용합니다."
)


def bucket_idx(pct):
    if pct <= -2: return 0
    if pct <= -1: return 1
    if pct < 1:   return 2
    if pct < 2:   return 3
    return 4


def _fetch_one(q):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?range=10d&interval=1d"
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=TIMEOUT))
    r = d['chart']['result'][0]
    ts, cl = r['timestamp'], r['indicators']['quote'][0]['close']
    pair = [(t, c) for t, c in zip(ts, cl) if c is not None]
    (_, prev), (t1, last) = pair[-2], pair[-1]
    return {'close': round(last, 2), 'chg': round((last / prev - 1) * 100, 2),
            'date': datetime.datetime.utcfromtimestamp(t1).strftime('%Y-%m-%d')}


def build():
    us, ok = {}, True
    for name, q, _ in SYMS:
        try:
            us[name] = _fetch_one(q)
        except Exception as e:
            print(f"[warn] {name} 조회 실패: {e}", file=sys.stderr)
            ok = False
    if ok and 'SOX' in us:
        json.dump({'us': us, 'fetched_at': datetime.datetime.now().isoformat(timespec='seconds')},
                  open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
        return {'us': us, 'stale': False}
    if os.path.exists(CACHE):
        c = json.load(open(CACHE, encoding='utf-8'))
        c['us'].update(us)
        return {'us': c['us'], 'stale': True, 'fetched_at': c.get('fetched_at')}
    return {'us': us, 'stale': True}


def block():
    b = build()
    sox = b['us'].get('SOX')
    out = {'stale': b.get('stale', False), 'fetched_at': b.get('fetched_at'),
           'us': [{'name': nm, 'code': c, **b['us'][c]} for c, _, nm in SYMS if c in b['us']],
           'footnote': FOOTNOTE}
    if sox:
        i = bucket_idx(sox['chg'])
        out['bucket'] = BUCKETS[i]
        out['bucket_n'] = NDAYS[i]
        out['sox'] = sox
        out['rows'] = [{'sector': s, 'exp': v[0][i], 'win': v[1][i], 'beta': v[2]}
                       for s, v in sorted(TRANSFER.items(), key=lambda kv: -kv[1][0][i])]
    today = datetime.date.today()
    out['calendar'] = [{'date': d, 'event': e, 'time': t, 'note': n,
                        'dday': (datetime.date.fromisoformat(d) - today).days}
                       for d, e, t, n in CALENDAR if datetime.date.fromisoformat(d) >= today][:6]
    return out


def main():
    b = block()
    if '--json' in sys.argv:
        print(json.dumps(b, ensure_ascii=False)); return
    print("[1-3] 미국장 전이 참고표" + ("  ※캐시(갱신 실패)" if b['stale'] else ""))
    for u in b['us']:
        print(f"  {u['name']:<16}{u['close']:>11,.2f}{u['chg']:>+8.2f}%   ({u['date']})")
    if 'bucket' in b:
        print(f"\n구간 [{b['bucket']}] — 과거 {b['bucket_n']}일")
        for r in b['rows']:
            print(f"  {r['sector']:<12} 평균 {r['exp']:+5.2f}%   상승확률 {r['win']:4.1f}%   β {r['beta']:.3f}")
    print("\n다가오는 발표 일정")
    for c in b['calendar']:
        print(f"  D{c['dday']:+3d}  {c['date']}  {c['event']:<24}{c['time']:<11}{c['note']}")
    print(f"\n※ {FOOTNOTE}")


if __name__ == '__main__':
    main()
