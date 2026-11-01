#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_pending_20260822.py — 키움 자격증명이 필요한 잔여 과제를 **명령 하나**로 끝낸다.

배경: 2026-08-22 세션에서 클라우드 컨테이너는 키움·KRX API 에 도달하지만 자격증명이 없고,
      사용자 PC 마운트 쉘(device_bash)은 프록시가 아웃바운드를 전부 막는다(pypi·github 포함).
      → **네트워크 + loop 폴더 + 자격증명이 모두 있는 환경**(아침 루틴이 도는 곳)에서
        이 스크립트 하나만 실행하면 된다.

하는 일
  1) 7년 패널 재구축 — `backtest/rebuild_ohlc_long.py` 를 완주까지 자동 반복
     (셸 45초 제한을 스크립트가 알아서 나눠 돈다. 검증 통과해야만 원자적 교체)
  2) 재구축된 패널로 **baseline·Rule LV 재확인** — 승격 근거가 최신 패널에서도 서는지
  3) (선택 `--atr`) `references/scripts/atr_feed_check.py` — 키움 고가 이상의 내부 원인 확인.
     ※ 원인은 이미 좁혀졌다(고가만 좁음). 이 단계는 기록용이며 건너뛰어도 된다.

사용:
    python3 references/scripts/run_pending_20260822.py
    python3 references/scripts/run_pending_20260822.py --atr        # ATR 진단까지
    python3 references/scripts/run_pending_20260822.py --skip-lv    # 재구축만

주의: 조회 전용. 주문·매매 기능은 호출하지 않는다. 자격증명은 출력하지 않는다.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
BT = os.path.join(LOOP, 'backtest')


def run(cmd, timeout=600):
    print(f'    $ {" ".join(os.path.basename(x) for x in cmd[1:])}')
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=LOOP)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def step_rebuild():
    print('\n[1/3] 7년 패널 재구축 (키움 ka10081, 재개 가능)')
    script = os.path.join(BT, 'rebuild_ohlc_long.py')
    if not os.path.exists(script):
        print('    rebuild_ohlc_long.py 없음 — 건너뜀'); return False
    t0 = time.time()
    for i in range(1, 61):                      # 최대 60회 (코드 201종이면 충분)
        rc, out = run([sys.executable, script, '32'], timeout=180)
        tail = [l for l in out.strip().splitlines() if l.strip()][-2:]
        print(f'    회차 {i:2d} rc={rc} | ' + ' / '.join(tail))
        if rc == 0:
            print(f'    → 완주 ({time.time()-t0:.0f}초)')
            return True
        if rc == 2:
            print('    → 검증 실패로 교체 중단. 위 메시지를 확인할 것.')
            return False
    print('    → 60회에도 미완주. 다시 실행하면 이어서 받는다.')
    return False


def step_lv():
    print('\n[2/3] 최신 패널로 baseline · Rule LV 재확인')
    for name in ('bt_base_long_20260819.py', 'bt_lv_full_20260819.py'):
        s = os.path.join(BT, name)
        if not os.path.exists(s):
            print(f'    {name} 없음 — 건너뜀'); continue
        rc, out = run([sys.executable, s], timeout=900)
        print(f'    --- {name} (rc={rc}) ---')
        keep = [l for l in out.splitlines()
                if any(t in l for t in ('CAGR', 'MDD', 'Sharpe', '누적', 'fold', 'p=', '채점'))]
        print('\n'.join('    ' + l for l in keep[:40]))
    print('\n    ※ 판정 기준(2026-08-22 승격 시): MDD −36.6→−25.4 · Sharpe 1.04→1.56 ·')
    print('      CAGR +30.5→+31.2. 최신 패널에서 **MDD·Sharpe 우위가 유지되면 Rule LV 유지**,')
    print('      뒤집히면 analysis-method.md 의 강등 조건에 따라 검증 대기로 내린다.')


def step_atr():
    print('\n[3/3] ATR 피드 진단 (기록용 — 원인은 이미 "고가만 좁음"으로 좁혀졌다)')
    s = os.path.join(HERE, 'atr_feed_check.py')
    if not os.path.exists(s):
        print('    atr_feed_check.py 없음 — 건너뜀'); return
    rc, out = run([sys.executable, s], timeout=600)
    print('\n'.join('    ' + l for l in out.splitlines()[-45:]))
    print(f'    rc={rc} (0=세 소스 일치 · 2=불일치 확인 · 1=조회 실패)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atr', action='store_true', help='ATR 피드 진단까지 실행')
    ap.add_argument('--skip-lv', action='store_true', help='재구축만 하고 종료')
    a = ap.parse_args()
    print('=' * 72)
    print('키움 자격증명 필요 잔여 과제 일괄 실행 — 2026-08-22')
    print('=' * 72)
    okr = step_rebuild()
    if okr and not a.skip_lv:
        step_lv()
    elif not okr:
        print('\n[2/3] 재구축이 끝나지 않아 LV 재확인은 건너뛴다.')
    if a.atr:
        step_atr()
    print('\n완료. 결과를 붙여 주시면 이어서 판정·문서 갱신하겠습니다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
