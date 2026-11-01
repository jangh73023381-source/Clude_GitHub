#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sector_flow_ref.py — 브리핑 [1-4] 테마별 자금 흐름(거래대금 ÷ 직전 40거래일 평균) 데이터
(2026-10-06 신설, fable/CLAUDE.md 27번).

성격: **참고 정보 전용 — 선정 로직 반영 금지.** 어제 돈이 어느 테마로 몰리고 빠졌는지만 보여준다.

분류: **KRX 업종이 아니라 종목→테마 매핑(`theme_map.csv`)** 으로 묶는다(사용자 지시 2026-10-06 —
      "반도체·2차전지가 뭉치면 안 된다"). KRX 업종은 전기·전자 하나가 시장 거래대금의 56%이고
      반도체 장비주는 기계·장비, 2차전지 소재는 화학에 흩어져 있어 쓸 수 없었다.
      한 종목은 한 테마에만 속한다 → 테마 합계 = 시장 전체(매핑 안 된 종목은 '기타(미분류)').
      매핑은 직전 40거래일 거래대금 상위 ~320종(시장의 약 91%)을 손으로 분류한 것이다.
      **매핑을 고칠 곳은 `theme_map.csv` 하나뿐이다.** 매 실행이 '미분류 상위'를 출력하므로 분기 1회 보강한다.

데이터:
  - 과거: loop/backtest/krx_stock_panel.csv (KRX 전종목 일별, `krx_api.py stock` 으로 멱등 연장 — 이 스크립트가 자동 호출)
  - D(어제): KRX 는 D 를 D+1 장중에 공개하므로 아침에는 없다 → **키움 ka10032(거래대금 상위, 전 종목 페이징)** 스냅샷으로 채운다.
    스냅샷은 `_flow_snap/kw_<D>.csv` 에 보관하고, 나중에 KRX 에 D 가 들어오면 KRX 값을 쓴다.
  - 거래량(주식 수)이 아니라 **거래대금(원)** 이다.

지표: 비율 = 그날 거래대금 ÷ 그날 직전 40거래일 평균(그날 제외). 등락 = 테마 내 거래대금 가중 평균 등락률.

사용:  python3 sector_flow_ref.py [--json] [--date YYYYMMDD]
출력 JSON 은 `_섹터자금흐름_템플릿.py` 의 add_sector_flow() 에 그대로 넘긴다(수기 재계산 금지).
캐시 `_sector_flow_cache.json` — 실패 시 캐시를 쓰고 stale=true.
"""
import sys, os, io, json, time, csv, datetime, contextlib, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.normpath(os.path.join(HERE, '..', 'loop'))
PANEL = os.path.join(LOOP, 'backtest', 'krx_stock_panel.csv')
MAP = os.path.join(HERE, 'theme_map.csv')
SNAP = os.path.join(HERE, '_flow_snap')
CACHE = os.path.join(HERE, '_sector_flow_cache.json')
WIN = 40            # 평균 창(거래일)
SHOW = 40           # 히트맵·미니차트 표시 일수
OTHER = '기타(미분류)'

sys.path.insert(0, LOOP)


def _settled_last():
    """기록 가능한 마지막 날짜(16:00 KST 전이면 어제까지) — loop ensure_data.settled() 와 같은 기준."""
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    return now.strftime('%Y%m%d') if now.hour >= 16 else (now - datetime.timedelta(days=1)).strftime('%Y%m%d')


def _last_trading_day(upto):
    """키움 코스피 업종일봉(ka20006 001)에서 upto 이하 마지막 거래일."""
    import kiwoom_api as k
    rows = k._call('/api/dostk/chart', 'ka20006', {'inds_cd': '001', 'base_dt': upto}).get('inds_dt_pole_qry', [])
    return max(r['dt'] for r in rows if r['dt'] <= upto)


def _extend_panel(D):
    """KRX 패널을 D 까지 멱등 연장(공개 안 된 날짜는 0행으로 지나간다)."""
    import krx_api
    last = ''
    with open(PANEL, 'rb') as f:
        f.seek(-4000, 2)
        for line in f.read().decode('utf-8', 'ignore').splitlines()[1:]:
            last = max(last, line.split(',')[0])
    if last >= D:
        return last
    a = (datetime.datetime.strptime(last, '%Y%m%d') + datetime.timedelta(days=1)).strftime('%Y%m%d')
    with contextlib.redirect_stdout(io.StringIO()):
        krx_api.cmd_stock(a, D)
    return last


def _kw_snapshot(D):
    """키움 ka10032 전 종목 거래대금(D 당일분). 파일로 보관해 재실행 시 재사용."""
    os.makedirs(SNAP, exist_ok=True)
    fp = os.path.join(SNAP, f'kw_{D}.csv')
    if os.path.exists(fp):
        R = list(csv.DictReader(open(fp, encoding='utf-8')))
        if R and 'name' in R[0] and sum(float(r['value']) for r in R) > 0:   # 2026-10-08: 장전 0원 스냅샷 재사용 금지
            return {r['code']: (float(r['value']), float(r['chg']), r['name']) for r in R}
    import kiwoom_api as k
    out, ck, nk = [], 'N', ''
    for _ in range(60):
        req = urllib.request.Request(k.BASE_URL + '/api/dostk/rkinfo', method='POST',
                                     data=json.dumps({'mrkt_tp': '000', 'mang_stk_incls': '0', 'stex_tp': '1'}).encode())
        for a, b in {'content-type': 'application/json;charset=UTF-8', 'authorization': 'Bearer ' + k.get_access_token(),
                     'api-id': 'ka10032', 'cont-yn': ck, 'next-key': nk}.items():
            req.add_header(a, b)
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode()); h = r.headers
        L = j.get('trde_prica_upper', [])
        out += L
        if h.get('cont-yn') != 'Y' or (L and int(L[-1]['trde_prica']) == 0):
            break
        ck, nk = 'Y', h.get('next-key', ''); time.sleep(0.2)
    snap = {x['stk_cd']: (int(x['trde_prica']) * 1e6, float(x['flu_rt']), x['stk_nm']) for x in out}
    if not snap or sum(v for v, _, _ in snap.values()) <= 0:
        # 2026-10-08 실측: 장전(06시) ka10032 는 D 가 아니라 '오늘(장 시작 전)' 기준이라 거래대금이 전부 0 으로 온다.
        # 0 스냅샷을 D 로 쓰면 [1-4] 가 '전 섹터 0%' 로 나온다 → 저장하지 않고 실패시킨다(호출 측이 --date 로 KRX 확정일 사용).
        raise RuntimeError(f'키움 ka10032 거래대금 합계 0 — {D} 당일분 아님(장전 리셋 추정)')
    with open(fp, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['code', 'value', 'chg', 'name'])
        for c, (v, p, n) in snap.items():
            w.writerow([c, v, p, n])
    return snap


def build(D):
    import pandas as pd
    _extend_panel(D)
    p = pd.read_csv(PANEL, dtype={'code': str, 'date': str}, usecols=['date', 'code', 'value', 'chg_pct'])
    p = p[p.date <= D]
    dates = sorted(p.date.unique())
    src = 'krx'
    names = {}
    if dates[-1] < D:   # D 가 KRX 에 아직 없다 → 키움 스냅샷
        snap = _kw_snapshot(D)
        univ = set(p[p.date == dates[-1]].code)
        names = {c: x[2] for c, x in snap.items()}
        add = pd.DataFrame([(D, c, x[0], x[1]) for c, x in snap.items() if c in univ],
                           columns=['date', 'code', 'value', 'chg_pct'])
        p = pd.concat([p, add]); dates.append(D); src = 'kiwoom'
    dates = dates[-(WIN + SHOW):]
    p = p[p.date.isin(dates)].copy()
    p['value'] = pd.to_numeric(p.value, errors='coerce').fillna(0)
    p['chg_pct'] = pd.to_numeric(p.chg_pct, errors='coerce')
    tm = {r['code']: r['theme'] for r in csv.DictReader(open(MAP, encoding='utf-8-sig'))}
    nm = dict(names); nm.update({r['code']: r['name'] for r in csv.DictReader(open(MAP, encoding='utf-8-sig')) if r['name']})
    p['theme'] = p.code.map(tm).fillna(OTHER)
    v = p.pivot_table(index='date', columns='theme', values='value', aggfunc='sum').reindex(dates).fillna(0)
    tot = v.sum(1)
    S = len(dates) - SHOW
    pd_ = p[p.date == D]
    out = []
    for t in v.columns:
        s = v[t].tolist()
        ratio = [s[i] / (sum(s[i - WIN:i]) / WIN) if sum(s[i - WIN:i]) else None for i in range(S, len(dates))]
        avg = [sum(s[i - WIN:i]) / WIN for i in range(S, len(dates))]
        g = pd_[pd_.theme == t]
        pct = float((g.chg_pct * g.value).sum() / g.value.sum()) if g.value.sum() else None
        lead = g.sort_values('value', ascending=False).head(3)
        out.append({'name': t, 'group': '',
                    'value_jo': [round(x / 1e12, 3) for x in s[S:]],
                    'avg40_jo': [round(x / 1e12, 3) for x in avg],
                    'ratio': [round(x, 3) if x else None for x in ratio],
                    'pct': round(pct, 2) if pct is not None else None,
                    'share': round(s[-1] / tot.iloc[-1] * 100, 2),
                    'share40': round(float((v[t] / tot).iloc[-WIN - 1:-1].mean() * 100), 2),
                    'leaders': [{'name': nm.get(c, c), 'value_eok': round(x / 1e8), 'chg': (round(ch, 2) if ch == ch else None)}
                                for c, x, ch in zip(lead.code, lead.value, lead.chg_pct)]})
    out.sort(key=lambda r: -(r['ratio'][-1] or 0))
    t_ = tot.tolist()
    unm = pd_[pd_.theme == OTHER].sort_values('value', ascending=False).head(8)
    tv = tot.iloc[-1]
    return {'date': D, 'source_D': src, 'dates': dates[S:],
            'market': {'value_jo': round(tv / 1e12, 2), 'avg40_jo': round(sum(t_[-WIN - 1:-1]) / WIN / 1e12, 2),
                       'ratio': round(tv / (sum(t_[-WIN - 1:-1]) / WIN), 3),
                       'ratio_series': [round(t_[i] / (sum(t_[i - WIN:i]) / WIN), 3) for i in range(S, len(dates))]},
            'sectors': out,
            'unmapped_top': [{'code': c, 'name': nm.get(c, ''), 'share': round(float(x / tv * 100), 2)} for c, x in zip(unm.code, unm.value)],
            'stale': False, 'warn': []}


def main():
    a = sys.argv[1:]
    try:
        D = a[a.index('--date') + 1] if '--date' in a else _last_trading_day(_settled_last())
        blk = build(D)
        json.dump(blk, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception as e:
        if not os.path.exists(CACHE):
            blk = {'error': str(e), 'stale': True, 'sectors': []}
        else:
            blk = json.load(open(CACHE, encoding='utf-8')); blk['stale'] = True
            blk['warn'] = [f'조회 실패 — 캐시 사용: {e}']
    big = [u for u in blk.get('unmapped_top', []) if u['share'] >= 1.0]
    if big:
        blk.setdefault('warn', []).append('미분류 종목이 시장 거래대금의 1% 이상(' + ', '.join(u['name'] or u['code'] for u in big)
                                          + ') — theme_map.csv 보강 필요')
    if '--json' in a:
        print(json.dumps(blk, ensure_ascii=False)); return
    m = blk.get('market', {})
    print(f"{blk.get('date')} (D 출처 {blk.get('source_D')}) 시장 {m.get('value_jo')}조 · 40일 평균의 {m.get('ratio', 0) * 100:.0f}%"
          + (' ※캐시' if blk.get('stale') else ''))
    for r in blk['sectors']:
        ld = ', '.join(x['name'] for x in r['leaders'])
        print(f"  {r['name']:<12} {r['value_jo'][-1]:>6.2f}조 평균의 {r['ratio'][-1] * 100:>4.0f}% 점유 {r['share']:>5.1f}%"
              f"(40일 {r['share40']:>4.1f}) 등락 {r['pct']}  [{ld}]")
    print('  미분류 상위:', blk.get('unmapped_top'))
    for w in blk.get('warn', []):
        print('  경고:', w)


if __name__ == '__main__':
    main()
