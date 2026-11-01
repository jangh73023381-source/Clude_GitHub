# -*- coding: utf-8 -*-
"""ETF -> 업종(섹터) 매핑 구축 — Rule CHB ETF 트랙 검정의 선행 조달 경로 (2026-08-25 신설).

배경: Rule CHB(업종 내 구성종목 채널위치 분포)를 ETF 트랙으로 올리려면 ETF 구성종목(PDF)이
필요한데, KRX OPEN API 에 PDF 경로가 없고(CLAUDE.md §0) **키움 REST 에도 없다**
(2026-08-25 실측: ka40002=기초지수명만 · ka40004=전체시세 · ka40010=시간대별추이).

대체 조달 경로: **기초지수명(base_idx / trace_idex_nm) 키워드 매핑**.
ETF 는 기초지수를 공시하고 그 이름에 업종·테마가 들어 있으므로, PDF 없이도 ETF 를 업종
버킷에 넣을 수 있다. 구성종목 가중까지는 못 가지만 CHB 는 '업종 단위 점수'를 쓰므로
업종 매핑만 있으면 ETF 트랙 검정이 가능하다.

조회 전용 — 기존 `backtest/krx_etf_panel.csv` 만 읽는다(신규 API 호출 없음).
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'krx_etf_panel.csv')
OUT = os.path.join(HERE, 'etf_sector_map.csv')

# 기초지수명 → 업종 버킷. 먼저 매칭되는 것을 쓴다(순서가 우선순위).
RULES = [
    ('반도체',   ['반도체', 'K-반도체', '시스템반도체', 'AI반도체']),
    ('2차전지',  ['2차전지', '이차전지', '배터리', '전기차', '전기&수소차']),
    ('바이오',   ['바이오', '헬스케어', '제약', '의료']),
    ('IT',       ['IT', '소프트웨어', '인터넷', '테크', '클라우드', 'AI', '게임']),
    ('은행금융', ['은행', '금융', '보험']),
    ('증권',     ['증권']),
    ('자동차',   ['자동차']),
    ('조선',     ['조선']),
    ('방산우주', ['방산', '우주', '항공']),
    ('원자력',   ['원자력', '원전']),
    ('전력',     ['전력', '전선', '전기설비']),
    ('로봇',     ['로봇']),
    ('신재생',   ['태양광', '신재생', '수소', 'ESS', '친환경']),
    ('건설',     ['건설', '인프라', '리츠', '부동산']),
    ('화장품',   ['화장품', '뷰티']),
    ('금속귀금속', ['금현물', '금선물', '은선물', '골드', '실버', '구리', '원자재', '광물']),
    ('통신',     ['통신', '네트워크']),
    ('소비재',   ['소비재', '유통', '식품', '음식료', '엔터', '미디어', '여행', '레저']),
    ('철강소재', ['철강', '화학', '소재']),
    ('지수',     ['KOSPI', '코스피', '코스닥', 'KRX 300', 'MSCI', 'S&P', '나스닥', 'NASDAQ',
                 'Fn가이드', '배당', '고배당', 'TOP', '대표']),
]


def bucket(idx_name):
    s = (idx_name or '').replace(' ', '')
    for sect, kws in RULES:
        for kw in kws:
            if kw.replace(' ', '') in s:
                return sect, kw
    return '', ''


def main():
    latest, rows = '', {}
    for r in csv.DictReader(open(SRC, encoding='utf-8')):
        d = r['date']
        if d > latest:
            latest = d
        rows.setdefault(r['code'], r)
        if r['date'] >= rows[r['code']]['date']:
            rows[r['code']] = r

    out, unmapped = [], 0
    for code, r in sorted(rows.items()):
        sect, kw = bucket(r.get('base_idx'))
        if not sect:
            unmapped += 1
        out.append({'code': code, 'name': r['name'],
                    'base_idx': r.get('base_idx', ''),
                    'sector': sect, 'matched_kw': kw})

    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['code', 'name', 'base_idx', 'sector', 'matched_kw'])
        w.writeheader()
        w.writerows(out)

    cov = 100.0 * (len(out) - unmapped) / max(1, len(out))
    print(f'[완료] {OUT}')
    print(f'  ETF {len(out)}종 · 매핑 {len(out)-unmapped}종 ({cov:.1f}%) · 미매핑 {unmapped}종')
    import collections
    c = collections.Counter(r['sector'] for r in out if r['sector'])
    print('  업종 분포:', dict(c.most_common()))


if __name__ == '__main__':
    main()
