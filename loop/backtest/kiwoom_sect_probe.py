#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiwoom_sect_probe.py — 키움 REST 업종(sect) 조회가 되는지, 당일 데이터가 오는지 확인.

왜 필요한가
  2026-08-18 루프 iteration 9(Rule SRV, 업종지수 → 테마 ETF 전이)는 KRX 업종지수를 썼는데,
  KRX OPEN API 는 D 일자를 D+1 장중에 공개한다. 선정 시각(아침 06:00)에는 D 값을 못 받는다.
  키움 REST 가 **같은 업종지수를 당일 저녁에** 주면 SRV 재시도 조건 하나가 풀린다.

왜 클라우드에서 못 하나
  키움 API 가 클라우드 IP를 차단한다(HTTP 400 Request Blocked). **사용자 PC에서 실행해야 한다.**

사용
  python3 backtest/kiwoom_sect_probe.py            # 결과가 화면 + kiwoom_sect_result.txt 에 저장
  (또는 loop 폴더의 `키움_업종조회_확인.bat` 더블클릭)

조회 전용이다. 주문·매매·이체는 호출하지 않는다.
"""
import io, json, os, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, LOOP)
OUT = os.path.join(HERE, 'kiwoom_sect_result.txt')

# (api-id, 경로, 바디) 후보 행렬. 어느 조합이 통하는지 모르므로 넓게 시도한다.
CANDIDATES = []
for aid in ('ka20003', 'ka20001', 'ka20002', 'ka20009'):
    for mkt in ('0', '1', '2'):
        for inds in ('001', '101'):
            CANDIDATES.append((aid, '/api/dostk/sect',
                               {'mrkt_tp': mkt, 'inds_cd': inds, 'stex_tp': '1'}))
            CANDIDATES.append((aid, '/api/dostk/sect',
                               {'mrkt_tp': mkt, 'inds_cd': inds}))


def main():
    lines = []

    def p(s=''):
        print(s)
        lines.append(str(s))

    p(f'실행 시각: {datetime.datetime.now():%Y-%m-%d %H:%M:%S} (로컬)')
    p('목적: 키움 REST 업종지수 조회 가능 여부 + 당일(오늘) 데이터 제공 여부')
    p('=' * 70)

    try:
        import kiwoom_api as KW
    except Exception as e:
        p(f'[중단] kiwoom_api 임포트 실패: {type(e).__name__} {e}')
        io.open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
        return 2

    try:
        KW.get_access_token()
        p('[1/2] 토큰 발급: 성공')
    except Exception as e:
        p(f'[1/2] 토큰 발급: 실패 — {type(e).__name__}: {str(e)[:300]}')
        p('      → 이 PC에서 키움 API 자체가 안 되는 상태다. 네트워크/키/IP 등록을 먼저 확인할 것.')
        io.open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
        return 2

    p('[2/2] 업종 엔드포인트 탐색 — 통하는 조합만 자세히 출력한다')
    ok = []
    seen = set()
    for aid, path, body in CANDIDATES:
        key = (aid, path, json.dumps(body, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        try:
            r = KW._call(path, aid, body)
        except Exception as e:
            continue                      # 400/404 는 그 조합이 없다는 뜻이므로 조용히 넘긴다
        rc = str(r.get('return_code', ''))
        if rc not in ('0', '', 'None'):
            continue
        blocks = {k: v for k, v in r.items()
                  if isinstance(v, list) and v and k not in ('return_code', 'return_msg')}
        if not blocks:
            continue
        ok.append((aid, body, blocks))
        p('')
        p(f'  ★ 성공 — api-id={aid}  body={json.dumps(body, ensure_ascii=False)}')
        for bk, bv in blocks.items():
            p(f'     블록 {bk}: {len(bv)}행 · 필드 {list(bv[0].keys())}')
            for row in bv[:3]:
                p(f'       {json.dumps(row, ensure_ascii=False)[:260]}')

    p('')
    p('=' * 70)
    if not ok:
        p('결과: 업종 조회에 성공한 조합이 없다.')
        p('  → 키움 경로는 닫힌 것으로 보고, Rule SRV 는 "당일 조달 불가"로 유지한다.')
    else:
        p(f'결과: {len(ok)}개 조합 성공.')
        p('  ★ 확인할 것 — 위 출력에 **오늘 날짜(또는 오늘 종가)** 가 들어 있는가?')
        p('    · 오늘 값이 있으면 → 당일 조달 가능. Rule SRV 재시도 조건 (b)가 풀린다.')
        p('    · 전 거래일까지만 있으면 → KRX 와 같은 지연이므로 SRV 는 그대로 보류.')
    p('')
    p(f'이 내용은 {OUT} 에도 저장했다. 다음 루프 세션에서 이 파일을 읽어 달라고 하면 된다.')
    io.open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
