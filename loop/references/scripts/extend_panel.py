#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
패널 연장기 (조회 전용) — 기존 panel_close_<MMDD>.csv 의 코드 유니버스에 대해
지정한 거래일들의 종가를 키움 ka10081 일봉으로 채워 새 패널을 만든다.

멱등·재개 가능: 부분 결과를 references/scripts/_panel_ext_<YYYYMMDD>.csv 에 누적하고
이미 받은 코드는 다시 조회하지 않는다. 45초 셸 제한 안에서 반복 실행하면 된다.

사용:
  python3 references/scripts/extend_panel.py --base backtest/panel_close_0724.csv --dates 20260727
  python3 references/scripts/extend_panel.py ... --finalize   # 완료 후 새 패널 저장
"""
import argparse
import os
import sys
import time

import pandas as pd

LOOP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, LOOP_DIR)
import kiwoom_api as k  # noqa: E402
from ensure_data import settled  # noqa: E402

SCRIPTS = os.path.join(LOOP_DIR, "references", "scripts")


def part_path(tag):
    return os.path.join(SCRIPTS, f"_panel_ext_{tag}.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--dates", required=True, help="쉼표구분 YYYYMMDD")
    ap.add_argument("--budget", type=float, default=35.0, help="이번 실행 최대 초")
    ap.add_argument("--finalize", action="store_true")
    a = ap.parse_args()

    base_path = a.base if os.path.isabs(a.base) else os.path.join(LOOP_DIR, a.base)
    want = [d.strip() for d in a.dates.split(",") if d.strip()]
    tag = want[-1]

    # 2026-11-01: 미확정 봉 유입 금지(CLAUDE.md §6) — ensure_data.ensure() 경로를 거치지 않는
    # 수동 직접 실행(이 스크립트의 공식 사용법)에서도 당일 미확정 종가가 패널에 섞이지 않게
    # 호출자가 어떻든 여기서도 재검증한다.
    unsettled = [d for d in want if not settled(d)]
    if unsettled:
        print(f"[거부] 미확정(미마감) 날짜 포함 — {unsettled} (16:00 KST 이후에만 확정)")
        return 2

    base = pd.read_csv(base_path, dtype={"code": str})
    codes = base[["code", "name"]].drop_duplicates("code").reset_index(drop=True)

    pp = part_path(tag)
    done = set()
    if os.path.exists(pp):
        prev = pd.read_csv(pp, dtype={"code": str})
        # 실패(close 결측)한 코드는 완료로 보지 않고 재시도한다
        ok = prev[prev["close"].notna()]
        done = set(ok["code"].unique())
        prev = prev[prev["code"].isin(done)]
        prev.to_csv(pp, index=False)

    todo = [r for r in codes.itertuples() if r.code not in done]
    print(f"코드 {len(codes)}종 · 완료 {len(done)} · 남은 {len(todo)}")

    if a.finalize:
        if todo:
            print(f"[중단] 아직 {len(todo)}종 남음 — finalize 불가")
            return 1
        ext = pd.read_csv(pp, dtype={"code": str})
        ext = ext[ext["close"].notna()]
        merged = pd.concat([base, ext], ignore_index=True)
        merged = merged.drop_duplicates(subset=["code", "date"], keep="last")
        out = os.path.join(LOOP_DIR, "backtest", f"panel_close_{tag[4:]}.csv")
        tmp = out + ".tmp"
        merged.to_csv(tmp, index=False)
        if os.path.exists(out):
            import safe_io
            safe_io.safe_replace(tmp, out)  # 2026-11-01: 생 to_csv 직접 덮어쓰기 대신 §6 safe_replace
        else:
            os.rename(tmp, out)
        print(f"[완료] {out} — {merged.shape[0]}행 · {merged.code.nunique()}종 · "
              f"최종거래일 {merged.date.max()}")
        return 0

    t0 = time.time()
    rows = []
    n_ok = 0
    for r in todo:
        if time.time() - t0 > a.budget:
            break
        try:
            # 키움 유량 제한 5req/s — 스로틀 + 429 재시도
            resp = None
            for attempt in range(4):
                try:
                    time.sleep(0.25)
                    resp = k.get_daily_chart(r.code)
                    break
                except Exception as e:  # noqa: BLE001
                    if "429" in str(e) and attempt < 3:
                        time.sleep(1.0 + attempt)
                        continue
                    raise
            arr = (resp or {}).get("stk_dt_pole_chart_qry") or []
            got = {}
            for it in arr:
                dt = str(it.get("dt", ""))
                if dt in want:
                    v = str(it.get("cur_prc", "")).replace("+", "").replace("-", "").strip()
                    if v:
                        got[dt] = abs(float(v))
            for dt in want:
                rows.append({"code": r.code, "name": r.name, "date": int(dt),
                             "close": got.get(dt)})
            n_ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  [실패] {r.code} {r.name}: {e}")
            for dt in want:
                rows.append({"code": r.code, "name": r.name, "date": int(dt), "close": None})

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(pp, mode="a", header=not os.path.exists(pp), index=False)
    print(f"이번 실행 {n_ok}종 수집 · {time.time() - t0:.1f}초")
    remain = len(todo) - n_ok
    print("남은 코드:", remain)
    return 0 if remain == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
