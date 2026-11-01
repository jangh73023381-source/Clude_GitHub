#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dart_scan_record.py — DART 공시 주간 스캔 채점·기록 (attention_pilot.md v2.3 신설 소스)

OpenDART 조회 자체는 MCP(`mcp__opendart__search_disclosures`)로 에이전트가 수행하고,
이 스크립트는 그 결과를 받아 **가점/감점 규칙에 따라 채점하고 CSV에 누적**한다.
(파이썬에서 MCP를 직접 호출할 수 없어 조회와 채점을 분리했다.)

v2.3 규칙 — 뉴스·유튜브와 달리 DART는 과거 조회가 가능해 **유일하게 진짜 백테스트가 되는**
관심 소스다. 초기 20영업일은 **기록 전용**이며 컴포짓에 반영하지 않는다.

  가점(+1) : 단일판매ㆍ공급계약체결 / 수주 / 공급계약 / 유형자산취득(증설) /
             투자판단관련주요경영사항
  감점(-1) : 유상증자결정 / 전환사채권발행결정 / 생산중단 / 영업정지 / 중대재해발생

주기: 매주 첫 거래일 1회. 점수는 5거래일 캐리(다음 스캔까지 유효).

★ 알려진 결함 (2026-09-14 실측) — 월요일 아침 창은 사실상 빈 창이다.
  스캔 창은 `start=그 주 월요일, end=오늘` 이라, 월요일 06:20 에 돌리면 창이 그 하루뿐이고
  DART 에 올라온 공시가 전 시장 1건(2026-09-14 실측)밖에 없다. 그런데 `already_scanned(ws)`
  가 그 주를 '스캔 완료'로 못 박아 버려서, 주중에 실제 공시가 쌓여도 같은 주를 다시 스캔하지
  않는다. 즉 **매주 월요일 실행이 그 주 공시를 구조적으로 놓친다.**
  기록 전용 소스라 선정·채점에는 영향이 없으나, 이 CSV 를 백테스트 입력으로 쓰기 전에는
  반드시 먼저 고쳐야 한다. 수정 위치·방법 두 가지:
    (a) `already_scanned()` 를 '그 주에 금요일까지의 창으로 기록됐는가'로 바꾸고 주중 재스캔
        시 같은 week_start 행을 교체(safe_io.safe_replace)한다. 또는
    (b) 창을 `start=지난주 월요일, end=오늘` 로 한 주 뒤로 밀어 완결된 주만 기록한다.
  (b) 가 멱등성을 깨지 않아 더 안전하다. 창 정의는 `--due` 분기의 'window' 와
  loop/CLAUDE.md §2 0-D 를 함께 고쳐야 한다.

사용:
  # 1) 에이전트가 MCP로 조회한 결과를 JSON으로 저장  {"삼성전자": ["공시제목1", ...], ...}
  # 2) 채점·기록
  python3 dart_scan_record.py --week-start 20260727 --input dart_raw_20260727.json

  python3 dart_scan_record.py --due            # 이번 주 스캔이 필요한지만 판정(JSON 출력)

산출: references/attention_dart_scan.csv
      (week_start, theme, company, n_pos, n_neg, score, titles)
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(HERE, '..'))
WATCHLIST = os.path.join(REF, 'attention_dart_watchlist.csv')
SCAN_CSV = os.path.join(REF, 'attention_dart_scan.csv')
KST = timezone(timedelta(hours=9))

POS_KEYS = ['단일판매', '공급계약체결', '공급계약', '수주', '유형자산 취득', '유형자산취득',
            '투자판단관련주요경영사항', '투자판단 관련 주요경영사항']
NEG_KEYS = ['유상증자결정', '유상증자 결정', '전환사채권발행결정', '전환사채권 발행결정',
            '생산중단', '영업정지', '중대재해발생', '중대재해 발생']


def load_watchlist():
    with open(WATCHLIST, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def week_start_of(date_str):
    d = datetime.strptime(date_str, '%Y%m%d')
    return (d - timedelta(days=d.weekday())).strftime('%Y%m%d')   # 그 주 월요일


def already_scanned(ws):
    if not os.path.exists(SCAN_CSV):
        return False
    with open(SCAN_CSV, encoding='utf-8') as f:
        return any(r.get('week_start') == ws for r in csv.DictReader(f))


def score_titles(titles):
    pos = neg = 0
    for t in titles:
        t = (t or '').replace(' ', '')
        # '[기재정정]' 등 접두어가 붙어도 부분일치로 잡는다
        if any(k.replace(' ', '') in t for k in POS_KEYS):
            pos += 1
        if any(k.replace(' ', '') in t for k in NEG_KEYS):
            neg += 1
    return pos, neg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week-start', default=datetime.now(KST).strftime('%Y%m%d'),
                    help='스캔 기준일(YYYYMMDD). 내부적으로 그 주 월요일로 정규화된다.')
    ap.add_argument('--input', help='{"회사명": ["공시제목", ...]} 형태 JSON 파일')
    ap.add_argument('--due', action='store_true', help='이번 주 스캔 필요 여부만 판정')
    a = ap.parse_args()

    ws = week_start_of(a.week_start)

    if a.due:
        wl = load_watchlist()
        print(json.dumps({
            'week_start': ws,
            'already_scanned': already_scanned(ws),
            'due': not already_scanned(ws),
            'n_companies': len(wl),
            'companies': [r.get('dart_name') or r['company'] for r in wl],
            'unresolved': [r['company'] for r in wl if not (r.get('dart_name') or '').strip()],
            'window': {'start': ws, 'end': a.week_start},
        }, ensure_ascii=False))
        return 0

    if not a.input:
        sys.exit('--input 또는 --due 중 하나가 필요합니다.')
    if already_scanned(ws):
        print(f'[{ws}] 이미 스캔 기록 있음 — 멱등 처리로 생략')
        return 0

    data = json.load(open(a.input, encoding='utf-8'))
    wl = load_watchlist()
    new = not os.path.exists(SCAN_CSV)
    tot_p = tot_n = 0
    with open(SCAN_CSV, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['week_start', 'theme', 'company', 'n_pos', 'n_neg', 'score', 'titles'])
        for r in wl:
            titles = data.get(r.get('dart_name') or r['company'], data.get(r['company'], []))
            p, n = score_titles(titles)
            tot_p += p
            tot_n += n
            w.writerow([ws, r['theme'], r['company'], p, n, p - n, ' | '.join(titles)[:500]])

    # 테마별 요약 출력 (기록 전용 — 컴포짓 미반영)
    agg = {}
    for r in wl:
        p, n = score_titles(data.get(r.get('dart_name') or r['company'], data.get(r['company'], [])))
        t = agg.setdefault(r['theme'], [0, 0])
        t[0] += p
        t[1] += n
    print(f'[{ws}] DART 주간 스캔 기록 — 워치리스트 {len(wl)}종목, 가점 {tot_p} / 감점 {tot_n}')
    for th, (p, n) in sorted(agg.items(), key=lambda x: -(x[1][0] - x[1][1])):
        if p or n:
            print(f'  {th:10s} +{p} / -{n}  (score {p - n:+d})')
    print(f'  → {SCAN_CSV}')
    print('  ※ 초기 20영업일은 기록 전용 — 트랙 B 컴포짓에 반영하지 않는다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
