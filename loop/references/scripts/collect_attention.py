#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_attention.py — 관심 신호 수집 (attention_pilot.md v2.3 소스 개편본 자동화)

통합 루프 0단계(0-A 사후수집 / 0-B 신규수집)를 커넥터 없이 스크립트로 수행한다.
네이버 오픈API(데이터랩 검색 + 뉴스 검색)를 직접 호출하므로 MCP 커넥터가 필요 없다.

수집 대상 (v2.3):
  - 데이터랩 검색 : 랭킹 축.  search = 당일 ratio / 직전 5영업일 평균
  - 뉴스(이벤트 키워드 쿼리) : 악재 배제필터용 감성.  sent = (buy-sell)/max(total,1)
  - 유튜브 / yt20 : **수집하지 않는다(v2.4에서 폐지 — rank-IC -0.128)** → 컬럼은 빈값으로 남긴다
                    (0으로 채우면 shadow의 liveness 게이트가 '진짜 0'으로 오인한다)

인증:
  loop 폴더에 아래 두 파일이 있어야 한다 (키움 키와 동일한 방식, 조회 전용).
      naver_clientid.txt   ← Naver Developers 애플리케이션 Client ID
      naver_secret.txt     ← 같은 애플리케이션 Client Secret
  발급: https://developers.naver.com/apps → 애플리케이션 등록 →
        사용 API 에 '검색' 과 '데이터랩(검색어트렌드)' 두 개를 모두 추가.
  키 파일이 없으면 수집하지 않고 exit code 2 로 종료한다(임의 대체 소스 금지 —
  shadow 표본 오염 방지).

사용:
  python3 collect_attention.py --date 20260727                 # 0-B 오늘 신호 수집
  python3 collect_attention.py --date 20260724 --post-hoc      # 0-A 사후수집(플래그 기록)
  python3 collect_attention.py --date 20260727 --check         # 행 존재 여부만 확인(수집 안 함)

산출:
  references/raw_<YYYYMMDD>.csv          — 15테마 raw 신호
  references/news_audit_<YYYYMMDD>.csv   — 감성 분류 검수용(theme,title,label)
  references/attention_collect_log.csv   — 수집 이력(사후수집·부분실패 추적)

주의: 조회 전용. 주문·매매 기능은 어떤 경우에도 호출하지 않는다.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(HERE, '..'))
LOOP = os.path.abspath(os.path.join(REF, '..'))

THEMES_CSV = os.path.join(REF, 'attention_pilot_themes.csv')
COLLECT_LOG = os.path.join(REF, 'attention_collect_log.csv')

KST = timezone(timedelta(hours=9))

# 데이터랩 검색 키워드 — 테마별 대표 검색어(그룹당 최대 5개 키워드, 그룹 최대 5개/호출)
THEME_KEYWORDS = {
    '반도체':   ['반도체', 'HBM', '메모리반도체'],
    '자동차':   ['자동차주', '현대차', '기아 주가'],
    '증권':     ['증권주', '증권 株', '증권사 주가'],
    '은행금융': ['은행주', '금융지주', 'KB금융'],
    '방산':     ['방산주', '한화에어로스페이스', '방위산업'],
    '조선':     ['조선주', 'HD현대중공업', '한화오션'],
    '2차전지':  ['2차전지', '배터리주', 'LG에너지솔루션'],
    '바이오':   ['바이오주', '제약바이오', '삼성바이오로직스'],
    '원자력':   ['원자력주', 'SMR', '두산에너빌리티'],
    'AI전력':   ['AI 전력', '전력설비', 'HD현대일렉트릭'],
    '우주항공': ['우주항공', '우주산업', '항공우주'],
    '로봇':     ['로봇주', '휴머노이드', '레인보우로보틱스'],
    '태양광':   ['태양광주', '한화솔루션', '신재생에너지'],
    '건설':     ['건설주', '건설사 주가', '대우건설'],
    '금귀금속': ['금 시세', '금현물', '고려아연'],
}

# 뉴스 이벤트 결합형 쿼리 (v2.3 — 테마명 단독 쿼리는 display 상한 절단편의로 폐기)
EVENT_SUFFIX = ['공급계약', '수주', '정부 지원', '증설', '규제']
MIN_ARTICLES = 20        # 윈도 내 기사가 이보다 적으면 별칭으로 폴백

# 뉴스 검색어 별칭 — 테마 라벨이 실제 한국어 검색어가 아닌 경우 대체어를 쓴다.
# (2026-07-27 추가: '금귀금속 공급계약' 같은 쿼리가 1건만 반환해 sent 가 단일 기사로 왜곡됐다.
#  라벨은 내부 식별자이고 검색어는 별개라는 점을 반영한 버그 수정이며, 트랙 B의 동결 파라미터
#  (mom20 하위컷·감성컷·픽 수) 변경이 아니다. 적용 시점을 loop-log 에 기록할 것.)
NEWS_ALIAS = {
    '금귀금속': ['금값', '귀금속', '고려아연'],
    'AI전력':   ['AI 데이터센터 전력', '전력기기', '변압기'],
    '은행금융': ['은행', '금융지주'],
    '2차전지':  ['2차전지', '배터리'],
    '우주항공': ['우주항공', '위성'],
}


def news_terms(theme):
    return NEWS_ALIAS.get(theme, [theme])

# 감성 어휘 사전 (제목·요약 기준). 자동 분류이며 sent_method 컬럼에 'lexicon'으로 기록한다.
POS = ['수주', '공급계약', '체결', '증설', '흑자', '호실적', '실적 개선', '어닝서프라이즈', '상향',
       '급등', '강세', '신고가', '최대 실적', '수출', '확대', '투자 유치', '선정', '승인', '돌파',
       '반등', '호재', '목표주가 상향', '수혜', '기대', '성장', '진출', '개선']
NEG = ['급락', '약세', '하락', '적자', '부진', '쇼크', '하향', '리콜', '중단', '취소', '철회',
       '유상증자', '전환사채', '규제', '제재', '과징금', '소송', '파업', '무산', '악재',
       '목표주가 하향', '우려', '경고', '감산', '구조조정', '신저가', '손실', '연기']


def _read_key(name):
    p = os.path.join(LOOP, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return f.read().strip()


def _api(url, headers, data=None, timeout=15):
    req = urllib.request.Request(url, headers=headers, data=data,
                                 method='POST' if data else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def load_themes():
    with open(THEMES_CSV, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def window_bounds(date_str):
    """장전 신호 윈도: D-1 16:00 ~ D 09:00 (KST). D-1은 직전 '달력일'이 아니라
    주말을 건너뛴 직전 영업일 기준으로 잡는다."""
    d = datetime.strptime(date_str, '%Y%m%d').replace(tzinfo=KST)
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5:            # 토(5)·일(6) 건너뜀
        prev -= timedelta(days=1)
    start = prev.replace(hour=16, minute=0, second=0, microsecond=0)
    end = d.replace(hour=9, minute=0, second=0, microsecond=0)
    return start, end


def classify(text):
    t = (text or '').replace('<b>', '').replace('</b>', '')
    pos = sum(1 for k in POS if k in t)
    neg = sum(1 for k in NEG if k in t)
    if pos > neg:
        return 'buy'
    if neg > pos:
        return 'sell'
    return 'neutral'


def fetch_search(themes, date_str, cid, sec):
    """데이터랩 검색어트렌드 → search = 당일 ratio / 직전 5영업일 평균."""
    d = datetime.strptime(date_str, '%Y%m%d')
    start = (d - timedelta(days=14)).strftime('%Y-%m-%d')
    end = d.strftime('%Y-%m-%d')
    headers = {'X-Naver-Client-Id': cid, 'X-Naver-Client-Secret': sec,
               'Content-Type': 'application/json'}
    out = {}
    groups = [{'groupName': t['theme'], 'keywords': THEME_KEYWORDS.get(t['theme'], [t['theme']])}
              for t in themes]
    for i in range(0, len(groups), 5):                    # API 제한: 그룹 5개/호출
        body = json.dumps({'startDate': start, 'endDate': end, 'timeUnit': 'date',
                           'keywordGroups': groups[i:i + 5]}, ensure_ascii=False).encode('utf-8')
        try:
            res = _api('https://openapi.naver.com/v1/datalab/search', headers, body)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"[datalab] HTTP {e.code} — {e.read()[:200].decode('utf-8', 'ignore')}")
        for g in res.get('results', []):
            pts = g.get('data', [])
            if not pts:
                out[g['title']] = ''
                continue
            same = [p for p in pts if p['period'] == end]
            cur = same[0]['ratio'] if same else pts[-1]['ratio']
            base = [p['ratio'] for p in pts if p['period'] != end][-5:]
            avg = sum(base) / len(base) if base else 0
            out[g['title']] = round(cur / avg, 4) if avg else ''
        time.sleep(0.3)
    return out


def _scan_query(term, suf, start, end, headers):
    """단일 (검색어, 이벤트접미사) 쿼리를 윈도 시작 시각까지 페이지네이션하며 훑는다.
    반환: (윈도 내 기사 리스트, capped, reached_window)"""
    q = urllib.parse.quote(f'{term} {suf}')
    hits, reached, capped = [], False, 0
    for st in range(1, 1001, 100):
        url = (f'https://openapi.naver.com/v1/search/news.json?query={q}'
               f'&display=100&start={st}&sort=date')
        try:
            res = _api(url, headers)
        except urllib.error.HTTPError as e:
            if e.code == 429:                     # 레이트리밋 — 잠깐 쉬고 한 번 재시도
                time.sleep(1.0)
                try:
                    res = _api(url, headers)
                except urllib.error.HTTPError:
                    break
            elif e.code == 400:                   # start 상한 초과
                break
            else:
                print(f"  [news] {term}/{suf} HTTP {e.code} — 건너뜀", file=sys.stderr)
                break
        items = res.get('items', [])
        if not items:
            break
        oldest = None
        for it in items:
            try:
                pub = datetime.strptime(it['pubDate'],
                                        '%a, %d %b %Y %H:%M:%S %z').astimezone(KST)
            except (KeyError, ValueError):
                continue
            oldest = pub if oldest is None else min(oldest, pub)
            if start <= pub <= end:
                reached = True
                hits.append((it.get('link') or it.get('originallink'),
                             (it.get('title') or '').replace('<b>', '').replace('</b>', ''),
                             it.get('description') or '',
                             pub.strftime('%Y-%m-%d %H:%M')))
        if oldest is not None and oldest < start:
            break                                 # 윈도 시작보다 과거까지 내려옴 → 완료
        if len(items) < 100:
            break
    else:
        capped = 1                                # start 1000 소진하고도 윈도 미도달
    return hits, capped, reached


def _tally(theme, results, seen, audit, pool=None):
    """pool: 5선 작성용 원본 보존 리스트(theme,title,link,pub,desc,label).
    news_audit는 shadow 검수용 포맷(theme,title,label)이라 컬럼을 늘리지 않고
    별도 파일 news_pool_<date>.csv 로 뽑는다."""
    tot = buy = sell = neu = 0
    for row in results:
        link, title, desc = row[0], row[1], row[2]
        pub = row[3] if len(row) > 3 else ''
        if link in seen:
            continue
        seen.add(link)
        lab = classify(title + ' ' + desc)
        tot += 1
        buy += lab == 'buy'
        sell += lab == 'sell'
        neu += lab == 'neutral'
        audit.append([theme, title, lab])
        if pool is not None:
            pool.append([theme, title, link, pub,
                         (desc or '').replace('<b>', '').replace('</b>', '')[:300], lab])
    return tot, buy, sell, neu


def fetch_news(themes, date_str, cid, sec, workers=8):
    """이벤트 결합형 쿼리로 윈도 내 발행 기사를 세고 제목·요약을 3분류.

    (테마 × 이벤트접미사) 쿼리 단위를 스레드풀로 병렬 실행한다 — 호출당 0.15초라
    순차로 돌리면 사후수집 시 수백 콜이 누적돼 수 분이 걸린다. 페이지네이션은 조기 종료가
    필요하므로 쿼리 단위 안에서는 순차로 유지한다."""
    start, end = window_bounds(date_str)
    headers = {'X-Naver-Client-Id': cid, 'X-Naver-Client-Secret': sec}
    counts, audit, pool = {}, [], []

    def run_terms(term_map):
        """{theme: [검색어...]} → {(theme, term, suf): (hits, capped, reached)}"""
        jobs = [(th, tm, sf) for th, tms in term_map.items() for tm in tms
                for sf in EVENT_SUFFIX]
        out = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fut = {ex.submit(_scan_query, tm, sf, start, end, headers): (th, tm, sf)
                   for th, tm, sf in jobs}
            for f in as_completed(fut):
                out[fut[f]] = f.result()
        return out

    # 1차 — 테마명으로만 (평상시 15테마 × 5쿼리)
    res = run_terms({t['theme']: [t['theme']] for t in themes})
    state = {}
    for t in themes:
        th = t['theme']
        seen = set()
        cap = max(res[(th, th, sf)][1] for sf in EVENT_SUFFIX)
        reach = any(res[(th, th, sf)][2] for sf in EVENT_SUFFIX)
        hits = [h for sf in EVENT_SUFFIX for h in res[(th, th, sf)][0]]
        tot, buy, sell, neu = _tally(th, hits, seen, audit, pool)
        state[th] = dict(total=tot, buy=buy, sell=sell, neutral=neu,
                         capped=cap, exhausted=int(cap and not reach), alias=0, seen=seen)

    # 2차 — 기사가 MIN_ARTICLES 미만인 테마만 별칭으로 폴백 (호출량 절약)
    fb = {th: [x for x in NEWS_ALIAS.get(th, []) if x != th]
          for th, v in state.items() if v['total'] < MIN_ARTICLES and NEWS_ALIAS.get(th)}
    fb = {k: v for k, v in fb.items() if v}
    if fb:
        desc = ', '.join('%s(%d건)' % (k, state[k]['total']) for k in fb)
        print("  [news] 별칭 폴백: " + desc, file=sys.stderr)
        res2 = run_terms(fb)
        for th, tms in fb.items():
            hits = [h for tm in tms for sf in EVENT_SUFFIX for h in res2[(th, tm, sf)][0]]
            t2, b2, s2, n2 = _tally(th, hits, state[th]['seen'], audit, pool)
            state[th]['total'] += t2
            state[th]['buy'] += b2
            state[th]['sell'] += s2
            state[th]['neutral'] += n2
            state[th]['alias'] = 1

    for th, v in state.items():
        v.pop('seen')
        counts[th] = v
    return counts, audit, pool


def log_run(date_str, post_hoc, n_search, n_news, note):
    new = not os.path.exists(COLLECT_LOG)
    with open(COLLECT_LOG, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['date', 'collected_at_kst', 'post_hoc', 'n_search_ok',
                        'n_news_ok', 'sent_method', 'note'])
        w.writerow([date_str, datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'),
                    1 if post_hoc else 0, n_search, n_news, 'lexicon', note])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True, help='YYYYMMDD')
    ap.add_argument('--pool-only', action='store_true',
                    help='news_pool_<date>.csv 만 재생성(raw·news_audit 미변경) — '
                         '5선용 풀이 없는 날의 복구용. shadow 표본을 건드리지 않는다.')
    ap.add_argument('--post-hoc', action='store_true',
                    help='장전 윈도 경과 후 사후수집임을 기록')
    ap.add_argument('--check', action='store_true', help='행 존재 여부만 확인')
    ap.add_argument('--force', action='store_true', help='기존 raw 파일이 있어도 재수집')
    a = ap.parse_args()

    raw_path = os.path.join(REF, f'raw_{a.date}.csv')

    if a.check:
        print(json.dumps({'date': a.date, 'exists': os.path.exists(raw_path),
                          'path': raw_path}, ensure_ascii=False))
        return 0

    if os.path.exists(raw_path) and not a.force and not a.pool_only:
        print(f'[{a.date}] raw 파일이 이미 존재 — 멱등 처리로 재수집 생략: {raw_path}')
        return 0

    cid, sec = _read_key('naver_clientid.txt'), _read_key('naver_secret.txt')
    if not cid or not sec:
        print('[ERROR] 네이버 오픈API 키가 없습니다.\n'
              '  loop 폴더에 naver_clientid.txt / naver_secret.txt 를 저장하세요.\n'
              '  발급: https://developers.naver.com/apps  (사용 API 에 "검색" + "데이터랩" 추가)\n'
              '  → 키가 없으면 대체 소스로 채우지 않고 중단합니다(shadow 표본 오염 방지).',
              file=sys.stderr)
        log_run(a.date, a.post_hoc, 0, 0, 'ABORT: 네이버 키 없음')
        return 2

    themes = load_themes()
    print(f'[{a.date}] 관심 신호 수집 시작 — 15테마, 윈도 {window_bounds(a.date)[0]:%m/%d %H:%M}'
          f' ~ {window_bounds(a.date)[1]:%m/%d %H:%M} KST'
          + (' (사후수집)' if a.post_hoc else ''))

    search = {} if a.pool_only else fetch_search(themes, a.date, cid, sec)
    news, audit, pool = fetch_news(themes, a.date, cid, sec)

    if a.pool_only:
        with open(os.path.join(REF, f'news_pool_{a.date}.csv'), 'w', newline='',
                  encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['theme', 'title', 'link', 'pub', 'desc', 'label'])
            w.writerows(pool)
        print(f'  [pool-only] news_pool_{a.date}.csv 재생성 {len(pool)}건 '
              f'— raw/news_audit 미변경')
        return 0

    header = ['theme', 'news_total', 'news_buy', 'news_sell', 'news_neutral', 'search',
              'yt_total', 'yt_buy', 'yt_sell', 'yt_neutral',
              'yt20_total', 'yt20_buy', 'yt20_sell', 'yt20_neutral',
              'news_capped', 'news_exhausted', 'news_alias', 'sent_method', 'post_hoc']
    n_s = n_n = 0
    with open(raw_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        for t in themes:
            th = t['theme']
            c = news.get(th, dict(total=0, buy=0, sell=0, neutral=0, capped=0, exhausted=0, alias=0))
            s = search.get(th, '')
            n_s += s != ''
            n_n += c['total'] > 0
            # 유튜브 4개 컬럼은 v2.3에서 수집 폐지 → 빈값(실패/미수집)으로 남긴다
            w.writerow([th, c['total'], c['buy'], c['sell'], c['neutral'], s,
                        '', '', '', '', '', '', '', '',
                        c['capped'], c.get('exhausted', 0), c.get('alias', 0),
                        'lexicon', 1 if a.post_hoc else 0])

    with open(os.path.join(REF, f'news_audit_{a.date}.csv'), 'w', newline='',
              encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['theme', 'title', 'label'])
        w.writerows(audit)

    # 5선 작성용 원본 풀 (링크·발행시각·요약 포함). news_audit와 달리 사람이 읽을 기사 단위.
    with open(os.path.join(REF, f'news_pool_{a.date}.csv'), 'w', newline='',
              encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['theme', 'title', 'link', 'pub', 'desc', 'label'])
        w.writerows(pool)

    log_run(a.date, a.post_hoc, n_s, n_n, f'raw_{a.date}.csv 생성 (기사 {len(audit)}건)')
    print(f'  검색 축 {n_s}/15 테마 · 뉴스 축 {n_n}/15 테마 · 기사 {len(audit)}건 분류')
    print(f'  → {raw_path}')
    if n_s < 15:
        print(f'  [주의] 검색 축 결손 {15 - n_s}테마 — 랭킹 축이므로 트랙 B 품질 저하', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
