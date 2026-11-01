#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eg_liq_shadow.py — Rule EG-LIQ shadow (2026-09-17 사용자 승인 등록, 조회 전용).

가설: 트랙 D(Rule EG) 매수 신호 중 **거래대금 상위 100 밖(低유동) 신호를 빼면** 성과가 좋아진다.
근거(CLAUDE.md §5 트랙 D): 187종 유니버스 R5 상위3일 제거 −0.0866(기각) vs 거래대금 상위 100 +0.2396(통과).
  저유동 그룹만 일별차 −0.5229·중앙 −0.0530. 유동성이 낮으면 소수 체결로 `V>=VA*1.3` 이 충족돼 게이트가 무력해진다.
  ※ 이 R5 비교는 v1.2(눌림 10일) 이전 5일 눌림 기준이다 — OOS 에서 v1.2 수식으로 다시 확인하는 것이 이 shadow 의 목적.

기록: `eg_track_tracker.csv` 의 buy_codes(그날 전체 신호)를 읽어, 신호일 D 기준 거래대금 상위 100
(eg_picks.liquid_top, 표시용과 같은 함수) 여부로 나눈다. **트랙 D 선정·표시·청산은 바꾸지 않는다.**
채점: 신호일 D 종가 → D+20거래일 종가(v1.1 청산 규칙), 동일가중.
  all_ret = 전체 신호 / liq_ret = 유동 신호만(없으면 현금 0) / liq_minus_all = liq_ret − all_ret.
  이벤트 = 低유동 신호가 1건 이상 있던 날(has_illiq=1) — 그 외 날은 두 포트폴리오가 같다.

판정: `judge_ready.py references/eg_liq_shadow.csv liq_minus_all --event has_illiq` 판정 가능 시
(a) 평균 > 0 (b) 잭나이프 하한 > 0. **2회 연속 미달이면 종결.** 3회 연속 기록 결손도 종결 후보.
**파라미터 동결**: 상위 100 · 20거래일 · D 종가. START 는 EG OOS_START(20260828, 설계 패널 이후 첫 신호일).

사용: python3 eg_liq_shadow.py [--report]   (기록·채점을 함께, 멱등)
"""
import argparse, csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.dirname(HERE)
sys.path.insert(0, HERE)
TRACK = os.path.join(REF, 'eg_liq_shadow.csv')
EG = os.path.join(REF, 'eg_track_tracker.csv')
START = 20260828; HOLD = 20; LIQ_N = 100; BENCH = '069500'
FIELDS = ['date', 'n_sig', 'liq_codes', 'illiq_codes', 'has_illiq', 'all_ret', 'liq_ret',
          'bench_ret', 'liq_minus_all']


def load():
    return list(csv.DictReader(open(TRACK, encoding='utf-8'))) if os.path.exists(TRACK) else []


def save(rows):
    import safe_io
    tmp = TRACK + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for r in sorted(rows, key=lambda x: x['date']):
            w.writerow({k: r.get(k, '') for k in FIELDS})
    safe_io.safe_replace(tmp, TRACK)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--report', action='store_true'); a = ap.parse_args()
    sig = [r for r in csv.DictReader(open(EG, encoding='utf-8'))
           if int(r['date']) >= START and r['buy_codes']]
    rows = load(); byd = {r['date']: r for r in rows}
    need_rec = [r for r in sig if r['date'] not in byd]
    need_score = [r for r in rows if not r.get('all_ret')]
    if need_rec or need_score:
        import eg_picks
        p = eg_picks.load_panel()
        for s in need_rec:
            liq = eg_picks.liquid_top(p, int(s['date']), LIQ_N)
            cs = s['buy_codes'].split('|')
            L = [c for c in cs if c in liq]; I = [c for c in cs if c not in liq]
            r = dict(date=s['date'], n_sig=len(cs), liq_codes='|'.join(L), illiq_codes='|'.join(I),
                     has_illiq=int(bool(I)))
            rows.append(r); need_score.append(r)
            print(f"  [eg-liq] {s['date']} 신호 {len(cs)} · 유동 [{r['liq_codes'] or '-'}] · 低유동 [{r['illiq_codes'] or '-'}]")
        cl = p.pivot_table(index='date', columns='code', values='close')
        ds = list(cl.index)
        for r in need_score:
            d = int(r['date'])
            if d not in ds or ds.index(d) + HOLD >= len(ds):
                continue
            e = ds[ds.index(d) + HOLD]

            def ret(codes):
                v = [(cl.at[e, c] / cl.at[d, c] - 1) * 100 for c in codes if c in cl and cl.at[d, c] == cl.at[d, c]
                     and cl.at[e, c] == cl.at[e, c]]
                return sum(v) / len(v) if v and len(v) == len(codes) else None
            L = [c for c in r['liq_codes'].split('|') if c]; A = L + [c for c in r['illiq_codes'].split('|') if c]
            ar, br = ret(A), ret([BENCH])
            lr = ret(L) if L else 0.0
            if ar is None or lr is None or br is None:
                continue
            r.update(all_ret=f'{ar:.4f}', liq_ret=f'{lr:.4f}', bench_ret=f'{br:.4f}', liq_minus_all=f'{lr - ar:.4f}')
            print(f"  [eg-liq] {r['date']} 채점(D+{HOLD}={e}) 전체 {ar:+.2f}% · 유동만 {lr:+.2f}% · 차 {lr - ar:+.2f}%p")
        save(rows)
    sc = [r for r in rows if r.get('all_ret')]
    ev = [float(r['liq_minus_all']) for r in sc if r['has_illiq'] == '1']
    print(f"  [eg-liq] 기록 {len(rows)}일 · 채점 {len(sc)}일 · 이벤트(低유동 포함일) {len(ev)}일"
          + (f" · 평균 차 {sum(ev) / len(ev):+.3f}%p" if ev else '') + ' — 판정은 judge_ready.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
