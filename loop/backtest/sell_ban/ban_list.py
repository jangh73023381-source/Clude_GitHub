#!/usr/bin/env python3
"""매수 금지 목록 스캐너(초안, 아침 루틴 미연결) — Rule SB 후보(V1): '역배열 진입' 후 최대 20거래일 매수 금지,
역배열이 풀리면 조기 해제. 조회 전용.
역배열 진입 = 신호일 D 에 MA5<MA20<MA60 이 처음 성립(전일은 불성립). 브리핑일 T 목록 = D ∈ [T-20, T-1] 이면서
T-1 종가(=데이터 마지막 날) 기준 아직 역배열인 종목. 목록 비중이 클수록(시장 전반 조정) 정보가 약하다(7년 실측).
사용: python3 ban_list.py [state_json]   (먼저 build_cache.py 로 캐시 갱신)"""
import os, sys, json
import numpy as np
import engine as E, signals as SG
BAN = 20
d = E.load(); I = E.indicators(d); C = I['C']; M, N = C.shape; dates = d['dates']; codes = d['codes']
sig = SG.build(I)['F14 역배열 진입']
state = (I['MA5'] < I['MA20']) & (I['MA20'] < I['MA60'])
flags = {}
if len(sys.argv) > 1:
    st = json.load(open(sys.argv[1], encoding='utf-8'))['picks']
    for c in st['picks5'].split(','):
        flags.setdefault(c, []).append('단기실매수')
    for x in st['short_etf10']:
        flags.setdefault(x['code'], []).append('6-1표')
    for x in st['mid_candidates']:
        flags.setdefault(x['code'], []).append('중기후보')
rows = []
for m in range(M):
    js = [j for j in range(max(0, N - BAN), N) if sig[m, j]]
    if not js or np.isnan(C[m, N - 1]) or not state[m, N - 1]:     # V1: 역배열 해소 시 조기 해제
        continue
    j = js[-1]; k = N - j                       # 경과 거래일(T 기준)
    rows.append(dict(sec=d['secs'][m], name=d['names'][codes[m]], code=codes[m], sig=int(dates[j]), elapsed=k,
                     remain=BAN - k + 1, still=bool(state[m, N - 1]), mom20=float(I['MOM20'][m, N - 1] * 100),
                     flag='·'.join(flags.get(codes[m], []))))
rows.sort(key=lambda r: (-r['remain'], r['sec']))
nu = int((~np.isnan(C[:, -1])).sum()); sh_ = len(rows) / nu * 100
rel = '강(개별 붕괴 위주)' if sh_ <= 5.4 else ('보통' if sh_ <= 17.2 else '약(시장 전반 조정 — 7년 실측상 목록 효과가 거의 없음)')
print(f'[매수 금지 목록 — 역배열 진입 후 최대 {BAN}거래일 · 해소 시 조기 해제] D={dates[-1]} 기준 · 목록 {len(rows)}종 / 유니버스 {nu}종 '
      f'= 비중 {sh_:.1f}% → 신뢰도 {rel}')
print(f"   {'섹터':8s} {'종목':30s} {'코드':6s} {'신호일':>8s} {'경과':>4s} {'남은금지':>6s} {'mom20':>7s}  비고")
for r in rows:
    print(f"   {r['sec']:8s} {r['name'][:28]:30s} {r['code']:6s} {r['sig']:>8d} {r['elapsed']:>4d} {r['remain']:>6d}일 "
          f"{r['mom20']:>+6.1f}%  {r['flag']}")
json.dump(dict(D=int(dates[-1]), n=len(rows), universe=nu, share=sh_, reliability=rel, rows=rows),
          open(os.path.join(E.HERE, f'ban_list_{dates[-1]}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
hit = [r for r in rows if r['flag']]
print(f'   ※ 오늘 추천·후보와 겹치는 종목 {len(hit)}건' + (': ' + ', '.join(f"{r['name']}({r['flag']})" for r in hit) if hit else ''))
