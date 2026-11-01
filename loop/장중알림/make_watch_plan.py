# -*- coding: utf-8 -*-
"""장중 알림용 '오늘의 감시 계획' 생성기 (2026-10-20 사용자 요청).

아침 루틴이 브리핑을 만든 뒤 한 번 실행한다. morning_state_<T>.json 의 picks·eg_track 을
그대로 읽고(수기 재계산 금지 — 선정은 손대지 않는다), 브리핑 5절과 같은 공식으로
가격선만 계산해 plans/watch_plan_<T>.json 에 쓴다. 장중 감시기(realtime_watch.py)가 이 파일을 읽는다.

    python3 make_watch_plan.py --mode 보수   # 급락(4번)·금리(11번) 게이트 발동일
    python3 make_watch_plan.py --mode 표준   # 게이트 미발동일
    [--date YYYYMMDD]  (기본: 오늘 KST)

가격 공식(브리핑 5절 _진입전략_템플릿.py 와 동일):
  매수상단 = 전일종가×1.006 (보수 모드 ×1.003) · 지정가 ×0.99 · 갭하락 기준 ×0.98
  손절 = 전일종가 − 2.0×ATR14 (etf_levels.py, KRX 정합 소스) · 목표 ×1.03
조회 전용. 주문 기능 없음.
"""
import argparse, datetime, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
SCRIPTS = os.path.join(LOOP, 'references', 'scripts')
FABLE = os.path.join(os.path.dirname(LOOP), 'fable')


def kst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime('%Y%m%d')


def load_state(T):
    p = os.path.join(SCRIPTS, f'morning_state_{T}.json')
    if not os.path.exists(p):
        sys.exit(f'[중단] {p} 없음 — 아침 루틴(morning_run.py)을 먼저 실행하십시오.')
    return json.load(open(p, encoding='utf-8'))


def prev_state(T):
    fs = sorted(f for f in glob.glob(os.path.join(SCRIPTS, 'morning_state_*.json'))
                if re.search(r'_(\d{8})\.json$', f) and re.search(r'_(\d{8})\.json$', f).group(1) < T)
    return json.load(open(fs[-1], encoding='utf-8')) if fs else None


def atr14(code):
    sys.path.insert(0, FABLE)
    try:
        import etf_levels as el
        b = el.bars(code)
        return round(el.atr(b)) if b else None
    except Exception:
        return None


def parse_eg(out):
    """eg_picks.py 출력(state eg_track.out)에서 오늘 집행할 매수·매도만 뽑는다."""
    res = {'regime_half': '약세' in out.split('\n')[1] if '\n' in out else False,
           'n_buy': 0, 'buys': [], 'sells': []}
    m = re.search(r'상위 (\d+)건만 매수', out)
    free = re.search(r'여유 (\d+)', out)
    n_rep = 0
    # 매수 표 행: "    1 섹터  종목명  코드  매수가 ..."
    sec = out.split('■ 매수')[1].split('■')[0] if '■ 매수' in out else ''
    rows = re.findall(r'^\s+(\d+)\s+(\S+)\s+(.+?)\s+([0-9A-Z]{6})\s+([\d,]+)원', sec, re.M)
    caps = {c: (int(a.replace(',', '')), int(b.replace(',', '')))
            for c, a, b in re.findall(r'([0-9A-Z]{6})?\s*포기 상단가\s+([\d,]+)원 / MA20\s+([\d,]+)원', sec)}
    # 포기 상단가 줄에는 코드가 없고 종목명만 있다 → 이름으로 매칭
    caps_by_name = {n.strip(): (int(a.replace(',', '')), int(b.replace(',', '')))
                    for n, a, b in re.findall(r'^\s+(\S.*?)\s+포기 상단가\s+([\d,]+)원 / MA20\s+([\d,]+)원', sec, re.M)}
    if m:
        res['n_buy'] = int(m.group(1))
    elif free:
        res['n_buy'] = min(int(free.group(1)), len(rows))
    else:
        res['n_buy'] = len(rows)
    for rank, sector, name, code, px in rows:
        cap = caps_by_name.get(name.strip())
        res['buys'].append({'rank': int(rank), 'sector': sector, 'name': name.strip(), 'code': code,
                            'signal_close': int(px.replace(',', '')),
                            'give_up_above': cap[0] if cap else None, 'ma20': cap[1] if cap else None})
    ssec = out.split('■ 매도')[1].split('■')[0] if '■ 매도' in out else ''
    for name, code in re.findall(r'^\s+(\S.*?)\s+([0-9A-Z]{6})\s', ssec, re.M):
        res['sells'].append({'name': name.strip(), 'code': code})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', required=True, choices=['보수', '표준'])
    ap.add_argument('--date', default=kst_today())
    a = ap.parse_args()
    T = a.date
    st = load_state(T)
    pv = prev_state(T)
    k_up = 1.003 if a.mode == '보수' else 1.006

    short = []
    by = {r['code']: r for r in st['picks']['short_etf10']}
    prev5 = set((pv or {}).get('picks', {}).get('picks5', '').split(',')) - {''}
    for code in st['picks']['picks5'].split(','):
        r = by[code]
        c = r['close']
        atr = atr14(code)
        short.append({'code': code, 'name': r['name'], 'prev_close': c, 'atr': atr,
                      'status': '유지' if code in prev5 else '신규',
                      'upper': round(c * k_up), 'limit': round(c * 0.99), 'gapdown': round(c * 0.98),
                      'stop': round(c - 2.0 * atr) if atr else round(c * 0.975),
                      'stop_basis': '2.0ATR' if atr else '고정-2.5%(ATR 조회 실패)',
                      'target': round(c * 1.03)})
    pnames = {}
    if pv:
        for r in pv['picks'].get('short_etf10', []):
            pnames[r['code']] = r['name']
    short_sells = [{'code': c, 'name': pnames.get(c, c)} for c in sorted(prev5 - set(st['picks']['picks5'].split(',')))]

    mid = st['picks'].get('mid_candidates', [])
    pmid = (pv or {}).get('picks', {}).get('mid_candidates', [])
    mid_sells = [m for m in pmid if m['code'] not in {x['code'] for x in mid}]

    plan = {'date': T, 'mode': a.mode, 'made_at_kst': (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).isoformat(timespec='seconds'),
            'short': short, 'short_sells': short_sells,
            'mid': mid, 'mid_sells': mid_sells,
            'mid_band': [-0.5, 1.5], 'mid_band2': [-1.0, 1.5],
            'trackD': parse_eg(st.get('eg_track', {}).get('out', '')),
            'note': '선정은 morning_state 그대로. 가격선은 브리핑 5절 공식. 알림은 참고이며 주문하지 않는다.'}
    out = os.path.join(HERE, 'plans', f'watch_plan_{T}.json')
    json.dump(plan, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'[감시 계획] {out}')
    print(f'  모드 {a.mode} · 단기 {len(short)}종 · 단기 청산 {len(short_sells)} · 중기 {len(mid)} · 중기 청산 {len(mid_sells)} '
          f'· 트랙D 매수 {plan["trackD"]["n_buy"]}/{len(plan["trackD"]["buys"])} · 매도 {len(plan["trackD"]["sells"])}')


if __name__ == '__main__':
    main()
