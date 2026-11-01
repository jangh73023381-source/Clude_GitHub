# -*- coding: utf-8 -*-
"""외국계 5% 공시 스크리닝 — 최종 정리. 조회 전용, 검증된 신호 아님."""
import json, csv
rows = json.load(open('_screen.json', encoding='utf-8'))
# 액티브 밸류·롱온리 하우스 (방향성 의미 큼) vs 패시브·IB 데스크(물량 성격 섞임)
ACTIVE = ('Miri', 'DALTON', 'Kopernik', 'Silchester', 'Orbis', 'FederatedHermes',
          'Swedbank', 'Wellington', '티로우', '인베스코', '슈로더', 'AllianceBernstein',
          'CapitalResearch', 'CapitalGroup', 'FILLIMITED', '피델리티', 'NorgesBank',
          'GICPrivate', 'GOVERNMENTOFSINGAPORE')
PASSIVE_IB = ('BlackRock', 'MORGANSTANLEY', 'J.P.MORGAN', 'JPMorgan', 'UBSAG', 'GOLDMANSACHS')
def kind(f):
    if any(k.lower() in f.lower() for k in ACTIVE): return '액티브'
    if any(k.lower() in f.lower() for k in PASSIVE_IB): return '패시브/IB'
    return '기타'
for r in rows: r['kind'] = kind(r['filer'])

def tbl(title, sel, note=''):
    print(f"\n{title} ({len(sel)}종목)")
    if note: print(f"  {note}")
    print(f"  {'보고일':<11}{'종목':<16}{'코드':<8}{'구분':<9}{'비율':>6}{'증감':>6}{'공시후':>8}{'20일':>7}{'52주고점차':>9}{'채널':>6}  제출인")
    for x in sel:
        print(f"  {x['dt']:<11}{x['name'][:14]:<16}{x['code']:<8}{x['kind']:<9}{x['rt']:>5.1f}%{x['irds']:>+6.1f}"
              f"{x['since']:>+8.1f}{x['d20']:>+7.1f}{x['frhi']:>+9.1f}{x['pos']:>5.0f}%  {x['filer'][:24]}")

recent = [r for r in rows if r['dt'] >= '2026-06-09']
# 1군: 최근 3개월 · 신규 5% 진입 · 공시 후 ±12% 이내 · 최근 20일 급등 아님
t1 = [r for r in recent if r['irds'] >= 4.9 and -12 <= r['since'] <= 12 and r['d20'] < 12]
# 2군: 최근 3개월 · 지분 확대(+1%p↑) · 공시 후 ±12% · 급등 아님
t2 = [r for r in recent if 1.0 <= r['irds'] < 4.9 and -12 <= r['since'] <= 12 and r['d20'] < 12]
# 3군: 공시 후 -25% 이상 하락 (싸졌거나 논리가 깨졌거나 — 별도 확인 필요)
t3 = sorted([r for r in rows if r['since'] <= -25], key=lambda x: x['since'])
for L in (t1, t2): L.sort(key=lambda x: x['dt'], reverse=True)

print(f"■ 외국계 기관·펀드 5% 이상 대량보유 공시 — 아직 안 움직인 종목")
print(f"  DART 12개월 전수 12,937건 → 외국계 413건 → 5%↑ 최신보고 84종목 → 가격 확보 {len(rows)}종목")
print(f"  기준일 {max(r['last'] for r in rows)} 종가")
tbl("■ 1군 — 최근 3개월 '신규 5% 진입' + 공시 후 거의 안 움직임(±12%) + 급등 아님", t1,
    "새로 들어온 자금인데 주가는 아직 반응하지 않은 경우")
tbl("■ 2군 — 최근 3개월 '지분 확대(+1%p 이상)' + 공시 후 ±12% + 급등 아님", t2,
    "이미 보유 중인 곳이 더 담았는데 주가는 조용한 경우")
tbl("■ 3군 — 공시 후 -25% 이상 하락 (해석 주의: 저가 매수 기회일 수도, 논리가 깨진 것일 수도)", t3[:12])

with open('foreign5_screen.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['보고일','종목','코드','제출인','구분','보유비율%','증감%p','보고사유',
                '현재가','공시후%','20일%','60일%','52주고점대비%','52주채널위치%','MA60대비%','MA120대비%'])
    for x in sorted(rows, key=lambda r: r['dt'], reverse=True):
        w.writerow([x['dt'],x['name'],x['code'],x['filer'],x['kind'],round(x['rt'],2),round(x['irds'],2),
                    x['resn'].replace('\n',' ')[:40], round(x['cur']), round(x['since'],1), round(x['d20'],1),
                    round(x['d60'],1), round(x['frhi'],1), round(x['pos']), round(x['vsma60'],1), round(x['vsma120'],1)])
print("\n→ 전체 77종목 표: foreign5_screen.csv")
