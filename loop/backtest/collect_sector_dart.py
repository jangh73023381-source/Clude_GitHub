#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_sector_dart.py — 종목 → 업종(한국표준산업분류 induty_code)을 DART 로 수집. 멱등·이어받기.

`collect_sector_yf.py`(GICS 계열)와 **같은 개념을 다른 분류로** 만들어 R3(정의 교체 재현)
관문을 처음부터 통과시키기 위한 대조군이다. 어느 한쪽에서만 나오는 결과는 채택하지 않는다.

준비 — API 키 1개
  DART OPEN API 키(이미 DART MCP 에 쓰고 있는 그 키)를 **`loop/dart_apikey.txt`** 에
  한 줄로 저장한다. 이 프로젝트의 다른 키들과 같은 방식이다.
  키는 읽기만 하며 화면·로그·보고서에 출력하지 않는다.

사용
  python3 backtest/collect_sector_dart.py            # 기본 600종씩
  python3 backtest/collect_sector_dart.py 3000
  같은 명령을 반복하면 아직 안 받은 종목만 이어받는다.

출력  backtest/stock_sector_dart.csv  (code, market, name, corp_code, induty_code)
      backtest/_dart_corpcode.csv     (종목코드 ↔ DART 고유번호 매핑 캐시, 1회 다운로드)
조회 전용이다. 공시 제출·수정 기능은 호출하지 않는다.
"""
import csv, io, os, sys, time, json, zipfile, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
KEYFILE = os.path.join(LOOP, 'dart_apikey.txt')
PANEL = os.path.join(HERE, 'krx_stock_panel.csv')
MAP = os.path.join(HERE, '_dart_corpcode.csv')
OUT = os.path.join(HERE, 'stock_sector_dart.csv')
BASE = 'https://opendart.fss.or.kr/api'
COLS = ['code', 'market', 'name', 'corp_code', 'induty_code']


def key():
    if not os.path.exists(KEYFILE):
        print(f'[중단] DART 키 파일이 없다: {KEYFILE}')
        print('       DART OPEN API 키를 이 파일에 한 줄로 저장한 뒤 다시 실행할 것.')
        sys.exit(2)
    return open(KEYFILE, encoding='utf-8').read().strip()


def corpcode_map(k):
    """종목코드 → DART 고유번호. 1회 다운로드 후 CSV 로 캐시한다."""
    if os.path.exists(MAP):
        return {r['stock_code']: r['corp_code']
                for r in csv.DictReader(open(MAP, encoding='utf-8'))}
    print('DART corpCode 전체 목록 다운로드 중(1회만)…')
    with urllib.request.urlopen(f'{BASE}/corpCode.xml?crtfc_key={k}', timeout=120) as r:
        raw = r.read()
    if not raw[:2] == b'PK':
        print(f'[중단] ZIP 이 아니다. 키가 잘못됐을 수 있다. 응답 앞부분: {raw[:200]!r}')
        sys.exit(2)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0])
    out = {}
    for e in ET.fromstring(xml).iter('list'):
        sc = (e.findtext('stock_code') or '').strip()
        if sc and sc != ' ':
            out[sc] = (e.findtext('corp_code') or '').strip()
    with open(MAP, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['stock_code', 'corp_code'])
        w.writerows(sorted(out.items()))
    print(f'  상장사 {len(out)}종 매핑 캐시 완료 → {MAP}')
    return out


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


def done():
    if not os.path.exists(OUT):
        return set()
    return {r['code'] for r in csv.DictReader(open(OUT, encoding='utf-8'))}


def main():
    k = key()
    cmap = corpcode_map(k)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    have = done()
    todo = [t for t in targets() if t[0] not in have]
    print(f'전체 {len(have) + len(todo)}종 · 완료 {len(have)}종 · 남은 {len(todo)}종 '
          f'→ 이번 실행 {min(limit, len(todo))}종')
    if not todo:
        print('더 받을 종목이 없다. 완료.')
        return 0

    new = not os.path.exists(OUT)
    fh = open(OUT, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh)
    if new:
        w.writerow(COLS)

    # 직렬로는 종목당 약 0.45초라 2,700종에 20분이 넘는다. 4스레드로 낮춘다.
    import queue, threading
    q = queue.Queue()
    for t in todo[:limit]:
        q.put(t)
    stat = {'ok': 0, 'nomap': 0, 'fail': 0}
    lock = threading.Lock()

    def work():
        while True:
            try:
                code, market, name = q.get_nowait()
            except queue.Empty:
                return
            cc = cmap.get(code, '')
            ind = ''
            key_ = 'nomap'
            if cc:
                try:
                    with urllib.request.urlopen(
                            f'{BASE}/company.json?crtfc_key={k}&corp_code={cc}', timeout=25) as r:
                        d = json.loads(r.read().decode('utf-8'))
                    if d.get('status') == '000':
                        ind = (d.get('induty_code') or '').strip()
                        key_ = 'ok'
                    else:
                        key_ = 'fail'
                except Exception:
                    key_ = 'fail'
            with lock:
                stat[key_] += 1
                w.writerow([code, market, name, cc, ind])
                n = sum(stat.values())
                if n % 200 == 0:
                    fh.flush()
                    print(f'  {n}/{min(limit, len(todo))} … 성공 {stat["ok"]} · '
                          f'매핑없음 {stat["nomap"]} · 실패 {stat["fail"]}')
            time.sleep(0.05)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    ok, nomap, fail = stat['ok'], stat['nomap'], stat['fail']
    fh.close()
    print(f'완료 — 성공 {ok} · DART 매핑없음 {nomap} · 실패 {fail}')
    print(f'출력: {OUT}')
    rest = len(todo) - min(limit, len(todo))
    if rest:
        print(f'아직 {rest}종 남았다. 같은 명령을 다시 실행하면 이어받는다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
