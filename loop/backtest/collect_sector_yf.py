#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_sector_yf.py — 종목 → 업종(GICS 계열 sector/industry) 매핑 수집. 멱등·이어받기.

왜 필요한가
  2026-08-18 확인: **KRX OPEN API 에는 업종(산업) 분류가 없다**(종목기본정보의 SECT_TP_NM 은
  코스닥 '소속부'이고 유가증권은 공란, 일별매매에는 업종 필드 자체가 없다). 업종별 breadth
  축(검증관 4회 이월 (a))을 열려면 외부 소스가 필요하다.

구현 메모 — yfinance 라이브러리를 쓰지 않는다
  yfinance(curl_cffi)는 이 클라우드에서 SSL reset 으로 죽는다. 반면 **표준 urllib 로
  finance.yahoo.com 쿠키 → getcrumb → quoteSummary(assetProfile)** 경로는 통한다(실측).
  그래서 의존성 없이 표준 라이브러리만 쓴다. 사용자 PC에서도 그대로 동작한다.

사용
  python3 backtest/collect_sector_yf.py            # 기본 600종
  python3 backtest/collect_sector_yf.py 3000
  같은 명령을 반복하면 아직 안 받은 종목만 이어받는다(중간에 끊겨도 안전).
  조회 실패도 빈값으로 기록해 무한 재시도를 막는다 — 빈값만 다시 받으려면 --retry-empty.

출력  backtest/stock_sector_yf.csv  (code, market, name, sector, industry)
조회 전용이다.
"""
import csv, json, os, queue, sys, threading, time
import urllib.request, urllib.parse, http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'krx_stock_panel.csv')
OUT = os.path.join(HERE, 'stock_sector_yf.csv')
COLS = ['code', 'market', 'name', 'sector', 'industry']
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
Q1 = 'https://query1.finance.yahoo.com'


SEEDS = ['https://fc.yahoo.com',
         'https://finance.yahoo.com/quote/005930.KS',
         'https://finance.yahoo.com/',
         'https://login.yahoo.com/']


def session(tries=4):
    """쿠키 + crumb 확보. 실패하면 (None, None).

    주의 — 씨앗 URL 은 404 를 내도 **쿠키는 심어 준다**(fc.yahoo.com 이 대표적이다).
    그래서 예외를 삼키고 계속 진행해야 한다. 여기서 return 해 버리면 세션이 안 잡힌다."""
    for attempt in range(tries):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        for seed in SEEDS:
            try:
                op.open(urllib.request.Request(seed, headers=UA), timeout=20).read()
            except Exception:
                pass                      # 404·403 이어도 쿠키는 남는다
            if len(cj):
                break
        try:
            crumb = op.open(urllib.request.Request(f'{Q1}/v1/test/getcrumb',
                                                   headers=UA), timeout=20).read().decode()
        except Exception:
            crumb = ''
        if crumb and '<' not in crumb and len(crumb) < 40:
            return op, crumb
        time.sleep(2 + 3 * attempt)
    return None, None


def profile(op, crumb, sym):
    u = (f'{Q1}/v10/finance/quoteSummary/{sym}?modules=assetProfile'
         f'&crumb={urllib.parse.quote(crumb)}')
    d = json.loads(op.open(urllib.request.Request(u, headers=UA), timeout=25).read())
    res = (d.get('quoteSummary') or {}).get('result') or []
    ap = (res[0].get('assetProfile') if res else {}) or {}
    return (ap.get('sector') or '').strip(), (ap.get('industry') or '').strip()


def targets():
    last = ''
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        if r['date'] > last:
            last = r['date']
    rows = {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        if r['date'] == last:
            rows[r['code']] = (r['code'], r['market'], r['name'])
    return sorted(rows.values())


def done(retry_empty=False):
    if not os.path.exists(OUT):
        return set()
    out = set()
    for r in csv.DictReader(open(OUT, encoding='utf-8')):
        if retry_empty and not r['sector']:
            continue
        out.add(r['code'])
    return out


def rewrite_without(codes):
    rows = [r for r in csv.DictReader(open(OUT, encoding='utf-8')) if r['code'] not in codes]
    with open(OUT, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    retry_empty = '--retry-empty' in sys.argv
    limit = int(args[0]) if args else 600

    have = done(retry_empty)
    if retry_empty and os.path.exists(OUT):
        empties = {r['code'] for r in csv.DictReader(open(OUT, encoding='utf-8'))
                   if not r['sector']}
        if empties:
            rewrite_without(empties)
            print(f'빈값 {len(empties)}종을 지우고 다시 받는다.')
    todo = [t for t in targets() if t[0] not in have]
    print(f'전체 {len(have) + len(todo)}종 · 완료 {len(have)}종 · 남은 {len(todo)}종 '
          f'→ 이번 실행 {min(limit, len(todo))}종')
    if not todo:
        print('더 받을 종목이 없다. 완료.')
        return 0

    op, crumb = session()
    if not op:
        print('[중단] 야후 세션(crumb) 확보 실패. 잠시 후 다시 실행할 것.')
        return 2

    q = queue.Queue()
    for t in todo[:limit]:
        q.put(t)
    rows, lock = [], threading.Lock()
    stat = {'ok': 0, 'fail': 0}

    def work():
        while True:
            try:
                code, market, name = q.get_nowait()
            except queue.Empty:
                return
            sym = code + ('.KS' if market == 'KOSPI' else '.KQ')
            sec = ind = ''
            try:
                sec, ind = profile(op, crumb, sym)
            except Exception:
                pass
            with lock:
                rows.append([code, market, name, sec, ind])
                stat['ok' if sec else 'fail'] += 1
                n = stat['ok'] + stat['fail']
                if n % 200 == 0:
                    print(f'  {n}/{min(limit, len(todo))} … 업종확보 {stat["ok"]} · 빈값 {stat["fail"]}')
            time.sleep(0.08)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(5)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COLS)
        w.writerows(sorted(rows))
    print(f'완료 — 업종확보 {stat["ok"]} · 빈값 {stat["fail"]} · 출력 {OUT}')
    rest = len(todo) - min(limit, len(todo))
    if rest:
        print(f'아직 {rest}종 남았다. 같은 명령을 다시 실행하면 이어받는다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
