#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_regime_long_20260819.py — 조건부 국면 전환을 **7년 패널(1,779일)** 에서 재검정.

왜 지금인가
  2026-08-14 세션이 조건부 국면 전환을 2년 패널(537일)에서 검정하고 이렇게 남겼다:
  "**병목은 표본.** 규칙 간 일별 차이 sd 2.407%p → +0.10%p 효과 탐지에 상태당 949일 필요.
   현재 상태당 179일." 그리고 "**미사용 자산: panel_ohlc_long.csv 1,800거래일(2019-04~2026-07),
  2020 코로나·2022 베어 포함. 3.35배.**"
  → 그 자산을 지금 쓴다. 상태당 표본이 약 590일로 **3.3배**가 된다.

왜 이 축인가 (2026-08-19 baseline 프로파일이 근거를 줬다)
  7년 baseline 은 벤치 수익률 5분위에 대해 초과가 **완전 단조**다:
  Q1(-2.07%) +0.5663%p → Q5(+2.13%) **-0.5948%p**. 즉 baseline 은 저베타 구조이고,
  **Q5(대형 상승일) 손실이 가장 큰 단일 레버**다. 상시 고베타는 2026-08-14 에 기각됐지만
  (알파·베타 단조 상충) **조건부**는 표본 부족으로 판정이 유보돼 있었다.

설계
  국면 정의 3종(전부 D 종가까지 정보) × 후보 규칙 5종.
  **워크포워드**: 각 시점에서 과거만 보고 상태별 최선 규칙을 고른다(룩어헤드 없음).
  ORACLE(사후 최선)은 상한선 참고용이며 승격 근거가 아니다.
  가드: 3분할 + fold3 + **R5 꼬리 기여도**(2026-08-18 신설).
"""
import os, statistics, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_base_long_20260819 as L

BURN = 250          # 워크포워드 번인(첫 1년은 baseline 고정)
MINOBS = 40         # 상태별 최소 관측이 쌓여야 규칙을 바꾼다


def vol(px, code, dates, i, k=20):
    rs = []
    for j in range(max(1, i - k + 1), i + 1):
        a, b = px[code].get(dates[j - 1]), px[code].get(dates[j])
        if a and b:
            rs.append(b / a - 1)
    return statistics.stdev(rs) * 100 if len(rs) > 2 else None


def main():
    px, names = L.load()
    dates = sorted({d for c in px for d in px[c]})
    cands = L.build(px, names, dates)
    pos = {d: i for i, d in enumerate(dates)}

    # ── 후보 규칙 5종 (전부 D 종가까지 정보)
    def r_mom(cd, d):
        return [c for _, c in cd[:L.NPICK]]

    def r_rev(cd, d):
        return [c for _, c in cd[-L.NPICK:]]

    def r_mom5(cd, d):
        i = pos[d]
        sc = []
        for _, c in cd[:30]:
            a, b = px[c].get(dates[i - 5]), px[c].get(d)
            if a and b:
                sc.append((b / a - 1, c))
        sc.sort(reverse=True)
        return [c for _, c in sc[:L.NPICK]] if len(sc) >= L.NPICK else r_mom(cd, d)

    def r_lowvol(cd, d):
        i = pos[d]
        sc = []
        for _, c in cd[:30]:
            v = vol(px, c, dates, i)
            if v:
                sc.append((v, c))
        sc.sort()
        return [c for _, c in sc[:L.NPICK]] if len(sc) >= L.NPICK else r_mom(cd, d)

    def r_hivol(cd, d):      # 고변동 = 고베타 대용(베타 추정보다 안정적)
        i = pos[d]
        sc = []
        for _, c in cd[:30]:
            v = vol(px, c, dates, i)
            if v:
                sc.append((v, c))
        sc.sort(reverse=True)
        return [c for _, c in sc[:L.NPICK]] if len(sc) >= L.NPICK else r_mom(cd, d)

    RULES = [('MOM', r_mom), ('REV', r_rev), ('MOM5', r_mom5),
             ('LOWVOL', r_lowvol), ('HIVOL', r_hivol)]

    # ── 규칙별 일별 초과 미리 계산
    day = []
    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        bm = L.fwd(px, L.BENCH, d, nxt)
        cd = cands.get(d)
        if bm is None or not cd or len(cd) < 2 * L.NPICK:
            continue
        rec = {}
        for nm, f in RULES:
            rs = [L.fwd(px, c, d, nxt) for c in f(cd, d)]
            rs = [x for x in rs if x is not None]
            if len(rs) < L.NPICK:
                rec = None
                break
            rec[nm] = sum(rs) / len(rs) - bm
        if rec:
            day.append((d, bm, rec))
    print(f'채점 {len(day)}일 ({day[0][0]}~{day[-1][0]}) · 규칙 {len(RULES)}종\n')

    print('=== 규칙별 무조건 성과 (7년) ===')
    for nm, _ in RULES:
        v = [r[nm] for _, _, r in day]
        print(f'  {nm:7s} 평균 {statistics.mean(v):+.4f}%p · 승률 '
              f'{sum(1 for x in v if x>0)/len(v)*100:4.1f}% · sd {statistics.stdev(v):.2f}')

    # ── 국면 정의 3종 (D 종가까지)
    bch = {}
    for i, d in enumerate(dates):
        bch[d] = px[L.BENCH].get(d)

    def st_idx5(d):
        i = pos[d]
        a, b = bch.get(dates[max(0, i - 5)]), bch.get(d)
        if not (a and b):
            return None
        r = (b / a - 1) * 100
        return 0 if r < -2 else (2 if r > 2 else 1)

    def st_trend(d):
        i = pos[d]
        a, b = bch.get(dates[max(0, i - 20)]), bch.get(d)
        if not (a and b):
            return None
        r = (b / a - 1) * 100
        return 0 if r < -3 else (2 if r > 3 else 1)

    def st_vol(d):
        i = pos[d]
        v = vol(px, L.BENCH, dates, i)
        if v is None:
            return None
        return v            # 연속값 → 아래에서 과거 분위로 이산화

    STATES = [('지수5일', st_idx5), ('추세20일', st_trend)]

    print('\n=== 워크포워드 조건부 전환 (룩어헤드 없음) ===')
    results = {}
    for sname, sf in STATES:
        labels = [sf(d) for d, _, _ in day]
        wf, oracle, chosen = [], [], []
        hist = defaultdict(lambda: defaultdict(list))
        for k, (d, bm, rec) in enumerate(day):
            s = labels[k]
            pick = 'MOM'
            if k >= BURN and s is not None:
                h = hist[s]
                if h and min(len(v) for v in h.values()) >= MINOBS:
                    pick = max(h, key=lambda nm: sum(h[nm]) / len(h[nm]))
            wf.append(rec[pick])
            chosen.append(pick)
            oracle.append(max(rec.values()))
            if s is not None:
                for nm, _ in RULES:
                    hist[s][nm].append(rec[nm])
        base = [r['MOM'] for _, _, r in day]
        n = len(wf)
        h = n // 2
        f3 = [sum(wf[i * n // 3:(i + 1) * n // 3]) / len(wf[i * n // 3:(i + 1) * n // 3])
              for i in range(3)]
        b3 = [sum(base[i * n // 3:(i + 1) * n // 3]) / len(base[i * n // 3:(i + 1) * n // 3])
              for i in range(3)]
        gain = [w - b for w, b in zip(wf, base)]
        cnt = defaultdict(int)
        for c in chosen[BURN:]:
            cnt[c] += 1
        print(f'\n  [{sname}]  ORACLE 상한 {statistics.mean(oracle):+.4f}%p/일')
        print(f'    WALK {statistics.mean(wf):+.4f} vs MOM {statistics.mean(base):+.4f} '
              f'→ 이득 {statistics.mean(gain):+.4f}%p/일')
        print(f'    train {statistics.mean(wf[:h]):+.4f}/{statistics.mean(base[:h]):+.4f} · '
              f'test {statistics.mean(wf[h:]):+.4f}/{statistics.mean(base[h:]):+.4f}')
        print(f'    fold  ' + ' '.join(f'{f3[i]:+.4f}/{b3[i]:+.4f}' for i in range(3)) +
              f'  → 초과 {sum(1 for i in range(3) if f3[i] > b3[i])}/3')
        print(f'    선택 분포(번인 후): ' + ' '.join(f'{k}:{v}' for k, v in
                                                sorted(cnt.items(), key=lambda x: -x[1])))
        # R5 꼬리
        g = sorted(gain, reverse=True)
        tot = sum(g)
        if abs(tot) > 1e-9:
            r5 = [(k, (tot - sum(g[:k])) / (n - k)) for k in (1, 3, 5, 10)]
            print('    R5 꼬리: ' + ' · '.join(f'상위{k}일 제거 {v:+.4f}' for k, v in r5) +
                  f' · 중앙값 {statistics.median(gain):+.4f}')
        results[sname] = statistics.mean(gain)

    print('\n=== 벤치 5분위 × 규칙 — 어떤 국면에서 무엇이 최선인가 (사후, 상한 참고용) ===')
    srt = sorted(day, key=lambda x: x[1])
    q = len(srt) // 5
    print(f'  {"분위":5s} {"벤치평균":>8s} ' + ' '.join(f'{nm:>8s}' for nm, _ in RULES))
    for i in range(5):
        seg = srt[i * q:(i + 1) * q] if i < 4 else srt[4 * q:]
        bm = statistics.mean(b for _, b, _ in seg)
        line = f'  Q{i+1:<4d} {bm:+7.2f}% '
        for nm, _ in RULES:
            line += f'{statistics.mean(r[nm] for _, _, r in seg):+8.3f} '
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
