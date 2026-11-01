#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sell_ban_list.py — 매수 금지 목록 (Rule SB, 2026-09-11 사용자 승인 · 브리핑 [8-3] 참고표 + OOS shadow). 조회 전용.

규칙
  매도 신호 = 신호일 D 종가에 MA5 < MA20 < MA60 이 **처음** 성립(전일은 불성립, '역배열 진입').
  매수 금지 = 다음 거래일부터 **최대 20거래일**. 매일 아침 **전일 종가 기준 역배열이 풀렸으면 목록에서 뺀다**(조기 해제).
  브리핑일 T 목록 = D ∈ [T-20, T-1] 신호 & T-1(=데이터 마지막 날) 종가 기준 여전히 역배열.
  **보유 종목은 팔지 않는다(사용자 선택). 트랙 A~D 선정·우선순위·청산에 반영하지 않는다(참고 전용).**

근거 — fable/매도신호_매수금지_검토_2026-09-11.pdf · loop/backtest/sell_ban/ (7년 1,830일)
  목록 일평균 초과 −11.24bp/일(NW t −4.63) · R1 27/27 · fold 3/3 · 연도 8/8 · R3 EMA/주봉 재현 · R5 20일 제거 −6.4 ·
  모멘텀 5분위 통제 −5.3bp(효과 절반만 모멘텀 밖). 약점: 2025~26 편중 · 약세장/pool30 내부 R5 부호 반전.
신뢰도(목록 비중 = 목록 수 / 유니버스) — 7년 3분위, 최적화 값 아님
  ≤5.4% 강(20일 초과 −2.42%p · 하회 62.9%) / ≤17.2% 보통(−1.61%p) / 그 외 약(−0.18%p, 시장 전반 조정 — 사실상 무효)

OOS 트래커 references/sell_ban_tracker.csv — 데이터일 D 1행(목록은 다음 거래일 T 용).
  채점: 목록 종목의 T 종가→T+1 종가 수익 평균 − 같은 날 유니버스 평균 = excess_bp. avoid_bp = −excess_bp(양수 = 금지가 옳았다).
  판정: python3 judge_ready.py references/sell_ban_tracker.csv avoid_bp → N* 도달 시 (a) 평균 avoid_bp > 0 (b) 잭나이프 하한 > 0.
  2회 연속 미달이면 종결(브리핑 [8-3] 폐지). **백테스트 기간 백필 금지** — 2026-09-10 데이터일부터 센다.

사용: python3 sell_ban_list.py [--record] [--score] [--catchup] [--asof YYYYMMDD] [--flags "picks5=a,b;short10=..;mid=.."]
"""
import argparse
import csv
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from eg_picks import load_panel                   # noqa: E402  같은 패널·같은 universe_filters(187종)
from etf_sector_map import sector                 # noqa: E402
from safe_io import safe_replace                  # noqa: E402

BAN = 20
TRACK = os.path.join(REF, 'sell_ban_tracker.csv')
EG_TRACK = os.path.join(REF, 'eg_track_tracker.csv')
FIELDS = ['date', 'next_date', 'n_list', 'universe_n', 'share_pct', 'reliability', 'codes',
          'n_scored', 'excess_bp', 'avoid_bp']
REL_CUT = (5.4, 17.2)


def reliability(share):
    return '강' if share <= REL_CUT[0] else ('보통' if share <= REL_CUT[1] else '약')


def wide(p):
    C = p.pivot(index='date', columns='code', values='close').sort_index()
    return C.where(C > 0)


def signals(C):
    ma = {w: C.rolling(w, min_periods=w).mean() for w in (5, 20, 60)}
    st = ((ma[5] < ma[20]) & (ma[20] < ma[60])).fillna(False)
    sig = st & ~st.shift(1, fill_value=False)
    return st, sig


def build_list(C, st, sig, i):
    """데이터일 인덱스 i(D) 기준 → 다음 거래일 목록."""
    lo = max(0, i - BAN + 1)
    rows = []
    last = C.iloc[i]
    for code in C.columns:
        if pd.isna(last[code]) or not bool(st.iloc[i][code]):
            continue
        js = np.where(sig.iloc[lo:i + 1][code].values)[0]
        if not len(js):
            continue
        j = lo + int(js[-1])
        rows.append(dict(code=code, sig=int(C.index[j]), elapsed=i + 1 - j, remain=BAN - i + j))
    return rows, int(last.notna().sum())


def load_flags(D, arg):
    fl = {}
    def add(codes, lab):
        for c in [x for x in codes if x]:
            fl.setdefault(c, []).append(lab)
    if arg:
        lab = {'picks5': '단기실매수', 'short10': '6-1표', 'mid': '중기후보'}
        for part in arg.split(';'):
            if '=' in part:
                k, v = part.split('=', 1)
                add(v.split(','), lab.get(k, k))
    else:
        for f in sorted(glob.glob(os.path.join(HERE, 'morning_state_*.json')), reverse=True)[:5]:
            try:
                pk = json.load(open(f, encoding='utf-8')).get('picks') or {}
            except Exception:                         # noqa: BLE001
                continue
            if str(pk.get('D_for_selection')) == str(D):
                add(pk.get('picks5', '').split(','), '단기실매수')
                add([x['code'] for x in pk.get('short10', [])], '6-1표')
                add([x['code'] for x in (pk.get('mid_candidates') or [])], '중기후보')
                break
    if os.path.exists(EG_TRACK):
        for r in csv.DictReader(open(EG_TRACK, encoding='utf-8')):
            if r['date'] == str(D):
                add(r['buy_codes'].split('|'), 'EG매수신호')
                add(r['hold_codes'].split('|'), 'EG보유(매도 안 함)')
    return fl


def read_track():
    if not os.path.exists(TRACK):
        return []
    return list(csv.DictReader(open(TRACK, encoding='utf-8')))


def write_track(rows):
    rows.sort(key=lambda r: r['date'])
    tmp = TRACK + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    if os.path.exists(TRACK):
        safe_replace(tmp, TRACK)
    else:
        os.rename(tmp, TRACK)


def record(C, st, sig, i, rows_by_d):
    lst, nu = build_list(C, st, sig, i)
    D = str(int(C.index[i])); sh = len(lst) / max(nu, 1) * 100
    old = rows_by_d.get(D, {})
    rows_by_d[D] = dict(date=D, next_date='', n_list=len(lst), universe_n=nu, share_pct=f'{sh:.2f}',
                        reliability=reliability(sh), codes='|'.join(x['code'] for x in lst),
                        n_scored=old.get('n_scored', ''), excess_bp=old.get('excess_bp', ''),
                        avoid_bp=old.get('avoid_bp', ''))
    if old.get('codes') and old['codes'] != rows_by_d[D]['codes']:
        print(f'  [sb] 경고: {D} 목록이 기존 기록과 다르다(패널 보정?) — 재기록하고 채점을 비운다')
        rows_by_d[D].update(n_scored='', excess_bp='', avoid_bp='')
    return lst, nu, sh


def score(C, rows_by_d):
    idx = {int(d): k for k, d in enumerate(C.index)}
    done = 0
    for D, r in rows_by_d.items():
        if r.get('n_scored') not in ('', None):
            continue
        k = idx.get(int(D))
        if k is None or k + 2 >= len(C.index):
            continue
        t, t1 = C.iloc[k + 1], C.iloc[k + 2]
        R = (t1 / t - 1).dropna()
        codes = [c for c in r['codes'].split('|') if c and c in R.index]
        r['next_date'] = str(int(C.index[k + 1]))
        if not codes:
            r.update(n_scored=0, excess_bp='', avoid_bp='')           # 빈 목록 — 판정 표본에서 제외(judge_ready 가 빈칸을 건너뜀)
        else:
            ex = (R[codes].mean() - R.mean()) * 1e4
            r.update(n_scored=len(codes), excess_bp=f'{ex:.3f}', avoid_bp=f'{-ex:.3f}')
        done += 1
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--catchup', action='store_true', help='트래커 마지막 데이터일 이후 빠진 날을 기록(최대 30일, 멱등)')
    ap.add_argument('--asof', type=int)
    ap.add_argument('--flags', default='')
    ap.add_argument('--json', default=None)
    a = ap.parse_args()

    p = load_panel()
    names = p.drop_duplicates('code').set_index('code')['name']
    C = wide(p)
    st, sig = signals(C)
    i = len(C.index) - 1 if not a.asof else int(np.where(C.index == a.asof)[0][0])
    D = int(C.index[i])
    rows = {r['date']: r for r in read_track()}

    if a.catchup and rows:
        last = max(int(d) for d in rows)
        todo = [k for k, d in enumerate(C.index) if int(d) > last and k < i][-30:]
        for k in todo:
            record(C, st, sig, k, rows)
        if todo:
            print(f'  [sb] catchup {len(todo)}일 기록')

    lst, nu = build_list(C, st, sig, i)
    sh = len(lst) / max(nu, 1) * 100
    if a.record:
        record(C, st, sig, i, rows)
    if a.score:
        n = score(C, rows)
        if n:
            print(f'  [sb] 채점 {n}행')
    if a.record or a.score or a.catchup:
        write_track(list(rows.values()))

    fl = load_flags(D, a.flags)
    rel = reliability(sh)
    relx = {'강': '강 — 개별 섹터 붕괴 위주(7년: 금지 종목 20일 초과 −2.42%p · 하회 62.9%)',
            '보통': '보통(7년: 20일 초과 −1.61%p · 하회 60.8%)',
            '약': '약 — 시장 전반 조정기(7년: 20일 초과 −0.18%p, 사실상 무효)'}[rel]
    out = []
    for x in lst:
        out.append(dict(x, name=names.get(x['code'], x['code']), sec=sector(names.get(x['code'], '')),
                        mom20=float((C.iloc[i][x['code']] / C.iloc[i - 20][x['code']] - 1) * 100)
                        if i >= 20 and pd.notna(C.iloc[i - 20][x['code']]) else None,
                        flag='·'.join(fl.get(x['code'], []))))
    out.sort(key=lambda r: (-r['remain'], r['sec'], r['name']))
    hit = [r for r in out if r['flag']]
    scored = [r for r in rows.values() if r.get('avoid_bp') not in ('', None)]
    oos = dict(days=len(scored), start=min(rows) if rows else None,
               avoid_bp=round(float(np.mean([float(r['avoid_bp']) for r in scored])), 3) if scored else None)
    blk = dict(D=D, n=len(out), universe_n=nu, share_pct=round(sh, 2), reliability=rel, reliability_text=relx,
               ban_days=BAN, rows=out, overlaps=[dict(code=r['code'], name=r['name'], flag=r['flag']) for r in hit],
               by_sector=pd.Series([r['sec'] for r in out]).value_counts().to_dict() if out else {}, oos=oos)
    jp = a.json or os.path.join(HERE, f'sell_ban_{D}.json')
    json.dump(blk, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'[매수 금지 목록 · Rule SB] D={D} 기준(다음 거래일용) · {len(out)}종 / 유니버스 {nu}종 = 비중 {sh:.1f}% → 신뢰도 {relx}')
    print('   규칙: 역배열 진입(MA5<MA20<MA60 첫 성립) 후 최대 20거래일 매수 금지 · 역배열 해소 시 조기 해제 · 보유 종목은 팔지 않음 · 선정 미반영')
    for r in out:
        m = f"{r['mom20']:+.1f}%" if r['mom20'] is not None else '—'
        print(f"   {r['sec']:8s} {r['name'][:28]:30s} {r['code']:6s} 신호 {r['sig']} 남은금지 최대 {r['remain']:>2d}일 mom20 {m:>7s}"
              + (f"  ★{r['flag']}" if r['flag'] else ''))
    print(f'   ※ 오늘 추천·후보·트랙 D 와 겹침 {len(hit)}건' + (': ' + ', '.join(f"{r['name']}({r['flag']})" for r in hit) if hit else ''))
    if oos['days']:
        print(f"   ※ OOS 누적 {oos['days']}일(시작 {oos['start']}) · 평균 avoid {oos['avoid_bp']:+.2f}bp/일(양수 = 금지가 옳았다) — "
              'judge_ready.py references/sell_ban_tracker.csv avoid_bp')
    else:
        print(f"   ※ OOS 채점 0일(기록 시작 {oos['start'] or D}) — 다음다음 거래일 종가부터 채점된다")
    print(f'   → {os.path.basename(jp)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
