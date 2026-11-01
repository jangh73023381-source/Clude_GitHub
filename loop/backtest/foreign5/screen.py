# -*- coding: utf-8 -*-
"""외국계 5% 공시 종목의 '시세 분출' 여부 스크리닝. 조회 전용 — 검증된 신호 아님."""
import json, statistics
cands = json.load(open('_cands.json', encoding='utf-8'))
px = {r['code']: r for r in (json.loads(L) for L in open('px.jsonl', encoding='utf-8'))}
rows = []
for c in cands:
    p = px.get(c['code'], {}).get('px') or []
    if len(p) < 150: continue
    ds = [x[0] for x in p]; vs = [x[1] for x in p]
    # 공시일 기준 인덱스
    i = next((k for k, d in enumerate(ds) if d >= c['dt']), None)
    if i is None or i >= len(vs) - 5: continue
    cur = vs[-1]
    since = (cur / vs[i] - 1) * 100                       # 공시일 종가 대비
    d20 = (cur / vs[-21] - 1) * 100 if len(vs) > 21 else float('nan')
    d60 = (cur / vs[-61] - 1) * 100 if len(vs) > 61 else float('nan')
    w52 = vs[-250:] if len(vs) >= 250 else vs
    hi, lo = max(w52), min(w52)
    frhi = (cur / hi - 1) * 100                            # 52주 고점 대비
    pos = (cur - lo) / (hi - lo) * 100 if hi > lo else 50  # 52주 채널 위치
    ma60 = statistics.mean(vs[-60:]); ma120 = statistics.mean(vs[-120:])
    rows.append({**c, 'cur': cur, 'since': since, 'd20': d20, 'd60': d60,
                 'frhi': frhi, 'pos': pos, 'vsma60': (cur / ma60 - 1) * 100,
                 'vsma120': (cur / ma120 - 1) * 100, 'last': ds[-1]})
json.dump(rows, open('_screen.json', 'w'), ensure_ascii=False)

def show(title, sel):
    print(f"\n{title}  ({len(sel)}종목)")
    print(f"{'보고일':<11}{'종목':<17}{'코드':<8}{'비율':>6}{'증감':>7}{'공시후':>8}{'20일':>7}{'60일':>7}{'52주고점차':>9}{'채널':>6}  제출인")
    for x in sel:
        print(f"{x['dt']:<11}{x['name'][:15]:<17}{x['code']:<8}{x['rt']:>5.1f}%{x['irds']:>+7.1f}"
              f"{x['since']:>+8.1f}{x['d20']:>+7.1f}{x['d60']:>+7.1f}{x['frhi']:>+9.1f}{x['pos']:>5.0f}%  {x['filer'][:26]}")

new = [r for r in rows if r['irds'] >= 4.9]     # 신규 5% 진입
print(f"기준일 {max(r['last'] for r in rows)} 종가 · 대상 {len(rows)}종목 "
      f"(공시 84종 중 가격 확보분)")
quiet = [r for r in rows if r['since'] < 15 and r['d20'] < 12 and r['frhi'] < -12]
quiet.sort(key=lambda x: x['dt'], reverse=True)
show("■ A. 아직 안 움직인 종목 — 공시후 <+15% · 최근20일 <+12% · 52주고점 대비 -12% 이하", quiet)
qn = [r for r in quiet if r['irds'] >= 4.9]
show("■ B. 그중 '신규 5% 진입'(증감 +5%p 이상) — 새로 들어온 자금", qn)
hot = sorted([r for r in rows if r['since'] >= 40], key=lambda x: -x['since'])[:12]
show("■ C. 참고 — 이미 크게 분출한 종목(공시후 +40% 이상)", hot)
