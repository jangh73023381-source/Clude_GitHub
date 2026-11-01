#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""news_top5.py — 데일리 브리핑 '2. 주요 뉴스 5선' 자동 후보 생성 (조회 전용).

배경(2026-07-28 사용자 지시): 종전 5선은 웹 검색에 의존했는데, 검색 엔진이 7/15·7/24자
기사를 7/27자로 반환하는 날짜 오매칭이 실측됐다. 관심신호 수집(collect_attention.py)이
이미 네이버 뉴스 API로 매일 1,600건 이상을 장전 윈도(D-1 16:00~D 09:00) 안에서 받아오고
있으므로, 그 원본 풀을 5선 작성에도 재사용한다. 발행시각이 API 응답값이라 날짜가 보장된다.

배분(사용자 확정, 혼합형): 추천 테마 2 + 보도량 급증 테마 2 + 악재 1 = 5건
  · 추천 테마 : 오늘 추천 ETF·단일종목이 속한 테마의 기사 (내가 살 종목의 뉴스)
  · 급증 테마 : 전일 대비 기사 수 증가율 상위 테마 (그날 시장 관심 이동)
  · 악재     : label=='sell' 중 최고 점수 1건 (리스크 조기 감지)
거시(FOMC·미국 지표)는 국내 뉴스만으로 놓치기 쉬우므로 웹 검색으로 별도 보강하되,
날짜가 검증되지 않으면 본문에서 제외한다 — 이 스크립트는 국내 뉴스 파트만 담당한다.

사용:
  python3 references/scripts/news_top5.py                 # 오늘(T) 기준
  python3 references/scripts/news_top5.py --date 20260728
산출:
  references/scripts/news5_<YYYYMMDD>.json  + 콘솔 표
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(REF, '..'))
KST = timezone(timedelta(hours=9))

# theme_map.csv 의 '배당'은 관심신호 테마 체계의 '은행금융'에 대응한다.
THEME_ALIAS = {'배당': '은행금융', '금속귀금속': '금귀금속'}

# Rule SU 단일종목 유니버스의 섹터 라벨 → 관심신호 테마
SU_SECTOR = {
    '000660': '반도체', '005380': '자동차', '006800': '증권', '105560': '은행금융',
    '012450': '방산', '329180': '조선', '373220': '2차전지', '207940': '바이오',
    '034020': '원자력', '010120': 'AI전력', '090430': '바이오', '277810': '로봇',
    '009830': '태양광', '047040': '건설', '010130': '금귀금속',
}

EVENT_KW = ['수주', '공급계약', '체결', '증설', '정부 지원', '규제', '승인', '실적',
            '투자', '인수', '출시', '양산', '수출', '제재', '소송', '유상증자']

# 시황과 무관한 홍보성·행사성 기사 감점 (2026-07-28 실측: 'HJ중공업 KLPGA 골프단 인수'가
# '인수'·'실적' 키워드만으로 상위에 올라왔다)
NOISE_KW = ['골프', '마케팅', 'ESG 경영', '사회공헌', '기부', '봉사', '행사', '캠페인',
            '위촉', '인사', '부고', '수상', '공모전', '이벤트', '후원', '축사', '간담회']

# 악재 슬롯 전용 — 부정어가 긍정 복합어 안에 들어가 오분류되는 사례를 차단한다
# (2026-07-28 실측: '규제혁신 아끼지 않겠다'가 '규제' 때문에 sell로 분류됐다)
FALSE_NEG = ['규제혁신', '규제 혁신', '규제완화', '규제 완화', '규제개선', '규제 개선',
             '우려 해소', '우려 완화', '적자 탈출', '적자 축소', '하락세 진정',
             '손실 축소', '리스크 해소']
STRONG_NEG = ['급락', '적자', '쇼크', '하향', '리콜', '중단', '취소', '철회', '유상증자',
              '전환사채', '제재', '과징금', '소송', '파업', '무산', '신저가', '감산',
              '구조조정', '부진', '악재', '경고']


# 표시용 테마 재판정 — pool 의 theme 은 '어떤 쿼리로 걸렸는가'라서 내용과 어긋날 수 있다
# (2026-07-28 실측: 두산에너빌리티 원전 수주 기사가 '건설' 쿼리로 수집됨). 제목에 다른
# 테마의 핵심어가 명확히 있으면 그쪽으로 바꿔 표기한다. 수집 테마 자체는 건드리지 않는다.
DISPLAY_KW = [
    ('반도체', ['반도체', 'HBM', 'D램', '낸드', '파운드리', 'SK하이닉스', '엔비디아']),
    ('원자력', ['원전', 'SMR', '원자력', '두산에너빌리티']),
    ('2차전지', ['배터리', '2차전지', '이차전지', 'LG에너지솔루션', '양극재']),
    ('바이오', ['바이오', '제약', '신약', '임상', '셀트리온']),
    ('조선', ['조선', '수주잔고', 'HD현대중공업', '한화오션']),
    ('방산', ['방산', '무기', '수출계약', '한화에어로']),
    ('AI전력', ['전력망', '변압기', '데이터센터 전력', '전력기기']),
    ('은행금융', ['은행', '금융지주', '기준금리', 'KB금융', '신한지주']),
    ('자동차', ['완성차', '현대차', '기아', '전기차']),
    ('건설', ['건설사', '분양', '재건축', '수주 텃밭']),
]


def display_theme(row):
    t = row['title']
    for th, kws in DISPLAY_KW:
        if any(k in t for k in kws):
            return th
    return row['theme']


def norm_title(t):
    t = re.sub(r'\[[^\]]*\]|\([^)]*\)', ' ', t or '')
    return re.sub(r'[^0-9A-Za-z가-힣]', '', t)


def load_pool(date):
    p = os.path.join(REF, f'news_pool_{date}.csv')
    if not os.path.exists(p):
        return None
    return list(csv.DictReader(open(p, encoding='utf-8')))


def load_raw(date):
    p = os.path.join(REF, f'raw_{date}.csv')
    if not os.path.exists(p):
        return {}
    out = {}
    for r in csv.DictReader(open(p, encoding='utf-8')):
        try:
            out[r['theme']] = int(r['news_total'] or 0)
        except ValueError:
            out[r['theme']] = 0
    return out


def prev_raw(date):
    """직전에 존재하는 raw_*.csv 를 찾아 (날짜, counts) 반환."""
    cands = sorted(f for f in os.listdir(REF)
                   if f.startswith('raw_') and f.endswith('.csv')
                   and f[4:12] < date)
    if not cands:
        return None, {}
    d = cands[-1][4:12]
    return d, load_raw(d)


def pick_themes(date):
    """오늘 추천 종목이 속한 테마 집합 (morning_state JSON 기준)."""
    p = os.path.join(HERE, f'morning_state_{date}.json')
    if not os.path.exists(p):
        return []
    st = json.load(open(p, encoding='utf-8'))
    picks = st.get('picks', {})
    tmap = {}
    tp = os.path.join(ROOT, 'backtest', 'theme_map.csv')
    if os.path.exists(tp):
        for r in csv.DictReader(open(tp, encoding='utf-8')):
            if r.get('theme'):
                tmap[r['code']] = THEME_ALIAS.get(r['theme'], r['theme'])
    themes, seen = [], set()
    for c in (picks.get('picks5') or '').split(','):
        t = tmap.get(c.strip())
        if t and t not in seen:
            seen.add(t)
            themes.append(t)
    for line in [picks.get('stock15_su') or '']:
        for code in re.findall(r'\((\d{6})\)', line):
            t = THEME_ALIAS.get(SU_SECTOR.get(code, ''), SU_SECTOR.get(code, ''))
            if t and t not in seen:
                seen.add(t)
                themes.append(t)
    return themes


def is_real_negative(row):
    """악재 슬롯 자격 — 어휘사전 sell 라벨만으로는 오분류가 섞이므로 2중 확인한다."""
    t = row['title'] + ' ' + row.get('desc', '')
    if any(k in t for k in FALSE_NEG):
        return False
    return sum(1 for k in STRONG_NEG if k in t) >= 1 and any(k in row['title'] for k in STRONG_NEG)


def score(row):
    s = 0.0
    title = row['title']
    s += 2.0 * sum(1 for k in EVENT_KW if k in title)
    s -= 3.0 * sum(1 for k in NOISE_KW if k in title)
    if row['label'] != 'neutral':
        s += 1.0
    try:
        pub = datetime.strptime(row['pub'], '%Y-%m-%d %H:%M')
        s += max(0.0, 3.0 - (datetime.now() - pub).total_seconds() / 36000.0)
    except (ValueError, KeyError):
        pass
    if len(title) < 12:
        s -= 2.0
    return s


def best(rows, used_titles, used_links, want_label=None, themes=None, n=1):
    if n <= 0:
        return []
    c = rows
    if themes:
        c = [r for r in c if r['theme'] in themes]
    if want_label == 'sell':
        c = [r for r in c if r['label'] == 'sell' and is_real_negative(r)]
    elif want_label:
        c = [r for r in c if r['label'] == want_label]
    c = [r for r in c
         if norm_title(r['title'])[:24] not in used_titles and r['link'] not in used_links]
    c.sort(key=score, reverse=True)
    out = []
    for r in c:
        key = norm_title(r['title'])[:24]
        if key in used_titles:
            continue
        used_titles.add(key)
        used_links.add(r['link'])
        out.append(r)
        if len(out) >= n:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=datetime.now(KST).strftime('%Y%m%d'))
    a = ap.parse_args()

    pool = load_pool(a.date)
    if pool is None:
        print(f'[결손] news_pool_{a.date}.csv 없음 — collect_attention.py 를 먼저 실행하세요.\n'
              f'       (2026-07-28 이전 수집분은 풀 파일이 없으므로 5선 자동생성 불가 — '
              f'웹 검색 보강으로 대체하고 보고서에 결손을 명시할 것)', file=sys.stderr)
        return 2

    # 보도량 '급증'은 절대 건수가 아니라 **점유율 변화**로 잰다.
    # 수집 시각(장전 05:30 vs 전일 21:00)에 따라 전체 수집량이 크게 달라져, 절대 건수를
    # 비교하면 모든 테마가 일제히 마이너스로 나온다(2026-07-28 실측: 전 테마 -34~-60%).
    # 점유율은 수집 시각에 불변이므로 테마 간 관심 이동만 남는다.
    cur = {}
    for r in pool:
        cur[r['theme']] = cur.get(r['theme'], 0) + 1
    pd_, prev = prev_raw(a.date)
    ct, pt_ = max(sum(cur.values()), 1), max(sum(prev.values()), 1)
    growth = []
    for th, n in cur.items():
        if n < 15:                        # 표본이 너무 적은 테마는 급증 판정에서 제외
            continue
        cs, ps = n / ct, prev.get(th, 0) / pt_
        growth.append((th, n, prev.get(th, 0), (cs / ps - 1) if ps > 0 else 0.0))
    growth.sort(key=lambda x: -x[3])

    pt = pick_themes(a.date)
    used_t, used_l = set(), set()
    items = []

    for r in best(pool, used_t, used_l, themes=pt, n=2):
        items.append(dict(bucket='추천테마', disp_theme=display_theme(r), **r))
    gt = [t for t, *_ in growth if t not in pt][:4]
    for r in best(pool, used_t, used_l, themes=gt, n=2):
        items.append(dict(bucket='보도급증', disp_theme=display_theme(r), **r))
    for r in best(pool, used_t, used_l, want_label='sell', n=1):
        items.append(dict(bucket='악재', disp_theme=display_theme(r), **r))

    # 부족분은 전체 풀 최고 점수로 채운다
    for r in best(pool, used_t, used_l, n=max(0, 5 - len(items))):
        items.append(dict(bucket='보완', disp_theme=display_theme(r), **r))

    out = {
        'date': a.date, 'pool_size': len(pool),
        'pick_themes': pt, 'prev_raw_date': pd_,
        'growth_top': [{'theme': t, 'now': n, 'prev': p, 'chg_pct': round(g * 100, 1)}
                       for t, n, p, g in growth[:5]],
        'items': items,
    }
    op = os.path.join(HERE, f'news5_{a.date}.json')
    json.dump(out, open(op, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'=== 주요 뉴스 5선 후보 ({a.date}) · 풀 {len(pool)}건 · '
          f'추천테마 {"·".join(pt) or "없음"} ===')
    print("보도량 점유율 급증 상위(수집시각 불변 지표): " + ", ".join(
        f'{t} {p}→{n}건({g * 100:+.0f}%)' for t, n, p, g in growth[:4]))
    for i, r in enumerate(items, 1):
        mark = '' if r['disp_theme'] == r['theme'] else f"(수집:{r['theme']})"
        print(f"\n{i}. [{r['bucket']}/{r['disp_theme']}{mark}/{r['label']}] {r['title']}")
        print(f"   {r['pub']}  {r['link']}")
    print(f'\n→ {op}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
