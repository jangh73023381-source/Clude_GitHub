# -*- coding: utf-8 -*-
"""2026-08-13 루프 3~5단계 — distinct 5축.

동기: 2026-08-13 채점(D=20260812)에서 트랙 A 는 1차 P&L **-0.860%(비용후)** →
코스피 대비 **-4.540%p**, KODEX200 대비 -4.875%p. 보조 이진 **0/5**
(순위 186·123·127·133·184/187, 컷오프 상위19위 +4.16%).

**8/12 와 같은 구조가 이틀 연속 반복됐다.** 그날 상위 20위를 반도체·IT 계열이 독식했고
(TIGER 200IT +6.27%, KODEX AI반도체TOP2 +5.95%, HANARO Fn K-반도체 +5.89% …) 이들의
**D-1 mom20 은 -8% ~ -15%**, 반대로 우리 픽(바이오·로봇)의 mom20 은 +12% ~ +24%였다.
최하위 5종 중 4종이 바이오다. 즉 모멘텀 랭킹이 정확히 **반대편**을 가리켰다.

검증관(2026-08-12)이 지정한 다음 회차 우선 시도축 (a)(b)를 iteration 1~2 로 그대로 검정하고,
남은 3축은 미시도 축으로 채운다.

 · iteration 1 Rule MR2 — **mom20 하위군의 단기 반등 상위 1슬롯 확보**. 검증관 지정 (a).
   7/28 기각된 MRV 는 *mom20 상위 풀 내부*의 전일역전 재정렬(재랭킹)이었고, 7/15 기각된 CC 는
   *교집합 필터*였다. MR2 는 **상위 풀 밖(하위 분위)에서 슬롯을 강제로 끌어올리는 할당**이라
   메커니즘이 다르다. 국면 무조건 버전과 조건부 버전(벤치 약세 / 횡단면 분산 상위)을 함께 본다.
   **이 축이 실패하면 반전 계열은 슬롯 할당 경로까지 소진되므로 종결한다.**
 · iteration 2 Rule RCG — **베타조정 잔차 모멘텀 λ 고원 재탐색**. 검증관 지정 (b).
   8/12 회차에서 λ0.5·λ2.0 이 3분할을 통과했으나 λ1.0 은 미통과라 고원이 없었다.
   0.25/0.5/0.75/1.0/1.5/2.0/3.0 격자로 통과 구간이 **연결돼 있는지** 확인한다.
   연결돼 있지 않으면 RC 축을 종결한다.
 · iteration 3 Rule CST — **모멘텀 경로 품질(일관성)**. 20일 수익률의 *크기*가 같아도 20일 중
   상승일 비율이 높은 종목이 더 견고하다는 가설. 7/13 기각된 X/X2(변동성으로 나눈 위험조정
   모멘텀)는 **분산 크기**를 썼고 CST 는 **부호의 빈도**를 쓴다 — 스케일 불변이라 다른 축이다.
 · iteration 4 Rule BWL — **레짐 조건부 장기 룩백 전환**(벤치 mom20 < 0 이면 mom20 → mom60).
   7/15 기각된 EE 와 8/12 기각된 DSC 는 국면에서 룩백을 **짧게**(mom5) 바꿨고 둘 다 유해했다.
   BWL 은 같은 국면에서 **길게** 바꾼다 — 방향이 반대이므로 미시도 축이다.
 · iteration 5 Rule XSN — **섹터(종목명 토큰) 내 z 정규화 후 횡단면 랭킹**.
   7/28 기각된 NMC 는 섹터당 **개수 상한**(cap)이었고, XSN 은 상한 없이 **점수 변환**만 한다.
   테마 전체가 달아오른 날 그 테마가 5슬롯을 다 먹는 것을 완화하되 잘라내지는 않는다.

1차 지표 = v2.3 P&L (픽5 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과 + 잭나이프 하한 > baseline 일 때만 후보 승격.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용. 조회 전용.
"""
import os
import re
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402
from bt_loop_20260806 import jackknife, tstat  # noqa: E402
from bt_loop_20260812 import build_xsd, xsd_pctl  # noqa: E402
import bt_loop_20260812 as P12  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0812.csv')
B.MINP = 0

TOKENS = ['반도체', '바이오', '로봇', '방산', '우주', '조선', '원자력', '2차전지', '전지',
          '건설', '화장품', '증권', '은행', '금융', '자동차', '태양광', '신재생', '전력',
          'IT', '인터넷', '게임', '헬스케어', '철강', '화학', '리츠', '고배당', '배당',
          '가치', '성장', '중공업', '기계', '소비재', '미디어', '통신']


def token_of(nm):
    n = (nm or '').replace(' ', '')
    for t in TOKENS:
        if t in n:
            return t
    return '기타'


# ---------------------------------------------------------------- iteration 1
def mr2_sel(cand, px=None, d=None, di=None, dates=None,
            q=25, k=3, nslot=1, cond=None, **_):
    """Rule MR2 — mom20 하위 q% 풀에서 최근 k일 반등 상위를 nslot 개 강제 확보."""
    base = B.base_sel(cand)
    if cond == 'bench':                       # 벤치 mom20 < 0 인 날만
        m = B.mom(px, B.BENCH, d, di, dates, 20)
        if m is None or m >= 0:
            return base
    elif cond == 'xsd':                       # 횡단면 분산 상위 p80 인 날만
        if not xsd_pctl(d, 80):
            return base
    ranked = sorted(cand, key=lambda x: x['mom'])
    n = max(5, int(len(ranked) * q / 100.0))
    pool = ranked[:n]
    scored = []
    for x in pool:
        r = B.mom(px, x['code'], d, di, dates, k)
        if r is not None:
            scored.append((x['code'], r))
    if not scored:
        return base
    scored.sort(key=lambda t: -t[1])
    add = [c for c, _ in scored if c not in base][:nslot]
    if not add:
        return base
    return base[:5 - len(add)] + add


# ---------------------------------------------------------------- iteration 2
def rcg_sel(cand, px=None, d=None, di=None, dates=None, lam=1.0, w=60, **_):
    """Rule RCG — 잔차 모멘텀 = mom20 - λ·β·(벤치 mom20). λ 고원 확인용."""
    bm = B.mom(px, B.BENCH, d, di, dates, 20)
    if bm is None:
        return B.base_sel(cand)
    scored = []
    for x in cand:
        b = P12._beta(px, x['code'], d, di, dates, w)
        if b is None:
            continue
        scored.append((x['code'], x['mom'] - lam * b * bm))
    if len(scored) < 5:
        return B.base_sel(cand)
    return [c for c, _ in sorted(scored, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 3
def _updays(px, c, d, di, dates, k=20):
    i = di[d]
    if i < k:
        return None
    up = tot = 0
    for j in range(i - k + 1, i + 1):
        a, b = px[c].get(dates[j - 1]), px[c].get(dates[j])
        if a and b:
            tot += 1
            up += 1 if b > a else 0
    return (up / tot) if tot >= k * 0.8 else None


def cst_sel(cand, px=None, d=None, di=None, dates=None, mode='blend', wgt=0.5, **_):
    """Rule CST — 모멘텀 경로 품질(20일 상승일 비율)로 랭킹 보정."""
    rows = []
    for x in cand:
        u = _updays(px, x['code'], d, di, dates, 20)
        if u is None:
            continue
        rows.append((x['code'], x['mom'], u))
    if len(rows) < 10:
        return B.base_sel(cand)
    if mode == 'filter':                      # 상승일 비율 중앙값 이상만 남기고 mom20 랭킹
        med = statistics.median(u for _, _, u in rows)
        keep = [(c, m) for c, m, u in rows if u >= med]
        if len(keep) < 5:
            return B.base_sel(cand)
        return [c for c, _ in sorted(keep, key=lambda t: -t[1])[:5]]
    ms = [m for _, m, _ in rows]
    us = [u for _, _, u in rows]
    mm, sm = statistics.mean(ms), (statistics.stdev(ms) or 1.0)
    mu, su = statistics.mean(us), (statistics.stdev(us) or 1.0)
    sc = [(c, (1 - wgt) * (m - mm) / sm + wgt * (u - mu) / su) for c, m, u in rows]
    return [c for c, _ in sorted(sc, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 4
def bwl_sel(cand, px=None, d=None, di=None, dates=None, k=60, **_):
    """Rule BWL — 벤치 mom20 < 0 인 국면에서만 룩백을 mom20 → mom{k} 로 늘린다."""
    bm = B.mom(px, B.BENCH, d, di, dates, 20)
    if bm is None or bm >= 0:
        return B.base_sel(cand)
    scored = []
    for x in cand:
        m = B.mom(px, x['code'], d, di, dates, k)
        if m is not None:
            scored.append((x['code'], m))
    if len(scored) < 5:
        return B.base_sel(cand)
    return [c for c, _ in sorted(scored, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- iteration 5
def xsn_sel(cand, px=None, d=None, di=None, dates=None, minn=3, **_):
    """Rule XSN — 종목명 토큰(섹터 프록시) 내부 z 로 정규화한 뒤 횡단면 랭킹."""
    grp = defaultdict(list)
    for x in cand:
        grp[token_of(x['name'])].append(x)
    sc = []
    for t, xs in grp.items():
        ms = [x['mom'] for x in xs]
        if len(xs) < minn:
            for x in xs:                      # 표본이 작은 토큰은 원점수 유지
                sc.append((x['code'], x['mom']))
            continue
        mu = statistics.mean(ms)
        sd = statistics.stdev(ms) if len(ms) > 1 else 0.0
        for x in xs:
            sc.append((x['code'], (x['mom'] - mu) / sd if sd else 0.0))
    if len(sc) < 5:
        return B.base_sel(cand)
    return [c for c, _ in sorted(sc, key=lambda t: -t[1])[:5]]


# ---------------------------------------------------------------- 실행
AXES = {
    'MR2': ('iteration 1 · Rule MR2 — mom20 하위군 단기반등 슬롯 확보 (검증관 지정 a)', [
        ('MR2 q25 k3 1슬롯', mr2_sel, {'q': 25, 'k': 3, 'nslot': 1}),
        ('MR2 q25 k5 1슬롯', mr2_sel, {'q': 25, 'k': 5, 'nslot': 1}),
        ('MR2 q40 k3 1슬롯', mr2_sel, {'q': 40, 'k': 3, 'nslot': 1}),
        ('MR2 q25 k3 2슬롯', mr2_sel, {'q': 25, 'k': 3, 'nslot': 2}),
        ('MR2 q25 k3 벤치약세', mr2_sel, {'q': 25, 'k': 3, 'nslot': 1, 'cond': 'bench'}),
        ('MR2 q25 k3 분산p80', mr2_sel, {'q': 25, 'k': 3, 'nslot': 1, 'cond': 'xsd'}),
    ]),
    'RCG': ('iteration 2 · Rule RCG — 잔차 모멘텀 λ 고원 재탐색 (검증관 지정 b)', [
        (f'RCG w60 λ{l}', rcg_sel, {'lam': l, 'w': 60})
        for l in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
    ]),
    'CST': ('iteration 3 · Rule CST — 모멘텀 경로 품질(상승일 비율)', [
        ('CST 블렌드 w0.3', cst_sel, {'mode': 'blend', 'wgt': 0.3}),
        ('CST 블렌드 w0.5', cst_sel, {'mode': 'blend', 'wgt': 0.5}),
        ('CST 블렌드 w0.7', cst_sel, {'mode': 'blend', 'wgt': 0.7}),
        ('CST 중앙값 필터', cst_sel, {'mode': 'filter'}),
    ]),
    'BWL': ('iteration 4 · Rule BWL — 벤치 약세 국면 장기 룩백 전환', [
        ('BWL mom40', bwl_sel, {'k': 40}),
        ('BWL mom60', bwl_sel, {'k': 60}),
        ('BWL mom90', bwl_sel, {'k': 90}),
    ]),
    'XSN': ('iteration 5 · Rule XSN — 토큰 내 z 정규화 랭킹', [
        ('XSN minn3', xsn_sel, {'minn': 3}),
        ('XSN minn5', xsn_sel, {'minn': 5}),
    ]),
}


def report_axis(key, px, name, dates, di, fo, ins, base, bfull, btr, bte):
    title, variants = AXES[key]
    print(f'\n=== {title} ===')
    print(f"{'변형':24s} {'전체':>9s} {'train':>9s} {'test':>9s} "
          f"{'잭나이프':>9s} {'t':>6s}  판정")
    print('-' * 90)
    for label, fn, kw in variants:
        r = B.run(fn, px, name, dates, di, fo, ins, **kw)
        if not r or len(r) != len(base):
            print(f'{label:24s} — 표본 불일치 {len(r)} vs {len(base)}')
            continue
        h = len(r) // 2
        full, tr, te = statistics.mean(r), statistics.mean(r[:h]), statistics.mean(r[h:])
        ok = full > bfull and tr > btr and te > bte
        jk = jackknife(r) if ok else None
        t = tstat(r, base)
        js = f'{jk:+9.4f}' if jk is not None else f'{"—":>9s}'
        ts = f'{t:+6.2f}' if t is not None else f'{"—":>6s}'
        verdict = ('기각(3분할 미통과)' if not ok else
                   ('후보승격' if (jk is not None and jk > bfull)
                    else '가드통과·잭나이프미달'))
        print(f'{label:24s} {full:+9.4f} {tr:+9.4f} {te:+9.4f} {js} {ts}  {verdict}')


def trigger_stats(fn, kw, px, name, dates, di, label):
    nchg, win, diffs = 0, 0, []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        b = B.base_sel(cand)
        a = fn(cand, px=px, d=d, di=di, dates=dates, **kw)
        if set(a) == set(b):
            continue

        def port(p):
            rs = [px[c][nxt] / px[c][d] - 1.0 for c in p
                  if px[c].get(d) and px[c].get(nxt)]
            return sum(rs) / len(rs) if rs else None
        pa, pb = port(a), port(b)
        if pa is None or pb is None:
            continue
        nchg += 1
        diffs.append(100 * (pa - pb))
        win += 1 if pa > pb else 0
    if not nchg:
        print(f'  [발동] {label}: 0일 — 발동 없음')
        return
    print(f'  [발동] {label}: {nchg}일 · 우위 {win}일({100*win/nchg:.1f}%) · '
          f'평균 차 {statistics.mean(diffs):+.4f}%p')


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    P12.XSD = build_xsd(px, name, dates, di)
    P12.XSD_SORTED = sorted(P12.XSD)
    import bt_loop_20260813 as SELF
    SELF.XSD = P12.XSD
    print(f'패널 {os.path.basename(B.PANEL)} · {len(dates)}거래일 '
          f'({dates[0]}~{dates[-1]}) · 코드 {len(px)}종')

    base = B.run(B.base_sel, px, name, dates, di, fo, ins)
    h = len(base) // 2
    bfull, btr, bte = (statistics.mean(base), statistics.mean(base[:h]),
                       statistics.mean(base[h:]))
    print(f'\n[baseline] mom20+RuleH  n={len(base)}일  '
          f'full {bfull:+.4f} · train {btr:+.4f} · test {bte:+.4f}  (%p/일, vs KODEX200)')

    want = sys.argv[1:] or ['MR2', 'RCG', 'CST', 'BWL', 'XSN']
    for key in ('MR2', 'RCG', 'CST', 'BWL', 'XSN'):
        if key not in want:
            continue
        report_axis(key, px, name, dates, di, fo, ins, base, bfull, btr, bte)
        if key == 'MR2':
            for kw in ({'q': 25, 'k': 3, 'nslot': 1},
                       {'q': 25, 'k': 3, 'nslot': 1, 'cond': 'bench'}):
                trigger_stats(mr2_sel, kw, px, name, dates, di,
                              f"MR2 q{kw['q']} k{kw['k']} {kw.get('cond') or '무조건'}")
        if key == 'BWL':
            trigger_stats(bwl_sel, {'k': 60}, px, name, dates, di, 'BWL mom60')
    return 0


if __name__ == '__main__':
    sys.exit(main())
