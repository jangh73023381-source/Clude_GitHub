#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dual_score.py — 통합 루프 2단계 이중 채점 (2026-07-26 신설)

트랙 A(확정방법, 실적용) = 데일리브리핑 단기 ETF 5종
트랙 B(조합제 SEARCH-LED, shadow) = 검색 랭킹 + mom20 하방필터 + 악재감성 배제

1차 지표: 코스피 지수(^KS11) 대비 초과수익 (픽5 동일가중·1일 보유·무비용 — 2026-08-14 사용자 지시)
병기    : KODEX200 대비 초과수익
보조    : 전체 ETF 유니버스 상위10% 이진 적중 (트랙 A)
참고    : 15섹터 등가중 기준선 (트랙 B의 실질 기준선)

사용:
  python3 dual_score.py 20260724 --picks 498410,091170,484880,466940,279530
  python3 dual_score.py 20260724 --picks ... --panel ../../backtest/panel_close_0724.csv
"""
import argparse, csv, math, os, sys
from collections import defaultdict

H = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(H, '..'))
ROOT = os.path.abspath(os.path.join(REF, '..'))
COST = 0.0  # 2026-08-14 사용자 지시 — 왕복비용 없음(무료 수수료·ETF 거래세 면제, 겹치는 종목은 계속 보유하고 교체분만 거래). 종전값 0.0010(왕복 10bp)
MOM_CUT, SENT_CUT, NPICK = 10, -0.15, 5      # 트랙 B 동결 파라미터 (20영업일 판정 전 변경 금지)


def newest_panel():
    d = os.path.join(ROOT, 'backtest')
    c = sorted(f for f in os.listdir(d) if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(d, c[-1]) if c else None


from universe_filters import is_cash, is_spot  # noqa: E402,F401  (제외 키워드 공용 상수)


# v2.7 (2026-07-29) — 채점 유니버스를 선정 유니버스와 정합화한다.
# 배경: morning_run.py 의 '선정' 유니버스는 현금성(머니마켓·CD금리·KOFR·초단기채·국고채·통안)을
# 제외하는데, 여기 '채점' 유니버스는 제외하지 않고 있었다. 하락일에는 상위10% 슬롯의 평균 35.8%,
# 2026-07-28 같은 폭락일에는 70.6%(17슬롯 중 12)가 현금성으로 채워지므로 이진 목표(5/5)가
# 구조적으로 달성 불가능했다(상승일에는 0%라 문제가 드러나지 않았다).
# 정합화 후 값을 1차로, 종전 값을 괄호에 병기해 과거 이력과의 연속성을 유지한다.
# 키워드 목록은 universe_filters.py 로 통일했다(2026-07-30 사용자 지시 정렬 작업).


def n_star(xs):
    """판정에 필요한 표본 수 (judge_ready.py 와 동일 식, 2026-07-31 규정).

    N* = (1.28 × sd/|평균|)² · 하한 8 · 상한 60. 부트스트랩 검증에서 실현 정확도
    89.9~91.1%(`backtest/bt_window_length.py`). 고정 20영업일 규정은 폐지됐다.
    """
    if len(xs) < 3:
        return None
    m = sum(xs) / len(xs)
    if not m:
        return 60
    sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    return max(8, min(60, math.ceil((1.28 * sd / abs(m)) ** 2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('date', help='채점일 YYYYMMDD')
    ap.add_argument('--picks', required=True, help='트랙 A 추천 5종 코드(콤마)')
    ap.add_argument('--panel', default='')
    ap.add_argument('--no-append', action='store_true', help='combo_shadow_tracker.csv에 기록하지 않음')
    a = ap.parse_args()

    panel = a.panel or newest_panel()
    px, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(panel, encoding='utf-8')):
        try: px[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError): pass
        nm[r['code']] = r['name']
    ks = {r['date']: float(r['close'])
          for r in csv.DictReader(open(os.path.join(ROOT, 'backtest', 'kospi_close.csv'), encoding='utf-8'))}
    dates = sorted(ks)
    D = a.date
    if D not in dates: sys.exit('코스피 종가에 %s 없음 — backtest/kospi_close.csv를 먼저 갱신하세요' % D)
    P = dates[dates.index(D) - 1]

    def ret(c):
        x, y = px.get(c, {}).get(P), px.get(c, {}).get(D)
        return (y / x - 1.0) if (x and y) else None
    def mom20(c):
        j = dates.index(P)
        if j < 20: return None
        x, y = px.get(c, {}).get(dates[j - 20]), px.get(c, {}).get(P)
        return (y / x - 1.0) if (x and y) else None

    kr = ks[D] / ks[P] - 1.0
    kd = ret('069500')
    print('채점일 %s (전일 %s) | 코스피 %+.2f%% · KODEX200 %s' %
          (D, P, kr * 100, ('%+.2f%%' % (kd * 100)) if kd is not None else 'n/a'))
    print('패널: %s\n' % os.path.basename(panel))

    # ---------- 트랙 A ----------
    picks = [c.strip().zfill(6) for c in a.picks.split(',') if c.strip()]
    print('=' * 78)
    print('[트랙 A] 확정방법 (mom20+RuleH) — 실제 추천')
    rs = []
    for c in picks:
        r = ret(c)
        if r is None: print('  %s %-24s 데이터 없음' % (c, nm.get(c, '')[:24])); continue
        rs.append(r); print('  %s %-24s %10s → %10s  %+.2f%%' %
                            (c, nm.get(c, '')[:24], format(int(px[c][P]), ','), format(int(px[c][D]), ','), r * 100))
    pa = sum(rs) / len(rs) - COST
    print('  픽5 동일가중(비용후) %+.3f%%  |  코스피 대비 %+.3f%%p  |  KODEX200 대비 %s' %
          (pa * 100, (pa - kr) * 100, ('%+.3f%%p' % ((pa - kd) * 100)) if kd is not None else 'n/a'))

    def binary(exclude_cash):
        u = []
        for c in px:
            x, y = px[c].get(P), px[c].get(D)
            # 최소가격 필터 폐지(2026-07-30) — 선정 유니버스와 정합을 맞춘다(v2.7 원칙).
            if not x or not y or not is_spot(nm.get(c, '')): continue
            if '숏' in (nm.get(c, '') or '').replace(' ', ''): continue
            if exclude_cash and is_cash(nm.get(c, '')): continue
            u.append((c, y / x - 1.0))
        u.sort(key=lambda t: -t[1])
        k = max(1, math.ceil(len(u) * 0.1))
        rk = {c: i + 1 for i, (c, _) in enumerate(u)}
        return u, k, rk, sum(1 for c in picks if rk.get(c, 10 ** 9) <= k)

    uni, cut, rank, hit = binary(True)          # v2.7 정합 유니버스(현금성 제외)
    o_uni, o_cut, o_rank, o_hit = binary(False)  # 종전(현금성 포함) — 과거 이력 비교용
    n_cash = len(o_uni) - len(uni)
    cash_in_top = sum(1 for c, _ in o_uni[:o_cut] if is_cash(nm.get(c, '')))
    print('  보조 이진(v2.7 현금성 제외): %d/5 적중 (유니버스 %d종, 컷오프 상위%d위 %+.2f%%)  순위 %s' %
          (hit, len(uni), cut, uni[cut - 1][1] * 100, ', '.join(str(rank.get(c, '-')) for c in picks)))
    print('    (종전 현금성 포함 기준: %d/5, 유니버스 %d종, 컷오프 상위%d위 %+.2f%%, 순위 %s)' %
          (o_hit, len(o_uni), o_cut, o_uni[o_cut - 1][1] * 100,
           ', '.join(str(o_rank.get(c, '-')) for c in picks)))
    print('    현금성 %d종 제외 · 종전 상위10%% 슬롯 중 현금성 %d/%d (%.1f%%)'
          % (n_cash, cash_in_top, o_cut, 100.0 * cash_in_top / o_cut))

    # ---------- 트랙 B ----------
    print('\n' + '=' * 78)
    print('[트랙 B] 조합제 SEARCH-LED — shadow (실제 추천 아님, 파라미터 동결)')
    sig = [r for r in csv.DictReader(open(os.path.join(REF, 'attention_shadow_picks.csv'), encoding='utf-8'))
           if r['date'] == D]
    if not sig:
        print('  ⚠ %s 관심 신호 행 없음 — 0단계(신호 수집)를 먼저 수행해야 채점 가능합니다.' % D)
        print('    (통합 루프 런북 references/integrated-loop-runbook.md 0단계 참조)')
        return
    mr = sorted(((r['code'], mom20(r['code']) if mom20(r['code']) is not None else -9) for r in sig),
                key=lambda t: -t[1])
    trk = {c: i + 1 for i, (c, _) in enumerate(mr)}
    bp, ex_m, ex_s = [], [], []
    for r in sorted(sig, key=lambda r: -float(r['z_search'])):
        if trk.get(r['code'], 99) > MOM_CUT: ex_m.append(r['theme']); continue
        if float(r['sent']) < SENT_CUT: ex_s.append(r['theme']); continue
        bp.append(r)
        if len(bp) == NPICK: break
    brs = [ret(r['code']) for r in bp]; brs = [x for x in brs if x is not None]
    pb = sum(brs) / len(brs) - COST
    for r in bp:
        print('  %s %-22s (%s) 검색z %+5.2f 감성z %+5.2f  %+.2f%%' %
              (r['code'], r['etf'][:22], r['theme'], float(r['z_search']), float(r['sent']),
               (ret(r['code']) or 0) * 100))
    print('  배제 — mom20 하방: %s / 악재감성: %s' % (', '.join(ex_m) or '없음', ', '.join(ex_s) or '없음'))
    print('  픽5 동일가중(비용후) %+.3f%%  |  코스피 대비 %+.3f%%p  |  KODEX200 대비 %s' %
          (pb * 100, (pb - kr) * 100, ('%+.3f%%p' % ((pb - kd) * 100)) if kd is not None else 'n/a'))
    sec = [ret(r['code']) for r in sig]; sec = [x for x in sec if x is not None]
    ps = sum(sec) / len(sec) - COST
    print('  (기준선) 15섹터 등가중 %+.3f%% | 코스피 대비 %+.3f%%p → 조합제 순수 선택력 %+.3f%%p' %
          (ps * 100, (ps - kr) * 100, (pb - ps) * 100))

    # ---------- 병기 요약 + 누적 ----------
    print('\n' + '=' * 78)
    print('[병기 요약] %s' % D)
    print('  %-28s %12s %12s' % ('', '코스피 대비', 'KODEX200 대비'))
    for lbl, v in (('트랙 A 확정방법(실적용)', pa), ('트랙 B 조합제(shadow)', pb), ('15섹터 등가중(기준선)', ps)):
        print('  %-28s %+11.3f%%p %+11.3f%%p' % (lbl, (v - kr) * 100, ((v - kd) * 100) if kd is not None else 0))

    if not a.no_append:
        os.system('cd %s && python3 %s %s > /dev/null 2>&1' %
                  (ROOT, os.path.join(H, 'combo_shadow_tracker.py'), D))
    trkf = os.path.join(REF, 'combo_shadow_tracker.csv')
    if os.path.exists(trkf):
        rows = list(csv.DictReader(open(trkf, encoding='utf-8')))
        v = [float(r['excess_vs_kospi_pct']) for r in rows]
        n = len(v)
        lo = min((sum(v) - x) / (n - 1) for x in v) if n > 1 else v[0]
        print('\n  조합제 shadow 누적 %d일 | 평균 초과(코스피) %+.3f%%p | 이김 %d/%d | 잭나이프 하한 %+.3f'
              % (n, sum(v) / n, sum(1 for x in v if x > 0), n, lo))
        # 2026-08-06 시정 — 고정 20영업일 규정은 2026-07-31 에 폐지됐는데(N* 로 전환)
        # 이 출력만 20일을 계속 세고 있었다. 규칙마다 잡음이 달라 필요 기간이 2배 이상
        # 벌어지므로, 판정 시점은 judge_ready.py 와 같은 식으로 표본에서 직접 구한다.
        ns = n_star(v)
        if ns is None:
            print('  판정 보류 — 표본 3일 미만')
        elif n < ns:
            print('  판정까지 %d일 남음 (필요 표본 N*=%d일, 90%% 신뢰)'
                  ' — 판정: 평균>0 · 15섹터 기준선 초과 · 잭나이프 하한>0' % (ns - n, ns))
            if ns >= 60:
                print('  ※ 잡음이 커서 N*가 상한(60)에 걸렸다 — 이 지표로는 판정이 어렵다.')
        else:
            print('  N*=%d일 도달 — 판정 가능 (평균>0 · 15섹터 기준선 초과 · 잭나이프 하한>0)' % ns)


if __name__ == '__main__':
    main()
