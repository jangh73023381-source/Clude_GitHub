#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_loop2_robust_20260818.py — iteration 6~10 통과 후보 2건의 강건성 검정.

통과 후보(3분할+잭나이프)
  ① Rule EFF  '환매(자금유출) 종목 배제' [D]
  ② Rule SRV  'mom20 상위15 중 업종지수 5일강세 상위5' [D]

두 후보 모두 **KRX 당일(D) 데이터**를 쓴다. KRX OPEN API 는 D 일자 데이터를 D+1 장중에
공개하므로(2026-08-18 20:03 KST 실측: 20260814 가용 / 20260818 미가용, 같은 날 06:24 에는
20260814 도 미가용) **선정 시각(T 06:00)에는 D-1 까지만 받을 수 있다.**
→ 실전 가능한 [D-1] 변형은 이미 3분할에서 탈락했다. 이 스크립트는 그럼에도
   (a) 무엇이 신호이고 무엇이 우연인지, (b) 당일 데이터 조달 경로가 열리면 살릴 값이 있는지를
   가른다.

검정 4종
  R1 파라미터 고원      span×pool 격자. 한 점만 통과하면 인공물(8/14 EWM 선례).
  R2 3분할(fold)        전·중·후 3등분 전부 baseline 초과 여부.
  R3 분류체계 강건성     KRX 시리즈 17종 → 코스피/코스닥 업종지수(40여종)로 교체 재현.
  R4 플라시보(순열)      ETF→업종 매핑을 무작위로 섞어 200회. 실제값의 경험적 p 값.
"""
import csv, os, random, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_breadth_20260818 as B          # noqa: E402
import bt_loop2_20260818 as L            # noqa: E402

IND = os.path.join(HERE, 'krx_ind_idx.csv')
# 코스피/코스닥 업종지수 중 '실업종'만(규모·스타일 지수 제외)
IND_KEEP = ['음식료·담배', '섬유·의류', '종이·목재', '화학', '제약', '비금속', '금속',
            '기계·장비', '전기전자', '의료·정밀기기', '운송장비·부품', '유통', '전기·가스',
            '건설', '운송·창고', '통신', '금융', '증권', '보험', '일반서비스',
            '오락·문화', 'IT 서비스', '부동산', '제조', '출판·매체복제', '기타제조']
NAME2IND = [
    (('반도체', '메모리', '팹리스'), '전기전자'),
    (('자동차', '모빌리티', '자율주행'), '운송장비·부품'),
    (('바이오', '제약', '헬스케어', '헬스'), '제약'),
    (('의료', '진단'), '의료·정밀기기'),
    (('은행', '금융', '지주'), '금융'),
    (('증권',), '증권'),
    (('보험',), '보험'),
    (('건설', '건자재', '리츠', '부동산'), '건설'),
    (('조선', '기계', '방산', '우주', '항공', '로봇', '휴머노이드', '중공업'), '기계·장비'),
    (('철강', '비철', '금속', '소재'), '금속'),
    (('2차전지', '배터리', '화학', '태양광', '수소', '풍력', 'ESS'), '화학'),
    (('원자력', '전력', '유틸리티', '가스', '에너지'), '전기·가스'),
    (('통신', '방송', '미디어'), '통신'),
    (('게임', '엔터', 'K팝', '콘텐츠', '웹툰'), '오락·문화'),
    (('AI', '소프트웨어', 'IT', '플랫폼', '인터넷', '클라우드', '데이터센터'), 'IT 서비스'),
    (('운송', '물류', '해운'), '운송·창고'),
    (('화장품', '식품', '음식료'), '음식료·담배'),
    (('유통', '소비재', '여행', '레저', '호텔'), '유통'),
]


def load_ind():
    out = defaultdict(dict)
    keep = set(IND_KEEP)
    for r in csv.DictReader(open(IND, encoding='utf-8')):
        if r['name'] in keep:
            try:
                v = float(r['chg_pct'])
            except ValueError:
                continue
            k = f"{r['market']}:{r['name']}"
            out[r['date']][k] = v
    return out


def ind_sector(name, market_pref=('KOSPI', 'KOSDAQ')):
    for toks, sec in NAME2IND:
        if any(t in name for t in toks):
            return f'{market_pref[0]}:{sec}'
    return None


def folds(res, k=3):
    n = len(res)
    b = [res[i * n // k:(i + 1) * n // k] for i in range(k)]
    return [sum(x for _, x in f) / len(f) if f else 0.0 for f in b]


def main():
    px, names = B.load_etf()
    brd = B.load_breadth()
    B.BRD_DATES = sorted(brd)
    dates = sorted({d for c in px for d in px[c]})
    dates = [d for d in dates if d >= B.BRD_DATES[0]]
    rec, mkt = L.load_etf_krx()
    sec_ret = L.load_sector_idx()
    c2s = {c: L.etf_sector(names.get(c, '')) for c in px}

    base_res = B.run(B.sel_base, px, names, dates, brd)
    base = B.stat(base_res, 'BASE')
    bf = folds(base_res)
    print(f'BASE full{base["mean"]:+.4f} train{base["train"]:+.4f} test{base["test"]:+.4f} '
          f'| fold {bf[0]:+.4f} {bf[1]:+.4f} {bf[2]:+.4f}\n')

    # ── R1 파라미터 고원 (SRV)
    print('=== R1 SRV 파라미터 고원 (span × pool, [D]) ===')
    print(f'{"":6s}' + ''.join(f'pool{p:<8d}' for p in (10, 15, 20, 25)))
    grid = {}
    for span in (1, 2, 3, 5, 8, 10, 20):
        row = f'{span:>3d}일 '
        for pool in (10, 15, 20, 25):
            s = B.stat(B.run(L.srv_tilt(sec_ret, c2s, 0, 'strong', pool, span),
                             px, names, dates, brd), '')
            grid[(span, pool)] = s
            g = '✔' if (s['mean'] > base['mean'] and s['train'] > base['train']
                        and s['test'] > base['test'] and s['jk'] > 0) else ' '
            row += f'{s["mean"]:+8.4f}{g} '
        print(row)
    npass = sum(1 for k, s in grid.items()
                if s['mean'] > base['mean'] and s['train'] > base['train']
                and s['test'] > base['test'] and s['jk'] > 0)
    print(f'  격자 28점 중 가드 통과 {npass}점\n')

    # ── R2 3분할 fold
    print('=== R2 3분할 fold (전·중·후) ===')
    cands = [
        ('SRV 상위15/5일강세 [D]', L.srv_tilt(sec_ret, c2s, 0, 'strong', 15, 5)),
        ('SRV 상위10/5일강세 [D]', L.srv_tilt(sec_ret, c2s, 0, 'strong', 10, 5)),
        ('SRV 상위15/5일강세 [D-1]', L.srv_tilt(sec_ret, c2s, 1, 'strong', 15, 5)),
        ('EFF 환매배제 [D]', L.eff_blend(rec, 0, 0, mode='exclude')),
        ('EFF 환매배제 [D-1]', L.eff_blend(rec, 0, 1, mode='exclude')),
    ]
    for lab, f in cands:
        r = B.run(f, px, names, dates, brd)
        s = B.stat(r, lab)
        fl = folds(r)
        okf = sum(1 for i in range(3) if fl[i] > bf[i])
        print(f'  {lab:26s} full{s["mean"]:+.4f} fold {fl[0]:+.4f} {fl[1]:+.4f} {fl[2]:+.4f} '
              f'→ baseline 초과 {okf}/3')
    print()

    # ── R3 분류체계 교체
    print('=== R3 분류체계 강건성 (KRX 17종 → 코스피/코스닥 업종지수) ===')
    ind_ret = load_ind()
    c2i = {c: ind_sector(names.get(c, '')) for c in px}
    print(f'  매핑 {sum(1 for c in c2i if c2i[c])}/{len(px)}종 · 업종지수 일자 {len(ind_ret)}일')
    for span in (3, 5, 8):
        for pool in (10, 15):
            s = B.stat(B.run(L.srv_tilt(ind_ret, c2i, 0, 'strong', pool, span),
                             px, names, dates, brd), f'IND {span}일/pool{pool} [D]')
            B.show(s, base)
    print()

    # ── R4 플라시보 순열
    print('=== R4 플라시보 — ETF→업종 매핑 무작위 순열 200회 (SRV 상위15/5일 [D]) ===')
    real = B.stat(B.run(L.srv_tilt(sec_ret, c2s, 0, 'strong', 15, 5), px, names, dates, brd), '')
    secs = [s for s in (c2s[c] for c in px) if s]
    codes = list(px)
    rng = random.Random(20260818)
    null = []
    for _ in range(200):
        sh = list(secs)
        rng.shuffle(sh)
        fake, i = {}, 0
        for c in codes:
            if c2s[c]:
                fake[c] = sh[i]; i += 1
            else:
                fake[c] = None
        null.append(B.stat(B.run(L.srv_tilt(sec_ret, fake, 0, 'strong', 15, 5),
                                 px, names, dates, brd), '')['mean'])
    null.sort()
    p = sum(1 for x in null if x >= real['mean']) / len(null)
    print(f'  실제 {real["mean"]:+.4f} · 플라시보 평균 {statistics.mean(null):+.4f} '
          f'sd {statistics.stdev(null):.4f}')
    print(f'  플라시보 분위 5%{null[9]:+.4f} 50%{null[99]:+.4f} 95%{null[189]:+.4f}')
    print(f'  경험적 p = {p:.3f}  (200회 중 실제 이상 {int(p*200)}회)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
