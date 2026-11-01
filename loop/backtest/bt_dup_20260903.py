#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_dup_20260903.py — Rule DUP(동일 기초지수 중복 제거) 정식 검정 · 7년 패널.

배경 — 2026-09-02 로그가 사전 등록한 '다음 회차 우선 시도축 ①'.
  9/1 채점에서 픽5 중 232080(TIGER 코스닥150)·270810(RISE 코스닥150)이 **사실상 같은 상품**
  이었고 둘이 동반 -2.94% 하며 -3.034%p 대패의 직접 원인이 됐다.

  기존 중복제거 계열은 전부 기각 상태다 — TD(테마 집중도)·XC(실현상관 0.85~0.95)·
  NMC(종목명 토큰 클러스터). 되살리려면 **새 정의**로 R1~R5 를 처음부터 밟아야 한다(N +1).
  이번 정의는 종목명·상관·테마가 아니라 **KRX 가 부여한 기초지수(base_idx)** 다 —
  "같은 지수를 추종하면 같은 상품"이라는 기계적·객관적 정의이며 판단이 개입하지 않는다.

규칙 DUP: 선정 순서대로 훑되 **정규화된 기초지수당 최대 cap 종**만 담고, 걸린 후보는
  건너뛰고 차순위로 채운다. 5종을 못 채우면 제약을 풀어 채운다(관망하지 않는다).
  · 적용 레이어는 '선정'뿐. 유니버스·Rule H·비용(0)·집행 전부 그대로.
  · 입력은 정적 매핑이라 **선정 시각 T 06:00 에 100% 확보 가능**(실전 조달 검정 통과).

축(R1 고원): cap ∈ {1,2,3} × 정규화 ∈ {N0 원문, N1 TR/괄호/지수 접미 제거}
기준선 2종: MOM(mom20+RuleH) · **LV(v2.9 현행 확정방법)** ← 1차 판정 대상
"""
import csv, os, random, re, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_base_long_20260819 as L

KRX = os.path.join(HERE, 'krx_etf_panel.csv')


def load_baseidx():
    m = {}
    for row in csv.DictReader(open(KRX, encoding='utf-8')):
        c = row['code']
        if c not in m or row['date'] > m[c][0]:
            m[c] = (row['date'], row['base_idx'])
    return {c: v[1] for c, v in m.items()}


def norm(s, level):
    if level == 0:
        return s
    s = re.sub(r'\([^)]*\)', ' ', s)              # 괄호 내용 제거 (TR)·(H)·(합성)
    s = re.sub(r'\b(TR|PR|Total Return)\b', ' ', s, flags=re.I)
    s = s.replace('지수', ' ')
    return re.sub(r'\s+', '', s)


def cum(rs):
    x, o = 1.0, []
    for r in rs:
        x *= (1 + r / 100)
        o.append(x)
    return o


def mdd(cv):
    pk, w = cv[0], 0.0
    for x in cv:
        pk = max(pk, x)
        w = min(w, x / pk - 1)
    return w * 100


def prof(v, label=''):
    c = cum(v)
    n = len(v)
    sd = statistics.stdev(v)
    return {'label': label, 'n': n, 'cum': (c[-1] - 1) * 100,
            'cagr': (c[-1] ** (252 / n) - 1) * 100, 'mdd': mdd(c),
            'sharpe': statistics.mean(v) / sd * 252 ** 0.5, 'mean': statistics.mean(v)}


def tstat(v):
    return statistics.mean(v) / (statistics.stdev(v) / len(v) ** 0.5)


def main():
    px, names = L.load()
    dates = sorted({d for c in px for d in px[c]})
    cands = L.build(px, names, dates)
    bidx = load_baseidx()

    rets = defaultdict(dict)
    for c in px:
        ds = sorted(px[c])
        for a, b in zip(ds, ds[1:]):
            x, y = px[c][a], px[c][b]
            if x and y:
                rets[c][b] = (y / x - 1) * 100

    def sigma(c, i, k=20):
        v = [rets[c].get(dates[j]) for j in range(max(1, i - k + 1), i + 1)]
        v = [x for x in v if x is not None]
        return statistics.stdev(v) if len(v) >= max(5, k // 3) else None

    def order_mom(cd, i):
        return [c for _, c in cd]

    def order_lv(cd, i, pool=30):
        sc = []
        for _, c in cd[:pool]:
            s = sigma(c, i)
            if s is not None:
                sc.append((s, c))
        if len(sc) < L.NPICK:
            return [c for _, c in cd]
        sc.sort()
        rest = [c for _, c in cd if c not in {x for _, x in sc}]
        return [c for _, c in sc] + rest

    def dedup(order, cap, level, imap):
        picks, cnt, skipped = [], defaultdict(int), []
        for c in order:
            if len(picks) >= L.NPICK:
                break
            g = imap.get(c)
            if g is not None and cnt[g] >= cap:
                skipped.append(c)
                continue
            picks.append(c)
            if g is not None:
                cnt[g] += 1
        for c in skipped + order:                 # 5종 미달 시 제약 해제 보충
            if len(picks) >= L.NPICK:
                break
            if c not in picks:
                picks.append(c)
        return picks[:L.NPICK]

    def run(orderf, cap=None, level=0, imap=None):
        out, act = [], 0
        for i, d in enumerate(dates[:-1]):
            nxt = dates[i + 1]
            cd = cands.get(d)
            if not cd or len(cd) < L.NPICK:
                continue
            od = orderf(cd, i)
            base = od[:L.NPICK]
            picks = base if cap is None else dedup(od, cap, level, imap)
            rs = [L.fwd(px, c, d, nxt) for c in picks]
            rs = [x for x in rs if x is not None]
            if len(rs) < L.NPICK:
                continue
            if cap is not None and set(picks) != set(base):
                act += 1
            out.append((d, sum(rs) / len(rs)))
        return out, act

    imaps = {lv: {c: norm(g, lv) for c, g in bidx.items()} for lv in (0, 1)}

    bench = {}
    for i, d in enumerate(dates[:-1]):
        r = rets[L.BENCH].get(dates[i + 1])
        if r is not None:
            bench[d] = r

    def excess(rows):
        return [(d, p - bench[d]) for d, p in rows if d in bench]

    print('=' * 78)
    print('Rule DUP — 동일 기초지수 중복 제거 · 7년 패널')
    print('=' * 78)
    dupg = defaultdict(list)
    for c, g in imaps[0].items():
        if c in px:
            dupg[g].append(c)
    print(f'기초지수 매핑 {len(bidx)}종 · 패널 내 중복군 '
          f'{sum(1 for v in dupg.values() if len(v)>1)}개\n')

    for bname, orderf in (('MOM', order_mom), ('LV', order_lv)):
        b_rows, _ = run(orderf)
        b_ex = excess(b_rows)
        bp = prof([x for _, x in b_rows], f'{bname} baseline')
        print(f'--- 기준선 {bname} · 채점 {len(b_ex)}일 '
              f'({b_ex[0][0]}~{b_ex[-1][0]}) ---')
        print(f'  누적{bp["cum"]:+8.1f}% CAGR{bp["cagr"]:+6.1f}% MDD{bp["mdd"]:7.1f}% '
              f'Sharpe{bp["sharpe"]:5.2f} · 초과평균 {statistics.mean([x for _,x in b_ex]):+.4f}%p '
              f't{tstat([x for _,x in b_ex]):+.2f}')
        bmap = dict(b_ex)
        print(f'\n  {"변형":18s}{"발동일":>7s}{"초과평균":>10s}{"Δ평균":>10s}{"t(Δ)":>8s}'
              f'{"중앙값Δ":>9s}{"누적":>9s}{"MDD":>8s}{"Sharpe":>8s}')
        for lv in (0, 1):
            for cap in (1, 2, 3):
                rows, act = run(orderf, cap, lv, imaps[lv])
                ex = excess(rows)
                p = prof([x for _, x in rows], '')
                dif = [v - bmap[d] for d, v in ex if d in bmap]
                print(f'  N{lv} cap{cap:<12d}{act:7d}'
                      f'{statistics.mean([x for _,x in ex]):+10.4f}'
                      f'{statistics.mean(dif):+10.4f}{tstat(dif):+8.2f}'
                      f'{statistics.median(dif):+9.4f}'
                      f'{p["cum"]:+9.1f}{p["mdd"]:+8.1f}{p["sharpe"]:+8.2f}')
        print()

    # ── 최선 변형 정밀 검정 (LV 기준, N1 cap1)
    print('=' * 78)
    print('정밀 검정 — LV × N1 cap1 (1차 판정 대상)')
    print('=' * 78)
    b_rows, _ = run(order_lv)
    bmap = dict(excess(b_rows))
    rows, act = run(order_lv, 1, 1, imaps[1])
    ex = excess(rows)
    dif = [(d, v - bmap[d]) for d, v in ex if d in bmap]
    dv = [x for _, x in dif]
    n = len(dv)
    print(f'  발동 {act}일 / {n}일 ({act/n*100:.1f}%) · Δ평균 {statistics.mean(dv):+.4f}%p '
          f't{tstat(dv):+.2f} · 중앙값 {statistics.median(dv):+.4f} · 승 '
          f'{sum(1 for x in dv if x>0)}/{sum(1 for x in dv if x!=0)}')

    print('\n  [R2] 3분할 fold')
    k = n // 3
    for fi, seg in enumerate((dv[:k], dv[k:2 * k], dv[2 * k:]), 1):
        print(f'    fold{fi}  Δ평균 {statistics.mean(seg):+.4f}%p  t{tstat(seg):+.2f}')

    print('\n  [R5] 꼬리 기여도')
    s = sorted(dv, reverse=True)
    tot = sum(s)
    for k2 in (1, 3, 5, 10):
        rem = s[k2:]
        print(f'    상위{k2:2d}일 제거 → Δ평균 {statistics.mean(rem):+.4f}%p '
              f'(기여 {sum(s[:k2])/tot*100 if tot else 0:.1f}%)')
    w = sorted(dv)
    wl = w[int(n * 0.05):int(n * 0.95)]
    print(f'    윈저화(5~95%) 평균 {statistics.mean(wl):+.4f}%p')

    print('\n  [R4] 플라시보 — 기초지수 라벨 무작위 셔플 200회')
    codes = [c for c in imaps[1] if c in px]
    labels = [imaps[1][c] for c in codes]
    rng = random.Random(20260903)
    obs = statistics.mean(dv)
    null = []
    for _ in range(200):
        sh = labels[:]
        rng.shuffle(sh)
        im = dict(zip(codes, sh))
        r2, _a = run(order_lv, 1, 1, im)
        e2 = excess(r2)
        d2 = [v - bmap[d] for d, v in e2 if d in bmap]
        null.append(statistics.mean(d2))
    p = sum(1 for x in null if x >= obs) / len(null)
    print(f'    관측 {obs:+.4f}%p · 귀무 평균 {statistics.mean(null):+.4f}%p '
          f'sd {statistics.stdev(null):.4f} · 경험적 p = {p:.3f}')

    print('\n  [발동일 한정] 실제로 픽이 바뀐 날만')
    onr, _ = run(order_lv, 1, 1, imaps[1])
    one = dict(excess(onr))
    ond = [(d, one[d] - bmap[d]) for d in one if d in bmap and one[d] != bmap[d]]
    if ond:
        ov = [x for _, x in ond]
        print(f'    {len(ov)}일 · 평균 {statistics.mean(ov):+.4f}%p · t{tstat(ov):+.2f} '
              f'· 승 {sum(1 for x in ov if x>0)}/{len(ov)}')


if __name__ == '__main__':
    main()
