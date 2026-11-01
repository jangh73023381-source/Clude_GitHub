#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""atr_feed_check.py — 키움 ka10081 일봉의 고가/저가를 KRX 공식 일별매매와 대조한다 (조회 전용).

배경 (2026-08-22 발견):
  fable/sector_levels.py 가 내는 ATR14 가 KRX 공식값 기준 재계산보다 **15종 전부 5~23%
  (평균 13.5%) 낮다.** 브리핑 진입전략의 손절선 = 종가 − 2.0×ATR14 가 그만큼 타이트해진다.

여기까지 좁혀진 것 (전부 클라우드에서 KRX 검증 데이터로 확인, `섹터별ETF_타점표_및_RuleCHB검정_2026-08-22.docx`):
  · 종가·채널위치·지지저항 레벨은 94/120 항목 일치 — **어긋나는 것은 ATR 계열뿐이다.**
  · 계산식은 정상이다. 단순평균14가 맞고 Wilder(비율 1.238±0.130)도, mean(H−L)도,
    ATR20 도, 1일 시프트도 키움 값을 재현하지 못했다. 단순평균14 비율이 1.132±0.049 로
    가장 가깝지만 1 이 아니다.
  · 창 종료일도 정상이다(15종 중 9종이 20260820 에서 최근접, 나머지도 설명 불가한 산포).
  · 8/19 급락봉 누락 가설도 기각(비율 1.162±0.075).
  → 남은 것은 **ka10081 이 돌려주는 고가/저가 값 자체**다.

  ★ 2026-08-22 추가 — **제1 용의자였던 `upd_stkpc_tp="1"`(수정주가)는 기각됐다.**
  `panel_ohlc_2y.csv` 는 `rebuild_ohlc_panel.py` 가 **같은 API·같은 파라미터**(ka10081,
  adjusted=True)로 받아 만든 것이다. 그 패널의 ATR14 를 야후(=KRX 검증)와 대조한 결과
  **거래대금 상위 ETF 20종 중 19종이 비율 1.000**(평균 0.9996 · 표준편차 0.0016)로 일치했다.
  → **ka10081 피드 자체는 정상이고, 수정주가 가설도 아니다.**

  남은 차이는 하나뿐 — **패널은 ETF 이고 `sector_levels.py` 는 개별주식이다.**
  그래서 이 스크립트는 **개별주식과 ETF 대조군을 같은 실행 안에서 나란히** 찍는다.
  · 주식만 어긋난다 → 종목 유형에 따른 ka10081 응답 차이.
  · 둘 다 맞다 → 원인은 `etf_levels.py` 의 `bars()`~`levels()` 경로다(피드 아님).
  수정주가 `1`/`0` 비교는 그대로 남겨 둔다 — 배제 근거를 실행마다 재확인하기 위함이다.

사용 (네트워크 + 키움/KRX 자격증명이 함께 있는 환경에서 1회 실행하면 판별된다):
  python3 references/scripts/atr_feed_check.py
  python3 references/scripts/atr_feed_check.py --codes 000660 105560 --days 20

종료코드: 0 = 세 소스 일치 / 2 = 불일치 발견(원인 확정) / 1 = 조회 실패
주의: 조회 전용이다. 주문·매매 기능은 호출하지 않는다. 자격증명은 출력하지 않는다.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, LOOP)

import kiwoom_api as KW          # noqa: E402
import krx_api as KX             # noqa: E402

# Rule SU(v2.6) 유니버스 중 괴리가 컸던 순서대로 — 기본 대상
# 개별주식(괴리가 컸던 순서) + **ETF 대조군**(패널 검정에서 1.000 일치 확인).
# 같은 실행 안에서 나란히 찍어야 '주식만 어긋나는가'가 판별된다.
DEFAULT = [('010120', 'LS ELECTRIC [주식]'), ('000660', 'SK하이닉스 [주식]'),
           ('006800', '미래에셋증권 [주식]'), ('090430', '아모레퍼시픽 [주식]'),
           ('069500', 'KODEX 200 [ETF 대조군]'), ('091160', 'KODEX 반도체 [ETF 대조군]')]
TOL = 0.005      # 0.5% 초과 차이는 불일치로 본다


def kiwoom_bars(code, adjusted):
    r = KW.get_daily_chart(code, '00000000', adjusted=adjusted)
    out = {}
    for d in (r.get('stk_dt_pole_chart_qry') or []):
        try:
            out[d['dt']] = (abs(float(d['high_pric'])), abs(float(d['low_pric'])),
                            abs(float(d['cur_prc'])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def krx_bars(dates):
    """KRX 일별매매 — 날짜별로 유가증권·코스닥을 모두 훑어 {날짜: {코드: (고,저,종)}}."""
    out = {}
    for d in dates:
        day = {}
        for path in ('sto/stk_bydd_trd', 'sto/ksq_bydd_trd'):
            st, data = KX.call(path, basDd=d)
            if st != 'ok':
                print(f'  KRX {d} {path}: {st} — 중단', file=sys.stderr)
                return None
            for r in KX.rows(data):
                c = r.get('ISU_SRT_CD') or r.get('ISU_CD')
                if not c:
                    continue
                try:
                    day[c] = (float(str(r['TDD_HGPRC']).replace(',', '')),
                              float(str(r['TDD_LWPRC']).replace(',', '')),
                              float(str(r['TDD_CLSPRC']).replace(',', '')))
                except (KeyError, TypeError, ValueError):
                    continue
        out[d] = day
    return out


def atr14(series):
    """series = [(date, high, low, close), ...] 오름차순. fable/etf_levels.py 와 동일한 단순평균."""
    if len(series) < 15:
        return None
    trs = []
    for i in range(len(series) - 14, len(series)):
        pc = series[i - 1][3]
        trs.append(max(series[i][1] - series[i][2],
                       abs(series[i][1] - pc), abs(series[i][2] - pc)))
    return sum(trs) / 14


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--codes', nargs='*', default=None)
    ap.add_argument('--days', type=int, default=20, help='대조할 최근 거래일 수 (기본 20)')
    a = ap.parse_args()
    targets = [(c, '') for c in a.codes] if a.codes else DEFAULT

    adj = {c: kiwoom_bars(c, True) for c, _ in targets}
    raw = {c: kiwoom_bars(c, False) for c, _ in targets}
    if not any(adj.values()):
        print('키움 일봉 조회 실패 — 자격증명·네트워크 확인', file=sys.stderr)
        return 1

    dates = sorted(set().union(*[set(v) for v in adj.values() if v]))[-a.days:]
    kx = krx_bars(dates)
    if kx is None:
        return 1

    bad = 0
    for code, name in targets:
        print('=' * 96)
        print(f'{name or code} ({code})   ※ 수정주가=키움 기본값(upd_stkpc_tp=1)')
        print(f"{'날짜':>10s} | {'KRX 고/저':>21s} | {'키움 수정주가 고/저':>21s} | "
              f"{'키움 원주가 고/저':>21s} | 판정")
        print('-' * 96)
        sa, sr, sk = [], [], []
        for d in dates:
            k_adj = adj[code].get(d)
            k_raw = raw[code].get(d)
            k_krx = (kx.get(d) or {}).get(code)
            if not k_krx:
                continue
            sk.append((d, k_krx[0], k_krx[1], k_krx[2]))
            if k_adj:
                sa.append((d, k_adj[0], k_adj[1], k_adj[2]))
            if k_raw:
                sr.append((d, k_raw[0], k_raw[1], k_raw[2]))
            def f(v):
                return f'{v[0]:,.0f}/{v[1]:,.0f}' if v else '—'
            ok_a = k_adj and abs(k_adj[0] / k_krx[0] - 1) <= TOL and abs(k_adj[1] / k_krx[1] - 1) <= TOL
            ok_r = k_raw and abs(k_raw[0] / k_krx[0] - 1) <= TOL and abs(k_raw[1] / k_krx[1] - 1) <= TOL
            mark = ('수정주가 O' if ok_a else '수정주가 X') + ' / ' + ('원주가 O' if ok_r else '원주가 X')
            if not ok_a:
                bad += 1
            print(f'{d:>10s} | {f(k_krx):>21s} | {f(k_adj):>21s} | {f(k_raw):>21s} | {mark}')
        base = atr14(sk)
        print('-' * 96)
        for lab, s in (('KRX 공식', sk), ('키움 수정주가', sa), ('키움 원주가', sr)):
            v = atr14(s)
            if v is None or base is None:
                print(f'  ATR14 {lab:12s}: 표본 부족')
            else:
                print(f'  ATR14 {lab:12s}: {v:>12,.0f}   (KRX 대비 {v / base - 1:+.1%})')
    print('=' * 96)
    if bad:
        print(f'불일치 {bad}건 — 원인 확정. 위 표에서 "원주가 O"가 뜨면 fable/etf_levels.py 의 '
              'bars() 를 adjusted=False 로 바꾸면 되고, 둘 다 X 면 일봉 소스를 KRX/패널로 교체한다.')
        return 2
    print('세 소스 일치 — ATR 괴리의 원인은 일봉 피드가 아니다. 다른 경로를 의심할 것.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
