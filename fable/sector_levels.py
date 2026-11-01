#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sector_levels.py — 섹터 대표 종목 지지·저항 표 (2026-07-31 신설, 조회 전용).

사용자 지시(2026-07-31): 데일리 브리핑의 **[6-3] ETF 지지·저항 참고표**와
**[7-3] 단일종목 지지·저항 참고표**를 폐지하고, 대신 **섹터 대표 종목 한 장짜리 표**로
대체한다. 열 구성은 사용자 지정:

  섹터분야 / 현재가 / ATR14 / 채널위치 / 1차지지 / 2차지지 / 1차저항 / 2차저항

대상은 Rule SU(v2.6) 유니버스인 **섹터 대표 개별종목 15종**이다. 추천 종목만 보던
종전 표와 달리 **매일 같은 15개 섹터를 고정으로** 보여주므로, 오늘 추천에 없는 섹터가
어디쯤 와 있는지도 함께 볼 수 있다.

레벨 산정은 `etf_levels.py` 의 로직을 그대로 쓴다(MA20·MA60·기간 고저·매물대 후보 중
현재가 기준 최근접). 예측 신호가 아니라 **집행 참고선**이라는 성격도 그대로다.

[2026-08-22] `etf_levels.bars()` 의 일봉 소스를 **KRX 정합 소스 우선**으로 교체했다.
종전 키움 ka10081 개별주 일봉은 **고가만 체계적으로 좁아** ATR14 가 평균 6.1% 과소산출됐고
(135쌍 대조 비율 0.9345, 8월 말 기준 13.5%), 그만큼 손절선이 타이트했다.
교체 후 Rule SU 15종 **15/15 가 KRX 공식 재계산과 비율 1.0000 일치**한다.
출력의 `src` 가 `kiwoom-fallback` 이면 그날 ATR 은 신뢰하지 말 것.

사용:
  python3 sector_levels.py            # 표 출력
  python3 sector_levels.py --json     # 브리핑 생성기에서 쓰는 JSON
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etf_levels as EL  # noqa: E402

# Rule SU(v2.6) 유니버스와 동일 — loop/references/scripts/stock15_picks.py 의 UNIVERSE.
# 분기 1회 시가총액 재조회로 대표가 바뀌면 양쪽을 함께 고쳐야 한다.
UNIVERSE = [
    ('반도체', '000660', 'SK하이닉스'),
    ('2차전지', '373220', 'LG에너지솔루션'),
    ('바이오', '207940', '삼성바이오로직스'),
    ('은행금융', '105560', 'KB금융'),
    ('증권', '006800', '미래에셋증권'),
    ('자동차', '005380', '현대차'),
    ('조선', '329180', 'HD현대중공업'),
    ('방산', '012450', '한화에어로스페이스'),
    ('원자력', '034020', '두산에너빌리티'),
    ('AI전력', '010120', 'LS ELECTRIC'),
    ('로봇', '277810', '레인보우로보틱스'),
    ('태양광', '009830', '한화솔루션'),
    ('건설', '047040', '대우건설'),
    ('화장품', '090430', '아모레퍼시픽'),
    ('금속귀금속', '010130', '고려아연'),
]


def zone(p120):
    """채널 위치 해석 — 2026-07-26 백테스트(5개 룩백 전부 동일 순서)."""
    if p120 is None:
        return ''
    if 0.80 <= p120 <= 0.95:
        return '저항선 직하 — 최강 구간'
    if 0.40 <= p120 <= 0.60:
        return '중간 구간 — 최약'
    if p120 < 0.10:
        return '극단 하단(신저가권)'
    return ''


def fmt(x):
    """레벨 하나를 '가격 (±%, ±ATR) 근거' 로 만든다. 없으면 안내 문구."""
    if not x:
        return '— (후보 없음)'
    return f"{x['price']:,.0f} ({x['pct']:+.1f}%, {x['atr']:+.1f}A) {x['label']}"


def collect():
    rows = []
    for sector, code, name in UNIVERSE:
        try:
            b = EL.bars(code)
            if not b:
                rows.append({'sector': sector, 'code': code, 'name': name,
                             'error': '일봉 조회 실패'})
                continue
            lv = EL.levels(b)
            rows.append({
                'sector': sector, 'code': code, 'name': name,
                # [2026-08-22] 일봉 소스 표기. 'kiwoom-fallback' 이면 ATR 이 7~13% 과소산출된다
                # (키움 개별주 일봉의 고가만 KRX 보다 좁다 — 근거는 etf_levels.bars() 주석).
                'src': EL.bars_source(code),
                'close': lv['close'],
                'atr': lv['atr'], 'atr_pct': lv['atr'] / lv['close'] * 100,
                'p120': lv.get('pos120'), 'p250': lv.get('pos250'),
                'zone': zone(lv.get('pos120')),
                's1': lv.get('sup1'), 's2': lv.get('sup2'),
                'r1': lv.get('res1'), 'r2': lv.get('res2'),
            })
        except Exception as e:                                # noqa: BLE001
            rows.append({'sector': sector, 'code': code, 'name': name,
                         'error': f'{type(e).__name__}: {e}'})
        time.sleep(0.25)                                      # 키움 유량 제한
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    rows = collect()
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print('=' * 116)
    print('섹터 대표 종목 지지·저항 참고표 — Rule SU 유니버스 15종')
    print('※ 예측 신호가 아니라 집행 참고선(손절·분할매수·목표가 설정용)')
    print('=' * 116)
    print(f'{"섹터분야":10s}{"종목(코드)":22s}{"현재가":>13s}  {"ATR14":>15s}'
          f'{"채널위치(6M/12M)":>18s}  {"1차지지":24s}{"1차저항":24s}')
    print('-' * 116)
    for r in rows:
        if r.get('error'):
            print(f'{r["sector"]:10s}{r["name"]:22s}  조회 실패 — {r["error"]}')
            continue
        p120 = f'{r["p120"]:.2f}' if r['p120'] is not None else '—'
        p250 = f'{r["p250"]:.2f}' if r['p250'] is not None else '—'
        nm = f'{r["name"]}({r["code"]})'
        av = f'{r["atr"]:,.0f}({r["atr_pct"]:.1f}%)'
        ch = f'{p120} / {p250}'
        print(f'{r["sector"]:10s}{nm:22s}{r["close"]:>13,.0f}  {av:>15s}'
              f'{ch:>18s}  {fmt(r["s1"])[:23]:24s}{fmt(r["r1"])[:23]:24s}')
        if r['zone']:
            print(f'{"":10s}└ {r["zone"]}')
    print('-' * 116)
    print('※ 2차 지지·저항은 --json 출력에 포함된다(보고서 표에는 전부 싣는다).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
