# -*- coding: utf-8 -*-
"""오늘(T)의 트랙 B 조합제(SEARCH-LED) 픽 — 브리핑 병기용 (2026-08-03 사용자 요청).

사용자 요청: "단기 ETF 추천할 때 아직 test 기간이지만 트랙 B 조합제(shadow) 종목도
같이 표시해 달라."

종전에는 트랙 B가 `dual_score.py` 안에서 **채점일(D) 기준으로만** 산출됐다. 즉 어제 픽이
어떻게 됐는지는 보였지만 **오늘 무엇을 고를지는 브리핑에 나오지 않았다.** 이 스크립트는
같은 동결 파라미터로 오늘(T) 신호 행에 선정 규칙만 적용해 픽을 뽑는다.

⚠ 파라미터 동결 원칙(2026-07-26 확정)을 지킨다 — MOM_CUT·SENT_CUT·NPICK 을 여기서
재정의하지 않고 `dual_score` 에서 그대로 import 한다. 이 파일은 **읽기만** 하며
`attention_shadow_picks.csv`·트래커를 건드리지 않는다(shadow 표본 오염 방지).

⚠ 트랙 B는 shadow 관측 대상이며 **실매수 추천이 아니다.** 브리핑에 실을 때는 반드시
그 사실을 함께 표기한다.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REF = os.path.abspath(os.path.join(HERE, '..'))
LOOP = os.path.abspath(os.path.join(REF, '..'))

from dual_score import MOM_CUT, SENT_CUT, NPICK  # noqa: E402  동결 파라미터 재사용


def _latest_panel():
    cands = [f for f in os.listdir(os.path.join(LOOP, 'backtest'))
             if f.startswith('panel_close_') and f.endswith('.csv')]
    if not cands:
        return None
    return os.path.join(LOOP, 'backtest', sorted(cands)[-1])


def _load_panel(path):
    px = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                px.setdefault(r['code'], {})[r['date']] = float(r['close'])
            except (ValueError, KeyError):
                continue
    return px, sorted({d for c in px for d in px[c]})


def picks(T, panel=None):
    """T 신호행 + 직전 종가 기준 mom20 으로 트랙 B 픽을 만든다.

    반환: {'sel': [...], 'ex_mom': [...], 'ex_sent': [...], 'basis': 종가일}
    """
    path = panel or _latest_panel()
    if not path or not os.path.exists(path):
        return {'error': '패널 없음'}
    px, dates = _load_panel(path)
    P = max(d for d in dates if d <= T) if any(d <= T for d in dates) else None
    if P is None or dates.index(P) < 20:
        return {'error': 'mom20 산출 불가(패널 이력 부족)'}
    j = dates.index(P)

    def mom20(c):
        x, y = px.get(c, {}).get(dates[j - 20]), px.get(c, {}).get(P)
        return (y / x - 1.0) if (x and y) else None

    sig = [r for r in csv.DictReader(
        open(os.path.join(REF, 'attention_shadow_picks.csv'), encoding='utf-8'))
        if r['date'] == T]
    if not sig:
        return {'error': f'{T} 관심 신호 행 없음 — 0-B 수집을 먼저 수행할 것'}

    # dual_score.py 와 동일한 순서: mom20 내림차순 랭크 → 검색z 내림차순 순회
    mr = sorted(((r['code'], mom20(r['code']) if mom20(r['code']) is not None else -9)
                 for r in sig), key=lambda t: -t[1])
    trk = {c: i + 1 for i, (c, _) in enumerate(mr)}
    sel, ex_m, ex_s = [], [], []
    for r in sorted(sig, key=lambda r: -float(r['z_search'])):
        if trk.get(r['code'], 99) > MOM_CUT:
            ex_m.append(r['theme'])
            continue
        if float(r['sent']) < SENT_CUT:
            ex_s.append(r['theme'])
            continue
        m = mom20(r['code'])
        sel.append({'code': r['code'], 'etf': r['etf'], 'theme': r['theme'],
                    'z_search': float(r['z_search']), 'sent': float(r['sent']),
                    'mom20': round(m * 100, 2) if m is not None else None,
                    'mom_rank': trk.get(r['code']),
                    'close': px.get(r['code'], {}).get(P)})
        if len(sel) == NPICK:
            break
    return {'sel': sel, 'ex_mom': ex_m, 'ex_sent': ex_s, 'basis': P,
            'params': {'MOM_CUT': MOM_CUT, 'SENT_CUT': SENT_CUT, 'NPICK': NPICK}}


if __name__ == '__main__':
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True, help='오늘 T (YYYYMMDD)')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    out = picks(a.date)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        raise SystemExit(0 if 'sel' in out else 2)
    if 'error' in out:
        raise SystemExit('트랙 B 산출 실패 — ' + out['error'])
    print(f"[트랙 B 조합제 SEARCH-LED] {a.date} 픽 (종가 기준 {out['basis']})")
    print('  ※ shadow 관측 전용 — 실매수 추천이 아님. 파라미터 동결 중')
    for i, s in enumerate(out['sel'], 1):
        c = f"{s['close']:,.0f}" if s['close'] else '—'
        print(f"  {i}. {s['code']:7s} {s['etf'][:24]:24s} ({s['theme']}) "
              f"종가 {c:>10s}  검색z {s['z_search']:+5.2f}  감성 {s['sent']:+5.3f}  "
              f"mom20 {s['mom20']:+6.2f}%(랭크 {s['mom_rank']}/15)")
    print(f"  배제 — mom20 하방: {', '.join(out['ex_mom']) or '없음'} / "
          f"악재감성: {', '.join(out['ex_sent']) or '없음'}")
