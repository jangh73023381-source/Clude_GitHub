#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""조합8(SEARCH-LED) shadow 워크포워드 트래커 — 코스피 지수 대비 초과수익 누적.

설계(2026-07-26 확정, 표본 10일 백테스트 근거):
  랭킹  = 네이버 데이터랩 검색 모멘텀 z (z_search)   ← 유일한 양(+) IC 소스
  필터1 = 테마 mom20 하방필터 (D-1 종가 기준 15테마 중 하위 1/3(11~15위) 배제)
  필터2 = 뉴스 감성 악재 배제 (sent < -0.15 테마 배제)  ← 뉴스는 랭킹이 아니라 배제용
  픽    = 상위 5종 동일가중, 1일 보유(D-1 종가 → D 종가), 무비용(2026-08-14~)

멱등 누적: 이미 기록된 date 행은 다시 쓰지 않는다.
사용: python3 combo_shadow_tracker.py [YYYYMMDD ...]   (인자 없으면 picks 전체 스캔)
주의: 이 트래커는 shadow(기록 전용)다. 실제 데일리 브리핑 선정에는 20영업일 누적·판정 전까지 반영하지 않는다.
"""
import csv, os, sys
from collections import defaultdict

H = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(H, '..'))
ROOT = os.path.abspath(os.path.join(REF, '..'))
PICKS = os.path.join(REF, 'attention_shadow_picks.csv')
def _newest_panel():
    """패널 파일명을 고정하면 패널을 연장해도 옛 날짜에서 채점이 멈춘다.
    (2026-07-28 실측: panel_close_0724 고정 탓에 20260727 행이 누락됨)"""
    d = os.path.join(ROOT, 'backtest')
    c = sorted(f for f in os.listdir(d)
               if f.startswith('panel_close_') and f.endswith('.csv'))
    return os.path.join(d, c[-1])


PANEL = _newest_panel()
KOSPI = os.path.join(ROOT, 'backtest', 'kospi_close.csv')
OUT = os.path.join(REF, 'combo_shadow_tracker.csv')
COST = 0.0  # 2026-08-14 사용자 지시 — 왕복비용 없음(무료 수수료·ETF 거래세 면제, 겹치는 종목은 계속 보유하고 교체분만 거래). 종전값 0.0010(왕복 10bp)
MOM_CUT = 10          # 15테마 중 mom20 상위 10위까지만 후보
SENT_CUT = -0.15      # 감성 z 이 값 미만이면 배제
NPICK = 5

def load_prices():
    px = defaultdict(dict); nm = {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try: px[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError): pass
        nm[r['code']] = r['name']
    return px, nm

def main():
    px, nm = load_prices()
    ks = {r['date']: float(r['close']) for r in csv.DictReader(open(KOSPI, encoding='utf-8'))}
    dates = sorted(ks)
    rows = list(csv.DictReader(open(PICKS, encoding='utf-8')))
    byd = defaultdict(list)
    for r in rows: byd[r['date']].append(r)

    done = set()
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding='utf-8')): done.add(r['date'])
    new = not os.path.exists(OUT)
    f = open(OUT, 'a', newline='', encoding='utf-8'); w = csv.writer(f)
    if new:
        w.writerow(['date','pick_themes','pick_codes','pick5_ret_pct','kospi_ret_pct',
                    'kodex200_ret_pct','excess_vs_kospi_pct','excess_vs_kodex_pct','n_excluded_mom','n_excluded_sent'])

    targets = sys.argv[1:] or sorted(byd)
    for d in targets:
        if d in done or d not in byd or d not in ks: continue
        i = dates.index(d)
        if i == 0: continue
        p = dates[i-1]
        def mom20(c):
            j = dates.index(p)
            if j < 20: return None
            a = px.get(c, {}).get(dates[j-20]); b = px.get(c, {}).get(p)
            return (b/a-1.0) if (a and b) else None
        rs = byd[d]
        mr = sorted(((r['code'], mom20(r['code']) if mom20(r['code']) is not None else -9) for r in rs),
                    key=lambda x: -x[1])
        rank = {c: k+1 for k, (c, _) in enumerate(mr)}
        picks = []; ex_m = 0; ex_s = 0
        for r in sorted(rs, key=lambda r: -float(r['z_search'])):
            if rank.get(r['code'], 99) > MOM_CUT: ex_m += 1; continue
            if float(r['sent']) < SENT_CUT: ex_s += 1; continue
            picks.append(r)
            if len(picks) == NPICK: break
        if not picks: continue
        def ret(c):
            a = px.get(c, {}).get(p); b = px.get(c, {}).get(d)
            return (b/a-1.0) if (a and b) else None
        rr = [ret(r['code']) for r in picks]; rr = [x for x in rr if x is not None]
        if not rr: continue
        pr = sum(rr)/len(rr) - COST
        kr = ks[d]/ks[p] - 1.0
        kd = ret('069500')
        w.writerow([d, '|'.join(r['theme'] for r in picks), '|'.join(r['code'] for r in picks),
                    round(pr*100, 2), round(kr*100, 2),
                    (round(kd*100, 2) if kd is not None else ''),
                    round((pr-kr)*100, 2),
                    (round((pr-kd)*100, 2) if kd is not None else ''), ex_m, ex_s])
        print('%s 픽 %s | 초과(코스피) %+.2f%%p' % (d, '·'.join(r['theme'] for r in picks), (pr-kr)*100))
    f.close()
    allr = list(csv.DictReader(open(OUT, encoding='utf-8')))
    if allr:
        v = [float(r['excess_vs_kospi_pct']) for r in allr]
        print('\n누적 %d일 | 평균 초과(코스피) %+.3f%%p | 코스피 이김 %d/%d'
              % (len(v), sum(v)/len(v), sum(1 for x in v if x > 0), len(v)))

if __name__ == '__main__':
    main()
