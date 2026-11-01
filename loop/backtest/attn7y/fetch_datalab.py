# -*- coding: utf-8 -*-
"""네이버 데이터랩 검색어 트렌드 7년 수집 (조회 전용, 멱등).
호출당 최대 5개 그룹. **ratio 는 호출 내 최대값=100 기준 상대값**이라 호출 간 레벨 비교는
무효다 — 그래서 분석은 섹터 자기 시계열의 비율(MA5/MA20)만 쓴다(스케일 불변).
"""
import json, os, sys, time, urllib.request, csv
from keywords import SECTOR_KW, PLACEBO_KW
LOOP = os.path.expanduser('~/mnt/loop')
CID = open(os.path.join(LOOP, 'naver_clientid.txt')).read().strip()
SEC = open(os.path.join(LOOP, 'naver_secret.txt')).read().strip()
START, END = '2019-04-01', '2026-09-07'

def call(groups):
    body = {"startDate": START, "endDate": END, "timeUnit": "date",
            "keywordGroups": [{"groupName": g, "keywords": k} for g, k in groups]}
    req = urllib.request.Request("https://openapi.naver.com/v1/datalab/search",
        data=json.dumps(body).encode(),
        headers={'X-Naver-Client-Id': CID, 'X-Naver-Client-Secret': SEC,
                 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))['results']

def run(kwmap, out):
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        print('skip', out); return
    items = list(kwmap.items())
    rows = {}
    for i in range(0, len(items), 5):
        chunk = items[i:i+5]
        for g in call(chunk):
            for p in g['data']:
                rows.setdefault(p['period'], {})[g['title']] = p['ratio']
        print('  batch', i//5+1, [c[0] for c in chunk]); time.sleep(0.4)
    cols = [g for g, _ in items]
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['date'] + cols)
        for d in sorted(rows):
            w.writerow([d.replace('-', '')] + [rows[d].get(c, '') for c in cols])
    print('wrote', out, len(rows), 'days x', len(cols))

if __name__ == '__main__':
    run(SECTOR_KW, 'sector_search.csv')
    run(PLACEBO_KW, 'placebo_search.csv')
