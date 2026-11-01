#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ensure_data.py — 아침 루틴 데이터 자동 보충 (2026-07-31 신설)

`morning_run.py` 가 채점 전에 호출한다. 2026-07-29·07-30·07-31 **3회 연속** 같은
결함으로 수동 개입이 필요했던 두 가지를 자동화한다.

  1. `backtest/panel_close_*.csv` 가 직전 거래일까지 안 채워져 있으면
     `extend_panel.py` 로 연장한다.
  2. `backtest/kospi_close.csv` 에 패널 거래일이 빠져 있으면 yfinance 로 보충한다.

45초 셸 제한 안에서 끝나지 않으면 예산 소진 시점에 멈추고 `done=False` 를 돌려준다.
`extend_panel.py` 의 부분 결과는 멱등하게 누적되므로 다시 호출하면 이어서 채운다.

**확정 종가만 쓴다.** yfinance 는 장중에도 그날 일봉을 돌려주므로(실측: 2026-07-31
09:00 이전 조회에서 당일 봉이 이미 존재), 진행 중인 세션 값을 종가로 적으면 트래커가
영구히 오염된다. 그래서 `settled()` 를 통과한 날짜만 기록한다 —
`날짜 < 오늘` 또는 `날짜 == 오늘 이고 지금이 16:00 KST 이후`(fable CLAUDE.md 3번).

조회 전용 — 주문·매매·이체 기능은 어떤 경로로도 호출하지 않는다.
"""
import os
import subprocess
import sys

# 2026-09-30 시정 — 워크스페이스 VM 의 /sessions 디스크(9.8G)가 다른 세션 잔재로 100% 가득 차
# $TMPDIR($HOME/tmp)·~/.local·~/.cache 쓰기가 전부 'No space left on device' 로 실패했다
# (pip install yfinance 실패 → 코스피 보충 불가). /tmp 는 루트 디스크라 여유가 있으므로
# $TMPDIR 이 쓰기 불가하면 /tmp 로 돌리고, pip 는 /tmp/pylib 에 --target 설치한다.
# os.environ 을 바꾸므로 morning_run 이 띄우는 하위 프로세스에도 그대로 상속된다.
import os as _os
_PYLIB = '/tmp/pylib'


def _writable(d):
    try:
        _os.makedirs(d, exist_ok=True)
        f = _os.path.join(d, '.wtest')
        with open(f, 'w') as h:
            h.write('x' * 4096)
        _os.remove(f)
        return True
    except Exception:                                         # noqa: BLE001
        return False


if not _writable(_os.environ.get('TMPDIR') or '/tmp'):
    _os.environ['TMPDIR'] = '/tmp'
_os.environ.setdefault('PIP_NO_CACHE_DIR', '1')
if _os.path.isdir(_PYLIB):
    if _PYLIB not in sys.path:
        sys.path.insert(0, _PYLIB)
    _pp = _os.environ.get('PYTHONPATH', '')
    if _PYLIB not in _pp.split(':'):
        _os.environ['PYTHONPATH'] = _PYLIB + (':' + _pp if _pp else '')
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
KST = timezone(timedelta(hours=9))
KOSPI_CSV = os.path.join(LOOP, 'backtest', 'kospi_close.csv')
CAL_CODE = '069500'          # 거래일 달력 기준 종목 (KODEX 200)
CLOSE_HOUR = 16              # 장 마감 기준 16:00 KST


def settled(day, now=None):
    """day(YYYYMMDD)가 '확정된 세션'인가 — 진행 중인 당일 값을 배제한다."""
    now = now or datetime.now(KST)
    today = now.strftime('%Y%m%d')
    if day < today:
        return True
    return day == today and now.hour >= CLOSE_HOUR


def trading_days(after, before_or_eq):
    """키움 일봉에서 실제 거래일을 읽어 (after, before_or_eq] 구간을 돌려준다.

    주말·공휴일을 직접 계산하지 않는다 — 임시 휴장·대체공휴일까지 맞히려면
    달력을 따로 관리해야 하고, 그 달력이 틀리면 조용히 결측이 생긴다.
    """
    sys.path.insert(0, LOOP)
    import kiwoom_api as k  # noqa: E402

    arr = (k.get_daily_chart(CAL_CODE) or {}).get('stk_dt_pole_chart_qry') or []
    days = sorted({str(it.get('dt', '')) for it in arr if str(it.get('dt', ''))})
    return [d for d in days if after < d <= before_or_eq and settled(d)]


def newest_panel():
    d = os.path.join(LOOP, 'backtest')
    c = sorted(f for f in os.listdir(d)
               if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(d, c[-1]) if c else None


def panel_last_date(path):
    import csv
    return max(str(r['date']) for r in csv.DictReader(open(path, encoding='utf-8')))


def _extend_one(base, day, deadline):
    """extend_panel.py 를 예산이 남는 동안 반복 호출하고, 다 받으면 finalize."""
    script = os.path.join(HERE, 'extend_panel.py')
    while time.time() < deadline:
        left = max(5.0, deadline - time.time() - 2.0)
        p = subprocess.run(
            [sys.executable, script, '--base', base, '--dates', day,
             '--budget', str(round(left, 1))],
            cwd=LOOP, capture_output=True, text=True, timeout=left + 60)
        if p.returncode == 0:          # 남은 코드 0 → finalize
            f = subprocess.run(
                [sys.executable, script, '--base', base, '--dates', day, '--finalize'],
                cwd=LOOP, capture_output=True, text=True, timeout=120)
            return f.returncode == 0, (f.stdout or p.stdout).strip().splitlines()[-1:]
        if p.returncode != 3:          # 3 = 예산 소진(정상 재개 대상)
            return False, [f'extend_panel rc={p.returncode}: {p.stderr.strip()[-200:]}']
    return False, ['예산 소진 — 재실행하면 이어서 받는다']


def ensure_panel(T, deadline):
    """패널을 직전 확정 거래일까지 연장한다."""
    base = newest_panel()
    if not base:
        return {'ok': False, 'done': False, 'note': 'panel_close_*.csv 없음'}
    last = panel_last_date(base)
    try:
        need = trading_days(last, T)
    except Exception as e:                                    # noqa: BLE001
        return {'ok': False, 'done': True, 'panel_last': last,
                'note': f'거래일 조회 실패 — 연장 생략: {type(e).__name__}: {e}'}
    if not need:
        return {'ok': True, 'done': True, 'panel_last': last, 'note': '패널 최신'}

    logs = []
    for day in need:
        ok, msg = _extend_one(base, day, deadline)
        logs += msg
        if not ok:
            return {'ok': False, 'done': False, 'panel_last': last,
                    'pending': need, 'note': ' / '.join(logs)}
        base = newest_panel()
        last = panel_last_date(base)
    return {'ok': True, 'done': True, 'panel_last': last,
            'filled': need, 'note': ' / '.join(logs)}


def _kospi_rows():
    import csv
    if not os.path.exists(KOSPI_CSV):
        return {}
    return {str(r['date']): r['close']
            for r in csv.DictReader(open(KOSPI_CSV, encoding='utf-8'))}


def ensure_kospi(days):
    """kospi_close.csv 에 빠진 확정 거래일을 채운다."""
    have = _kospi_rows()
    want = [d for d in days if d not in have and settled(d)]
    if not want:
        return {'ok': True, 'filled': [], 'note': '코스피 종가 최신'}
    try:
        import yfinance as yf
    except ImportError:
        # 2026-08-06 시정 — 샌드박스가 세션마다 초기화돼 yfinance 미설치가 매 실행
        # 반복됐다(7/29·8/4·8/6 확인). 그때마다 사람이 설치해 주는 대신 여기서 한 번
        # 시도한다. 실패해도 결손으로 넘어갈 뿐 루틴을 중단시키지 않는다.
        import importlib
        try:
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                                'yfinance', '--break-system-packages'],
                               check=True, capture_output=True, timeout=180)
            except Exception:                                 # noqa: BLE001
                # 2026-09-30 — 사용자 site(~/.local)가 디스크 부족이면 /tmp/pylib 로 설치
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                                '--no-cache-dir', '--target', _PYLIB, 'yfinance'],
                               check=True, capture_output=True, timeout=180,
                               env=dict(_os.environ, TMPDIR='/tmp'))
                if _PYLIB not in sys.path:
                    sys.path.insert(0, _PYLIB)
                _pp = _os.environ.get('PYTHONPATH', '')
                if _PYLIB not in _pp.split(':'):
                    _os.environ['PYTHONPATH'] = _PYLIB + (':' + _pp if _pp else '')
            # 설치 직후 그냥 import 하면 실패한 조회 결과가 캐시돼 ModuleNotFoundError 가
            # 그대로 다시 난다(실측). 파인더 캐시를 비워야 새로 설치된 패키지가 보인다.
            importlib.invalidate_caches()
            import yfinance as yf  # noqa: F811
        except Exception as e:                                # noqa: BLE001
            return {'ok': False, 'filled': [], 'missing': want,
                    'note': f'yfinance 미설치 · 자동 설치 실패({type(e).__name__}) — '
                            'pip install yfinance --break-system-packages'}

    got, note = {}, []
    try:                                    # 1순위: 일봉(확정 시계열)
        # 2026-09-16 시정(9/15 로그 사전 등록 축 ⑥) — 종전 `period='3mo'` 는 Yahoo 가
        # 그 창에서 **마지막 봉을 빼고** 돌려줘 직전 거래일이 구조적으로 결손됐다
        # (9/15 실측: 3mo 에 20260914 없음 / start·end 명시 창에는 있음).
        # want 의 최소일 -5일 ~ 오늘+1 로 창을 좁혀 질의한다.
        _s = (datetime.strptime(min(want), '%Y%m%d') - timedelta(days=5)).strftime('%Y-%m-%d')
        _e = (datetime.now(KST) + timedelta(days=1)).strftime('%Y-%m-%d')
        h = yf.Ticker('^KS11').history(start=_s, end=_e)
        for ts, row in h.iterrows():
            d = ts.astimezone(KST).strftime('%Y%m%d')
            if d in want:
                got[d] = round(float(row['Close']), 2)
    except Exception as e:                                    # noqa: BLE001
        note.append(f'일봉 조회 실패: {type(e).__name__}')

    # 2026-09-16 실측 — 창을 명시해도 Yahoo ^KS11 **일봉은 직전 거래일 1개가 늘 빠진다**
    # (오늘 06:20 KST: 3mo·명시창 모두 마지막 봉이 20260914, 20260915 없음). 즉 **최신
    # 거래일은 사실상 2순위 스냅샷으로만 채워진다**(regularMarketTime D 20:05 → 16:00
    # 가드 통과). 창 명시는 결손 폭을 줄일 뿐 최신일 결손을 없애지 못한다 —
    # 스냅샷 경로(`.info`)가 실패하면 그날 결손이 그대로 남으므로 이 분기를 지우지 말 것.
    miss = [d for d in want if d not in got]
    if miss:                                # 2순위: 스냅샷 — 일봉이 하루 늦는 날
        try:                                # regularMarketTime 으로 '어느 날 종가인지'를 검증한다
            info = yf.Ticker('^KS11').info
            ts = info.get('regularMarketTime')
            price = info.get('regularMarketPrice')
            if ts and price:
                t = (datetime.fromtimestamp(ts, KST) if isinstance(ts, (int, float))
                     else datetime.fromisoformat(str(ts)).replace(tzinfo=KST))
                d = t.strftime('%Y%m%d')
                if d in miss and t.hour >= CLOSE_HOUR:
                    got[d] = round(float(price), 2)
                    note.append(f'{d}는 스냅샷 보충(regularMarketTime {t:%Y-%m-%d %H:%M})')
                elif d in miss:
                    note.append(f'{d} 스냅샷은 장중값({t:%H:%M})이라 기록하지 않음')
        except Exception as e:                                # noqa: BLE001
            note.append(f'스냅샷 조회 실패: {type(e).__name__}')

    if got:
        body = open(KOSPI_CSV, encoding='utf-8').read()
        if not body.endswith('\n'):
            body += '\n'
        body += ''.join(f'{d},{got[d]}\n' for d in sorted(got))
        open(KOSPI_CSV, 'w', encoding='utf-8').write(body)
    still = [d for d in want if d not in got]
    return {'ok': not still, 'filled': sorted(got), 'missing': still,
            'note': ' / '.join(note) or f'{len(got)}일 보충'}


def ensure(T, budget=30.0):
    """**코스피 → 패널** 순으로 보충한다. done=False 면 호출자가 다시 부르면 된다.

    2026-08-18 순서 변경. 종전에는 패널을 먼저 채우고 남은 예산으로 코스피를 채웠는데,
    패널 보충이 예산을 다 쓰면 코스피가 그냥 넘어가 `dual_score.py` 가 rc=1 로 실패했다.
    8/13·8/14·8/18 **3회 연속 같은 순서로 재발**해 8/14 로그에 걸어 둔 조건("3회 연속이면
    순서를 바꾼다")이 충족됐다. 코스피 보충은 yfinance 1콜이면 끝나므로 예산과 무관하게
    먼저 돌린다. 대상 날짜는 (아직 연장 전인) 현재 패널의 마지막 10일 + T 로 잡는다.
    """
    import csv
    deadline = time.time() + budget

    # ── 코스피 먼저(1콜) — 예산 소진과 무관하게 반드시 수행한다
    kp = None
    path0 = newest_panel()
    if path0:
        days0 = sorted({str(r['date'])
                        for r in csv.DictReader(open(path0, encoding='utf-8'))})
        kp = ensure_kospi(days0[-10:] + [T])
        print(f'  [코스피] {kp["note"]}'
              + (f' · 미보충 {kp["missing"]}' if kp.get('missing') else ''))

    p = ensure_panel(T, deadline)
    print(f'  [패널] {p["note"]} (마지막 {p.get("panel_last", "?")})')
    if not p['done']:
        # 2026-09-18 시정(9/16·9/17 로그 등록 축 ⑥ — 3회 연속 재현으로 원인 분리).
        # **원인**: 1차 `kp` 대상이 `days0[-10:] + [T]` 라서, 패널이 아직 D-1 까지만
        # 채워진 시점에는 **직전 거래일 D 가 어느 쪽에도 없다** — days0 의 마지막은
        # D-1 이고 T(오늘)는 D 가 아니다. 그래서 `ensure_kospi` 가 조회할 날짜 자체가
        # 없어 `'코스피 종가 최신'` 이라는 **거짓 OK** 를 돌려주고, 조기 반환으로 2차
        # `kp2` 도 건너뛴다. rc=3 여부와 무관한 '대상 날짜 누락' 결함이다.
        # 2026-09-18 실측: 06:20 실행에서 패널 20260916 · T=20260918 · D=20260917 →
        # 1차 kp 가 '최신' 보고, 직후 `ensure_kospi(['20260917'])` 단독 호출은 즉시 성공
        # (스냅샷 경로, 6,715.41). 사후 무결성 검사가 20260917 결손을 오류로 잡았다.
        # **시정**: 조기 반환 전에 `ensure_panel` 이 계산한 미충족 거래일(`pending`)로
        # 코스피를 한 번 더 채운다. 코스피 보충은 yfinance 1콜이라 예산과 무관하다.
        pend = [d for d in (p.get('pending') or []) if settled(d)]
        if pend:
            kp3 = ensure_kospi(pend)
            print(f'  [코스피/보류일] {kp3["note"]}'
                  + (f' · 미보충 {kp3["missing"]}' if kp3.get('missing') else ''))
            if kp3.get('filled') or kp3.get('missing'):
                kp = kp3
        return {'done': False, 'panel': p, 'kospi': kp}

    # 패널이 연장돼 새 거래일이 생겼으면 그 날짜만 한 번 더 채운다
    path = newest_panel()
    days = sorted({str(r['date']) for r in csv.DictReader(open(path, encoding='utf-8'))})
    kp2 = ensure_kospi(days[-10:])
    # 2026-09-14 시정 — 종전 `kospi: kp or kp2` 는 kp 가 항상 truthy dict 라 kp2 를 절대
    # 반환하지 않았다. 그래서 **2차 보충이 실패해도 state 에는 1차의 '코스피 종가 최신' 이
    # 남아** 결손이 은닉됐다(9/14 실측: 패널을 20260911 로 연장한 뒤 2차 보충이 0911 을
    # 채우지 못했는데 prep.kospi 는 '최신'으로 보고 → dual_score rc=1).
    # 성공·실패 어느 쪽이든 2차 결과를 드러낸다. 사후 무결성 검사가 잡아 주지만,
    # state 가 거짓 OK 를 말하면 원인 추적이 불가능해진다.
    if kp2.get('filled'):
        print(f'  [코스피/2차] {kp2["note"]}')
        kp = kp2
    elif not kp2.get('ok', True) or kp2.get('missing'):
        print(f'  [코스피/2차] 실패 — {kp2["note"]}'
              + (f' · 미보충 {kp2["missing"]}' if kp2.get('missing') else ''))
        kp = kp2
    return {'done': True, 'panel': p, 'kospi': kp, 'kospi2': kp2}


if __name__ == '__main__':
    T = sys.argv[1] if len(sys.argv) > 1 else datetime.now(KST).strftime('%Y%m%d')
    bud = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    print(f'=== 데이터 자동 보충 — T={T} · 예산 {bud:.0f}초 ===')
    r = ensure(T, bud)
    sys.exit(0 if r['done'] else 3)
