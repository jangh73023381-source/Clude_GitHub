#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""safe_io.py — 데이터 파일 오염 방지 유틸 (2026-07-31 신설).

2026-07-30·07-31 두 차례 오염 사고에서 확인된 실패 유형에 맞춰 만들었다.

  ① 절단 — 이 마운트에서 `os.replace` 가 원자적이지 않다. 갱신 도중 프로세스가 죽으면
     대상 파일이 행 중간에서 잘린다(실측 96,692행 → 6,172행).
  ② 축소 — 부분 실패한 갱신이 원본보다 훨씬 적은 행으로 덮어쓴다.
  ③ 중복 — 비멱등 record 가 같은 (날짜,코드) 키를 여러 번 적재한다(7/30 15행 → 90행).

핵심 아이디어는 두 가지다.
  · **쓰기 전 스냅샷** — 덮어쓰기 직전 원본을 `_snapshots/` 에 보관한다. 실패하면 되돌린다.
  · **쓰기 후 검증** — replace 후 파일을 다시 읽어 행 수·마지막 줄 완결성을 확인하고,
    이상하면 **즉시 스냅샷으로 롤백**한다. replace 가 원자적이지 않으므로 사후 검증이 필수다.

조회·파일 조작 전용. 네트워크·주문 기능 없음.
"""
import csv
import glob
import os
import shutil
import time

KEEP = 5          # 파일당 보관할 스냅샷 수


def snap_dir(path):
    d = os.path.join(os.path.dirname(os.path.abspath(path)), '_snapshots')
    os.makedirs(d, exist_ok=True)
    return d


def snapshot(path, tag=None):
    """덮어쓰기 직전 원본을 보관한다. 오래된 것은 KEEP 개만 남긴다."""
    if not os.path.exists(path):
        return None
    base = os.path.basename(path)
    tag = tag or time.strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(snap_dir(path), f'{base}.{tag}')
    if not os.path.exists(dst):
        shutil.copy2(path, dst)
    old = sorted(glob.glob(os.path.join(snap_dir(path), f'{base}.*')))
    for p in old[:-KEEP]:
        try:
            os.remove(p)
        except OSError:
            pass          # 마운트가 삭제를 막아도 치명적이지 않다
    return dst


def snapshots(path):
    base = os.path.basename(path)
    return sorted(glob.glob(os.path.join(snap_dir(path), f'{base}.*')))


def line_count(path):
    try:
        with open(path, encoding='utf-8') as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def looks_complete(path, min_lines=2):
    """행 수가 충분하고 마지막 줄이 개행으로 끝나는가(절단 탐지)."""
    if not os.path.exists(path) or line_count(path) < min_lines:
        return False
    with open(path, 'rb') as f:
        if f.seek(0, os.SEEK_END) == 0:
            return False
        f.seek(-1, os.SEEK_END)
        return f.read(1) == b'\n'


def safe_replace(tmp, dst, shrink_ok=0.90):
    """tmp → dst 교체. 사후 검증에 실패하면 스냅샷으로 롤백한다.

    shrink_ok: 원본 대비 허용 최소 행 비율. 0.90 이면 10% 넘게 줄면 거부한다.
    """
    before = line_count(dst) if os.path.exists(dst) else 0
    if not looks_complete(tmp):
        raise IOError(f'safe_replace: 임시 파일이 불완전하다 — {tmp}')
    if before and line_count(tmp) < before * shrink_ok:
        raise IOError(f'safe_replace: 행 수가 {before} → {line_count(tmp)} 로 급감 — 거부')
    snap = snapshot(dst)
    os.replace(tmp, dst)
    if not looks_complete(dst) or (before and line_count(dst) < before * shrink_ok):
        if snap:
            shutil.copy2(snap, dst)
            raise IOError(f'safe_replace: 교체 후 검증 실패 → 스냅샷 롤백({os.path.basename(snap)})')
        raise IOError('safe_replace: 교체 후 검증 실패 · 롤백할 스냅샷 없음')
    return True


def restore_latest(path):
    """가장 최근 스냅샷으로 되돌린다."""
    s = snapshots(path)
    if not s:
        return None
    shutil.copy2(s[-1], path)
    return s[-1]


def dedupe_csv(path, keys):
    """(keys) 조합이 중복된 행을 뒤쪽만 남기고 제거한다. 제거 건수를 돌려준다."""
    if not os.path.exists(path):
        return 0
    with open(path, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
        fields = rows and list(rows[0]) or []
    if not rows:
        return 0
    seen = {}
    for r in rows:
        seen[tuple(r.get(k, '') for k in keys)] = r
    if len(seen) == len(rows):
        return 0
    snapshot(path)
    tmp = path + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(seen.values())
    os.replace(tmp, path)
    return len(rows) - len(seen)
