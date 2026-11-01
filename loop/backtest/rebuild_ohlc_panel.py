# -*- coding: utf-8 -*-
"""panel_ohlc_2y.csv 재구축 (2026-07-31 — 날짜 밀림·꼬리 결손 시정).

발견된 결함:
  1. 마지막 2거래일(20260730·20260731) 행의 고가·저가가 종가와 같았다(O=H=L=C).
     → 캔들 형태 분석이 통째로 불가능(레인지 0).
  2. 같은 두 행의 값이 **하루씩 밀려** 있었다 — '20260731' 행의 종가가 실제 7/30 종가였다.
     → mom150 등 이 패널을 쓰는 계산이 하루 묵은 가격을 최신으로 착각한다.

원인 추정: 갱신 도중 부분 실패한 행이 스냅샷성 값으로 채워진 뒤 그대로 남았다.
가장 안전한 복구는 **키움 일봉으로 전 구간을 다시 받아 덮어쓰는 것**이다(멱등).

재개 가능 — 45초 셸 제한 안에서 반복 실행하면 이어서 받는다. 조회 전용.
"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, LOOP)
import kiwoom_api as k  # noqa: E402

TARGET = os.path.join(HERE, 'panel_ohlc_2y.csv')
PART = os.path.join(HERE, '_ohlc_rebuild_part.csv')
FIELDS = ['code', 'name', 'date', 'open', 'high', 'low', 'close', 'volume']

sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from ensure_data import settled  # noqa: E402  (확정 종가 판정 — 2026-08-06 신설)


def universe():
    """기존 패널의 코드·종목명을 그대로 쓴다(유니버스를 바꾸지 않는다)."""
    seen = {}
    for r in csv.DictReader(open(TARGET, encoding='utf-8')):
        seen.setdefault(r['code'], r['name'])
    return sorted(seen.items())


def main(budget=32.0):
    uni = universe()
    done = set()
    if os.path.exists(PART):
        done = {r['code'] for r in csv.DictReader(open(PART, encoding='utf-8'))}
    todo = [(c, n) for c, n in uni if c not in done]
    print(f'코드 {len(uni)}종 · 완료 {len(done)} · 남은 {len(todo)}')

    t0, rows, cnt = time.time(), [], 0
    for c, name in todo:
        if time.time() - t0 > budget:
            break
        try:
            resp = None
            for att in range(4):
                try:
                    time.sleep(0.25)
                    resp = k.get_daily_chart(c)
                    break
                except Exception as e:                        # noqa: BLE001
                    if '429' in str(e) and att < 3:
                        time.sleep(1.0 + att)
                        continue
                    raise
            for x in (resp or {}).get('stk_dt_pole_chart_qry') or []:
                try:
                    o = abs(float(str(x['open_pric']).replace('+', '').replace('-', '')))
                    h = abs(float(str(x['high_pric']).replace('+', '').replace('-', '')))
                    lo = abs(float(str(x['low_pric']).replace('+', '').replace('-', '')))
                    cl = abs(float(str(x['cur_prc']).replace('+', '').replace('-', '')))
                    v = float(x.get('trde_qty') or 0)
                except (KeyError, ValueError):
                    continue
                if min(o, h, lo, cl) <= 0 or h < lo:
                    continue
                # 2026-08-06 시정 — 미확정 봉 배제. 키움 일봉은 장중에도 그날 행을
                # 돌려주므로(8/6 실행에서 O=H=L=C·거래량 0 인 20260806 행 201개가
                # 유입돼 수동 제거해야 했다), 확정 종가 원칙(fable CLAUDE.md 3번:
                # 날짜<오늘 또는 오늘이면서 16:00 KST 이후)을 여기서도 적용한다.
                if not settled(str(x['dt'])):
                    continue
                rows.append({'code': c, 'name': name, 'date': str(x['dt']),
                             'open': o, 'high': h, 'low': lo, 'close': cl, 'volume': v})
            cnt += 1
        except Exception as e:                                # noqa: BLE001
            print(f'  [실패] {c}: {e}')
    if rows:
        # 2026-08-10 시정 — 완료 시 PART 를 os.remove 하지 못하면 '내용만 비운' 0바이트
        # 파일이 남는데, 그때 os.path.exists 만 보면 헤더를 쓰지 않아 다음 재구축의
        # 재개(45행 csv.DictReader)가 KeyError:'code' 로 죽는다(실측). 크기도 함께 본다.
        new = (not os.path.exists(PART)) or os.path.getsize(PART) == 0
        with open(PART, 'a', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerows(rows)
    left = len(todo) - cnt
    print(f'이번 실행 {cnt}종 · {time.time() - t0:.1f}초 · 남은 {left}')

    if left == 0:
        bak = TARGET + '.bak_20260731'
        if not os.path.exists(bak):
            os.replace(TARGET, bak)
            print(f'  원본 백업 → {os.path.basename(bak)}')
        data = list(csv.DictReader(open(PART, encoding='utf-8')))
        data.sort(key=lambda r: (r['code'], r['date']))
        # 2026-09-07 시정 — 종전에는 TARGET 을 open(...,'w') 로 **직접** 덮어썼다.
        # 이 마무리 블록이 쓰기 도중 killed 되면 TARGET 이 UTF-8 문자 중간에서 잘려
        # csv.DictReader 가 UnicodeDecodeError 로 죽고 패널을 아무도 못 읽는다.
        # 재현: `timeout 40 python3 rebuild_ohlc_panel.py 32` 를 반복 호출해 마지막
        # 실행이 여기서 잘리게 한다(2026-09-07 실측 — 8,130,660 → 6,045,696바이트 절단).
        # CLAUDE.md §6 "파일을 통째로 덮어쓰는 코드는 반드시 safe_io.safe_replace" 적용.
        # 주의: dst 가 이미 손상돼 있으면 safe_replace 가 line_count(dst) 에서 죽는다 —
        # 그때는 손상본을 먼저 옆으로 옮긴 뒤 호출한다.
        sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
        from safe_io import safe_replace  # noqa: E402
        tmp = TARGET + '.tmp'
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(data)
        safe_replace(tmp, TARGET)
        # 2026-08-06 시정 — 이 마운트에서 os.remove 가 PermissionError 를 던진다
        # (8/4·8/6 연속 발생, "다음 회차 과제"로 적어두고 미이행). 내용을 비우면
        # 다음 실행이 새로 시작하므로 삭제와 같은 효과이고 실패하지 않는다.
        try:
            os.remove(PART)
        except OSError:
            open(PART, 'w').close()
            print('  [주의] PART 삭제 불가 — 내용만 비움(다음 실행에 영향 없음)')
        days = sorted({r['date'] for r in data})
        print(f'  [완료] {len(data)}행 · {len({r["code"] for r in data})}종 · '
              f'{days[0]}~{days[-1]}')
        return 0
    return 3


if __name__ == '__main__':
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 32.0))
