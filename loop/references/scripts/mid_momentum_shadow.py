#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mid_momentum_shadow.py — 중기 ETF 선정 축 shadow 트래커 (2026-07-29 신설)

배경: 2026-07-29 중기 트랙 백테스트(`중기트랙_비가격축_백테스트_2026-07-29.docx`)에서
현행 [6-2] 중기 선정룰("mom60 < -10% 낙폭과대 + 3·5일 반등")이 보유 20일 기준
-4.958%/20일(오프셋 0/20)로 구조적 열위임이 확인됐고, 대안 mom150 상위 5종이
+1.234%/20일(오프셋 18/20)로 우위였다. 다만 레짐 의존·생존편의 위험이 남아
**즉시 교체가 아니라 20영업일 shadow 병행 관측** 후 승격 판정하기로 했다.

하는 일 (전부 조회 전용 — 주문·매매 기능 없음)
  --update   : backtest/panel_ohlc_2y.csv 를 최신 거래일까지 연장 (ka10081, 멱등·재개)
  --record D : D 종가 기준 두 트랙의 픽 5종씩을 트래커에 1행 기록 (멱등)
  --score    : 기록된 행 중 익일 종가가 확보된 것을 채점 (탈락청산 기준, 아래 참조)
  --report   : 누적 성과·승격 3조건 판정 출력
  (인자 없으면 update → record(최신거래일) → score → report 순으로 전부 수행)

[2026-08-06 개편] 채점 기준을 '보유 20거래일' → **탈락청산(A안) 일별 손익**으로 교체.
근거: 2026-08-03 검정(`backtest/bt_mid_exit_20260803.py`, N 대장 #476)에서 실제 집행
규칙이 '추천 탈락 시 청산'임이 확정됐고 A안이 B안(20일고정)보다 +0.0410%p/일 우위였다.
그럼에도 이 스크립트는 8/6까지 HOLD=20 으로 채점을 대기시켜 **기록 6건 전부 미채점**
이었다 — 즉 확정된 규칙이 아니라 폐기된 규칙을 측정하고 있었다. 탈락청산에서는 매일의
보유집합이 그날의 픽5와 같으므로, 각 행을 **D→D+1 수익률**로 채점하면 그것이 곧 A안의
일별 손익이다. 비용은 2026-08-14 사용자 지시로 0이다 (종전: 회전분에만 부과
(진입·청산 각 5bp, 직전 트래커 행 대비 신규진입·탈락 건수 기준).

승격 3조건 (판정 시점은 judge_ready.py 의 N* 로 결정 — 고정 20일 아님)
  (a) mom150 트랙의 KODEX200 대비 평균 초과수익 > 0
  (b) 잭나이프(1회차 제거) 하한 > 0
  (c) 현행 낙폭과대 트랙 대비 우위
  셋 다 충족할 때만 [6-2] 선정 축 교체를 사용자에게 승인 요청한다.
"""
import argparse
import csv
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(HERE, '..'))
LOOP = os.path.abspath(os.path.join(REF, '..'))
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
UNIV = os.path.join(LOOP, 'etf_universe.csv')
TRACKER = os.path.join(REF, 'mid_momentum_shadow.csv')
BENCH = '069500'
HOLD = 1           # 채점 지평 = 1거래일 (탈락청산이면 보유집합 = 그날의 픽5, 2026-08-06 개편)
NPICK = 5
COST = 0.0  # 2026-08-14 사용자 지시 — 왕복비용 없음(무료 수수료·ETF 거래세 면제, 겹치는 종목은 계속 보유하고 교체분만 거래). 종전값 0.0005(편도 5bp, 회전분에만 부과)
MINP_SHORT = 10000  # 중기 슬롯은 최소가격 제한 없음 (단기에만 적용)

DERIV = ['인버스', '곱버스', '레버리지', '2X', '2배', '숏']
CASH = ['머니마켓', 'CD1년', 'CD금리', '초단기', 'KOFR', 'MMF', '국고채', '통안',
        'SOFR', '금리액티브', '현금']

COLS = ['date', 'score_date', 'status', 'regime',
        'mom150_codes', 'mom150_names', 'cur_codes', 'cur_names',
        'n_mom150', 'n_cur',
        'mom150_ret', 'cur_ret', 'kodex_ret', 'basket_ret',
        'mom150_excess', 'cur_excess', 'note']


def regime_at(px, dates, i):
    """국면 라벨 (기록 전용 — 선정 로직에는 쓰지 않는다. 2026-07-29 사용자 질문 후속).

    KODEX200의 D종가까지만 사용: close>MA60 & MA20>MA60 = BULL,
    close<MA60 & MA20<MA60 = BEAR, 그 외 SIDE.
    20회차 누적 후 '국면별로 성과가 갈리는가'를 OOS로 확인하기 위한 라벨이며,
    이 값에 따라 픽을 바꾸지 않는다(파라미터 분기는 표본을 얇게 만들어 과최적화를 부른다).
    """
    v = px.get(BENCH) or {}
    if i < 60:
        return ''
    try:
        w = [v[dates[j]] for j in range(i - 59, i + 1)]
    except KeyError:
        return ''
    ma60 = sum(w) / 60
    ma20 = sum(w[-20:]) / 20
    c = w[-1]
    if c > ma60 and ma20 > ma60:
        return 'BULL'
    if c < ma60 and ma20 < ma60:
        return 'BEAR'
    return 'SIDE'


# ---------------------------------------------------------------- 데이터
def is_deriv(n):
    n = (n or '').replace(' ', '')
    return any(x in n for x in DERIV)


def is_cash(n):
    n = (n or '').replace(' ', '')
    return any(x in n for x in CASH)


def load_panel():
    px = defaultdict(dict); nm = {}
    if not os.path.exists(PANEL):
        return px, nm, []
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                px[r['code']][r['date']] = float(r['close'])
            except (ValueError, KeyError):
                continue
            nm[r['code']] = r['name']
    dates = sorted({d for v in px.values() for d in v})
    return px, nm, dates


def update_panel(budget=300.0, target=None):
    """최신 거래일까지 패널 연장. 코드별 최신일이 target 미만이면 ka10081 재조회."""
    rows = defaultdict(dict); nm = {}
    if os.path.exists(PANEL):
        with open(PANEL, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                rows[r['code']][r['date']] = (r['open'], r['high'], r['low'],
                                              r['close'], r['volume'])
                nm[r['code']] = r['name']
    universe = []
    with open(UNIV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            universe.append((r['티커'].strip(), r['종목명'].strip()))

    # 목표 최신일: 지정 없으면 벤치마크를 먼저 조회해 결정
    # [2026-08-07] 키움 ka10081 은 장 시작 전에도 당일 봉을 O=H=L=C·거래량 0 으로
    # 돌려준다(실측 201종 전부). settled() 로 미확정 세션을 배제하지 않으면 그 유령
    # 봉이 패널에 들어가 mom150·채점을 오염시킨다 — rebuild_ohlc_panel.py 는 이미
    # 같은 가드를 쓰고 있었으나 이 경로에는 빠져 있었다.
    import ensure_data as _ed
    if target is None:
        try:
            res = k.get_daily_chart(BENCH)
            arr = res.get('stk_dt_pole_chart_qry') or []
            days = sorted({str(it.get('dt', '')) for it in arr if str(it.get('dt', ''))})
            days = [d for d in days if _ed.settled(d)]
            target = days[-1] if days else None
        except Exception as e:
            print(f'  [update] 기준일 조회 실패: {e}')
            target = None
    if target is None:
        return 0, None

    t0 = time.time(); n = 0
    for code, name in universe:
        if time.time() - t0 > budget:
            print('  [update] 예산 소진 — 다음 실행에서 재개')
            break
        have = rows.get(code) or {}
        if have and max(have) >= target:
            continue
        try:
            res = k.get_daily_chart(code)
        except Exception as e:
            print(f'  [update] {code} 실패: {e}')
            continue
        for x in res.get('stk_dt_pole_chart_qry') or []:
            d = x.get('dt')
            if not d or d in have or not _ed.settled(d):
                continue
            try:
                rows[code][d] = (str(abs(float(x['open_pric']))),
                                 str(abs(float(x['high_pric']))),
                                 str(abs(float(x['low_pric']))),
                                 str(abs(float(x['cur_prc']))),
                                 str(float(x.get('trde_qty') or 0)))
            except (ValueError, KeyError):
                continue
        nm[code] = name
        n += 1
        time.sleep(0.2)

    if n:
        tmp = PANEL + '.tmp'
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['code', 'name', 'date', 'open', 'high', 'low', 'close', 'volume'])
            for code in sorted(rows):
                for d in sorted(rows[code]):
                    w.writerow([code, nm.get(code, ''), d, *rows[code][d]])
        # 2026-07-31 — 이 마운트에서 os.replace 가 원자적이지 않아, 갱신 도중 프로세스가
        # 죽으면 패널이 행 중간에서 잘린다(실측 96,692행 → 6,172행). 쓰기 전 스냅샷 +
        # 교체 후 재검증 + 실패 시 롤백을 safe_io 가 담당한다.
        import safe_io
        safe_io.safe_replace(tmp, PANEL)
    return n, target


# ---------------------------------------------------------------- 선정
def eligible(px, nm, dates, i):
    """중기 슬롯 유니버스 — 파생·현금성 제외. 최소가격 제한 없음(morning_run과 동일)."""
    d = dates[i]
    out = []
    for c, v in px.items():
        if d not in v:
            continue
        n = nm.get(c, '')
        if is_deriv(n) or is_cash(n):
            continue
        out.append(c)
    return out


def pick_mom150(px, nm, dates, i, lb=150, n=NPICK):
    """신규 후보 — 150거래일 모멘텀 상위 5종. Rule H 과열필터 동일 적용.
    n: 반환 종목 수(기본 5 = Rule MM). 2026-09-26 Rule MLV shadow 가 pool 30 을 같은 계산으로 받기 위해 추가."""
    if i < lb:
        return []
    d, d0 = dates[i], dates[i - lb]
    d1, d3 = dates[i - 1], dates[i - 3]
    sc = []
    for c in eligible(px, nm, dates, i):
        v = px[c]
        if d0 not in v or d1 not in v or d3 not in v or not v[d0]:
            continue
        if v[d] / v[d1] - 1 > 0.10 or v[d] / v[d3] - 1 > 0.20:   # Rule H
            continue
        sc.append((v[d] / v[d0] - 1, c))
    sc.sort(reverse=True)
    return [c for _, c in sc[:n]]


def pick_current(px, nm, dates, i):
    """현행 [6-2] 룰 재현 — mom60 < -10% 중 r3 3~14%, r3+r5 상위 5종."""
    if i < 60:
        return []
    d = dates[i]; d3, d5, d60 = dates[i - 3], dates[i - 5], dates[i - 60]
    sc = []
    for c in eligible(px, nm, dates, i):
        v = px[c]
        if not all(x in v for x in (d3, d5, d60)) or not v[d60]:
            continue
        m60 = v[d] / v[d60] - 1
        r3 = v[d] / v[d3] - 1
        r5 = v[d] / v[d5] - 1
        if m60 >= -0.10 or not (0.03 < r3 < 0.14):
            continue
        sc.append((r3 + r5, c))
    sc.sort(reverse=True)
    return [c for _, c in sc[:NPICK]]


# ---------------------------------------------------------------- 트래커
def read_tracker():
    if not os.path.exists(TRACKER):
        return []
    with open(TRACKER, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_tracker(rows):
    tmp = TRACKER + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x['date']):
            w.writerow({c: r.get(c, '') for c in COLS})
    os.replace(tmp, TRACKER)


def record(D=None):
    px, nm, dates = load_panel()
    if not dates:
        print('패널 없음 — --update 먼저 실행'); return 2
    if D is None:
        D = dates[-1]
    if D not in dates:
        print(f'패널에 {D} 없음 (마지막 {dates[-1]})'); return 2
    rows = read_tracker()
    if any(r['date'] == D for r in rows):
        print(f'  [record] {D} 이미 기록됨 — 생략(멱등)'); return 0
    i = dates.index(D)
    a = pick_mom150(px, nm, dates, i)
    b = pick_current(px, nm, dates, i)
    rows.append({
        'date': D, 'score_date': '', 'status': 'pending',
        'regime': regime_at(px, dates, i),
        'mom150_codes': ';'.join(a), 'mom150_names': ';'.join(nm.get(c, '') for c in a),
        'cur_codes': ';'.join(b), 'cur_names': ';'.join(nm.get(c, '') for c in b),
        'n_mom150': len(a), 'n_cur': len(b),
        'mom150_ret': '', 'cur_ret': '', 'kodex_ret': '', 'basket_ret': '',
        'mom150_excess': '', 'cur_excess': '',
        'note': '' if b else '현행룰 후보 0종(관망)',
    })
    write_tracker(rows)
    print(f'  [record] {D} 기록 — mom150 {len(a)}종 / 현행 {len(b)}종')
    print(f'    mom150: {", ".join(nm.get(c, c) for c in a)}')
    print(f'    현행  : {", ".join(nm.get(c, c) for c in b) or "(후보 없음)"}')
    return 0


def basket_ret(px, nm, dates, i, j):
    d, dn = dates[i], dates[j]
    rs = []
    for c in eligible(px, nm, dates, i):
        v = px[c]
        if dn in v and v[d]:
            rs.append(v[dn] / v[d] - 1)
    return sum(rs) / len(rs) if rs else None


def port_ret(px, codes, d, dn, prev_codes=None):
    """탈락청산 기준 일별 손익 (2026-08-06 개편).

    보유집합 = 그날의 픽(codes). 비용은 회전분에만 부과한다 —
    직전 행 대비 신규진입 + 탈락 건수 × 편도 5bp 를 보유 종목 수로 나눈다
    (`backtest/bt_mid_exit_20260803.py` simulate(mode='dropout') 와 동일 계산).
    prev_codes 가 None 이면 최초 진입으로 보아 전량 신규진입 처리한다.
    """
    rs = []
    for c in codes:
        v = px.get(c) or {}
        if d in v and dn in v and v[d]:
            rs.append(v[dn] / v[d] - 1)
    if not rs:
        return None
    cur = set(codes)
    prev = set(prev_codes) if prev_codes is not None else set()
    turnover = len(cur - prev) + len(prev - cur)
    return sum(rs) / len(rs) - turnover * COST / len(rs)


def score():
    px, nm, dates = load_panel()
    rows = sorted(read_tracker(), key=lambda r: r['date'])
    n = 0
    for k_i, r in enumerate(rows):
        if r['status'] == 'scored' or r['date'] not in dates:
            continue
        i = dates.index(r['date'])
        if i + HOLD >= len(dates):
            continue
        j = i + HOLD
        d, dn = dates[i], dates[j]
        bv = px.get(BENCH) or {}
        if d not in bv or dn not in bv:
            continue
        prev = rows[k_i - 1] if k_i else None
        pa = [c for c in prev['mom150_codes'].split(';') if c] if prev else None
        pc = [c for c in prev['cur_codes'].split(';') if c] if prev else None
        kr = bv[dn] / bv[d] - 1
        br = basket_ret(px, nm, dates, i, j)
        ar = port_ret(px, [c for c in r['mom150_codes'].split(';') if c], d, dn, pa)
        cr = port_ret(px, [c for c in r['cur_codes'].split(';') if c], d, dn, pc)
        r.update({
            'score_date': dn, 'status': 'scored',
            'kodex_ret': f'{kr*100:.4f}',
            'basket_ret': f'{br*100:.4f}' if br is not None else '',
            'mom150_ret': f'{ar*100:.4f}' if ar is not None else '',
            'cur_ret': f'{cr*100:.4f}' if cr is not None else '',
            'mom150_excess': f'{(ar-kr)*100:.4f}' if ar is not None else '',
            'cur_excess': f'{(cr-kr)*100:.4f}' if cr is not None else '',
        })
        n += 1
    if n:
        write_tracker(rows)
    print(f'  [score] {n}건 채점 (탈락청산 기준, D→D+{HOLD}거래일)')
    return 0


def jackknife_low(xs):
    n = len(xs)
    if n < 3:
        return None
    s = sum(xs)
    return min((s - x) / (n - 1) for x in xs)


def n_star(xs):
    """판정에 필요한 표본 수 (judge_ready.py 와 동일 식, 2026-07-31 규정).

    N* = (1.28 × sd/|평균|)²  · 하한 8 · 상한 60.
    고정 20영업일 규정은 2026-07-31 에 폐지됐다 — 규칙마다 잡음이 달라
    필요 기간이 2배 이상 벌어지기 때문이다.
    """
    if len(xs) < 3:
        return None
    m = sum(xs) / len(xs)
    if not m:
        return 60
    sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    return max(8, min(60, math.ceil((1.28 * sd / abs(m)) ** 2)))


def report(insample=False):
    rows = [r for r in read_tracker() if r['status'] == 'scored']
    pend = len(read_tracker()) - len(rows)
    if not rows:
        print(f'채점 완료 0건 (대기 {pend}건).')
        return 0
    A = [float(r['mom150_excess']) for r in rows if r['mom150_excess']]
    C = [float(r['cur_excess']) for r in rows if r['cur_excess']]
    both = [(float(r['mom150_excess']), float(r['cur_excess'])) for r in rows
            if r['mom150_excess'] and r['cur_excess']]
    print('\n=== 중기 모멘텀 shadow 트래커 ===')
    print(f'채점 완료 {len(rows)}회차 · 대기 {pend}회차 (탈락청산 일별 채점)')
    print(f'기간 {rows[0]["date"]} ~ {rows[-1]["date"]} (채점일 {rows[-1]["score_date"]})')
    print(f'\n{"트랙":<22}{"회차":>5}{"평균 일별초과%":>15}{"승률%":>8}{"잭나이프 하한%":>15}')
    for lbl, xs in (('mom150 (신규 후보)', A), ('현행 낙폭과대룰', C)):
        if not xs:
            print(f'{lbl:<22}{0:>5}{"-":>15}{"-":>8}{"-":>15}')
            continue
        jk = jackknife_low(xs)
        print(f'{lbl:<22}{len(xs):>5}{sum(xs)/len(xs):>15.3f}'
              f'{sum(1 for x in xs if x > 0)/len(xs)*100:>8.1f}'
              f'{(jk if jk is not None else 0):>15.3f}')
    if both:
        diff = [a - c for a, c in both]
        print(f'\n동일 회차 페어 비교 {len(both)}회 — mom150 − 현행 = {sum(diff)/len(diff):+.3f}%p '
              f'(mom150 우세 {sum(1 for x in diff if x > 0)}회)')
    cur_zero = sum(1 for r in read_tracker() if r.get('n_cur') in ('0', 0))
    print(f'현행룰 후보 0종(관망) 회차: {cur_zero}')

    # 국면별 분해 (기록·관찰 전용 — 선정 분기는 하지 않는다)
    byreg = defaultdict(list)
    for r in rows:
        if r.get('regime') and r['mom150_excess']:
            byreg[r['regime']].append(float(r['mom150_excess']))
    if byreg:
        print('\n국면별 mom150 초과수익 (관찰 전용, 분기 미적용):')
        for rg in ('BULL', 'SIDE', 'BEAR'):
            xs = byreg.get(rg)
            if xs:
                print(f'  {rg:<5} {len(xs):>3}회  평균 {sum(xs)/len(xs):+.3f}%')

    if insample:
        print('\n⚠ 백필(in-sample) 결과 — 승격 판정에 쓰지 않는다.')
        print('  ① 2026-07-29 백테스트와 같은 구간이라 OOS가 아니다.')
        print('  ② 백테스트 구간과 겹치므로 선택편의가 남는다.')
        print('  용도는 스크립트 정합성 확인과 최근 국면 참고까지다.')
        return 0

    print('\n--- 승격 3조건 판정 ---')
    ok1 = bool(A) and sum(A) / len(A) > 0
    jk = jackknife_low(A) if A else None
    ok2 = jk is not None and jk > 0
    ok3 = bool(both) and sum(a - c for a, c in both) > 0
    for lbl, ok in (('(a) mom150 평균 초과 > 0', ok1),
                    ('(b) 잭나이프 하한 > 0', ok2),
                    ('(c) 현행 룰 대비 우위', ok3)):
        print(f'  {"○" if ok else "✗"} {lbl}')
    ns = n_star(A)
    if ns is None:
        print('\n판정 보류 — 표본 3회 미만.')
    elif len(A) < ns:
        print(f'\n판정 보류 — 필요 표본 N*={ns}회 (현 {len(A)}회, {ns-len(A)}회 남음).'
              ' 현 시점 수치는 참고용.')
        if ns >= 60:
            print('  ※ 잡음이 커서 N*가 상한(60)에 걸렸다 — 이 지표로는 판정이 어렵다.')
    elif ok1 and ok2 and ok3:
        print(f'\n★ N*={ns}회 도달 · 3조건 전부 충족 — [6-2] 선정 축 교체를 사용자에게 승인 요청할 것.')
    else:
        print(f'\nN*={ns}회 도달 · 3조건 미충족 — 2회 연속 미달이면 검증 대기로 강등.')
    return 0


def backfill(n_days):
    """검증 전용 — 과거 n_days 거래일을 별도 파일에 채운다.

    주의: 백필 행은 백테스트 표본과 겹치므로 OOS가 아니다. 승격 판정에는 절대
    쓰지 않고, 스크립트 정합성 확인과 최근 추세 참고용으로만 본다.
    """
    global TRACKER
    TRACKER = os.path.join(REF, 'mid_momentum_backfill.csv')
    px, nm, dates = load_panel()
    if not dates:
        print('패널 없음'); return 2
    start = max(160, len(dates) - n_days)
    for i in range(start, len(dates)):
        record(dates[i])
    score()
    report(insample=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--update', action='store_true')
    ap.add_argument('--record', nargs='?', const='LATEST')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--backfill', type=int, default=0,
                    help='검증 전용: 과거 N거래일을 mid_momentum_backfill.csv에 채움')
    ap.add_argument('--budget', type=float, default=300.0)
    a = ap.parse_args()
    if a.backfill:
        return backfill(a.backfill)
    any_flag = a.update or a.record or a.score or a.report

    if a.update or not any_flag:
        n, t = update_panel(budget=a.budget)
        print(f'  [update] {n}종 갱신 (목표 최신일 {t})')
    if a.record or not any_flag:
        record(None if (a.record in (None, 'LATEST')) else a.record)
    if a.score or not any_flag:
        score()
    if a.report or not any_flag:
        report()
    return 0


if __name__ == '__main__':
    sys.exit(main())
