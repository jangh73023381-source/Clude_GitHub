# -*- coding: utf-8 -*-
"""ETF 추천 보조표 — 대표 구성종목 · 지지선 · 저항선(반등 목표) 산출 (조회 전용).

데일리 브리핑 [6-1]/[6-2] ETF 추천 표에 붙이는 참고 열을 만든다.

  대표종목  : ETF의 테마를 판정해 그 테마의 최대 시총 순수주(Rule SU 유니버스 원칙과 동일)
  지지선    : 현재가 '아래'에서 가장 가까운 기술적 레벨 (1차·2차)
  저항선    : 현재가 '위'에서 가장 가까운 기술적 레벨 (= 반등 시 1차 목표)
  ATR거리   : 지지·저항까지의 거리를 ATR(14)로 나눈 값. 종목마다 변동성이 달라
              "-3%"가 의미하는 바가 다르므로, 몇 ATR인지가 실제 판단 기준이다.

레벨 후보 = MA20 · MA60 · 20/60/120일 저점 · 20/60/120일 고점
  → 현재가 미만 중 최댓값 = 1차 지지, 그 다음 = 2차 지지
  → 현재가 초과 중 최솟값 = 1차 저항

⚠ 중요 — 이 레벨은 '예측 신호'가 아니라 '집행 참고선'이다.
   2026-07-26 백테스트(N대장 #51~#116, 66조합)에서 이평선·가격채널 기반 지지·저항 룰은
   익일 수익률 예측력이 통계적으로 유의하지 않았다(전부 p > 0.11). 따라서 이 값으로
   종목을 고르지 말고, 이미 선정된 종목의 손절선·분할매수·목표가를 잡는 용도로만 쓴다.

사용법
    python3 etf_levels.py 091160 305720 463250
    python3 etf_levels.py --file picks.txt
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# 일봉차트(ka10081)는 loop 폴더의 kiwoom_api.py에만 구현돼 있으므로 그쪽을 우선 사용한다.
# (fable 폴더의 kiwoom_api.py는 현재가·기본정보 전용)
LOOP_DIR = os.path.abspath(os.path.join(HERE, '..', 'loop'))
sys.path.insert(0, LOOP_DIR if os.path.exists(os.path.join(LOOP_DIR, 'kiwoom_api.py')) else HERE)
import kiwoom_api as k  # noqa: E402

if not hasattr(k, 'get_daily_chart'):
    raise SystemExit('kiwoom_api에 get_daily_chart가 없습니다 — loop 폴더 연결을 확인하세요.')

_basic = getattr(k, 'get_basic_info', None) or getattr(k, 'get_stock_basic_info', None)

# ── 테마 → 대표 개별종목 (Rule SU와 동일 원칙: 최대 시총 순수주) ────────────────
THEME_REP = {
    '반도체':   ('000660', 'SK하이닉스'),
    '자동차':   ('005380', '현대차'),
    '증권':     ('006800', '미래에셋증권'),
    '은행금융': ('105560', 'KB금융'),
    '방산':     ('012450', '한화에어로스페이스'),
    '조선':     ('329180', 'HD현대중공업'),
    '2차전지':  ('373220', 'LG에너지솔루션'),
    '바이오':   ('207940', '삼성바이오로직스'),
    '원자력':   ('034020', '두산에너빌리티'),
    'AI전력':   ('010120', 'LS ELECTRIC'),
    '화장품':   ('090430', '아모레퍼시픽'),
    '로봇':     ('277810', '레인보우로보틱스'),
    '태양광':   ('009830', '한화솔루션'),
    '건설':     ('047040', '대우건설'),
    '금귀금속': ('010130', '고려아연'),
    '우주항공': ('012450', '한화에어로스페이스'),
    '배당':     ('105560', 'KB금융'),
    '지수':     ('005930', '삼성전자'),
    '2차전지소재': ('005490', 'POSCO홀딩스'),
}

# 이름 키워드 → 테마 (theme_map.csv 미분류 97종을 덮기 위한 보조 분류기)
KEYWORD_THEME = [
    (('반도체', 'HBM', '소부장', '전공정', '비메모리', 'AI칩', '필라델피아'), '반도체'),
    (('원자력', '원전', 'SMR'), '원자력'),
    (('방산', '국방'), '방산'),
    (('우주', '항공', 'UAM'), '우주항공'),
    (('조선',), '조선'),
    (('2차전지', '배터리', '전고체', '음극재', '양극재'), '2차전지'),
    (('자동차', '모빌리티'), '자동차'),
    (('바이오', '헬스케어', '제약', '의료'), '바이오'),
    (('은행', '금융', '보험'), '은행금융'),
    (('증권',), '증권'),
    (('로봇', '휴머노이드', '피지컬AI'), '로봇'),
    (('전력', '전기', '변압기', '전선', '인프라'), 'AI전력'),
    (('태양광', 'ESS', '풍력', '신재생', '수소'), '태양광'),
    (('건설', '리츠', '부동산'), '건설'),
    (('금현물', '골드', '은현물', '실버', '귀금속', '구리', '비철'), '금귀금속'),
    (('화장품', '뷰티', '소비재', '음식료'), '화장품'),
    (('배당', '커버드콜', '인컴', '채권'), '배당'),
    (('200', '코스피', '코스닥', '나스닥', 'S&P', '지수', 'TOP'), '지수'),
]


def load_theme_map():
    """loop/backtest/theme_map.csv 를 우선 사용하고, 없거나 미분류면 키워드로 보완."""
    import csv
    m = {}
    for cand in (r'/sessions/wizardly-exciting-wozniak/mnt/loop/backtest/theme_map.csv',
                 os.path.join(HERE, '..', 'loop', 'backtest', 'theme_map.csv')):
        if os.path.exists(cand):
            for r in csv.DictReader(open(cand, encoding='utf-8')):
                if r.get('theme'):
                    m[r['code']] = r['theme']
            break
    return m


THEME_MAP = load_theme_map()


def theme_of(code, name):
    t = THEME_MAP.get(code)
    if t:
        return t
    n = (name or '').replace(' ', '')
    for keys, th in KEYWORD_THEME:
        if any(kw in n for kw in keys):
            return th
    return None


# ── 시세 ──────────────────────────────────────────────────────────────────
# [2026-08-22 소스 교체] 일봉을 **KRX 정합 소스 우선**으로 받는다. 키움은 폴백.
#
# 왜 바꿨나 — 포렌식 근거 (`loop/backtest/atr_forensic_20260822.py`, 135쌍 대조)
#   키움 ka10081 개별주식 일봉을 KRX 공식(`krx_stock_panel.csv`)과 9개 날짜 × 15종목으로
#   항목별 대조한 결과:
#     · 종가            135/135 = 100% 일치
#     · 20일저점·60일저점  48/48 · 47/47 = 100% 일치
#     · MA20 · MA60      비율 0.9992 · 0.9933 (사실상 일치)
#     · **20일고점        63 정확 / 키움이 더 낮음 27 / 더 높음 4**
#     · **ATR14          비율 0.9345 (sd 0.0226)**
#   → **종가도 저가도 정확한데 고가만 체계적으로 좁다.** 수정주가였다면 MA도 같은 비율로
#     줄었어야 하고(0.999), 날짜 축 문제였다면 MA가 틀렸어야 한다. 둘 다 아니다.
#   → TR = max(H−L, |H−C전일|, |L−C전일|) 이므로 고가가 낮으면 ATR 이 그대로 깎인다.
#     그 결과 브리핑 손절선(종가 − 2.0×ATR14)이 **평균 13.5% 타이트**했다.
#
# 대체 소스의 정합성은 검증됐다 — 야후 일봉 OHLC 를 KRX 공식 패널과 3종목 × 10거래일
# **30/30봉 완전 일치** 확인(2026-08-22). ETF 도 거래대금 상위 20종 ATR14 비율 19/20 = 1.000.
#
# 주의: 야후 `quote` 는 **원주가**(분배금·배당 미조정)다. 지지·저항은 "실제로 체결된 가격대"를
# 보는 것이므로 원주가가 오히려 맞다. 다만 키움(수정주가)과는 과거 구간에서 값이 다르다 —
# 백테스트 패널(`panel_ohlc_2y.csv` = 키움 수정주가)과 직접 비교하지 말 것.
_BARS_SOURCE = {}          # code -> 'krx-compat' | 'kiwoom-fallback'
_YF_CACHE = {}


def _yahoo_bars(code, timeout=20):
    """KRX 정합 일봉. 실패하면 None 을 돌려 폴백에 맡긴다."""
    import json as _json
    import urllib.request as _u
    import datetime as _dt
    if code in _YF_CACHE:
        return _YF_CACHE[code]
    hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    for suf in ('.KS', '.KQ'):
        try:
            url = ('https://query1.finance.yahoo.com/v8/finance/chart/'
                   f'{code}{suf}?range=2y&interval=1d')
            d = _json.load(_u.urlopen(_u.Request(url, headers=hdr), timeout=timeout))
            r = d['chart']['result'][0]
            ts = r['timestamp']
            q = r['indicators']['quote'][0]
            out = []
            for i in range(len(ts)):
                c = q['close'][i]
                if c is None:
                    continue
                out.append({'dt': _dt.datetime.utcfromtimestamp(ts[i]).strftime('%Y%m%d'),
                            'o': float(q['open'][i] if q['open'][i] is not None else c),
                            'h': float(q['high'][i] if q['high'][i] is not None else c),
                            'l': float(q['low'][i] if q['low'][i] is not None else c),
                            'c': float(c),
                            'v': float(q['volume'][i] or 0)})
            if len(out) >= 70:                      # levels() 가 요구하는 최소 60봉 + 여유
                out.sort(key=lambda x: x['dt'])
                _YF_CACHE[code] = out
                return out
        except Exception:                           # noqa: BLE001 — 폴백으로 넘긴다
            continue
    _YF_CACHE[code] = None
    return None


def _kiwoom_bars(code):
    r = k.get_daily_chart(code, '00000000')
    arr = r.get('stk_dt_pole_chart_qry') or []
    out = []
    for d in arr:
        try:
            out.append({'dt': d['dt'], 'o': abs(float(d['open_pric'])),
                        'h': abs(float(d['high_pric'])), 'l': abs(float(d['low_pric'])),
                        'c': abs(float(d['cur_prc'])),
                        'v': float(d.get('trde_qty') or 0)})
        except Exception:
            continue
    out.sort(key=lambda x: x['dt'])
    return out


def bars(code, need=260):
    b = _yahoo_bars(code)
    if b:
        _BARS_SOURCE[code] = 'krx-compat'
    else:
        b = _kiwoom_bars(code)
        _BARS_SOURCE[code] = 'kiwoom-fallback'      # ATR 이 약 7~13% 과소산출된다
    return b[-need:]


def bars_source(code=None):
    """어떤 소스로 받았는지 — 보고서 각주에 쓴다. 폴백이 섞이면 ATR 을 신뢰하지 말 것."""
    if code is not None:
        return _BARS_SOURCE.get(code)
    return dict(_BARS_SOURCE)


def volume_profile(b, N=120, nbins=40):
    """매물대 — 최근 N일 거래량을 각 일의 [저가, 고가] 구간에 균등 분배해 가격대별로 집계.

    지지·저항이 생기는 미시구조적 근거는 '그 가격대에서 실제로 손바뀜한 물량'이다.
    거래량이 몰린 가격대(High Volume Node)는 되돌아왔을 때 매물 출회/본전 심리가 작동한다.
    반환: [(가격대 중앙값, 거래량비중%), ...] 비중 내림차순
    """
    seg = b[-N:] if len(b) >= N else b
    if len(seg) < 20:
        return []
    lo = min(x['l'] for x in seg)
    hi = max(x['h'] for x in seg)
    if hi <= lo:
        return []
    w = (hi - lo) / nbins
    acc = [0.0] * nbins
    for x in seg:
        if x['v'] <= 0:
            continue
        a = max(0, min(nbins - 1, int((x['l'] - lo) / w)))
        z = max(0, min(nbins - 1, int((x['h'] - lo) / w)))
        span = z - a + 1
        for i in range(a, z + 1):
            acc[i] += x['v'] / span
    tot = sum(acc) or 1.0
    out = [(lo + (i + 0.5) * w, acc[i] / tot * 100) for i in range(nbins)]
    out.sort(key=lambda t: -t[1])
    return out


def nearest_node(prof, px, side, min_share=2.0):
    """현재가 기준 아래(below)/위(above)에서 가장 가까운 고거래량 가격대."""
    cands = [(p, s) for p, s in prof if s >= min_share
             and ((p < px) if side == 'below' else (p > px))]
    if not cands:
        return None
    p, s = min(cands, key=lambda t: abs(t[0] - px))
    return {'price': p, 'share': s}


def atr(b, n=14):
    if len(b) < n + 1:
        return None
    trs = []
    for i in range(len(b) - n, len(b)):
        pc = b[i - 1]['c']
        trs.append(max(b[i]['h'] - b[i]['l'], abs(b[i]['h'] - pc), abs(b[i]['l'] - pc)))
    return sum(trs) / len(trs)


def _dedupe(items, tol=0.005):
    """0.5% 이내로 붙은 레벨은 하나로 합치고 라벨을 결합한다."""
    out = []
    for nm, v in items:
        for o in out:
            if abs(v / o[1] - 1) <= tol:
                if nm not in o[0]:
                    o[0] += '·' + nm
                break
        else:
            out.append([nm, v])
    return out


def levels(b):
    """현재가 기준 1·2차 지지선, 1·2차 저항선을 산출 (매물대 포함)."""
    if len(b) < 60:
        return None
    px = b[-1]['c']
    cand = []
    for N in (20, 60, 120, 250):
        if len(b) >= N:
            seg = b[-N:]
            cand.append((f'{N}일저점', min(x['l'] for x in seg)))
            cand.append((f'{N}일고점', max(x['h'] for x in seg)))
    for N in (20, 60):
        if len(b) >= N:
            cand.append((f'MA{N}', sum(x['c'] for x in b[-N:]) / N))

    prof = volume_profile(b)
    vn_dn = nearest_node(prof, px, 'below')
    vn_up = nearest_node(prof, px, 'above')
    if vn_dn:
        cand.append((f"매물대{vn_dn['share']:.0f}%", vn_dn['price']))
    if vn_up:
        cand.append((f"매물대{vn_up['share']:.0f}%", vn_up['price']))

    below = _dedupe(sorted([c for c in cand if c[1] < px], key=lambda x: -x[1]))
    above = _dedupe(sorted([c for c in cand if c[1] > px], key=lambda x: x[1]))
    a = atr(b)

    # 채널 위치 — 백테스트상 0.80~0.95 구간이 초과수익 최고, 0.40~0.60이 최악
    def pos(N):
        if len(b) < N:
            return None
        seg = b[-N:]
        lo, hi = min(x['l'] for x in seg), max(x['h'] for x in seg)
        return (px - lo) / (hi - lo) if hi > lo else None

    def fmt(item):
        if not item:
            return None
        nm, v = item
        return {'label': nm, 'price': v, 'pct': (v / px - 1) * 100,
                'atr': ((v - px) / a) if a else None}

    return {'close': px, 'atr': a,
            'sup1': fmt(below[0] if below else None),
            'sup2': fmt(below[1] if len(below) > 1 else None),
            'res1': fmt(above[0] if above else None),
            'res2': fmt(above[1] if len(above) > 1 else None),
            'pos120': pos(120), 'pos250': pos(250),
            'newlow': not below, 'newhigh': not above}


def analyze(code):
    b = bars(code)
    if not b:
        return None
    try:
        info = _basic(code)
        name = info.get('stk_nm') or code
    except Exception:
        name = code
    lv = levels(b)
    th = theme_of(code, name)
    rep = THEME_REP.get(th)
    rep_lv = None
    if rep:
        time.sleep(0.3)
        rb = bars(rep[0])
        rep_lv = levels(rb) if rb else None
    return {'code': code, 'name': name, 'theme': th, 'lv': lv,
            'rep': rep, 'rep_lv': rep_lv}


def line(v, indent=''):
    lv = v['lv']
    if not lv:
        return f"{indent}{v['name']}({v['code']}) — 데이터 부족"

    def s(x, alt='—'):
        if not x:
            return f'{alt:>34s}'
        return (f"{x['price']:>11,.0f} ({x['pct']:+6.1f}%, {x['atr']:+4.1f}ATR) "
                f"{x['label']}")

    p120 = f"{lv['pos120']:.2f}" if lv['pos120'] is not None else '-'
    p250 = f"{lv['pos250']:.2f}" if lv['pos250'] is not None else '-'
    zone = ''
    if lv['pos120'] is not None:
        q = lv['pos120']
        zone = ('  [저항선 직하 — 백테스트상 최강 구간]' if 0.80 <= q <= 0.95 else
                '  [중간 구간 — 백테스트상 최약]' if 0.40 <= q <= 0.60 else '')
    out = [f"{indent}{v['name']}({v['code']})  현재가 {lv['close']:,.0f}  "
           f"ATR14 {lv['atr']:,.0f}({lv['atr']/lv['close']*100:.1f}%)  "
           f"채널위치 6M {p120} / 12M {p250}{zone}"]
    out.append(f"{indent}   1차 지지 {s(lv['sup1'], '없음(신저가권)')}")
    out.append(f"{indent}   2차 지지 {s(lv['sup2'])}")
    out.append(f"{indent}   1차 저항 {s(lv['res1'], '없음(신고가권)')}   ← 반등 1차 목표")
    out.append(f"{indent}   2차 저항 {s(lv['res2'])}")
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('codes', nargs='*')
    ap.add_argument('--file')
    a = ap.parse_args()
    codes = list(a.codes)
    if a.file:
        codes += [x.strip() for x in open(a.file, encoding='utf-8') if x.strip()]
    if not codes:
        raise SystemExit('종목코드를 입력하세요')

    print('=' * 92)
    print('ETF 추천 보조표 — 대표 구성종목 · 지지선 · 저항선')
    print('※ 예측 신호가 아니라 집행 참고선 (손절·분할매수·목표가 설정용)')
    print('=' * 92)
    for c in codes:
        v = analyze(c)
        if not v:
            print(f'\n{c} — 조회 실패')
            continue
        print()
        print(line(v))
        if v['rep']:
            print(f"   └ 대표 구성종목 [{v['theme']}] {v['rep'][1]}")
            if v['rep_lv']:
                print(line({'name': v['rep'][1], 'code': v['rep'][0], 'lv': v['rep_lv']},
                           indent='      '))
        else:
            print('   └ 대표 구성종목 판정 불가(테마 미분류)')
        time.sleep(0.3)


if __name__ == '__main__':
    main()
