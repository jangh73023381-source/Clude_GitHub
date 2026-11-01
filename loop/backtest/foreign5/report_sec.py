# -*- coding: utf-8 -*-
import json, collections, csv, stock_sector
rows = json.load(open('_screen.json', encoding='utf-8'))
ACTIVE = ('Miri','DALTON','Kopernik','Silchester','Orbis','FederatedHermes','Swedbank',
          'Wellington','티로우','인베스코','슈로더','AllianceBernstein','CapitalResearch',
          'CapitalGroup','FILLIMITED','피델리티','NorgesBank','GICPrivate','GOVERNMENTOFSINGAPORE')
for r in rows:
    r['sec'], _ = stock_sector.sector(r['code'])
    r['act'] = '★' if any(k.lower() in r['filer'].lower() for k in ACTIVE) else ' '
    if r['irds'] >= 4.9: r['tier'] = '신규'
    elif r['irds'] >= 1.0: r['tier'] = '확대'
    elif r['irds'] <= -1.0: r['tier'] = '축소'
    else: r['tier'] = '유지'
    q = (r['since'] < 15 and r['d20'] < 12 and r['frhi'] < -12)
    r['quiet'] = '조용' if q else ('분출' if r['since'] >= 25 else '  ')

by = collections.defaultdict(list)
for r in rows: by[r['sec']].append(r)
order = sorted(by, key=lambda s: (-len(by[s]), s))
print("■ 외국계 5% 이상 대량보유 — 섹터별 (77종목 · 기준 2026-09-08 종가)")
print("  ★=액티브 밸류하우스 / 신규=+5%p 신규진입 · 확대=+1%p↑ · 축소=-1%p↓ / 조용=아직 안 움직임\n")
for s in order:
    lst = sorted(by[s], key=lambda x: x['dt'], reverse=True)
    nq = sum(1 for x in lst if x['quiet'] == '조용')
    print(f"── {s}  ({len(lst)}종목 · 조용 {nq})")
    print(f"   {'보고일':<11}{'종목':<15}{'코드':<8}{'':<2}{'구분':<5}{'비율':>6}{'증감':>6}{'공시후':>8}{'20일':>7}{'고점차':>8}{'상태':>5}  제출인")
    for x in lst:
        print(f"   {x['dt']:<11}{x['name'][:13]:<15}{x['code']:<8}{x['act']:<2}{x['tier']:<5}"
              f"{x['rt']:>5.1f}%{x['irds']:>+6.1f}{x['since']:>+8.1f}{x['d20']:>+7.1f}{x['frhi']:>+8.1f}"
              f"{x['quiet']:>5}  {x['filer'][:22]}")
    print()

with open('foreign5_by_sector.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f)
    w.writerow(['섹터','보고일','종목','코드','제출인','액티브','구분','보유비율%','증감%p','보고사유',
                '현재가','공시후%','20일%','60일%','52주고점대비%','채널위치%','MA60대비%','상태'])
    for s in order:
        for x in sorted(by[s], key=lambda r: r['dt'], reverse=True):
            w.writerow([s,x['dt'],x['name'],x['code'],x['filer'],'Y' if x['act']=='★' else '',
                        x['tier'],round(x['rt'],2),round(x['irds'],2),x['resn'].replace('\n',' ')[:40],
                        round(x['cur']),round(x['since'],1),round(x['d20'],1),round(x['d60'],1),
                        round(x['frhi'],1),round(x['pos']),round(x['vsma60'],1),x['quiet'].strip()])
print("→ foreign5_by_sector.csv 저장")
