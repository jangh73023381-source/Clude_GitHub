#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_loop2_20260818.py — 2026-08-18 2차 세션 iteration 6~10 (상한 5→10회 확대분).

같은 채점 대상일(D=20260814)에 대해 오전 회차가 iteration 1~5(BRD·TVC·TAL·CWS·BTL)를
전량 기각한 뒤 이어지는 5개 distinct 축이다. 채점 틀·baseline 은 오전과 동일
(`bt_breadth_20260818.py` 재사용) — 비교 가능성을 위해 절대 바꾸지 않는다.

  iteration 6  Rule TVQ  거래대금 집중도 **롤링 분위수 임계** — 오전 iteration 2(TVC)가
                         고정임계 0.30~0.40 이 매일 발동해 축퇴(degenerate)했다. 검증관이
                         "재시도 금지 목록에 넣지 않는다"고 명시한 재검정.
  iteration 7  Rule EFF  ETF 설정/환매 순자금흐름 — 상장좌수(LIST_SHRS) 변화. 창출/환매는
                         실제 자금 유출입이며 NV(괴리율, 8/08 기각)와 다른 정보다.
  iteration 8  Rule LIS  레버리지·인버스 거래대금 점유율 = 투기심리 레짐 + ETF 거래대금 집중도.
  iteration 9  Rule SRV  KRX 업종지수(17종) → 테마 ETF 전이. 검증관이 4회 연속 이월한
                         (a) 업종축을 **공식 업종지수 경로**로 착수한다(종목기본정보 미승인 우회).
  iteration 10 Rule ADP  자기실현 스프레드 적응형 부호 — 외부 지표가 아니라 **전략 자신의
                         실현 스프레드**(상위5 − 하위5)의 최근 부호로 방향을 정한다.

가드(오전과 동일): full·train·test 3분할 전부 baseline 초과 AND 잭나이프 하한 > 0.
추가 관문(8/13 절차): 통과해도 더 긴 별도 패널 재검정 전 승격 금지.
  ※ KRX 파생 축(6~9)은 데이터가 113일뿐이라 **긴 패널 재검정 자체가 불가능** →
    통과하더라도 '잠정' 이상으로 올릴 수 없다. ADP(10)만 2년 패널 재검정이 가능하다.
"""
import csv, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_breadth_20260818 as B                     # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))
from universe_filters import eligible               # noqa: E402

KRX_STK = os.path.join(HERE, 'krx_stock_panel.csv')
KRX_ETF = os.path.join(HERE, 'krx_etf_panel.csv')
KRX_IDX = os.path.join(HERE, 'krx_sector_idx.csv')

# ─────────────────────────────────────────── 공통 유틸

def _num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def at(d, lag):
    """KRX 계열 일자에서 lag 만큼 뒤로. lag=1 이 실전 가능(KRX D+1 지연)."""
    ds = [x for x in B.BRD_DATES if x <= d]
    return ds[max(len(ds) - 1 - lag, 0)] if ds else None


def pct_rank(hist, v):
    """hist(과거값 리스트) 안에서 v 의 분위. 룩어헤드 없음(hist 는 D 이전만)."""
    if not hist:
        return None
    return sum(1 for x in hist if x <= v) / len(hist)


# ─────────────────────────────────────────── 데이터 로드

def load_stock_conc():
    """일자별 개별종목 거래대금 집중도(상위 20종목 점유율)."""
    day = defaultdict(list)
    for r in csv.DictReader(open(KRX_STK, encoding='utf-8')):
        v = _num(r['value'], 0.0)
        day[r['date']].append(v)
    out = {}
    for d, v in day.items():
        tot = sum(v) or 1.0
        out[d] = sum(sorted(v, reverse=True)[:20]) / tot
    return out


def load_etf_krx():
    """ETF 일별매매 → code별 시계열 + 일자별 시장집계."""
    rec = defaultdict(dict)          # code -> date -> dict
    day = defaultdict(list)          # date -> [(name, value, code)]
    for r in csv.DictReader(open(KRX_ETF, encoding='utf-8')):
        d, c = r['date'], r['code']
        rec[c][d] = {'shrs': _num(r['list_shrs']), 'na': _num(r['netasset']),
                     'val': _num(r['value'], 0.0), 'close': _num(r['close'])}
        day[d].append((r['name'], _num(r['value'], 0.0), c))
    mkt = {}
    for d, v in day.items():
        tot = sum(x[1] for x in v) or 1.0
        lev = sum(x[1] for x in v if not eligible(x[0]))
        top10 = sum(sorted((x[1] for x in v), reverse=True)[:10])
        mkt[d] = {'lev': lev / tot, 'conc': top10 / tot}
    return rec, mkt


SECTOR_IDX = ['KRX 자동차', 'KRX 반도체', 'KRX 헬스케어', 'KRX 은행', 'KRX 에너지화학',
              'KRX 철강', 'KRX 방송통신', 'KRX 건설', 'KRX 증권', 'KRX 기계장비',
              'KRX 보험', 'KRX 운송', 'KRX 경기소비재', 'KRX 필수소비재', 'KRX K콘텐츠',
              'KRX 정보기술', 'KRX 유틸리티']

# ETF 종목명 토큰 → KRX 업종지수. 매핑되지 않는 ETF 는 중립(랭크 보정 없음).
NAME2SEC = [
    (('반도체', 'AI반도체', '메모리', '팹리스', '시스템반도체'), 'KRX 반도체'),
    (('자동차', '車', '모빌리티', '자율주행'), 'KRX 자동차'),
    (('바이오', '헬스케어', '제약', '의료', '헬스'), 'KRX 헬스케어'),
    (('은행', '금융', '지주'), 'KRX 은행'),
    (('증권',), 'KRX 증권'),
    (('보험',), 'KRX 보험'),
    (('건설', '건자재', '리츠', '부동산'), 'KRX 건설'),
    (('조선', '기계', '방산', '우주', '항공', '로봇', '휴머노이드', '중공업'), 'KRX 기계장비'),
    (('철강', '비철', '금속', '소재'), 'KRX 철강'),
    (('2차전지', '배터리', '화학', '에너지', '태양광', '수소', '풍력', 'ESS'), 'KRX 에너지화학'),
    (('통신', '미디어', '방송'), 'KRX 방송통신'),
    (('게임', '엔터', 'K팝', '콘텐츠', '웹툰'), 'KRX K콘텐츠'),
    (('AI', '소프트웨어', 'IT', '플랫폼', '인터넷', '클라우드', '데이터센터'), 'KRX 정보기술'),
    (('원자력', '전력', '유틸리티', '가스'), 'KRX 유틸리티'),
    (('운송', '물류', '해운', '항공운송'), 'KRX 운송'),
    (('화장품', '식품', '음식료', '유통', '소비재'), 'KRX 필수소비재'),
    (('여행', '레저', '호텔'), 'KRX 경기소비재'),
]


def etf_sector(name):
    for toks, sec in NAME2SEC:
        if any(t in name for t in toks):
            return sec
    return None


def load_sector_idx():
    """일자별 업종지수 등락률(%)."""
    out = defaultdict(dict)
    keep = set(SECTOR_IDX)
    for r in csv.DictReader(open(KRX_IDX, encoding='utf-8')):
        if r['name'] in keep:
            v = _num(r['chg_pct'])
            if v is not None:
                out[r['date']][r['name']] = v
    return out


# ─────────────────────────────────────────── 변형 생성기

def gate_pct(series, q, lag, above=True, window=60):
    """롤링 분위수 게이트 — series[d] 가 과거 window 일 분포의 q 분위를 넘으면 역전."""
    dates = sorted(series)

    def f(cands, d, brd):
        ref = at(d, lag)
        if ref is None or ref not in series:
            return B.sel_base(cands, d, brd)
        i = dates.index(ref)
        hist = [series[x] for x in dates[max(0, i - window):i]]
        p = pct_rank(hist, series[ref])
        if p is None or len(hist) < 20:
            return B.sel_base(cands, d, brd)
        hit = (p > q) if above else (p < 1 - q)
        return [c for _, c in (cands[-B.NPICK:] if hit else cands[:B.NPICK])]
    return f


def flow_of(rec, code, d, span=1):
    """상장좌수 변화율(%) — 창출(+)/환매(-). d 시점 기준 직전 span 거래일."""
    s = rec.get(code)
    if not s:
        return None
    ds = sorted(x for x in s if x <= d)
    if len(ds) < span + 1:
        return None
    a, b = s[ds[-span - 1]]['shrs'], s[ds[-1]]['shrs']
    if not a or not b:
        return None
    return (b / a - 1) * 100


def eff_blend(rec, w, lag, span=1, pool=None, mode='blend'):
    """Rule EFF — mom20 랭크와 설정/환매 랭크를 결합하거나 상위 pool 내 재정렬."""
    def f(cands, d, brd):
        ref = at(d, lag)
        if ref is None:
            return B.sel_base(cands, d, brd)
        sub = cands[:pool] if pool else cands
        fl = [(flow_of(rec, c, ref, span), c) for _, c in sub]
        known = [x for x in fl if x[0] is not None]
        if len(known) < B.NPICK:
            return B.sel_base(cands, d, brd)
        if mode == 'top':                                   # 풀 내 자금유입 상위
            known.sort(reverse=True)
            return [c for _, c in known[:B.NPICK]]
        if mode == 'bottom':                                # 대조군(역방향)
            known.sort()
            return [c for _, c in known[:B.NPICK]]
        if mode == 'exclude':                               # 순환매(유출) 종목 배제
            keep = [c for v, c in fl if v is None or v >= 0]
            return keep[:B.NPICK] if len(keep) >= B.NPICK else B.sel_base(cands, d, brd)
        mr = {c: i for i, (_, c) in enumerate(sub)}         # mom20 랭크
        known.sort(reverse=True)
        fr = {c: i for i, (_, c) in enumerate(known)}
        sc = sorted(mr, key=lambda c: (1 - w) * mr[c] + w * fr.get(c, len(fr)))
        return sc[:B.NPICK]
    return f


def srv_tilt(sec_ret, code2sec, lag, direction, pool=15, span=1):
    """Rule SRV — mom20 상위 pool 중 업종지수 강세(또는 약세) 순으로 5종."""
    dates = sorted(sec_ret)

    def sec_mom(ref, sec):
        ds = [x for x in dates if x <= ref][-span:]
        vs = [sec_ret[x].get(sec) for x in ds]
        vs = [v for v in vs if v is not None]
        return sum(vs) if vs else None

    def f(cands, d, brd):
        ref = at(d, lag)
        if ref is None or ref not in sec_ret:
            return B.sel_base(cands, d, brd)
        sub = cands[:pool]
        sc = []
        for _, c in sub:
            s = code2sec.get(c)
            v = sec_mom(ref, s) if s else None
            sc.append((v, c))
        known = [x for x in sc if x[0] is not None]
        if len(known) < B.NPICK:
            return B.sel_base(cands, d, brd)
        known.sort(reverse=(direction == 'strong'))
        return [c for _, c in known[:B.NPICK]]
    return f


def adp(spread, k):
    """Rule ADP — 최근 k 일 실현 스프레드(상위5−하위5) 평균이 음수면 하위5로 전환.
    선정일 D 에서 쓸 수 있는 마지막 실현값은 '선정일 D-1' 분이다(룩어헤드 없음)."""
    def f(cands, d, brd):
        ds = [x for x in sorted(spread) if x < d][-k:]
        if len(ds) < k:
            return B.sel_base(cands, d, brd)
        m = sum(spread[x] for x in ds) / k
        return [c for _, c in (cands[:B.NPICK] if m >= 0 else cands[-B.NPICK:])]
    return f


def realized_spread(px, names, dates):
    """선정일별 (상위5 평균 − 하위5 평균) 익일 수익률. 채점 전용 사후값."""
    out = {}
    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        cands = B.ranked(px, names, d, dates)
        if len(cands) < 2 * B.NPICK:
            continue
        top = [B.fwd(px, c, d, nxt) for _, c in cands[:B.NPICK]]
        bot = [B.fwd(px, c, d, nxt) for _, c in cands[-B.NPICK:]]
        top = [x for x in top if x is not None]
        bot = [x for x in bot if x is not None]
        if len(top) < B.NPICK or len(bot) < B.NPICK:
            continue
        out[d] = sum(top) / len(top) - sum(bot) / len(bot)
    return out


# ─────────────────────────────────────────── 실행

def main():
    px, names = B.load_etf()
    brd = B.load_breadth()
    B.BRD_DATES = sorted(brd)
    dates = sorted({d for c in px for d in px[c]})
    dates = [d for d in dates if d >= B.BRD_DATES[0]]

    conc = load_stock_conc()
    rec, mkt = load_etf_krx()
    sec_ret = load_sector_idx()
    code2sec = {c: etf_sector(names.get(c, '')) for c in px}
    mapped = sum(1 for c in px if code2sec[c])
    spread = realized_spread(px, names, dates)

    print(f'ETF {len(dates)}일 {dates[0]}~{dates[-1]} · 유니버스 {len(px)}종')
    print(f'KRX ETF패널 {len({d for c in rec for d in rec[c]})}일 · 업종지수 {len(sec_ret)}일 '
          f'{len(SECTOR_IDX)}종 · ETF→업종 매핑 {mapped}/{len(px)}종')
    print(f'레버리지·인버스 거래대금 점유 평균 {sum(v["lev"] for v in mkt.values())/len(mkt):.3f} · '
          f'개별종목 상위20 집중도 평균 {sum(conc.values())/len(conc):.3f}\n')

    base = B.stat(B.run(B.sel_base, px, names, dates, brd), 'BASE mom20+RuleH')
    B.show(base)

    blocks = []

    # ── iteration 6 · Rule TVQ
    v6 = []
    for lag in (0, 1):
        tag = 'D' if lag == 0 else 'D-1'
        for q in (0.50, 0.70, 0.80, 0.90):
            v6.append((f'TVQ 집중도 롤링p{int(q*100)} 초과 역전 [{tag}]',
                       gate_pct(conc, q, lag, True)))
        v6.append((f'TVQ(대조) 집중도 롤링p30 미만 역전 [{tag}]', gate_pct(conc, 0.70, lag, False)))
    blocks.append(('iteration 6 — Rule TVQ 거래대금 집중도(롤링 분위수)', v6))

    # ── iteration 7 · Rule EFF
    v7 = []
    for lag in (0, 1):
        tag = 'D' if lag == 0 else 'D-1'
        for w in (0.2, 0.3, 0.5):
            v7.append((f'EFF 설정환매1일 블렌드 w={w} [{tag}]', eff_blend(rec, w, lag)))
        v7.append((f'EFF 상위15중 유입상위5 [{tag}]', eff_blend(rec, 0, lag, pool=15, mode='top')))
        v7.append((f'EFF 상위15중 유입상위5(5일) [{tag}]',
                   eff_blend(rec, 0, lag, span=5, pool=15, mode='top')))
        v7.append((f'EFF 환매(유출)종목 배제 [{tag}]', eff_blend(rec, 0, lag, mode='exclude')))
        v7.append((f'EFF(대조) 상위15중 유출상위5 [{tag}]',
                   eff_blend(rec, 0, lag, pool=15, mode='bottom')))
    blocks.append(('iteration 7 — Rule EFF ETF 설정/환매 자금흐름', v7))

    # ── iteration 8 · Rule LIS
    lev = {d: v['lev'] for d, v in mkt.items()}
    econ = {d: v['conc'] for d, v in mkt.items()}
    v8 = []
    for lag in (0, 1):
        tag = 'D' if lag == 0 else 'D-1'
        for q in (0.70, 0.80, 0.90):
            v8.append((f'LIS 레버인버스점유 롤링p{int(q*100)} 초과 역전 [{tag}]',
                       gate_pct(lev, q, lag, True)))
        v8.append((f'LIS(대조) 점유 하위30% 역전 [{tag}]', gate_pct(lev, 0.70, lag, False)))
        v8.append((f'LIS-C ETF거래대금집중 롤링p80 초과 역전 [{tag}]',
                   gate_pct(econ, 0.80, lag, True)))
    blocks.append(('iteration 8 — Rule LIS 레버리지·인버스 점유율(투기심리)', v8))

    # ── iteration 9 · Rule SRV
    v9 = []
    for lag in (0, 1):
        tag = 'D' if lag == 0 else 'D-1'
        for dirn in ('strong', 'weak'):
            kr = '강세' if dirn == 'strong' else '약세'
            v9.append((f'SRV 상위15중 업종{kr}5 (1일) [{tag}]',
                       srv_tilt(sec_ret, code2sec, lag, dirn, 15, 1)))
            v9.append((f'SRV 상위15중 업종{kr}5 (5일) [{tag}]',
                       srv_tilt(sec_ret, code2sec, lag, dirn, 15, 5)))
        v9.append((f'SRV 상위10중 업종강세5 (5일) [{tag}]',
                   srv_tilt(sec_ret, code2sec, lag, 'strong', 10, 5)))
    blocks.append(('iteration 9 — Rule SRV KRX 업종지수 전이', v9))

    # ── iteration 10 · Rule ADP
    v10 = [(f'ADP 최근{k}일 실현스프레드 부호전환', adp(spread, k)) for k in (3, 5, 10, 20, 40)]
    blocks.append(('iteration 10 — Rule ADP 자기실현 스프레드 적응형', v10))

    allrows = []
    for title, variants in blocks:
        print(f'\n=== {title} ({len(variants)}변형) ===')
        for label, f in variants:
            s = B.stat(B.run(f, px, names, dates, brd), label)
            B.show(s, base)
            if s:
                s['axis'] = title.split('—')[1].strip().split()[0]
                allrows.append(s)

    print('\n--- 3분할+잭나이프 가드 (full·train·test 전부 baseline 초과 AND jk>0) ---')
    ok = [s for s in allrows
          if s['mean'] > base['mean'] and s['train'] > base['train']
          and s['test'] > base['test'] and s['jk'] > 0]
    if ok:
        for s in ok:
            B.show(s, base)
        print('\n※ 통과 변형 있음 — 113일 소표본. 8/13 절차에 따라 긴 패널 재검정 필수.')
        print('  KRX 파생축(6~9)은 데이터가 113일뿐이라 재검정 불가 → 잠정 이상 승격 금지.')
    else:
        print('  통과 0건 — iteration 6~10 전량 기각.')
    print(f'\n총 변형 {len(allrows)}개 · baseline n={base["n"]}일')
    return 0


if __name__ == '__main__':
    sys.exit(main())
