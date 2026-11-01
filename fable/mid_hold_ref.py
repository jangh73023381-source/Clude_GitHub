# -*- coding: utf-8 -*-
"""[6-3] 중기 ETF 보유 경과·만기 참고 열 (2026-09-19 사용자 승인 — 표시 전용).

사용자 결정: "만기일 열만 추가". **Rule CB 청산 규칙은 바꾸지 않는다.**
이 모듈은 아무것도 선정하지 않고, 아무 규칙도 발동시키지 않는다 —
`loop/backtest/picks_mid_etf.json` 에 이미 기록된 '그날 [6-3]에 실린 코드'를 읽어
연속 추천 최초일(=편입일)과 20거래일째가 언제인지만 계산한다.

근거: `보유기간_종목선정과_0.5퍼센트_트레일링스톱_검정_2026-09-19`
 — mom150 은 5·10·20일 전부 fold 3/3 양수이고 20거래일이 초과수익의 고원(+0.609%p),
   40일은 fold3 +0.21 로 얇아진다. 즉 **20거래일이 상한**이다.
 - 다만 현행 [6-3] 청산은 Rule CB(재추천되면 계속 보유)라 보유기간이 고정이 아니다.
   이 열은 "지금 며칠째인가"를 보여줄 뿐이며 **청산을 지시하지 않는다.**

조회 전용. mom150 을 재계산하지 않는다(§5 Rule MM "같은 값을 두 곳에서 계산하지 말 것").
"""
import csv
import datetime as dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.join(os.path.dirname(HERE), 'loop')
REG = os.path.join(LOOP, 'backtest', 'picks_mid_etf.json')
PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_long.csv')
HOLD = 20          # 검정상 고원 구간. 이 값은 표시 기준일 뿐 청산 트리거가 아니다.


def _cal():
    """패널에 실재하는 거래일 목록(확정분)."""
    ds = set()
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            ds.add(r['date'])
    return sorted(ds)


def _add_bdays(d8, n):
    """확정 거래일이 없는 미래 구간은 주말만 제외해 더한다(공휴일 미반영 — 추정)."""
    d = dt.date(int(d8[:4]), int(d8[4:6]), int(d8[6:]))
    while n > 0:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.strftime('%Y%m%d')


def rows(D=None):
    """D(선정 기준일, YYYYMMDD) 기준 [6-3] 5종의 편입일·경과·잔여·만기(추정)."""
    reg = json.load(open(REG, encoding='utf-8'))
    keys = sorted(reg)                                   # 'YYYY-MM-DD'
    if not keys:
        return []
    if D is None:
        k_now = keys[-1]
    else:
        k_now = f'{D[:4]}-{D[4:6]}-{D[6:]}'
        if k_now not in reg:
            prev = [k for k in keys if k <= k_now]
            if not prev:
                return []
            k_now = prev[-1]
    i_now = keys.index(k_now)
    cal = _cal()
    out = []
    for code, name in zip(reg[k_now]['codes'], reg[k_now].get('names', [])):
        j = i_now
        while j - 1 >= 0 and code in reg[keys[j - 1]]['codes']:
            j -= 1
        since = keys[j].replace('-', '')
        # 경과 = 편입일부터 오늘까지의 '실제 거래일' 수(편입일 포함)
        seg = [d for d in cal if since <= d <= k_now.replace('-', '')]
        elapsed = len(seg) if seg else (i_now - j + 1)
        left = HOLD - elapsed
        si = cal.index(since) if since in cal else None
        if si is not None and si + HOLD - 1 < len(cal):
            due, est = cal[si + HOLD - 1], False        # 만기일이 이미 확정 거래일 안
        else:
            due, est = _add_bdays(since, HOLD - 1), True
        have = {k.replace('-', '') for k in keys}
        gaps = [d for d in cal if since <= d <= k_now.replace('-', '') and d not in have]
        out.append({'code': code, 'name': name, 'since': since, 'elapsed': elapsed,
                    'left': left, 'due': due, 'due_est': est,
                    'spells': i_now - j + 1, 'gaps': gaps})
    out.sort(key=lambda x: -x['elapsed'])
    return out


def fmt(r):
    """표 셀 3개: 편입일 / 만기(D+20) / 잔여."""
    f = lambda d: f'{d[4:6]}/{d[6:]}'                     # noqa: E731
    due = f(r['due']) + ('(추정)' if r['due_est'] else '')
    left = f"{r['left']}거래일" if r['left'] > 0 else f"**경과 {-r['left']}거래일**"
    return f(r['since']), due, left


NOTE = ("※ **편입일·만기(D+20)·잔여 열은 표시 전용입니다** — 청산은 지금까지와 같이 "
        "**Rule CB**(다음 브리핑에도 재추천되면 계속 보유, 추천에서 빠지는 첫 브리핑일 "
        "종가 청산)를 따릅니다. **이 열은 매도를 지시하지 않습니다.** "
        "D+20 은 2026-09-19 검정에서 mom150 의 초과수익이 고원을 이루는 구간(+0.609%p, "
        "fold 3/3)이자 상한이라는 뜻이며(40일은 fold3 +0.21 로 얇아짐), 잔여가 0 이하인 "
        "종목은 **검정 근거가 얇어지는 구간에 들어갔다**는 표시입니다. "
        "편입일은 `picks_mid_etf.json` 에 기록된 실제 [6-3] 추천 이력에서 읽으며 "
        "mom150 을 재계산하지 않습니다. 만기일 '(추정)'은 아직 오지 않은 거래일이라 "
        "주말만 제외해 계산한 값으로 **공휴일이 끼면 하루씩 밀립니다**. "
        "연속 구간 안에 브리핑이 기록되지 않은 거래일이 있으면 그 날은 건너뛰고 세므로 "
        "편입일이 실제보다 이를 수 있습니다 — 해당 날짜는 `gaps` 로 함께 반환합니다.")

if __name__ == '__main__':
    import sys
    D = sys.argv[1] if len(sys.argv) > 1 else None
    rs = rows(D)
    if '--json' in sys.argv:
        print(json.dumps({'rows': rs, 'note': NOTE}, ensure_ascii=False, indent=1))
    else:
        print(f"{'종목명':26s} {'코드':8s} {'편입일':10s} {'만기(D+20)':12s} {'잔여':10s}")
        for r in rs:
            a, b, c = fmt(r)
            print(f"{r['name']:26s} {r['code']:8s} {a:10s} {b:12s} {c:10s} (경과 {r['elapsed']})")
