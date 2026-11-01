#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""morning_run.py — 아침 통합 루프 0~2단계 단일 실행기 (2026-07-27 신설)

"아침 루틴 실행해줘" 한 번에 아래가 전부 돈다. 사용자가 관심모멘텀 파일럿을 따로
요청할 필요가 없다(CLAUDE.md [2026-07-26 추가] 통합 루프 절차의 스크립트 구현).

  0-A  채점 대상일 D 관심신호 행 확인 → 없으면 사후수집(post_hoc)
  0-B  오늘 T 관심신호 신규 수집 → v2/shadow/ns2 픽 기록
  1    채점 대상 판정 (신규 브리핑 유무 · 채점일 종가 유무)
  2    트랙 A(확정방법) · 트랙 B(조합제 shadow) · 트랙 C(Rule SU) · Rule CB 채점
  0-D  중기 모멘텀 shadow — 현행 [6-2] 낙폭과대룰 vs 신규 mom150 병행 기록·채점
       (2026-07-29 신설. 20영업일 도달 시 승격 3조건 판정)
  +    오늘 브리핑용 선정 산출 (mom20+RuleH 단기10 / 중기5 / Rule SU 단일5 / 하락예상5)

결과는 references/scripts/morning_state_<T>.json 에 쓴다. 3~5단계(개선·검증관)와
6단계(보고서·브리핑)는 이 JSON을 읽어 에이전트가 이어서 수행한다.

사용:
  python3 morning_run.py                    # 오늘(KST) 기준 실행
  python3 morning_run.py --date 20260727    # 특정 실행일로 재현
  python3 morning_run.py --skip-collect     # 관심신호 수집 생략(네트워크 차단 시)

주의: 조회 전용. 주문·매매·이체 기능은 어떤 경로로도 호출하지 않는다.
"""
import argparse
import collections
import csv
import json
import os
import re
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(HERE, '..'))
LOOP = os.path.abspath(os.path.join(REF, '..'))
FABLE = os.path.join(os.path.dirname(LOOP), 'fable')
KST = timezone(timedelta(hours=9))

# [2026-08-22 확정 v2.9] Rule LV — mom20 상위 pool 안에서 실현변동성이 낮은 순으로 정렬한다.
# 파라미터는 7년 패널 6관문 검정의 고원 중심점이며, 판정 전까지 변경 금지(동결).
LV_POOL, LV_K, LV_MINRET = 30, 20, 6

from universe_filters import is_cash, is_deriv  # noqa: E402  (제외 키워드 공용 상수)
import ensure_data  # noqa: E402  (패널·코스피 자동 보충)


def run(cmd, cwd=LOOP, timeout=600, keep=4000):
    """서브프로세스 실행 — 실패해도 전체를 중단시키지 않고 결과를 반환한다.
    keep = stdout 보존 길이(끝에서부터). 0-G 는 신뢰도 표(2026-09-11)가 붙어 더 길게 보존한다."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {'rc': p.returncode, 'out': p.stdout[-keep:], 'err': p.stderr[-2000:]}
    except Exception as e:
        return {'rc': -1, 'out': '', 'err': f'{type(e).__name__}: {e}'}


def newest_panel():
    d = os.path.join(LOOP, 'backtest')
    c = sorted(f for f in os.listdir(d)
               if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(d, c[-1]) if c else None


def trading_days_upto(D, n):
    """D 를 포함해 직전 n 거래일을 오래된 순으로 돌려준다 (2026-08-06 신설).

    밀린 채점을 회수하는 데 쓴다 — 하루만 돌리면 '익일 종가 미확보'로 건너뛴 날이
    다음 실행에서도 다시 시도되지 않아 표본이 영구히 빈다.
    """
    path = newest_panel()
    if not path:
        return [D]
    ds = sorted({r['date'] for r in csv.DictReader(open(path, encoding='utf-8'))})
    if D not in ds:
        return [D]
    i = ds.index(D)
    return ds[max(0, i - n + 1):i + 1]


def load_panel():
    path = newest_panel()
    px, nm = collections.defaultdict(dict), {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        try:
            px[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError):
            continue
        nm[r['code']] = r.get('name', '')
    dates = sorted({d for v in px.values() for d in v})
    return path, px, nm, dates


def compute_picks(px, nm, dates, D=None):
    """mom20 + Rule H 선정 (D = 선정 기준일). 룩어헤드 없음.

    D 를 명시하지 않으면 패널 마지막 거래일을 쓴다. 아침 루틴은 항상 '실행일 T 직전
    거래일'을 넘긴다 — 장 마감 후 패널이 T 까지 연장되면(2026-07-31 자동 보충 신설)
    dates[-1] 이 T 가 되어 그날 배포한 브리핑과 다른 픽이 조용히 만들어지기 때문이다.
    """
    D = D or dates[-1]
    i = dates.index(D)
    d1, d3, d5, d20 = dates[i - 1], dates[i - 3], dates[i - 5], dates[i - 20]
    d10 = dates[i - 10]
    d60 = dates[i - 60] if i - 60 >= 0 else None

    rows = []
    for c, v in px.items():
        need = [D, d1, d3, d5, d10, d20]
        if not all(x in v for x in need):
            continue
        n = nm[c]
        if is_deriv(n) or is_cash(n):
            continue
        r1, r3 = v[D] / v[d1] - 1, v[D] / v[d3] - 1
        rows.append(dict(
            code=c, name=n, close=v[D],
            mom20=v[D] / v[d20] - 1, r1=r1, r3=r3,
            r5=v[D] / v[d5] - 1, r10=v[D] / v[d10] - 1,
            mom60=(v[D] / v[d60] - 1) if (d60 and d60 in v) else None,
            ruleH=(r1 > 0.10 or r3 > 0.20)))
    rows.sort(key=lambda x: -x['mom20'])

    # [2026-07-30 사용자 지시] 최소가격(1만원) 필터 폐지 — 금액과 무관하게 ETF 유니버스 전체를
    # 단기 후보로 쓴다. 거래대금 등 유동성 필터도 두지 않는다(사용자 취소). 파생·현금성 제외는 유지.
    short_univ = list(rows)
    excluded = [r for r in short_univ if r['ruleH']]
    passed = [r for r in short_univ if not r['ruleH']]

    # [2026-08-22 확정 v2.9 — Rule LV] mom20 상위 LV_POOL 종 안에서 최근 LV_K 거래일
    # 실현변동성(일간수익률 표본표준편차)이 **낮은 순**으로 다시 정렬한다.
    #   · 유니버스·Rule H·비용(v2.8 무비용)은 전부 그대로다. 바뀌는 것은 pool 내부 정렬뿐이다.
    #   · 입력이 ETF 종가뿐이라 선정 시각 T 06:00 에 100% 조달된다(CLAUDE.md §4-6 통과).
    #   · 근거: 7년 패널 1,779일 — MDD -36.6%→-25.4% · Sharpe 1.04→1.56 · CAGR +30.5%→+31.2%.
    #     플라시보(pool30 무작위 5종 200회)에서 MDD·Sharpe p=0.000 → 분산효과가 아니라
    #     변동성 선택 자체의 값이다. 일평균 %p 초과로는 -0.0086(t=-0.27)로 무차별이며,
    #     이 규칙은 **수익이 아니라 위험을 줄인다**(연도별 MDD 8년 중 8년 우위).
    #   · σ 산출 가능 종목이 5종 미만이면 mom20 순서로 되돌린다(안전 폴백).
    def _sigma(code):
        v = px[code]
        rs = []
        for a, b in zip(dates[i - LV_K:i], dates[i - LV_K + 1:i + 1]):
            if a in v and b in v and v[a]:
                rs.append((v[b] / v[a] - 1) * 100)
        return statistics.stdev(rs) if len(rs) >= LV_MINRET else None

    lv = []
    for r in passed[:LV_POOL]:
        sg = _sigma(r['code'])
        if sg is not None:
            r['sigma20'] = sg
            lv.append(r)
    if len(lv) >= 5:
        lv.sort(key=lambda x: x['sigma20'])
        short10, lv_applied = lv[:10], True
    else:
        short10, lv_applied = passed[:10], False

    # 중기 후보: 60일 낙폭과대 + 최근 3~5일 반등, 단 3일 반등 과열(+14%↑)은 추격 위험으로 제외
    midpool = [r for r in rows if r['mom60'] is not None and r['mom60'] < -0.10
               and r['r3'] > 0.03 and r['r3'] < 0.14]
    midpool.sort(key=lambda x: -(x['r3'] + x['r5']))
    fall5 = short_univ[-5:][::-1]
    return dict(D=D, d20=d20, universe_n=len(short_univ), short10=short10,
                mid_pool=midpool[:12], fall5=fall5, ruleH_excluded=excluded,
                lv_applied=lv_applied, lv_pool_n=len(lv),
                mom_short10=[r['code'] for r in passed[:10]])


def mom150_picks(T):
    """[6-2] 중기 ETF 선정 — Rule MM(mom150 상위 5종). 2026-07-31 확정 승격.

    mom150 은 150거래일 이력이 필요한데 `panel_close_*.csv` 는 100여일뿐이라
    `mid_momentum_shadow.py` 가 유지하는 2년 패널의 산출물을 그대로 읽는다.
    (같은 값을 두 곳에서 계산하면 브리핑과 트래커가 어긋난다.)
    """
    p = os.path.join(REF, 'mid_momentum_shadow.csv')
    if not os.path.exists(p):
        return []
    row = None
    for r in csv.DictReader(open(p, encoding='utf-8')):
        if r.get('date') == T:
            row = r
    if not row or not row.get('mom150_codes'):
        return []
    codes = [c for c in row['mom150_codes'].split(';') if c]
    names = row.get('mom150_names', '').split(';')
    return [{'code': c, 'name': names[i] if i < len(names) else ''}
            for i, c in enumerate(codes)]


def trackb_safe(T):
    """오늘의 트랙 B(조합제 shadow) 픽. 브리핑 병기용(2026-08-03 사용자 요청).

    실매수 추천이 아니라 관측 병기용이며, 파라미터는 dual_score 에서 그대로 가져온다.
    실패해도 루틴을 세우지 않는다.
    """
    try:
        import trackb_today
        return trackb_today.picks(T)
    except Exception as e:                                   # noqa: BLE001
        return {'error': f'{type(e).__name__}: {e}'}


def mid_tenure_safe(D):
    """[6-2] 픽의 연속 추천일수. 실패해도 루틴 전체를 세우지 않는다(표시용 부가정보)."""
    try:
        import mid_tenure
        return [{'code': t['code'], 'name': t['name'], 'days': t['days'],
                 'since': t['since'], 'label': mid_tenure.label(t)}
                for t in mid_tenure.tenures(D)]
    except Exception as e:                                   # noqa: BLE001
        return {'error': f'{type(e).__name__}: {e}'}


def prev_trading_day(dates, t):
    """패널 날짜열에서 실행일 T 직전 거래일을 찾는다."""
    earlier = [d for d in dates if d < t]
    return earlier[-1] if earlier else dates[-1]


def latest_briefing():
    if not os.path.isdir(FABLE):
        return None
    c = sorted(f for f in os.listdir(FABLE)
               if f.startswith('데일리브리핑_') and f.endswith(('.docx', '.pdf')))
    return c[-1] if c else None


def tracker_last(path, col='date'):
    if not os.path.exists(path):
        return None
    rows = [r for r in csv.DictReader(
        l for l in open(path, encoding='utf-8') if not l.startswith('#'))]
    return rows[-1] if rows else None


def integrity(stage):
    """무결성 검증관 호출 (2026-07-30 신설). 별도 프로세스로 돌려 순환 import 를 피한다.
    rc: 0=정상 / 1=경고 / 2=오류."""
    r = run([sys.executable, os.path.join(HERE, 'integrity_check.py'), '--quiet'], timeout=120)
    tail = [l for l in r['out'].splitlines() if l.strip().startswith(('[무결성', '[경고]', '[오류]'))]
    print(f'--- 무결성 검증관({stage}) ---')
    for l in tail:
        print('  ' + l)
    return {'stage': stage, 'rc': r['rc'], 'lines': tail}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=datetime.now(KST).strftime('%Y%m%d'))
    ap.add_argument('--skip-collect', action='store_true')
    ap.add_argument('--skip-integrity', action='store_true',
                    help='무결성 검사 생략 — 복구 작업 중에만 쓴다')
    ap.add_argument('--skip-prep', action='store_true',
                    help='패널·코스피 자동 보충 생략')
    ap.add_argument('--prep-budget', type=float, default=30.0,
                    help='보충에 쓸 최대 초 — 소진되면 rc=3, 다시 실행하면 이어서 받는다')
    a = ap.parse_args()
    T = a.date

    # 사전 검사: 오염된 데이터로 채점하면 보고서에 틀린 수치가 실리고 그 수치가 다시
    # 방법 개선의 근거가 되어 오류가 증폭된다. rc=2 면 아무것도 건드리지 않고 중단한다.
    pre = None
    if not a.skip_integrity:
        pre = integrity('사전')
        if pre['rc'] == 2:
            # 2026-07-31 — 종전에는 여기서 그냥 멈춰 사용자가 손으로 고쳐야 했다. 알려진
            # 오염 유형(중복·절단·꼬리결손·날짜밀림·종가결손)은 자동 복구를 1회 시도한다.
            print('\n[무결성 오류] 자동 복구를 시도한다 — repair_data.py --fix')
            r = run([sys.executable, os.path.join(HERE, 'repair_data.py'), '--fix'],
                    timeout=300)
            print(r['out'][-1200:])
            pre = integrity('사전-복구후')
            state_repair = {'attempted': True, 'rc': r['rc']}
            if pre['rc'] == 2:
                print('\n[중단] 자동 복구 실패 — 수동 확인이 필요하다.')
                print('       진단: python3 references/scripts/repair_data.py')
                print('       재구축: python3 backtest/rebuild_ohlc_panel.py 32 (완료까지 반복)')
                return 2
            print('[복구 성공] 정상 상태로 진행한다.')
        else:
            state_repair = {'attempted': False}

    # 당일 스냅샷 (2026-07-31 신설) — 오늘 어떤 단계에서 오염돼도 '오늘 아침의 정상 상태'로
    # 되돌릴 수 있게, 어떤 쓰기보다 먼저 핵심 파일을 보관한다. repair_data.py 가 이걸 쓴다.
    if not a.skip_prep:
        import safe_io
        snapped = 0
        for rel in ('backtest/panel_ohlc_2y.csv', 'backtest/kospi_close.csv',
                    'references/close_bet_band_tracker.csv',
                    'references/combo_shadow_tracker.csv',
                    'references/stock15_oos_tracker.csv',
                    'references/mid_momentum_shadow.csv',
                    'references/rg_shadow.csv', 'references/cd_shadow.csv',
                    'references/lv_oos_tracker.csv',
                    'references/nhi_shadow.csv', 'references/eg_liq_shadow.csv',
                    'references/mlv_mid_shadow.csv', 'references/ibs_shadow.csv',
                    'references/credit_u_shadow.csv', 'references/foreign_avoid_shadow.csv',
                    'references/breadth_shadow.csv'):
            p = os.path.join(LOOP, rel)
            if os.path.exists(p) and safe_io.snapshot(p, tag=T):
                snapped += 1
        print(f'--- 당일 스냅샷 {snapped}개 보관 (tag={T}) ---')

    # 데이터 자동 보충 (2026-07-31 신설) — 패널 정체·코스피 종가 결손으로 3회 연속
    # (7/29·7/30·7/31) 수동 개입이 필요했다. 예산을 넘기면 rc=3 으로 알리고, 다시
    # 호출하면 부분 결과에서 이어받는다(extend_panel.py 가 멱등).
    prep = None
    if not a.skip_prep:
        print('--- 데이터 자동 보충 ---')
        prep = ensure_data.ensure(T, a.prep_budget)
        if not prep['done']:
            print(f'\n[재개 필요] 보충 예산({a.prep_budget:.0f}초) 소진 — 같은 명령을 다시 실행하십시오.')
            return 3

    panel_path, px, nm, dates = load_panel()
    D = prev_trading_day(dates, T)
    picks = compute_picks(px, nm, dates, D)
    state = {'run_at': datetime.now(KST).isoformat(), 'T': T, 'D': D,
             'panel': os.path.basename(panel_path), 'panel_last': dates[-1],
             'prep': prep, 'auto_repair': locals().get('state_repair')}

    print(f'=== 아침 통합 루프 — 실행일 T={T} · 채점 대상일 D={D} ===')
    print(f'패널: {state["panel"]} (마지막 거래일 {dates[-1]})')

    # ---------- 0단계 : 관심 신호 ----------
    att = {'skipped': a.skip_collect}
    if not a.skip_collect:
        # 0-A 채점용
        raw_d = os.path.join(REF, f'raw_{D}.csv')
        att['A_existed'] = os.path.exists(raw_d)
        if not att['A_existed']:
            r = run([sys.executable, os.path.join(HERE, 'collect_attention.py'),
                     '--date', D, '--post-hoc'])
            att['A_collect'] = {'rc': r['rc'], 'post_hoc': True}
            print(f'[0-A] {D} 사후수집 rc={r["rc"]}')
            if r['rc'] == 2:
                att['A_error'] = '네이버 키 없음'
        else:
            print(f'[0-A] {D} 신호 행 존재 — 재수집 생략(멱등)')
        # 0-B 오늘
        r = run([sys.executable, os.path.join(HERE, 'collect_attention.py'), '--date', T])
        att['B_collect'] = {'rc': r['rc']}
        att['B_ok'] = (r['rc'] == 0 and os.path.exists(os.path.join(REF, f'raw_{T}.csv')))
        print(f'[0-B] {T} 수집 rc={r["rc"]} → {"성공" if att["B_ok"] else "결손"}')
        if r['rc'] == 2:
            att['B_error'] = '네이버 키 없음 — loop 폴더에 naver_clientid.txt/naver_secret.txt 필요'
            print('       ' + att['B_error'])
        # 픽 기록 (v2 / shadow / ns2) — raw 가 생긴 날짜에 대해서만
        for day in [d for d in (D, T) if os.path.exists(os.path.join(REF, f'raw_{d}.csv'))]:
            for script in ('attention_pilot_v2.py', 'attention_pilot_shadow.py',
                           'attention_pilot_shadow_ns2.py'):
                rr = run([sys.executable, os.path.join(HERE, script), 'record',
                          '--date', day, '--raw', os.path.join(REF, f'raw_{day}.csv')])
                att.setdefault('record', []).append(
                    {'date': day, 'script': script, 'rc': rr['rc']})
    else:
        print('[0단계] --skip-collect 지정 — 관심 신호 수집 생략')
    # DART 주간 스캔 필요 여부 (매주 첫 거래일 1회, 기록 전용)
    r = run([sys.executable, os.path.join(HERE, 'dart_scan_record.py'), '--due',
             '--week-start', T])
    try:
        att['dart'] = json.loads(r['out'].strip().splitlines()[-1])
    except Exception:
        att['dart'] = {'due': None, 'err': r['err'][:200]}
    if att['dart'].get('due'):
        print(f'[0-D] DART 주간 스캔 필요 — 워치리스트 {att["dart"].get("n_companies")}종목 '
              f'(에이전트가 opendart MCP로 조회 후 dart_scan_record.py 로 기록)')
    else:
        print('[0-D] DART 주간 스캔 — 이번 주 기록 있음(또는 판정 불가), 생략')
    state['attention'] = att

    # ---------- 1단계 : 채점 대상 판정 ----------
    holdings = os.path.join(LOOP, 'current-holdings.md')
    htxt = open(holdings, encoding='utf-8').read() if os.path.exists(holdings) else ''
    combo_last = tracker_last(os.path.join(REF, 'combo_shadow_tracker.csv'))
    stock_last = tracker_last(os.path.join(REF, 'stock15_oos_tracker.csv'))
    cb_last = tracker_last(os.path.join(REF, 'close_bet_band_tracker.csv'))

    already = combo_last and combo_last.get('date', '') >= D
    d_close_ready = D in dates
    scoring = {'latest_briefing': latest_briefing(),
               'trackB_last': combo_last.get('date') if combo_last else None,
               'trackC_last': stock_last.get('date') if stock_last else None,
               'ruleCB_last': cb_last.get('date') if cb_last else None,
               'D_close_available': d_close_ready}
    if already:
        scoring['new_target'] = False
        scoring['reason'] = f'{D} 은 이미 채점 완료 — 신규 대상 없음'
    elif not d_close_ready:
        scoring['new_target'] = False
        scoring['reason'] = f'{D} 종가 미확보 — 채점 불가'
    else:
        scoring['new_target'] = True
        scoring['reason'] = f'{D} 신규 채점 대상 있음'
    print(f'[1단계] {scoring["reason"]}')

    # ---------- 2단계 : 채점 ----------
    # ★ 룩어헤드 주의 (2026-08-24 실측) — 아래는 current-holdings.md 의 **첫** picks 줄을
    #   D 의 채점 대상으로 쓴다. 즉 "오늘 블록을 등록하기 전에 러너를 돌린다"는 순서에
    #   암묵적으로 의존한다. 2026-08-24 실행에서 무결성 오류(신규 코드 0072R0 미등록)를
    #   고치려고 오늘 블록을 먼저 등록한 뒤 러너를 재실행했더니, **오늘 픽이 어제 채점에
    #   들어가** 트랙 A 가 -0.257%p 로 잘못 나왔다(정정값 -5.804%p).
    #   재현 조건: current-holdings.md 최상단 블록의 날짜 > D.
    #   ▶ 2026-08-28 수정 — 같은 사고가 재발(오늘 블록을 먼저 등록한 뒤 재실행)해서 아래처럼
    #   블록 날짜 헤더('## YYYY-MM-DD ...')를 함께 읽어 **날짜 ≤ D 인 첫 블록**의 picks 만 쓴다.
    #   이제 등록 순서와 무관하게 안전하다.
    if scoring['new_target']:
        #   ▶ 2026-09-22 수정 — 'picks' 와 코드가 **줄바꿈으로 갈라진** 블록에서 추출기가
        #   그 줄을 건너뛰고 아래의 '종전 mom20 순서 picks5 는 `...`' 대조군 줄을 잡아,
        #   D=20260921 트랙 A 채점이 MOM 대조군으로 나갔다(LV -1.587% 가 정답, MOM 은 별개).
        #   재현 조건: current-holdings.md 등록 줄이 "... picks" 로 끝나고 코드가 다음 줄.
        #   아래처럼 'picks' 줄 직후 한 줄까지 이어서 본다(pending). 등록 줄이 블록 최상단이라
        #   대조군 줄보다 먼저 잡히므로 한 줄/두 줄 서식 모두 안전하다.
        picks_d = None
        blk_ok = False
        pending = False
        for line in htxt.splitlines():
            if line.startswith('## '):
                m = re.search(r'(\d{4})-(\d{2})-(\d{2})', line)
                blk_ok = bool(m) and (m.group(1) + m.group(2) + m.group(3)) <= D
                pending = False
                continue
            if not blk_ok:
                continue
            has_picks = 'picks' in line
            if has_picks or pending:
                seg = [s for s in line.split('`') if ',' in s and s.replace(',', '').isalnum()]
                if seg:
                    picks_d = seg[0].strip()
                    break
                pending = has_picks
            else:
                pending = False
        scoring['picks_scored'] = picks_d
        if picks_d:
            r = run([sys.executable, os.path.join(HERE, 'dual_score.py'), D,
                     '--picks', picks_d])
            scoring['dual_score'] = {'rc': r['rc'], 'out': r['out']}
            print(r['out'][-1500:])
        else:
            scoring['dual_score'] = {'rc': -1, 'err': 'current-holdings.md 에서 picks 추출 실패'}
        # Rule RG shadow (2026-07-31 신설) — 리스크온 게이트 관측. 실추천 무영향.
        if picks_d:
            r = run([sys.executable, os.path.join(HERE, 'rg_shadow.py'),
                     '--record', D, '--picks', picks_d, '--report'], timeout=180)
            scoring['rg_shadow'] = {'rc': r['rc'], 'out': r['out'][-600:]}
            print(r['out'][-600:])
        # Rule CD shadow (2026-07-31 신설) — 캔들 꼬리 신호 관측. 실추천 무영향.
        r = run([sys.executable, os.path.join(HERE, 'cd_shadow.py'),
                 '--record', D, '--report'], timeout=180)
        scoring['cd_shadow'] = {'rc': r['rc'], 'out': r['out'][-600:]}
        print(r['out'][-600:])
        # 트랙 C(Rule SU) — D 하나만 채점하면 '익일 종가 미확보'로 건너뛴 날이 영구히
        # 빈다(2026-08-06 확인: 20260804 행이 그렇게 유실됐다). D 를 포함해 직전
        # 몇 거래일을 함께 돌려 밀린 날짜를 회수한다. 기록은 멱등이라 중복되지 않는다.
        sc_out = []
        for sd in trading_days_upto(D, 4):
            r = run([sys.executable, os.path.join(HERE, 'stock15_picks.py'), '--score', sd])
            sc_out.append(f'--- {sd} (rc={r["rc"]})\n' + r['out'][-500:])
        scoring['stock15'] = {'rc': 0, 'out': '\n'.join(sc_out)[-2000:]}
        print(sc_out[-1][-800:])
    state['scoring'] = scoring

    # ---------- 0-D 중기 모멘텀 shadow 트래커 (2026-07-29 신설) ----------
    # 현행 [6-2] 낙폭과대룰 vs 신규 mom150 을 매일 병행 기록·채점한다.
    # 채점 대상 유무와 무관하게 매 실행 수행 — 표본이 끊기면 20영업일 판정이 밀린다.
    # 실패해도 전체를 중단시키지 않는다(shadow는 관측 전용, 실추천에 영향 없음).
    ms = os.path.join(HERE, 'mid_momentum_shadow.py')
    r = run([sys.executable, ms, '--update', '--budget', '240'], timeout=420)
    upd = {'rc': r['rc'], 'out': r['out'][-400:]}
    r = run([sys.executable, ms, '--record'], timeout=120)
    rec = {'rc': r['rc'], 'out': r['out'][-600:]}
    r = run([sys.executable, ms, '--score'], timeout=120)
    sc = {'rc': r['rc'], 'out': r['out'][-300:]}
    r = run([sys.executable, ms, '--report'], timeout=120)
    state['mid_shadow'] = {'update': upd, 'record': rec, 'score': sc,
                           'report': r['out'][-2500:], 'rc': r['rc']}
    print('[0-D] 중기 모멘텀 shadow')
    print(rec['out'])
    print(r['out'][-1200:])

    # Rule TV shadow (2026-08-01 신설) — mom150 후보에 거래대금 확인 필터.
    # 패널은 위 mid_momentum_shadow --update 가 이미 갱신했으므로 재조회하지 않는다.
    tv = os.path.join(HERE, 'tv_shadow.py')
    r = run([sys.executable, tv, '--record', '--score', '--report'], timeout=180)
    state['tv_shadow'] = {'rc': r['rc'], 'out': r['out'][-600:]}
    print(r['out'][-600:])

    # Rule DR·IL shadow (2026-08-01 신설) — 낙폭 국면 선정축 전환 · 인버스 센티먼트 게이트.
    # 실패해도 루틴을 중단시키지 않는다(shadow 전용).
    rs = os.path.join(HERE, 'regime_shadow.py')
    r = run([sys.executable, rs, '--record', '--score', '--report'], timeout=180)
    state['regime_shadow'] = {'rc': r['rc'], 'out': r['out'][-800:]}
    print(r['out'][-800:])

    # ---------- 오늘 브리핑용 선정 ----------
    r = run([sys.executable, os.path.join(HERE, 'stock15_picks.py'), '--date', picks['D']])
    su_line = [l for l in r['out'].splitlines() if l.startswith('단기 추천 5종')]
    state['picks'] = {
        'D_for_selection': picks['D'], 'D20': picks['d20'],
        'universe_n': picks['universe_n'],
        'ruleH_excluded': [{'code': x['code'], 'name': x['name'],
                            'r1': round(x['r1'] * 100, 2), 'r3': round(x['r3'] * 100, 2)}
                           for x in picks['ruleH_excluded']],
        'short_etf10': [{'code': x['code'], 'name': x['name'], 'close': x['close'],
                         'mom20': round(x['mom20'] * 100, 2), 'r1': round(x['r1'] * 100, 2),
                         'r3': round(x['r3'] * 100, 2),
                         'sigma20': (round(x['sigma20'], 3) if x.get('sigma20') is not None else None)}
                        for x in picks['short10']],
        'picks5': ','.join(x['code'] for x in picks['short10'][:5]),
        # Rule LV(v2.9) 적용 여부와, 비교용 종전 mom20 순서. lv_oos.py 가 이 둘을 읽어
        # LV−MOM 페어를 매일 누적한다(OOS 판정용).
        'lv': {'applied': picks['lv_applied'], 'pool': LV_POOL, 'k': LV_K,
               'pool_scored_n': picks['lv_pool_n'],
               'mom_picks5': ','.join(picks['mom_short10'][:5])},
        # [6-2] 중기 ETF — 2026-07-31 Rule MM(mom150) 확정 승격으로 선정축 교체.
        # 종전 낙폭과대룰은 430일 표본에서 매매일 평균 -3.565%p/20일이었고 5종을 채우는 날이
        # 8일 중 1일뿐이었다. 종전 후보는 관측용으로 mid_legacy_pool 에 남긴다.
        # 2026-08-03 시정: shadow 는 '선정 기준일 D' 로 행을 기록하므로 T 로 찾으면 항상 공집합이다
        # (실측 — 2026-08-03 실행에서 [6-2] 중기 후보가 0종으로 비었다).
        'mid_candidates': mom150_picks(picks['D']),
        # 연속 추천일수 — 청산 트리거가 아니라 표시용(2026-08-03 사용자 요청).
        # 완결 스펠 중앙값이 3거래일뿐이라 오래 남은 픽은 그 자체로 드문 신호다.
        'mid_tenure': mid_tenure_safe(picks['D']),
        # 트랙 B(조합제 shadow) 오늘 픽 — 브리핑 [6-1b] 병기용. 실매수 대상이 아니다.
        'trackb_today': trackb_safe(T),
        'mid_legacy_pool': [{'code': x['code'], 'name': x['name'], 'close': x['close'],
                             'mom20': round(x['mom20'] * 100, 2),
                             'mom60': round(x['mom60'] * 100, 2),
                             'r3': round(x['r3'] * 100, 2), 'r5': round(x['r5'] * 100, 2),
                             'r10': round(x['r10'] * 100, 2)} for x in picks['mid_pool']],
        'fall5': [{'code': x['code'], 'name': x['name'], 'close': x['close'],
                   'mom20': round(x['mom20'] * 100, 2), 'r1': round(x['r1'] * 100, 2)}
                  for x in picks['fall5']],
        'stock15_su': su_line[0] if su_line else r['out'][-400:],
    }

    # ---------- 0-E Rule CB OOS 트래커 (2026-08-06 신설 — 러너 미연결 결함 시정) ----------
    # CLAUDE.md 2026-07-26·3차 #1 은 "매 루프 0-A 에서 전일 Rule CB 결과를 1행 누적"을
    # 의무로 정했으나 close_bet_record 호출이 러너 어디에도 없었다(2026-08-06 확인).
    # 그 결과 트래커가 2026-08-03 에서 멈춰 8/04·8/05 가 통째로 빠졌다.
    # 여기서 (1) 오늘 중기 후보를 picks_mid_etf.json 에 등록하고 (2) --all 로 밀린 날짜를
    # 한꺼번에 채운다. 둘 다 멱등이라 재실행해도 중복되지 않는다.
    try:
        midp = os.path.join(LOOP, 'backtest', 'picks_mid_etf.json')
        reg = json.load(open(midp, encoding='utf-8')) if os.path.exists(midp) else {}
        Ds = picks['D']
        iso = f'{Ds[:4]}-{Ds[4:6]}-{Ds[6:]}'
        mc = state['picks']['mid_candidates'] or []
        if iso not in reg and mc:
            reg[iso] = {'src': f'morning_state_{T}.json',
                        'codes': [x['code'] for x in mc],
                        'names': [x.get('name', '') for x in mc]}
            json.dump(reg, open(midp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        r = run([sys.executable, os.path.join(HERE, 'close_bet_record.py'),
                 '--all', '--method', 'mom150'], timeout=180)
        state['close_bet'] = {'rc': r['rc'], 'out': r['out'][-600:]}
        print('\n[0-E] Rule CB 트래커\n' + r['out'][-600:])
    except Exception as e:                                    # noqa: BLE001
        state['close_bet'] = {'rc': -1, 'err': str(e)[:300]}
        print(f'\n[0-E] Rule CB 기록 실패(무시하고 진행): {e}', file=sys.stderr)

    print(f'\n[선정] 유니버스 {picks["universe_n"]}종 · Rule H 제외 {len(picks["ruleH_excluded"])}종')
    for k, x in enumerate(picks['short10'][:5], 1):
        print(f'  단기{k} {x["code"]} {x["name"][:30]:30s} mom20 {x["mom20"]*100:+6.2f}%')
    print(f'  picks5 = {state["picks"]["picks5"]}')
    if picks['lv_applied']:
        print(f'  Rule LV(v2.9) 적용 — pool{LV_POOL} 중 σ{LV_K} 하위 5종. '
              f'종전 mom20 순서 picks5 = {",".join(picks["mom_short10"][:5])}')
    else:
        print(f'  [경고] Rule LV 미적용 — σ 산출 가능 종목 {picks["lv_pool_n"]}종(<5). '
              f'mom20 순서로 폴백했다.')

    # Rule LV OOS 트래커 (2026-08-22 신설) — 승격 근거가 in-sample 이므로 OOS 를 새로 센다.
    # 실패해도 루틴을 중단시키지 않는다(기록 전용, 오늘 추천에 영향 없음).
    # [알려진 결함 2026-10-14] 이 시점엔 오늘 morning_state 가 아직 저장되지 않아 lv_oos --record 가
    # '직전' state 의 D 를 기록한다(하루 지연). 직전 실행의 D 가 같으면(휴장 뒤 등) 그 선정일은 영구 결손.
    # 재현: 10/12 러너 D=20261008 → 20261012 선정 페어 없음. 수정안: state 저장 후 호출 또는 picks 인자 전달(표본 정의 변경 — 사용자 확인 후).
    r = run([sys.executable, os.path.join(HERE, 'lv_oos.py'),
             '--record', '--score', '--report'], timeout=180)
    state['lv_oos'] = {'rc': r['rc'], 'out': r['out'][-800:]}
    print(r['out'][-800:])

    # 0-F2 — Rule NHI shadow (2026-09-17 사용자 승인). 신고가근접×KODEX200 MA20 게이트 위에서 같은 LV 선정기를
    # 돌려 LV 와 페어로 기록한다. 선정·브리핑에 반영하지 않는다. 실패해도 루틴을 중단시키지 않는다.
    r = run([sys.executable, os.path.join(HERE, 'nhi_shadow.py'),
             '--record', '--score', '--report'], timeout=180)
    state['nhi_shadow'] = {'rc': r['rc'], 'out': r['out'][-800:]}
    print(r['out'][-800:])

    # 0-F3 — Rule MLV shadow (2026-09-26 사용자 승인). [6-3] 중기 mom150 pool30 → σ20 하위 5종을 20거래일 트랜치로
    # mom150 과 페어 기록한다. 선정·브리핑·Rule CB·Rule MM 에 반영하지 않는다. 실패해도 루틴을 중단시키지 않는다.
    r = run([sys.executable, os.path.join(HERE, 'mlv_mid_shadow.py'),
             '--record', '--score', '--report'], timeout=180)
    state['mlv_mid_shadow'] = {'rc': r['rc'], 'out': r['out'][-800:]}
    print(r['out'][-800:])

    # 0-F4 — Rule IBS shadow (2026-10-21 사용자 승인). KODEX200 IBS<0.2 진입·>0.8 청산 타이밍을 보유와 페어로
    # 기록한다(위험 축). 선정·브리핑·Rule CB·트랙 A~D 에 반영하지 않는다. 실패해도 루틴을 중단시키지 않는다.
    r = run([sys.executable, os.path.join(HERE, 'ibs_shadow.py'),
             '--record', '--score', '--report'], timeout=120)
    state['ibs_shadow'] = {'rc': r['rc'], 'out': r['out'][-600:]}
    print(r['out'][-600:])

    # 0-F5 — Rule CRU shadow (2026-10-22 사용자 승인). 신용잔고 상대수준(z250, D−2) U자 노출 — 상·하위 20% 100% / 중간 50% —
    # 를 KODEX200 보유와 페어로 기록한다(위험 축). 선정·브리핑·Rule LV·트랙 A~D 에 반영하지 않는다. 실패해도 루틴을 중단시키지 않는다.
    r = run([sys.executable, os.path.join(HERE, 'credit_u_shadow.py'),
             '--record', '--score', '--report'], timeout=120)
    state['credit_u_shadow'] = {'rc': r['rc'], 'out': r['out'][-600:]}
    print(r['out'][-600:])

    # 0-F6 — Rule FIA shadow (2026-10-22 사용자 승인). 전일 외국인 최종 순매수가 확장창 하위 20%면 KODEX200 을
    # 다음 날 시가 매도·종가 재매수(장중 회피)한 것으로 보유와 페어 기록한다. 선정·브리핑·트랙 A~D·Rule LV 미반영. 실패해도 계속.
    r = run([sys.executable, os.path.join(HERE, 'foreign_avoid_shadow.py'),
             '--record', '--score', '--report'], timeout=150)
    state['foreign_avoid_shadow'] = {'rc': r['rc'], 'out': r['out'][-600:]}
    print(r['out'][-600:])

    # 0-F7 — Rule BRD shadow (2026-10-27 사용자 승인). 시장 폭(유동 개별주 중 종가>MA200 비율) ≥ 50% 면 KODEX200 보유 —
    # KRX D+1 공개라 1일 지연(D 신호 → D+1→D+2 수익)으로 보유와 페어 기록한다(위험 축). 종가 이력은 KRX 조회로 멱등 보충.
    # 선정·브리핑·Rule CB·트랙 A~D 에 반영하지 않는다. 실패해도 루틴을 중단시키지 않는다.
    r = run([sys.executable, os.path.join(HERE, 'breadth_shadow.py'),
             '--fetch', '--record', '--score', '--report', '--budget', '90'], timeout=150)
    state['breadth_shadow'] = {'rc': r['rc'], 'out': r['out'][-600:]}
    print(r['out'][-600:])

    # 0-G — 트랙 D(Rule EG 매수·매도 타점) 스캔 (2026-08-31 신설).
    # 트랙 A~C 선정과 무관한 별도 타점 목록이다. 실패해도 루틴을 중단시키지 않는다.
    # 2026-09-11: 신뢰도 상세·보유 흔들림·기준선 표가 붙어 출력이 길어졌다 — 종전 2,500자 절단이면
    # 맨 앞의 매수 표가 잘리므로 전체(최대 20,000자)를 보존한다. 브리핑 9절은 이 out 을 그대로 옮긴다.
    r = run([sys.executable, os.path.join(HERE, 'eg_picks.py'), '--record'], timeout=180, keep=20000)
    state['eg_track'] = {'rc': r['rc'], 'out': r['out']}
    print(r['out'])

    # 0-G2 — Rule EG-LIQ shadow (2026-09-17 사용자 승인). eg_track_tracker 의 신호를 거래대금 상위 100 안/밖으로
    # 나눠 20거래일 성과를 기록한다. 트랙 D 선정·표시·청산은 바꾸지 않는다. 실패해도 루틴을 중단시키지 않는다.
    r = run([sys.executable, os.path.join(HERE, 'eg_liq_shadow.py')], timeout=180)
    state['eg_liq_shadow'] = {'rc': r['rc'], 'out': r['out'][-800:]}
    print(r['out'][-800:])

    # 0-H — 매수 금지 목록(Rule SB) — **2026-09-17 사용자 지시로 폐지**(브리핑 [8-3] 삭제 · shadow 종결).
    # 종전 호출: sell_ban_list.py --record --score --catchup --flags ... → state['sell_ban'].
    # 트래커 references/sell_ban_tracker.csv 는 보관만 한다. 되살리려면 사용자 승인 후 새로 등록.
    state['sell_ban'] = {'rc': None, 'out': '폐지(2026-09-17)', 'data': None}

    if su_line:
        print(f'  {su_line[0]}')

    # 0-C — 주요 뉴스 5선 후보 (2026-07-28 신설). picks 확정 후에 돌려야 '추천테마' 슬롯이 채워진다.
    out = os.path.join(HERE, f'morning_state_{T}.json')
    json.dump(state, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    rn = run([sys.executable, os.path.join(HERE, 'news_top5.py'), '--date', T])
    n5p = os.path.join(HERE, f'news5_{T}.json')
    if rn['rc'] == 0 and os.path.exists(n5p):
        state['news5'] = json.load(open(n5p, encoding='utf-8'))
        print('\n[0-C] 주요 뉴스 5선 후보 생성 — ' +
              ' / '.join(f"{x['bucket']}:{x['title'][:24]}" for x in state['news5']['items']))
    else:
        state['news5'] = {'error': rn['out'][-300:] or 'news_top5.py 실패'}
        print('\n[0-C] 뉴스 5선 생성 실패 — 웹 검색으로 보강하고 보고서에 결손 명시',
              file=sys.stderr)
    # 사후 검사: 이번 실행 중 재실행·수동 개입으로 중복이 생겼는지 본다.
    # 2026-07-30 오염이 정확히 이 경로로 발생했으므로 사전 검사만으로는 부족하다.
    if not a.skip_integrity:
        state['integrity'] = {'pre': pre, 'post': integrity('사후')}
        if state['integrity']['post']['rc'] == 2:
            print('\n[경고] 루틴 실행 중 무결성 오류가 발생했습니다. '
                  '보고서·브리핑을 만들기 전에 반드시 해결하십시오.')
    json.dump(state, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n=== state → {out} ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
