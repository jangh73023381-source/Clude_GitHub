# -*- coding: utf-8 -*-
"""korea.kr 「사실은 이렇습니다」 7년 전수 수집 — 멱등·재개형(조회 전용).
목록 HTML에 본문 요약이 통째로 들어 있어 상세 페이지를 열지 않는다(수집비용 1/20).
사용: python3 fetch.py <예산(페이지수)>   — 남은 페이지가 없으면 즉시 종료
"""
import re, html, json, os, sys, time, urllib.request
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
BASE = "https://www.korea.kr/briefing/actuallyList.do"
OUT = 'actually_raw.jsonl'
STATE = '_state.json'
YEARS = [(f"{y}-01-01", f"{y}-12-31") for y in range(2019, 2027)]

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode('utf-8', 'replace')

def parse(h):
    out = []
    for m in re.finditer(r'actuallyView\.do\?newsId=(\d+)([^>]*)>(.*?)</a>', h, flags=re.S):
        txt = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', m.group(3)))).strip()
        if txt:
            out.append({'id': m.group(1), 'text': txt})
    return out

def main():
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    st = json.load(open(STATE)) if os.path.exists(STATE) else {'yi': 0, 'page': 1, 'done': False}
    seen = set()
    if os.path.exists(OUT):
        for L in open(OUT, encoding='utf-8'):
            try: seen.add(json.loads(L)['id'])
            except: pass
    f = open(OUT, 'a', encoding='utf-8')
    used = 0
    while used < budget and st['yi'] < len(YEARS):
        s, e = YEARS[st['yi']]
        u = f"{BASE}?pageIndex={st['page']}&startDate={s}&endDate={e}"
        try:
            items = parse(get(u))
        except Exception as ex:
            print('ERR', u, ex); break
        used += 1
        if not items:
            st['yi'] += 1; st['page'] = 1
            json.dump(st, open(STATE, 'w')); continue
        new = 0
        for it in items:
            if it['id'] in seen: continue
            seen.add(it['id']); it['year'] = s[:4]
            f.write(json.dumps(it, ensure_ascii=False) + '\n'); new += 1
        st['page'] += 1
        json.dump(st, open(STATE, 'w'))
        if used % 20 == 0: print(f"  {s[:4]} p{st['page']} 누적 {len(seen)}")
        time.sleep(0.15)
    f.close()
    st['done'] = st['yi'] >= len(YEARS)
    json.dump(st, open(STATE, 'w'))
    print(f"요청 {used}회 · 누적 {len(seen)}건 · 진행 {YEARS[min(st['yi'],len(YEARS)-1)][0][:4]} p{st['page']} · done={st['done']}")

if __name__ == '__main__':
    main()
