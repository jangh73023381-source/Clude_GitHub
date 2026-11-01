# -*- coding: utf-8 -*-
"""
송재호식 참고표 [8-4] 데이터 조달 모듈  (조회 전용)
--------------------------------------------------
검정: loop/송재호식_종목선정_백테스트_2026-09-12.docx
판정: 6축 중 '실적 확인 × 주도주 집중' 2축만 생존(상호작용 +1.46%p/20일).
      승격 불가(다중검정 탈락·꼬리 의존·KODEX200 상시보유에 156%p 열위) → 참고 전용 shadow.

규칙 (Rule SJH v1.0 — 백테스트 원문 그대로, 최적화 금지):
  게이트  : KODEX200 종가 > 20일 이동평균 (OFF면 현금, 신규 편입 없음)
  필터    : PIT 유동종목(거래대금 5억↑·주가 1,000원↑·시총 300억↑)
            ∩ 매출액 YoY > 0 ∩ 영업이익 YoY > 0 ∩ 당기·전년 모두 흑자
  랭킹    : 20일 평균 거래대금 상위 10종
  집행    : 20거래일 비중복 리밸런싱(바스켓 통째 교체). 손절 없음.

사용: python3 sjh_ref.py --json
"""
import os, sys, json, re, time, datetime as dt
import pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor

FABLE = os.path.dirname(os.path.abspath(__file__))
LOOP  = os.path.join(os.path.dirname(FABLE), 'loop')
BT    = os.path.join(LOOP, 'backtest')
CACHE = os.path.join(FABLE, '_sjh_ref_cache.json')
STATE = os.path.join(FABLE, '_sjh_ref_state.json')

BENCH = '069500'          # KODEX200
TOPN  = 10
CYCLE = 20                # 리밸런싱 주기(거래일)
H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.naver.com/'}
URL = ('https://api.finance.naver.com/siseJson.naver?symbol={}&requestType=1'
       '&startTime={}&endTime={}&timeframe=day')

FOOTNOTE = (
    "이 표는 **예측 신호가 아니라 외부 기법의 실측 재현표**입니다. 2026-09-12 검정"
    "(개별종목 3,101종·7.7년 486만행)에서 송재호식 6가지 키워드 중 **4가지는 기각**됐습니다 — "
    "'선취매'는 부호가 반대이고(정반대인 신고가 근접으로 바꾸면 +0.32→+2.77%p), "
    "'바닥권·눌림목'은 t=−2.93으로 유의하게 해로웠으며, '섹터 선점'도 단독 −0.47%p였습니다. "
    "**남은 것은 '실적 확인'과 그 위에서만 작동하는 '주도주 집중' 두 축뿐**이며, 이 표는 그 둘만 재현한 것입니다"
    "(원안대로 6축을 전부 AND로 걸면 하루 평균 1종목만 남아 집행 자체가 불가능합니다). "
    "**승격 규칙이 아닙니다** — 다중검정(Bonferroni |t|≥3.16 대비 최고 t=2.43) 탈락, 상위 25%가 초과의 "
    "135.9%를 만드는 꼬리 의존, 그리고 같은 기간 실전 복리가 **KODEX200 상시보유 +367%에 +211%로 뒤집니다**"
    "(MDD도 −38.6% vs −37.4%로 더 나쁨). 2021~22 하락장에서는 −3.8%p·−1.25%p로 무너졌습니다. "
    "종목 선정·우선순위·청산에 사용하지 않으며 시황 참고로만 사용합니다."
)

def _trading_days_between(a, b, dates):
    """dates(정렬된 int YYYYMMDD 배열)에서 a 초과 b 이하의 거래일 수"""
    return int(((dates > a) & (dates <= b)).sum())

def _fetch(code, start, end):
    for att in range(2):
        try:
            import requests
            t = requests.get(URL.format(code, start, end), headers=H, timeout=10).text
            out = []
            for rr in re.findall(r"\[([^\[\]]*)\]", t)[1:]:
                p = [x.strip().strip("'\"") for x in rr.split(',')]
                if len(p) < 6 or not p[0].isdigit():
                    continue
                try:
                    out.append((code, int(p[0]), float(p[4]), float(p[5])))  # code,date,close,volume
                except Exception:
                    pass
            return out
        except Exception:
            time.sleep(0.4)
    return []

def build(force=False):
    today = int(dt.datetime.now().strftime('%Y%m%d'))
    warn = []

    # ---------- 1) PIT 유니버스 (분기 갱신) ----------
    pit = pd.read_csv(os.path.join(BT, '_krx_pit.csv'), dtype={'code': str})
    snap = int(pit.date.max())
    g = pit[pit.date == snap]
    g = g[(g.value >= 5e8) & (g.close >= 1000) & (g.mktcap >= 3e10)]
    names = dict(zip(g.code, g.name))
    uni = set(g.code)
    if (dt.datetime.strptime(str(today), '%Y%m%d') -
        dt.datetime.strptime(str(snap), '%Y%m%d')).days > 130:
        warn.append('PIT 유니버스 스냅샷이 %d로 오래됨(분기 갱신 필요)' % snap)

    # ---------- 2) 실적 필터 (분기 갱신) ----------
    fu = pd.read_csv(os.path.join(BT, 'sjh', 'fund.csv'), dtype={'code': str})
    fu = fu[fu.avail <= today].sort_values('avail')
    last = fu.groupby('code').tail(1)
    fund_asof = int(last.avail.max())
    if (dt.datetime.strptime(str(today), '%Y%m%d') -
        dt.datetime.strptime(str(fund_asof), '%Y%m%d')).days > 100:
        warn.append('DART 재무 가용일이 %d로 오래됨(분기 갱신 필요)' % fund_asof)
    last = last[(last.sa_g > 0) & (last.op_g > 0) & (last.op_pos.astype(str).str.lower() == 'true')]
    pool = sorted(uni & set(last.code))
    fmap = {r.code: (float(r.sa_g), float(r.op_g)) for r in last.itertuples()}

    # ---------- 3) 일봉 (매일) ----------
    start = int((dt.datetime.now() - dt.timedelta(days=90)).strftime('%Y%m%d'))
    rows = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for o in ex.map(lambda c: _fetch(c, start, today), pool + [BENCH]):
            rows.extend(o)
    if not rows:
        raise RuntimeError('일봉 조회 실패')
    df = pd.DataFrame(rows, columns=['code', 'date', 'close', 'volume'])
    df = df[df.close > 0].drop_duplicates(['code', 'date'])

    b = df[df.code == BENCH].sort_values('date')
    if len(b) < 21:
        raise RuntimeError('벤치마크 일봉 부족')
    asof = int(b.date.iloc[-1])
    bclose = float(b.close.iloc[-1])
    bma20 = float(b.close.iloc[-20:].mean())
    gate = bclose > bma20
    dates = np.array(sorted(df[df.code != BENCH].date.unique()))

    s = df[df.code != BENCH].copy()
    s = s[s.date <= asof]
    s['to'] = s.close * s.volume
    last20 = s.sort_values('date').groupby('code').tail(20)
    agg = last20.groupby('code').agg(to20=('to', 'mean'), n=('to', 'size'),
                                     close=('close', 'last')).reset_index()
    agg = agg[agg.n >= 15]
    agg = agg.sort_values('to20', ascending=False)
    ranked = agg.code.tolist()

    def row(code, gubun, entry=None, left=None):
        r = agg[agg.code == code]
        sa, op = fmap.get(code, (float('nan'), float('nan')))
        return dict(
            gubun=gubun, code=code, name=names.get(code, code),
            close=int(r.close.iloc[0]) if len(r) else None,
            to20=float(r.to20.iloc[0]) if len(r) else None,
            rank=(ranked.index(code) + 1) if code in ranked else None,
            sa_g=None if pd.isna(sa) else round(sa * 100, 1),
            op_g=None if pd.isna(op) else round(op * 100, 1),
            entry=entry, left=left)

    # ---------- 4) 상태(보유 바스켓) · 20거래일 비중복 리밸런싱 ----------
    st = {}
    if os.path.exists(STATE):
        try:
            st = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            st = {}
    held = st.get('holdings', [])            # [{code, entry}]
    last_rb = int(st.get('last_rebalance', 0))
    elapsed = _trading_days_between(last_rb, asof, dates) if last_rb else CYCLE
    is_rb = (not held) or (elapsed >= CYCLE)

    top = ranked[:TOPN]
    items = []
    if is_rb and gate:
        prev = {h['code'] for h in held}
        for c in top:
            items.append(row(c, '유지' if c in prev else '신규', entry=asof, left=CYCLE))
        for c in sorted(prev - set(top)):
            e = next((h['entry'] for h in held if h['code'] == c), None)
            items.append(row(c, '청산', entry=e, left=0))
        held = [{'code': c, 'entry': asof,
                 'px': float(agg[agg.code == c].close.iloc[0])} for c in top]
        st['bench_entry'] = bclose
        last_rb, elapsed = asof, 0
    elif is_rb and not gate:
        for h in held:
            items.append(row(h['code'], '청산(게이트 OFF)', entry=h['entry'], left=0))
        held, last_rb, elapsed = [], asof, 0
    else:
        for h in held:
            items.append(row(h['code'], '유지', entry=h['entry'],
                             left=max(0, CYCLE - elapsed)))
        items.sort(key=lambda x: (x['rank'] is None, x['rank'] or 999))
    cand = [row(c, '후보', left=None) for c in top if c not in {i['code'] for i in items}]

    bench_entry = float(st.get('bench_entry') or bclose)
    json.dump({'holdings': held, 'last_rebalance': last_rb, 'asof': asof,
               'bench_entry': bench_entry},
              open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 사이클 경과 수익(진입 종가 대비) — OOS 기록용
    cur = {c: float(agg[agg.code == c].close.iloc[0])
           for c in [h['code'] for h in held] if c in set(agg.code)}
    rets = [cur[h['code']] / h['px'] - 1 for h in held if h.get('px') and h['code'] in cur]
    bret = bclose / bench_entry - 1 if bench_entry else None
    pnl = float(np.mean(rets)) if rets else None

    nxt = max(0, CYCLE - elapsed)
    blk = dict(
        asof=asof, stale=False, gate=bool(gate),
        bench_close=bclose, bench_ma20=round(bma20, 1),
        pool=len(pool), ranked=len(ranked), pit_asof=snap, fund_asof=fund_asof,
        is_rebalance=bool(is_rb), days_to_rebalance=nxt, elapsed=elapsed,
        cycle_ret=None if pnl is None else round(pnl * 100, 3),
        cycle_bench=None if bret is None else round(bret * 100, 3),
        cycle_excess=None if (pnl is None or bret is None) else round((pnl - bret) * 100, 3),
        items=items, candidates=cand, warn=warn, footnote=FOOTNOTE)
    blk['summary'] = _summary(blk)
    blk['kakao'] = _kakao(blk)
    json.dump(blk, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return blk

def _summary(b):
    g = '게이트 ON' if b['gate'] else '게이트 OFF(현금)'
    hold = [i for i in b['items'] if i['gubun'].startswith('유지') or i['gubun'] == '신규']
    nm = ' · '.join(i['name'] for i in hold[:5])
    return ('송재호식 참고(shadow) — %s · 실적필터 풀 %d종 · 보유 %d종%s · 다음 리밸런싱 %d거래일 후'
            % (g, b['pool'], len(hold), (' (' + nm + ' 등)') if nm else '', b['days_to_rebalance']))

def _kakao(b):
    g = 'ON' if b['gate'] else 'OFF(현금)'
    new = [i['name'] for i in b['items'] if i['gubun'] == '신규']
    out = [i['name'] for i in b['items'] if i['gubun'].startswith('청산')]
    s = '송재호식 참고 — 게이트 %s, 풀 %d종' % (g, b['pool'])
    if new: s += ' / 신규 ' + ', '.join(new[:4]) + ('…' if len(new) > 4 else '')
    if out: s += ' / 청산 ' + ', '.join(out[:4]) + ('…' if len(out) > 4 else '')
    if not new and not out: s += ' / 변동 없음(다음 리밸런싱 %d거래일 후)' % b['days_to_rebalance']
    return s + ' ※참고 전용, 실매수 아님'

TRACKER = os.path.join(LOOP, 'references', 'sjh_tracker.csv')


def record(blk):
    """OOS 기록 — 하루 1행 누적(백필 금지). judge_ready.py 로 판정한다."""
    if blk.get('stale') or blk.get('asof') is None:
        return None
    hdr = 'date,gate,pool,n_hold,elapsed,cycle_ret,cycle_bench,cycle_excess,is_rebalance\n'
    line = '%d,%d,%d,%d,%d,%s,%s,%s,%d\n' % (
        blk['asof'], int(bool(blk['gate'])), blk['pool'],
        len([i for i in blk['items'] if not i['gubun'].startswith('청산')
             and i['gubun'] != '후보']),
        blk.get('elapsed', 0),
        '' if blk.get('cycle_ret') is None else blk['cycle_ret'],
        '' if blk.get('cycle_bench') is None else blk['cycle_bench'],
        '' if blk.get('cycle_excess') is None else blk['cycle_excess'],
        int(bool(blk['is_rebalance'])))
    os.makedirs(os.path.dirname(TRACKER), exist_ok=True)
    seen = set()
    if os.path.exists(TRACKER):
        with open(TRACKER, encoding='utf-8') as f:
            seen = {l.split(',')[0] for l in f.read().splitlines()[1:] if l.strip()}
    else:
        with open(TRACKER, 'w', encoding='utf-8') as f:
            f.write(hdr)
    if str(blk['asof']) in seen:      # 같은 날 재실행 → 덮어쓰기
        with open(TRACKER, encoding='utf-8') as f:
            ls = f.read().splitlines(True)
        ls = [l for l in ls if not l.startswith(str(blk['asof']) + ',')]
        with open(TRACKER, 'w', encoding='utf-8') as f:
            f.writelines(ls)
    with open(TRACKER, 'a', encoding='utf-8') as f:
        f.write(line)
    return TRACKER


def main():
    try:
        blk = build()
    except Exception as e:
        if os.path.exists(CACHE):
            blk = json.load(open(CACHE, encoding='utf-8'))
            blk['stale'] = True
            blk.setdefault('warn', []).append('갱신 실패(%s) — 캐시 사용' % e)
        else:
            blk = {'stale': True, 'items': [], 'warn': ['산출 실패(%s) · 캐시 없음' % e],
                   'footnote': FOOTNOTE, 'summary': '송재호식 참고표 산출 실패',
                   'kakao': '', 'gate': None, 'pool': 0}
    if '--record' in sys.argv:
        try:
            record(blk)
        except Exception as e:
            blk.setdefault('warn', []).append('OOS 기록 실패(%s)' % e)
    if '--json' in sys.argv:
        print(json.dumps(blk, ensure_ascii=False))
    else:
        print(blk.get('summary'))
        for i in blk.get('items', []):
            print(' %-14s %-12s %s  %s억  매출%s%% 영업이익%s%%  잔여%s' % (
                i['gubun'], i['name'], i['code'],
                '' if i['to20'] is None else round(i['to20'] / 1e8),
                i['sa_g'], i['op_g'], i['left']))
        if blk.get('warn'): print('WARN:', blk['warn'])

if __name__ == '__main__':
    main()
