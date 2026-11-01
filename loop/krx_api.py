#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""krx_api.py — 한국거래소 정보데이터시스템 OPEN API 수집기 (조회 전용).

2026-08-14 신설. 승인 대기 중 미리 작성해 둔 것으로, 서비스 승인이 나면
그대로 실행하면 된다.

인증: 헤더 `AUTH_KEY`. 키는 `loop/krx_apikey.txt` 에서 읽으며 절대 출력하지 않는다.
      (CLAUDE.md 0장 — 자격증명은 읽지도, 로그·보고서에 출력하지도 않는다)

응답 판별
  {"respMsg":"Unauthorized Key"}      → 키 자체가 무효
  {"respMsg":"Unauthorized API Call"} → 키는 유효하나 **해당 서비스 미승인**
  {"OutBlock_1":[...]}                → 정상

주문·매매 기능은 존재하지 않으며 구현하지 않는다.

사용:
  python3 krx_api.py check                      # 서비스별 승인 상태 점검
  python3 krx_api.py stock 20260801 20260813    # 개별종목 일별 패널 수집
  python3 krx_api.py breadth 20260801 20260813  # 등락 breadth 산출
"""
import json, os, sys, time, urllib.request, urllib.error, csv
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE if os.path.exists(os.path.join(HERE, 'krx_apikey.txt')) else os.path.dirname(HERE)
KEYFILE = os.path.join(ROOT, 'krx_apikey.txt')
BASE = 'https://data-dbg.krx.co.kr/svc/apis'
OUT_PANEL = os.path.join(ROOT, 'backtest', 'krx_stock_panel.csv')
OUT_BREADTH = os.path.join(ROOT, 'references', 'breadth_daily.csv')

SERVICES = {
    # ── 필수 (이것만 있어도 breadth·업종분류·ETF 패널이 전부 열린다)
    'sto/stk_bydd_trd':      '★필수 유가증권 일별매매 — breadth·개별종목 패널',
    'sto/ksq_bydd_trd':      '★필수 코스닥 일별매매 — breadth(코스닥 포함)',
    'sto/stk_isu_base_info': '★필수 유가증권 종목기본정보 — 공식 업종분류',
    'sto/ksq_isu_base_info': '★필수 코스닥 종목기본정보 — 공식 업종분류',
    'etp/etf_bydd_trd':      '★필수 ETF 일별매매 — 현 패널 공식소스 교체',
    # ── 권장
    'idx/kospi_dd_trd':      '☆권장 코스피 지수 — ensure_kospi 결함 해소',
    'idx/kosdaq_dd_trd':     '☆권장 코스닥 지수 — 코스피/코스닥 상대강도축',
    'idx/krx_dd_trd':        '☆권장 KRX 시리즈 지수',
    # ── 불필요 (유니버스 대상 아님): knx_*(코넥스) · sw/sr_bydd_trd(신주인수권)
    #    · bon_dd_trd(채권지수) · drvprod_dd_trd(파생지수) · etn/elw_bydd_trd
}



def _key():
    with open(KEYFILE, encoding='utf-8') as f:
        return f.read().strip()


def call(path, **params):
    """단일 호출. (status, payload) 반환. status = ok | unapproved | badkey | error"""
    q = '&'.join(f'{k}={v}' for k, v in params.items())
    req = urllib.request.Request(f'{BASE}/{path}?{q}', headers={'AUTH_KEY': _key()})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode('utf-8'))
        except Exception:
            return 'error', {'respMsg': f'HTTP {e.code}'}
    except Exception as e:
        return 'error', {'respMsg': type(e).__name__}
    msg = str(data.get('respMsg', ''))
    if 'Unauthorized Key' in msg:
        return 'badkey', data
    if 'Unauthorized API Call' in msg:
        return 'unapproved', data
    if 'does not exist' in msg:
        return 'error', data
    return 'ok', data


def rows(data):
    for k, v in data.items():
        if k.startswith('OutBlock') and isinstance(v, list):
            return v
    return []


def cmd_check():
    print('서비스 승인 상태 (basDd=20260813 기준 시험 호출)')
    print('-' * 62)
    n_ok = 0
    for path, name in SERVICES.items():
        st, d = call(path, basDd='20260813')
        mark = {'ok': '★ 사용가능', 'unapproved': '미승인(신청 필요)',
                'badkey': '키 무효', 'error': '오류'}[st]
        if st == 'ok':
            n_ok += 1
            mark += f' · {len(rows(d))}행'
        print(f'  {path:24s} {name:28s} {mark}')
        time.sleep(0.2)
    print('-' * 62)
    print(f'사용 가능 {n_ok}/{len(SERVICES)}')
    if n_ok == 0:
        print('\n전부 미승인이면 키는 유효하나 서비스 신청이 아직 승인되지 않은 상태다.')
        print('KRX 정보데이터시스템 OPEN API 사이트에서 위 ★필수 서비스를 신청할 것.')
    return 0 if n_ok else 2


def _dates(a, b):
    """거래일 여부는 응답 행수로 판단(휴장일은 0행)."""
    import datetime as dt
    d0 = dt.datetime.strptime(a, '%Y%m%d').date()
    d1 = dt.datetime.strptime(b, '%Y%m%d').date()
    out = []
    while d0 <= d1:
        if d0.weekday() < 5:
            out.append(d0.strftime('%Y%m%d'))
        d0 += dt.timedelta(days=1)
    return out


def cmd_stock(a, b):
    """개별종목 일별 패널. 멱등 — 이미 있는 (날짜,코드) 는 건너뛴다."""
    have = set()
    if os.path.exists(OUT_PANEL):
        with open(OUT_PANEL, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                have.add((r['date'], r['code']))
    new, skipped = [], 0
    for d in _dates(a, b):
        got = 0
        for path, mkt in (('sto/stk_bydd_trd', 'KOSPI'), ('sto/ksq_bydd_trd', 'KOSDAQ')):
            st, data = call(path, basDd=d)
            if st != 'ok':
                print(f'  {d} {mkt}: {st} — 중단'); return 2
            for r in rows(data):
                code = r.get('ISU_SRT_CD') or r.get('ISU_CD')
                if not code or (d, code) in have:
                    skipped += 1; continue
                new.append({
                    'date': d, 'code': code, 'name': r.get('ISU_ABBRV', ''), 'market': mkt,
                    'open': r.get('TDD_OPNPRC'), 'high': r.get('TDD_HGPRC'),
                    'low': r.get('TDD_LWPRC'), 'close': r.get('TDD_CLSPRC'),
                    'chg_pct': r.get('FLUC_RT'), 'volume': r.get('ACC_TRDVOL'),
                    'value': r.get('ACC_TRDVAL'), 'mktcap': r.get('MKTCAP'),
                    'sector': r.get('IDX_IND_NM', ''),
                })
                got += 1
        print(f'  {d}: +{got}행')
        time.sleep(0.3)
    if not new:
        print('신규 행 없음 (멱등)'); return 0
    fields = list(new[0])
    exist = os.path.exists(OUT_PANEL)
    os.makedirs(os.path.dirname(OUT_PANEL), exist_ok=True)
    with open(OUT_PANEL, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exist:
            w.writeheader()
        w.writerows(new)
    print(f'기록 {len(new)}행 · 중복 건너뜀 {skipped} → {OUT_PANEL}')
    return 0


def cmd_breadth(a, b):
    """등락 breadth — 전체·업종별 상승종목 비율. 검증관이 3회 이월한 (a) 축."""
    if not os.path.exists(OUT_PANEL):
        print('먼저 stock 수집을 실행할 것'); return 2
    by = defaultdict(list)
    with open(OUT_PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if not (a <= r['date'] <= b):
                continue
            try:
                by[r['date']].append((r['sector'], float(r['chg_pct'])))
            except (TypeError, ValueError):
                continue
    out = []
    for d in sorted(by):
        v = by[d]
        up = sum(1 for _, c in v if c > 0)
        sec = defaultdict(lambda: [0, 0])
        for s, c in v:
            sec[s][1] += 1
            if c > 0:
                sec[s][0] += 1
        out.append({'date': d, 'n': len(v), 'up': up,
                    'breadth': round(up / len(v), 4) if v else '',
                    'sector_breadth': '|'.join(
                        f'{s}:{u}/{t}' for s, (u, t) in sorted(sec.items()) if t >= 5)})
    os.makedirs(os.path.dirname(OUT_BREADTH), exist_ok=True)
    with open(OUT_BREADTH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    print(f'breadth {len(out)}일 → {OUT_BREADTH}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    c = sys.argv[1]
    if c == 'check':
        sys.exit(cmd_check())
    if c in ('stock', 'breadth') and len(sys.argv) == 4:
        sys.exit((cmd_stock if c == 'stock' else cmd_breadth)(sys.argv[2], sys.argv[3]))
    print(__doc__); sys.exit(1)
