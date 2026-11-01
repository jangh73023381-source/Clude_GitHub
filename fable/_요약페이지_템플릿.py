# -*- coding: utf-8 -*-
"""데일리 브리핑 맨 앞장 '[한눈에 보기] 오늘의 선정 종목' 요약 페이지 (2026-09-26 신설, fable/CLAUDE.md 26번).

사용자 요청: "데일리 브리핑 맨 앞장에 선정된 종목을 요약식으로 정리해서, 바쁠 때는 그것만 봐도 되게."

원칙
  · **새 정보를 만들지 않는다.** 본문(3·5·6·8·9절)에 있는 값을 한 장으로 옮길 뿐이다.
    선정·우선순위·청산 로직에 어떤 형태로도 반영하지 않는다.
  · **가격은 5절과 같은 공식으로 계산한다** — 매수상단(평상 +0.6% / 게이트 +0.3%) · 지정가 -1.0% ·
    손절 = 종가 - 2.0×ATR14 · 목표 +3.0%. 5절에 넘긴 picks(ATR 포함)를 **그대로** 넘겨야
    두 곳의 숫자가 어긋나지 않는다.
  · 신규/유지/청산 구분은 직전 morning_state 의 picks5·mid_candidates 와 비교해 자동으로 판정한다.
  · 한 페이지를 넘기지 않는다. 경고는 3줄까지만 싣는다(근거는 본문).

사용법(생성 스크립트에서 title() 바로 다음, 기존 note/경고 박스보다 앞에 호출):

    _sp = _load('_요약페이지_템플릿.py', 'summary_tpl')
    _sp.add_summary_page(
        state_path=STATE, picks=PICKS5, gates=GATES,
        exec_date='2026-09-28 (월)',
        headlines=['원/달러 +17원·미 10년물 +21bp — 성장·기술주 역풍',
                   '9/28은 분기말 매도 정점(D-0) — 금액 축소·분할'],
        para=para, make_table=make_table, note=note, doc=doc,
        RED=RED_TXT, GREEN=GREEN_TXT, NAVY=NAVY)

    PICKS5 = [{'name':..., 'code':..., 'close':..., 'atr':...}, ...]  ← 5절 add_entry_strategy 와 같은 목록
    GATES  = {'crash': bool, 'rate': bool, 'riskon': bool}          ← 5절과 같은 dict
"""
import glob
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ 데이터
def _prev_state(state_path):
    """같은 폴더에서 state_path 보다 앞선 가장 최근 morning_state_<T>.json."""
    d = os.path.dirname(os.path.abspath(state_path))
    cur = os.path.basename(state_path)
    cands = sorted(p for p in glob.glob(os.path.join(d, 'morning_state_2*.json'))
                   if os.path.basename(p) < cur)
    # 2026-09-28: 같은 데이터일 D 의 state(휴장일 재실행분)는 건너뛴다 — 직전 '거래일' 선정과 비교해야 한다.
    try:
        cur_d = json.load(open(state_path, encoding='utf-8')).get('D')
    except Exception:
        cur_d = None
    for p in reversed(cands):
        try:
            s = json.load(open(p, encoding='utf-8'))
            if cur_d and s.get('D') == cur_d:
                continue
            if s.get('picks', {}).get('picks5'):
                return s
        except Exception:
            continue
    return None


def _eg_block(out, head):
    """eg_track.out 에서 '■ 매수'/'■ 매도' 블록의 종목 줄을 뽑는다. [(이름, 코드, 원문)]"""
    items, on = [], False
    for ln in (out or '').splitlines():
        s = ln.strip()
        if s.startswith('■'):
            # 2026-10-07 수정: '■ 매수 신호 신뢰도 상세' 블록도 '■ 매수'로 시작해 [표본] 행이 매수 목록에 중복 유입됐다.
            on = s.startswith(head) and '신뢰도' not in s
            continue
        if not on or not s or s == '없음' or s.startswith('※') or s.startswith('['):
            continue
        m = re.search(r'\s([0-9A-Z]{6})\s', ' ' + s + ' ')
        if m:
            nm = re.sub(r'^\d+\s+\S+\s+', '', s[:m.start()].strip())  # 매수 행 앞의 '순 섹터' 제거(2026-10-07)
            items.append((nm, m.group(1), s))
    return items


def from_state(state_path):
    st = json.load(open(state_path, encoding='utf-8'))
    pk = st.get('picks', {})
    prev = _prev_state(state_path)
    pp = (prev or {}).get('picks', {})

    short = [r for r in pk.get('short_etf10', [])]
    by_code = {r['code']: r for r in short}
    cur5 = [c for c in (pk.get('picks5') or '').split(',') if c]
    prev5 = [c for c in (pp.get('picks5') or '').split(',') if c]
    names = {r['code']: r['name'] for r in short}
    for r in pp.get('short_etf10', []):
        names.setdefault(r['code'], r['name'])

    mid = pk.get('mid_candidates', []) or []
    prev_mid = pp.get('mid_candidates', []) or []
    mid_codes = [m['code'] for m in mid]
    prev_mid_codes = [m['code'] for m in prev_mid]
    mid_names = {m['code']: m['name'] for m in prev_mid + mid}

    eg_out = st.get('eg_track', {}).get('out', '')
    return {
        'D': st.get('D'), 'T': st.get('T'),
        'has_prev': prev is not None,
        'short5': [by_code.get(c, {'code': c, 'name': names.get(c, c)}) for c in cur5],
        'short_status': {c: ('유지' if c in prev5 else '신규') for c in cur5} if prev else {},
        'short_exit': [(c, names.get(c, c)) for c in prev5 if c not in cur5],
        'mid5': mid,
        'mid_status': {c: ('보유' if c in prev_mid_codes else '신규') for c in mid_codes} if prev else {},
        'mid_exit': [(c, mid_names.get(c, c)) for c in prev_mid_codes if c not in mid_codes],
        'eg_buy': _eg_block(eg_out, '■ 매수'),
        # [2026-10-07 미해결] eg '■ 매도' 는 D(채점일) 종가 청산분이다. 전일 브리핑이 이미 'D 종가 매도'로 안내했다면
        # 집행일 매도로 오독된다 — 재현: morning_state_20261007(10/6 청산 4건). 생성기에서 표기를 덮어써 대응 중.
        'eg_sell': _eg_block(eg_out, '■ 매도'),
        'eg_ok': bool(eg_out),
        'fall5': pk.get('fall5', []) or [],
    }


def _atr(code, close):
    try:
        import importlib.util as il
        s = il.spec_from_file_location('entry_tpl_sp', os.path.join(_HERE, '_진입전략_템플릿.py'))
        m = il.module_from_spec(s)
        s.loader.exec_module(m)
        return m._atr_won(code, close)
    except Exception:
        return None


def _apply_widths(t, widths):
    """make_table 이 colwidths 를 무시하므로 고정 레이아웃으로 폭을 강제한다(_데이터검증_템플릿과 동일)."""
    if t is None:
        return t
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Twips
    t.autofit = False
    tot = sum(widths); sc = min(1.0, 10400 / tot) if tot else 1.0  # widths가 빈 리스트면 0으로 나누지 않는다
    pr = t._tbl.tblPr
    for el in pr.findall(qn('w:tblLayout')):      # autofit 흔적 제거 후 fixed 하나만 둔다
        pr.remove(el)
    lay = OxmlElement('w:tblLayout'); lay.set(qn('w:type'), 'fixed'); pr.append(lay)
    for el in pr.findall(qn('w:tblW')):
        pr.remove(el)
    tw = OxmlElement('w:tblW'); tw.set(qn('w:w'), str(int(tot * sc))); tw.set(qn('w:type'), 'dxa')
    pr.append(tw)
    for i, gc in enumerate(t._tbl.tblGrid.findall(qn('w:gridCol'))):
        gc.set(qn('w:w'), str(int(widths[i] * sc)))
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Twips(int(w * sc))
            for p in row.cells[i].paragraphs:      # 요약 페이지는 한 장에 들어가야 하므로 행 간격 최소화
                p.paragraph_format.space_after = 0
                p.paragraph_format.space_before = 0
    return t


def _tbl(make_table, headers, rows, widths):
    return _apply_widths(make_table(headers, rows, widths), widths)


def _w(v):
    return f'{v:,.0f}'


def _mmdd(D):
    return f'{int(D[4:6])}/{int(D[6:8])}' if D and len(D) == 8 else (D or '')


# ------------------------------------------------------------------ 렌더링
def add_summary_page(state_path, picks, gates, exec_date, para, make_table, note, doc,
                     RED, GREEN, NAVY, headlines=None, page_break=True):
    S = from_state(state_path)
    D = _mmdd(S['D'])
    crash, rate = gates.get('crash'), gates.get('rate')
    cons = bool(crash or rate)
    up = 0.003 if cons else 0.006

    # 머리띠
    para([('[한눈에 보기]  오늘의 선정 종목 — 바쁘면 이 페이지만 보세요', 13, True, NAVY)],
         space_before=2, space_after=2)
    note(f"{D} 종가 기준 · 집행일 {exec_date} · 아래 값은 본문 3·5·6·8·9절과 같은 값을 옮긴 것입니다"
         f"(새로 반영된 규칙 없음).", size=8.5)

    # 오늘의 모드
    if cons:
        sig = []
        if crash:
            sig.append('4번 급락 게이트')
        if rate:
            sig.append('11번 금리 게이트')
        para([('오늘 모드: 보수 (게이트 발동 — ' + ' · '.join(sig) + ')  ', 10.5, True, RED),
              ('매수상단 +0.3% · 종목당 금액 평소의 2/3 · 14:30까지 미체결이면 사지 않음(케이스 ③ 미적용).',
               9.5, False, None)], space_after=4, shading='FCE4E4')
    else:
        para([('오늘 모드: 표준 (게이트 미발동)  ', 10.5, True, GREEN),
              ('매수상단 +0.6% · 14:30까지 미체결이면 종가 무렵 시장가로 담음(케이스 ③).',
               9.5, False, None)], space_after=4, shading='E2EFDA')

    # ① 단기 실매수 5종
    para([('① 단기 ETF 실매수 5종 ', 10.5, True, NAVY),
          ('— 09:00 시가를 보고 매수, 익일 종가 청산 ([6-1]·5절)', 8.5, False, None)],
         space_before=4, space_after=2)
    st_map = S['short_status']
    rows = []
    for i, p in enumerate(picks, 1):
        c = float(p['close'])
        a = p.get('atr') or _atr(p['code'], c)
        stop = _w(round(c - 2.0 * a)) if a else _w(round(c * 0.975)) + '*'
        rows.append([str(i), f"{p['name']} ({p['code']})", st_map.get(p['code'], '—'),
                     _w(c), _w(round(c * (1 + up))), _w(round(c * 0.99)), stop,
                     _w(round(c * 1.03))])
    _tbl(make_table, ['#', '종목 (코드)', '구분', f'{D} 종가',
                f"매수상단({'+0.3' if cons else '+0.6'}%)", '지정가(-1%)', '손절(2ATR)', '목표(+3%)'],
               rows, [350, 3500, 600, 1000, 1250, 1050, 1050, 1000])
    new = [p['name'] for p in picks if st_map.get(p['code']) == '신규']
    keep = [p['name'] for p in picks if st_map.get(p['code']) == '유지']
    ex = [n for _, n in S['short_exit']]
    if S['has_prev']:
        note(f"※ 오늘 할 거래 — 매도 {len(ex)}건" + (f"({', '.join(ex)} → {exec_date} 종가)" if ex else '')
             + f" · 매수 {len(new)}건" + (f"({', '.join(new)})" if new else '')
             + f" · 계속 보유 {len(keep)}건(팔고 다시 사지 않음).", size=8.5)
    # 5절 목록과 state picks5 가 다르면 경고(값 불일치 방지)
    sc = [r['code'] for r in S['short5']]
    if sc and sc != [p['code'] for p in picks]:
        note('※ [확인 필요] 요약에 넘긴 picks 순서/구성이 morning_state picks5 와 다릅니다: '
             + ','.join(sc), size=8.5)

    # ② 중기 5종
    para([('② 중기 ETF 5종 ', 10.5, True, NAVY),
          ('— 15:20~15:30 종가 단일가, 당일 등락 -0.5%~+1.5%인 종목만 매수 · 추천에서 빠지는 날 종가 청산 ([6-3]·Rule CB)',
           8.5, False, None)], space_before=4, space_after=2)
    ms = S['mid_status']
    # 한 장에 넣기 위해 가로형(5열)으로 싣는다: 열 = 순위, 1행 = 종목(코드), 2행 = 구분
    mids = S['mid5'][:5]
    if mids:
        _tbl(make_table, [f'{i}위' for i in range(1, len(mids) + 1)],
             [[f"{m['name']} ({m['code']})" for m in mids],
              [ms.get(m['code'], '—') for m in mids]],
             [2080] * len(mids))
    else:
        # 2026-11-01: mids가 비면 열 수(=len(mids))가 0이 돼 _apply_widths의
        # sum(widths)=0으로 ZeroDivisionError가 났다(중기 후보 0건인 날 요약 페이지 전체가 죽음).
        note('중기 추천 없음', size=9.5)
    if S['mid_exit']:
        note('※ 중기 청산: ' + ', '.join(f'{n}({c})' for c, n in S['mid_exit'])
             + ' — 추천 탈락, 첫 브리핑일 종가 청산.', size=8.5)

    # ③ 기타 신호
    para([('③ 그 밖의 신호', 10.5, True, NAVY)], space_before=4, space_after=2)

    def _fmt(lst):
        return ', '.join(f'{n}({c})' for n, c, _ in lst) if lst else '없음'
    eg_b = _fmt(S['eg_buy']) if S['eg_ok'] else '산출 없음(9절 확인)'
    eg_s = _fmt(S['eg_sell']) if S['eg_ok'] else '산출 없음(9절 확인)'
    avoid = ', '.join(f"{r['name']}({r['code']})" for r in S['fall5']) or '—'
    _tbl(make_table, ['구분', '내용'], [
        ['트랙 D 매수 (9절, 종가)', eg_b],
        ['트랙 D 매도 (9절, 20일째 종가)', eg_s],
        ['매수 피할 ETF (8절, mom20 하위)', avoid],
    ], [2600, 7200])

    # ④ 핵심 경고(최대 3줄)
    hl = [h for h in (headlines or []) if h][:3]
    if hl:
        para([('④ 오늘 꼭 알아둘 것', 10.5, True, RED)], space_before=4, space_after=2)
        for h in hl:
            note('· ' + h, size=9)

    note('※ 이 페이지는 요약입니다. 판정 근거·예외 케이스(갭상승·갭하락 대응)는 3·5절, '
         '선정 근거는 6절에 있습니다. 투자 판단과 금액은 본인 책임입니다.', size=8)
    if page_break:
        doc.add_page_break()
    return S
