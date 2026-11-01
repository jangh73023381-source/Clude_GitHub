# -*- coding: utf-8 -*-
"""korea.kr 「사실은 이렇습니다」 7년 전수 수집 — 멱등·재개형(조회 전용).
목록 HTML에 제목·요약·날짜·부처가 전부 들어 있어 상세 페이지를 열지 않는다.
주의 ① 상단 'List Top Style01' 추천 항목은 날짜 필터를 무시하므로 연도 밖이면 버린다.
     ② 페이지를 넘겨도 신규 0건이면 그 연도는 끝난 것이다(마지막 페이지가 반복 반환된다).
사용: python3 fetch2.py <예산(페이지수)>
"""
import re, html, json, os, sys, time, urllib.request
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
BASE = "https://www.korea.kr/briefing/actuallyList.do"
OUT, STATE = 'actually2.jsonl', '_state3.json'
YEARS = [(f"{y}-01-01", f"{y}-12-31") for y in range(2019, 2027)]

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode('utf-8', 'replace')

def clean(x):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', x))).strip()

def parse(h, year):
    out = []
    for m in re.finditer(r'actuallyView\.do\?newsId=(\d+)[^>]*>(.*?)</a>', h, flags=re.S):
        blk = m.group(2)
        dm = re.search(r'class="source">\s*<span>\s*(\d{4})[.-](\d{2})[.-](\d{2})\s*</span>\s*<span>\s*([^<]*)</span>', blk)
        if not dm: continue
        d = dm.group(1) + dm.group(2) + dm.group(3)
        if d[:4] != year: continue
        t = re.search(r'<strong>(.*?)</strong>', blk, flags=re.S)
        ld = re.search(r'class="lead">(.*?)</span>', blk, flags=re.S)
        out.append({'id': m.group(1), 'date': d, 'org': dm.group(4).strip(),
                    'title': clean(t.group(1)) if t else '',
                    'lead': clean(ld.group(1)) if ld else ''})
    return out

def main():
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    st = json.load(open(STATE)) if os.path.exists(STATE) else {'yi': 0, 'page': 1, 'dry': 0}
    seen = set()
    if os.path.exists(OUT):
        for L in open(OUT, encoding='utf-8'):
            try: seen.add(json.loads(L)['id'])
            except: pass
    f = open(OUT, 'a', encoding='utf-8'); used = 0
    while used < budget and st['yi'] < len(YEARS):
        s, e = YEARS[st['yi']]; yr = s[:4]
        try:
            items = parse(get(f"{BASE}?pageIndex={st['page']}&startDate={s}&endDate={e}"), yr)
        except Exception as ex:
            print('ERR', ex); break
        used += 1; new = 0
        for it in items:
            if it['id'] in seen: continue
            seen.add(it['id']); f.write(json.dumps(it, ensure_ascii=False) + '\n'); new += 1
        st['dry'] = st['dry'] + 1 if new == 0 else 0
        if st['dry'] >= 2:
            print(f"  {yr} 완료 (누적 {len(seen)})"); st['yi'] += 1; st['page'] = 1; st['dry'] = 0
        else:
            st['page'] += 1
        json.dump(st, open(STATE, 'w')); time.sleep(0.12)
    f.close()
    done = st['yi'] >= len(YEARS)
    json.dump({**st, 'done': done}, open(STATE, 'w'))
    nxt = YEARS[min(st['yi'], len(YEARS)-1)][0][:4]
    print(f"요청 {used}회 · 누적 {len(seen)}건 · 진행 {nxt} p{st['page']} · done={done}")

if __name__ == '__main__':
    main()
