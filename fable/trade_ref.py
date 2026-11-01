#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""데일리 브리핑 [8-2] 월간 수출입 참고표 생성기 (2026-09-02 신설).

성격: **참고 정보 전용 — 예측 신호 아님.** 근거는 loop/수출입데이터_섹터로테이션_검정_20260902.md
(6개 축 전부 기각, 수출↔주가 상관 정점이 k=0 동시점).

동작: 월 1회만 관세청 API를 때린다. 캐시(_trade_ref_cache.json)에 최신 확정월이 들어 있으면
그대로 재사용하므로 매일 실행해도 네트워크 비용이 거의 없다. 새 달 데이터가 공개되면
자동으로 갱신한다. 네트워크 실패 시 캐시를 그대로 쓰고 stale 플래그를 세운다.

사용:
    python3 trade_ref.py            # 표 출력(사람이 확인용)
    python3 trade_ref.py --json     # 브리핑 생성 스크립트가 읽을 JSON
"""
import os, sys, json, datetime, urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '_trade_ref_cache.json')
KEYFILE = os.path.join(HERE, '..', 'loop', 'customs_apikey_encoded.txt')
BASE = "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"

# 표에 실을 품목 — 국내 증시 섹터와 대응되는 것만. 단가는 동질적 단일 HS10 코드에서만 계산
# (HS 8541에 태양전지가 섞여 있어 섹터 단위 단가는 아티팩트가 된다 — 검정 보고서 3절 참조)
ITEMS = [
    ('반도체(집적회로)', ['8542']),
    ('디램',            ['8542321010']),
    ('자동차',          ['8703']),
    ('이차전지',        ['8507']),
    ('선박',            ['8901','8902','8905','8906']),
    ('철강',            ['72']),
    ('석유제품',        ['2710']),
    ('의약품',          ['3004']),
    ('화장품',          ['3304']),
    ('기계',            ['84']),
]
ASP_ITEM = '디램'   # 단가를 표기할 품목(동질적 단일 코드)

def ym_add(ym, k):
    y, m = int(ym[:4]), int(ym[4:6]); i = y*12 + (m-1) + k
    return f"{i//12}{i%12+1:02d}"

def _key():
    return open(KEYFILE, encoding='utf-8').read().strip()

def _fetch(ym, timeout=40):
    url = f"{BASE}?serviceKey={_key()}&numOfRows=15000&pageNo=1&strtYymm={ym}&endYymm={ym}&hsSgn=&imexTp=1"
    root = ET.fromstring(urllib.request.urlopen(url, timeout=timeout).read())
    if root.findtext('.//resultCode') != '00':
        raise RuntimeError(root.findtext('.//resultMsg'))
    agg = defaultdict(lambda: [0, 0, 0])   # exp, imp, expWgt
    for it in root.findall('.//item'):
        if (it.findtext('year') or '') == '총계':      # 총계행 제외(계측 함정)
            continue
        hs = it.findtext('hsCode') or ''
        e = int(it.findtext('expDlr') or 0)
        m = int(it.findtext('impDlr') or 0)
        w = int(it.findtext('expWgt') or 0)
        for name, pref in ITEMS:
            if any(hs.startswith(p) for p in pref):
                v = agg[name]; v[0] += e; v[1] += m; v[2] += w
    if not agg or agg['반도체(집적회로)'][0] == 0:
        raise RuntimeError(f'{ym} 데이터 없음(미공개)')
    return {k: v for k, v in agg.items()}

def _load_cache():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding='utf-8'))
        except Exception:
            pass
    return None

def build(force=False):
    today = datetime.date.today()
    cache = _load_cache()
    target = ym_add(f"{today.year}{today.month:02d}", -1)      # 전월부터 시도

    if cache and not force and cache.get('data_month') == target:
        cache['stale'] = False
        return cache

    last_err = None
    for back in range(0, 4):                                    # 전월→전전월… 최대 4개월 소급
        ym = ym_add(target, -back)
        if cache and cache.get('data_month') == ym and not force:
            cache['stale'] = False
            return cache                                        # 이미 최신 확정월을 갖고 있음
        try:
            cur = _fetch(ym)
            prev = _fetch(ym_add(ym, -12))
            out = {
                'data_month': ym,
                'fetched_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                'cur': cur, 'prev': prev, 'stale': False,
            }
            json.dump(out, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
            return out
        except Exception as e:
            last_err = e
            continue
    if cache:
        cache['stale'] = True
        cache['error'] = str(last_err)
        return cache
    raise RuntimeError(f'수출입 데이터 조달 실패: {last_err}')

FOOTNOTE = ("월간 수출입 실적은 **예측 신호가 아니라 국면 설명·참고 정보**입니다. "
            "2026-09-02 검정(관세청 품목별·국가별 데이터, 6개 축 전부 기각)에서 수출 증감률로 "
            "섹터·종목을 고르는 규칙의 익월 예측력은 확인되지 않았습니다. 수출과 주가의 상관은 "
            "정점이 동시점(k=0, 반도체 +0.76)이고 발표는 그보다 한 달 늦으므로 선행 지표로 쓸 수 "
            "없습니다. 종목 선정에는 사용하지 않으며 시황 서술에만 사용합니다.")

def rows(block):
    cur, prev = block['cur'], block['prev']
    out = []
    for name, _ in ITEMS:
        if name not in cur:
            continue
        e, m, w = cur[name]
        pe = prev.get(name, [0, 0, 0])[0]
        yoy = (e/pe - 1) * 100 if pe else None
        out.append({'품목': name, '수출': e/1e9, 'YoY': yoy, '수입': m/1e9, '무역수지': (e-m)/1e9})
    return out

def asp_line(block):
    cur, prev = block['cur'], block['prev']
    if ASP_ITEM not in cur:
        return None
    e, _, w = cur[ASP_ITEM]
    pe, _, pw = prev.get(ASP_ITEM, [0, 0, 0])
    if not w or not pw or not pe:
        return None
    now, before = e/w, pe/pw
    return {'품목': ASP_ITEM, '단가': now, '전년동월': before, '증감률': (now/before - 1) * 100}

def summary(block):
    r = [x for x in rows(block) if x['YoY'] is not None]
    if not r:
        return ''
    r.sort(key=lambda x: -x['YoY'])
    ym = block['data_month']
    head = f"{ym[:4]}년 {int(ym[4:]):d}월 수출 기준 — "
    top = ', '.join(f"{x['품목']} {x['YoY']:+.1f}%" for x in r[:3])
    bot = ', '.join(f"{x['품목']} {x['YoY']:+.1f}%" for x in r[-2:])
    return head + f"증가 상위 {top} / 부진 {bot}"

def flash_block(confirmed_ym):
    """산업통상부 1일 잠정치(trade_flash.py) — 확정월보다 새로울 때만 반환. 실패해도 None(확정표는 그대로)."""
    try:
        sys.path.insert(0, HERE)
        import trade_flash as tf
        f = tf.build()
        if 'items' not in f or f.get('data_month', '') <= confirmed_ym:
            return None
        return {'data_month': f['data_month'], 'stale': f.get('stale', False),
                'fetched_at': f.get('fetched_at'), 'url': f.get('url'),
                '총수출': f['총수출'], '총수출YoY': f['총수출YoY'], '총수입': f['총수입'],
                '총수입YoY': f['총수입YoY'], '무역수지': f['무역수지'],
                'rows': tf.rows(f), 'summary': tf.summary(f)}
    except Exception:
        return None

def main():
    block = build(force=('--force' in sys.argv))
    fl = flash_block(block['data_month'])
    if '--json' in sys.argv:
        print(json.dumps({'data_month': block['data_month'], 'stale': block.get('stale', False),
                          'fetched_at': block.get('fetched_at'), 'rows': rows(block),
                          'asp': asp_line(block),
                          # 카톡 1줄·'기준월 같으면 생략' 판정은 basis_month 로 한다(18-(h)·(i))
                          'summary': fl['summary'] if fl else summary(block),
                          'basis_month': fl['data_month'] if fl else block['data_month'],
                          'flash': fl, 'footnote': FOOTNOTE}, ensure_ascii=False))
        return
    if fl:
        print(f"[속보·잠정] {fl['summary']}  (출처 산업통상부 {fl['url']})")
    ym = block['data_month']
    print(f"[8-2] 월간 수출입 참고표 — {ym[:4]}년 {int(ym[4:]):d}월 확정"
          + ("  ※캐시(갱신 실패)" if block.get('stale') else ""))
    print(f"{'품목':<16}{'수출($B)':>10}{'전년동월비':>11}{'수입($B)':>10}{'무역수지($B)':>13}")
    for x in rows(block):
        y = f"{x['YoY']:+.1f}%" if x['YoY'] is not None else "-"
        print(f"{x['품목']:<16}{x['수출']:>10.2f}{y:>11}{x['수입']:>10.2f}{x['무역수지']:>13.2f}")
    a = asp_line(block)
    if a:
        print(f"\n{a['품목']} 실현단가(수출금액÷중량): {a['단가']:,.0f}$/kg "
              f"(전년동월 {a['전년동월']:,.0f}, {a['증감률']:+.1f}%)")
    print(f"\n요약: {summary(block)}")
    print(f"\n※ {FOOTNOTE}")

if __name__ == '__main__':
    main()
