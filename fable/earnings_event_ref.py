# -*- coding: utf-8 -*-
"""데일리 브리핑 [1-6] 실적 이벤트 달력 — 생성 데이터 (2026-10-28 신설, fable/CLAUDE.md 29번). 조회 전용.

왜: 2026-10-28 SK하이닉스 3Q 실적(장전 발표, 영업이익 83조 — 추정 76~77조 상회) 날 KODEX200 +7.6%·반도체 +8% 였는데
    브리핑은 그 일정을 싣지 않았다. 일정은 **2주 전 DART '기업설명회(IR)개최(안내공시)'** 에 이미 있었다(2026-10-14 공시, 일시 10-28 09:00).
무엇: 코스피 시가총액 상위 기업의 IR 안내공시를 읽어 **앞으로 10일 안의 실적 발표 일정**을 표로 싣고,
      하이닉스·삼성전자는 7년 실측 '발표일 반응 통계'를 함께 싣는다.
**참고 전용 — 선정 반영 금지.** 2026-10-28 검정에서 '실적 좋을 것 → 발표일 반도체 강세'와 '발표 후 시가 추종'은 둘 다
    과거 기대값이 음수였다(아래 STATS). 이 표의 목적은 방향 예측이 아니라 **변동성 큰 날을 미리 알고 비중·추격 여부를 정하는 것**이다.

사용: python3 earnings_event_ref.py --json      (캐시 _earnings_cal_cache.json, 실패 시 stale)
키: loop/dart_apikey.txt 를 읽기만 하고 출력하지 않는다.
"""
import argparse, csv, io, json, os, re, sys, time, urllib.parse, urllib.request, zipfile
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.join(os.path.dirname(HERE), 'loop')
CACHE = os.path.join(HERE, '_earnings_cal_cache.json')
HORIZON_DAYS = 10
TOPN = 15
FALLBACK = ['005930', '000660', '373220', '207940', '005380', '000270', '068270', '105560', '012450',
            '035420', '329180', '055550', '005490', '042660', '028260']

# 2026-10-28 실측(ETF 패널 2019-04~2026-09, loop/backtest/source_20261027/earn_semis*.py). 반도체 ETF=KODEX 반도체(091160).
STATS = {
    '000660': ("하이닉스 발표일(29회): 반도체 ETF − KODEX200 평균 **−0.29%p**, 이긴 날 38% · "
               "사전 목표가 상향 우세 14회는 −0.52%p(이긴 날 29%) · 발표 후 반도체 +1% 이상 갭 시작 8회는 장중 −1.26% · "
               "발표일 반도체 |등락| 2.08% (평소 1.70%), ±3% 이상 21% (평소 14%)"),
    '005930': ("삼성전자 발표일(잠정·확정 59회): 반도체 ETF − KODEX200 평균 +0.11%p, 이긴 날 56% · "
               "+1% 이상 갭 시작 13회는 장중 초과 −0.67%p · 갭 하락 시작 24회는 장중 초과 +0.69%p(71%) · "
               "발표일 반도체 |등락| 1.82% (평소 1.70%)"),
}
FOOTNOTE = ("※ **참고 전용 — 선정·비중·청산에 쓰지 않습니다.** 실적 일정은 방향 신호가 아닙니다: 7년 실측에서 '좋은 실적 예상 → 발표일 "
            "반도체 강세'와 '발표 후 시가 추종'은 모두 평균이 음수였습니다. 큰 변동이 날 수 있는 날을 미리 아는 용도입니다.")


def _key():
    return open(os.path.join(LOOP, 'dart_apikey.txt'), encoding='utf-8-sig').read().strip()


def _get(url, raw=False, tries=3):
    for k in range(tries):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()
            return b if raw else json.loads(b.decode('utf-8', 'ignore'))
        except Exception:
            time.sleep(1 + k)
    return None


def targets():
    """코스피 시가총액 상위 TOPN (loop/backtest/krx_stock_panel.csv 최신일), 실패 시 FALLBACK."""
    p = os.path.join(LOOP, 'backtest', 'krx_stock_panel.csv')
    try:
        last, rows = '', []
        with open(p, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r['market'] != 'KOSPI':
                    continue
                if r['date'] > last:
                    last, rows = r['date'], []
                if r['date'] == last:
                    rows.append((float(r['mktcap'] or 0), r['code'], r.get('name') or ''))
        rows.sort(reverse=True)
        out = [(c, n) for _, c, n in rows[:TOPN]]
        if len(out) >= 5:
            return out
    except Exception:
        pass
    return [(c, '') for c in FALLBACK]


def corp_map():
    m = {}
    with open(os.path.join(LOOP, 'backtest', '_dart_corpcode.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            m[r['stock_code'].zfill(6)] = r['corp_code']
    return m


def parse_ir(key, rcept_no):
    b = _get('https://opendart.fss.or.kr/api/document.xml?' + urllib.parse.urlencode(dict(crtfc_key=key, rcept_no=rcept_no)), raw=True)
    if not b:
        return None
    try:
        z = zipfile.ZipFile(io.BytesIO(b)); t = z.read(z.namelist()[0]).decode('utf-8', 'ignore')
    except Exception:
        return None
    t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t))
    m = re.search(r'일시\s*(\d{4}-\d{2}-\d{2})\s*(\d{1,2}:\d{2})?', t)
    pur = re.search(r'개최목적\s*(.{0,60}?)\s*4\.', t)
    if not m:
        return None
    return dict(date=m.group(1).replace('-', ''), time=m.group(2) or '', purpose=(pur.group(1).strip() if pur else ''))


def build(today):
    key = _key(); cm = corp_map(); rows = []
    bgn = (datetime.strptime(today, '%Y%m%d') - timedelta(days=45)).strftime('%Y%m%d')
    end_lim = (datetime.strptime(today, '%Y%m%d') + timedelta(days=HORIZON_DAYS)).strftime('%Y%m%d')
    for code, name in targets():
        cc = cm.get(code)
        if not cc:
            continue
        r = _get('https://opendart.fss.or.kr/api/list.json?' + urllib.parse.urlencode(
            dict(crtfc_key=key, corp_code=cc, bgn_de=bgn, end_de=today, page_count=100)))
        if not r or r.get('status') not in ('000', '013'):
            raise RuntimeError('DART 조회 실패')
        seen = {}
        for x in r.get('list', []):                      # 최신 공시 우선(정정 포함 — 정정이 최종 일시)
            if '기업설명회' not in x['report_nm']:
                continue
            info = parse_ir(key, x['rcept_no'])
            if not info or not ('실적' in info['purpose'] or '경영' in info['purpose']):
                continue
            if info['date'] in seen:                     # 같은 IR 일시의 이전(최초) 안내공시 → 안내일만 앞당긴다
                seen[info['date']]['filed'] = min(seen[info['date']]['filed'], x['rcept_dt'])
                continue
            row = dict(code=code, name=x['corp_name'] or name, date=info['date'], time=info['time'],
                       purpose=info['purpose'][:40], filed=x['rcept_dt'], stat=STATS.get(code, ''))
            seen[info['date']] = row
            if today <= info['date'] <= end_lim:
                rows.append(row)
        time.sleep(0.2)
    rows.sort(key=lambda z: (z['date'], z['time']))
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json', action='store_true'); ap.add_argument('--date')
    a = ap.parse_args()
    today = a.date or datetime.now(KST).strftime('%Y%m%d')
    blk = dict(asof=today, horizon_days=HORIZON_DAYS, stale=False, rows=[], footnote=FOOTNOTE)
    try:
        blk['rows'] = build(today)
        json.dump(blk, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception as e:
        if os.path.exists(CACHE):
            old = json.load(open(CACHE, encoding='utf-8'))
            blk['rows'] = [r for r in old.get('rows', []) if r['date'] >= today]
        blk['stale'] = True; blk['error'] = type(e).__name__
    if a.json:
        print(json.dumps(blk, ensure_ascii=False))
    else:
        for r in blk['rows']:
            print(r['date'], r['time'], r['name'], r['purpose'], '| 공시', r['filed'])
            if r['stat']:
                print('   ', r['stat'])
        print(FOOTNOTE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
