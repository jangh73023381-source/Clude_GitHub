# -*- coding: utf-8 -*-
"""공개용 데일리 브리핑 요약 생성 + 텔레그램 채널 게시 (2026-10-21 사용자 요청).

  python3 references/scripts/public_post.py            # 미리보기만(게시 안 함, 기본)
  python3 references/scripts/public_post.py --send     # 텔레그램 채널에 게시
  python3 references/scripts/public_post.py --date 20261021

- 입력: 장중알림/plans/watch_plan_<T>.json(선정·가격선 — 브리핑 5절 공식) + references/lv_oos_tracker.csv(성과).
  **선정을 재계산하지 않는다.** 브리핑 PDF 를 만든 뒤에만 실행한다.
- 공개본에서 빼는 것: 트랙 D 보유·평가손익(개인 운용), 루프 내부 용어(검증관·N 대장·shadow), 회사 결재.
- 산출: fable/공개/공개브리핑_YYYY-MM-DD.md (웹 아카이브 원본) · fable/공개/index.md(누적 목록).
- 자격증명: loop/telegram_bot_token.txt · loop/telegram_chat_id.txt — 읽기만 하고 출력하지 않는다.
- 멱등: references/telegram_post_log.csv 에 게시일이 있으면 생략(--force 로 강제).
- 게시 전용. 주문·매매 기능 없음.
"""
import argparse, csv, json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
LOOP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FABLE = os.path.abspath(os.path.join(LOOP, '..', 'fable'))
PUB = os.path.join(FABLE, '공개')
LOG = os.path.join(LOOP, 'references', 'telegram_post_log.csv')

DISCLAIMER = ("※ 본 자료는 개인이 자체 규칙으로 만든 참고 정보이며 투자 권유·자문이 아닙니다. "
              "과거 성과와 백테스트는 미래 수익을 보장하지 않습니다. 매매 판단과 손익의 책임은 투자자 본인에게 있습니다. "
              "유료 서비스·1:1 상담·리딩을 하지 않습니다.")


def perf():
    rows = list(csv.DictReader(open(os.path.join(LOOP, 'references', 'lv_oos_tracker.csv'), encoding='utf-8')))
    rows = [r for r in rows if r.get('lv_ret') not in ('', None)]
    lv = bm = 1.0
    for r in rows:
        lv *= 1 + float(r['lv_ret']) / 100
        bm *= 1 + float(r['bench_ret']) / 100
    last = rows[-1]
    # 중기 5종(Rule MM mom150) — 단기와 같은 선정일 구간, 보유 5종을 매일 그대로 들고 있었다고 가정(종가 밴드 미반영).
    dates = {r['date'] for r in rows}
    mrows = [r for r in csv.DictReader(open(os.path.join(LOOP, 'references', 'mid_momentum_shadow.csv'), encoding='utf-8'))
             if r.get('status') == 'scored' and r['date'] in dates and r.get('mom150_ret') not in ('', None)]
    mid = 1.0
    for r in mrows:
        mid *= 1 + float(r['mom150_ret']) / 100
    return dict(n=len(rows), start=rows[0]['date'], lv=(lv - 1) * 100, bm=(bm - 1) * 100,
                last_lv=float(last['lv_ret']), last_bm=float(last['bench_ret']),
                mid=(mid - 1) * 100 if mrows else None, mid_n=len(mrows),
                last_mid=float(mrows[-1]['mom150_ret']) if mrows else None)


def build(T):
    wp = json.load(open(os.path.join(LOOP, '장중알림', 'plans', f'watch_plan_{T}.json'), encoding='utf-8'))
    p = perf()
    d = datetime.strptime(T, '%Y%m%d')
    wd = '월화수목금토일'[d.weekday()]
    L = [f"📊 데일리 ETF 브리핑 {d.month}/{d.day}({wd})", ""]
    if wp['mode'] == '보수':
        L += ["⚠️ 오늘은 보수 모드 — 급락·금리 경고 신호 발동", "매수상단 전일종가 +0.3% · 금액 평소의 2/3 · 14:30까지 미체결이면 매수하지 않음", ""]
    else:
        L += ["✅ 표준 모드 — 매수상단 전일종가 +0.6%", ""]
    L.append("■ 단기 ETF 5종 (저변동 정렬 규칙 · 익일 교체)")
    for s in wp['short']:
        L.append(f"· {s['name']}({s['code']}) [{s['status']}]")
        L.append(f"  전일 {s['prev_close']:,.0f} / 매수상단 {s['upper']:,} / 지정가 {s['limit']:,} / 손절 {s['stop']:,} / 목표 {s['target']:,}")
    if wp.get('short_sells'):
        L.append("  오늘 종가 교체(제외): " + ", ".join(x['name'] for x in wp['short_sells']))
    L += ["", "■ 중기 ETF 5종 (150일 모멘텀 · 종가 무렵 당일 등락 "
          f"{wp['mid_band'][0]:+.1f}%~{wp['mid_band'][1]:+.1f}% 일 때만)"]
    L += ["· " + ", ".join(f"{m['name']}({m['code']})" for m in wp['mid'])]
    L += ["", f"■ 성과 공개 (누적 {p['n']}거래일 {p['start'][4:6]}/{p['start'][6:]}~ · 무비용 가정 · 손실일 포함)",
          f"단기 5종 {p['lv']:+.2f}% (직전 {p['last_lv']:+.2f}%)"]
    if p.get('mid') is not None:
        L.append(f"중기 5종 {p['mid']:+.2f}% (직전 {p['last_mid']:+.2f}%)")
    L += [f"KODEX200 {p['bm']:+.2f}% (직전 {p['last_bm']:+.2f}%)",
          "※ 중기는 5종을 매일 그대로 보유했다고 가정한 값(종가 진입 밴드 미반영)"]
    uf = os.path.join(LOOP, 'references', 'public_site_url.txt')
    if os.path.exists(uf):
        L += ["", "📈 누적 성과 차트·지난 브리핑: " + open(uf, encoding='utf-8').read().strip()]
    L += ["", DISCLAIMER]
    return "\n".join(L)


def send(text):
    tok = open(os.path.join(LOOP, 'telegram_bot_token.txt'), encoding='utf-8-sig').read().strip()
    chat = open(os.path.join(LOOP, 'telegram_chat_id.txt'), encoding='utf-8-sig').read().strip()
    data = urllib.parse.urlencode({'chat_id': chat, 'text': text, 'disable_web_page_preview': 'true'}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendMessage', data=data)
    try:
        r = json.load(urllib.request.urlopen(req, timeout=20))
    except Exception as e:  # 토큰이 URL 에 있으므로 예외 문자열은 출력하지 않는다
        return False, type(e).__name__
    return bool(r.get('ok')), r.get('description', '')


def build_pdf(T):
    """공개용 1~2쪽 PDF (개인 보유·내부 용어 제외 · 면책 고지 포함). 반환: pdf 경로 또는 None."""
    import subprocess
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    wp = json.load(open(os.path.join(LOOP, '장중알림', 'plans', f'watch_plan_{T}.json'), encoding='utf-8'))
    p = perf()
    d = datetime.strptime(T, '%Y%m%d'); wd = '월화수목금토일'[d.weekday()]
    NAVY, RED, GREEN = RGBColor(0x1F, 0x38, 0x64), RGBColor(0xB3, 0x40, 0x2A), RGBColor(0x1E, 0x7B, 0x34)
    doc = Document()
    st = doc.styles['Normal']; st.font.name = '맑은 고딕'; st.font.size = Pt(10)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), '맑은 고딕')
    def para(text, size=10, bold=False, color=None, after=4):
        q = doc.add_paragraph(); r = q.add_run(text); r.font.size = Pt(size); r.bold = bold
        if color: r.font.color.rgb = color
        q.paragraph_format.space_after = Pt(after); return q
    def table(head, rows, widths=None):
        tb = doc.add_table(rows=1, cols=len(head)); tb.style = 'Table Grid'; tb.autofit = False
        for i, h in enumerate(head):
            c = tb.rows[0].cells[i]; c.text = ''; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(8.5)
        for row in rows:
            cs = tb.add_row().cells
            for i, v in enumerate(row):
                cs[i].text = ''; r = cs[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(8.5)
                if i > 1: cs[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if widths:
            for col, w in zip(tb.columns, widths): col.width = Inches(w)
            grid = tb._tbl.tblGrid
            for gc, w in zip(grid.findall(qn('w:gridCol')), widths): gc.set(qn('w:w'), str(int(w * 1440)))
            for row in tb.rows:
                for c, w in zip(row.cells, widths): c.width = Inches(w)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
    para(f"데일리 ETF 브리핑 — {d.year}년 {d.month}월 {d.day}일({wd})", 16, True, NAVY, 2)
    para("전일 종가 기준 · 장 시작 전 발행 · 텔레그램 @daily_etf_brief_kr", 9, color=RGBColor(0x59, 0x59, 0x59), after=8)
    if wp['mode'] == '보수':
        para("■ 보수 모드 — 급락·금리 경고 신호 발동", 11, True, RED, 2)
        para("매수상단 전일종가 +0.3% · 종목당 금액 평소의 2/3 · 14:30까지 지정가 미체결이면 매수하지 않음", 9.5, after=8)
    else:
        para("■ 표준 모드", 11, True, GREEN, 2)
        para("매수상단 전일종가 +0.6% · 14:30까지 미체결이면 종가 무렵 시장가", 9.5, after=8)
    para("1. 단기 ETF 5종 (저변동 정렬 규칙 · 하루 보유 후 교체)", 12, True, NAVY)
    table(["종목", "코드", "구분", "전일종가", "매수상단", "지정가(-1%)", "손절(2ATR)", "목표(+3%)"],
          [[s['name'], s['code'], s['status'], f"{s['prev_close']:,.0f}", f"{s['upper']:,}", f"{s['limit']:,}", f"{s['stop']:,}", f"{s['target']:,}"] for s in wp['short']],
          [2.35, 0.65, 0.45, 0.7, 0.7, 0.7, 0.7, 0.7])
    if wp.get('short_sells'):
        para("오늘 종가 교체(제외): " + ", ".join(x['name'] for x in wp['short_sells']), 9, after=8)
    para("2. 중기 ETF 5종 (150일 모멘텀)", 12, True, NAVY)
    para(f"종가 무렵(15:20~15:30) 당일 등락 {wp['mid_band'][0]:+.1f}% ~ {wp['mid_band'][1]:+.1f}% 인 종목만 매수 · 추천에서 빠지는 날 종가 청산", 9)
    table(["종목", "코드"], [[m['name'], m['code']] for m in wp['mid']], [3.2, 1.0])
    para("3. 성과 공개 (무비용 가정 · 손실일 포함)", 12, True, NAVY)
    mid_l = f"{p['last_mid']:+.2f}%" if p.get('mid') is not None else '—'
    mid_c = f"{p['mid']:+.2f}%" if p.get('mid') is not None else '—'
    table(["구분", "단기 5종", "중기 5종", "KODEX200"],
          [["직전 거래일", f"{p['last_lv']:+.2f}%", mid_l, f"{p['last_bm']:+.2f}%"],
           [f"누적 {p['n']}거래일({p['start'][4:6]}/{p['start'][6:]}~)", f"{p['lv']:+.2f}%", mid_c, f"{p['bm']:+.2f}%"]], [2.3, 1.2, 1.2, 1.2])
    para("중기는 5종을 매일 그대로 보유했다고 가정한 값입니다(종가 진입 밴드 미반영). 호가 스프레드·슬리피지는 반영하지 않았습니다.", 8.5, after=10)
    para("면책 고지", 10, True)
    para(DISCLAIMER.lstrip('※ '), 8.5)
    os.makedirs(PUB, exist_ok=True)
    day = f"{T[:4]}-{T[4:6]}-{T[6:]}"
    dx = os.path.join(PUB, f'공개브리핑_{day}.docx'); doc.save(dx)
    # 2026-10-27: /tmp 는 세션 간 공유라 이전 세션이 만든 /tmp/lohome(nobody 소유)에 쓰지 못하면
    # soffice 가 무응답으로 120초 타임아웃된다(실측). 쓸 수 없으면 세션별 디렉터리로 돌린다.
    lohome = '/tmp/lohome'
    os.makedirs(lohome, exist_ok=True)
    if not os.access(lohome, os.W_OK):
        lohome = f'/tmp/lohome_{os.getuid()}'
        os.makedirs(lohome, exist_ok=True)
    env = dict(os.environ, HOME=lohome, TMPDIR='/tmp')
    subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', dx, '--outdir', PUB], env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    pdf = dx[:-5] + '.pdf'
    return pdf if os.path.exists(pdf) else None


def redact_original(src, out):
    """원본 브리핑 PDF 의 공개판(2026-10-23). 개인 운용(트랙 D) 정보를 뺀다.
    ① '9. 매수·매도 타점' 시작 쪽 ~ '10.' 시작 쪽(9절 꼬리 포함)을 통째로 뺀다.
    ② 남은 쪽 중 '평가손익'·'매입가'가 있는 쪽도 뺀다.
    ③ '트랙 D' 와 손익률(%)이 같은 줄에 있으면 그 줄을 검게 가린다(텍스트 삭제).
    pymupdf 가 없거나 9절을 못 찾으면 None(원본을 붙이지 않음 — 안전 쪽)."""
    try:
        import pymupdf
    except Exception:
        import subprocess, importlib, site
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', '-q', 'pymupdf'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=150)
        try:
            importlib.invalidate_caches(); sys.path.insert(0, site.getusersitepackages()); import pymupdf
        except Exception:
            print('  [공개판] pymupdf 없음(설치 실패) — 원본 미첨부'); return None
    import re
    try:
        doc = pymupdf.open(src); n = doc.page_count
        txt = [doc[i].get_text() for i in range(n)]
        s9 = next((i for i in range(n) if re.search(r'(?m)^9\. 매수·매도 타점', txt[i])), None)
        if s9 is None:
            print('  [공개판] 9절 미발견 — 원본 미첨부'); return None
        s10 = next((i for i in range(s9, n) if re.search(r'(?m)^10\. ', txt[i])), n - 1)
        drop = set(range(s9, s10 + 1)) | {i for i in range(n) if ('평가손익' in txt[i] or '매입가' in txt[i])}
        keep = [i for i in range(n) if i not in drop]
        for i in keep:
            pg = doc[i]; hit = 0
            for b in pg.get_text('dict')['blocks']:
                for ln in b.get('lines', []):
                    t = ''.join(sp['text'] for sp in ln['spans'])
                    if '트랙 D' in t and '%' in t:
                        pg.add_redact_annot(ln['bbox'], fill=(0, 0, 0)); hit += 1
            if hit:
                pg.apply_redactions()
        doc.select(keep); doc.save(out, garbage=3, deflate=True); doc.close()
        chk = pymupdf.open(out); bad = [i for i in range(chk.page_count)
                                          if re.search(r'평가손익|매입가|9\. 매수·매도 타점', chk[i].get_text())]
        chk.close()
        if bad:
            print(f'  [공개판] 검증 실패(쪽 {bad}) — 원본 미첨부'); os.remove(out); return None
        print(f'  [공개판] 원본 {n}쪽 → {len(keep)}쪽 (제외 {sorted(x + 1 for x in drop)})'); return out
    except Exception as e:
        print(f'  [공개판] 오류 {e} — 원본 미첨부'); return None


def send_photo(path, caption=''):
    """요약 카드 PNG 게시(sendPhoto, multipart). 토큰은 출력하지 않는다."""
    import uuid
    tok = open(os.path.join(LOOP, 'telegram_bot_token.txt'), encoding='utf-8-sig').read().strip()
    chat = open(os.path.join(LOOP, 'telegram_chat_id.txt'), encoding='utf-8-sig').read().strip()
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat}\r\n'.encode()]
    if caption:
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode())
    parts.append((f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="summary.png"\r\n'
                  'Content-Type: image/png\r\n\r\n').encode() + open(path, 'rb').read() + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendPhoto', data=b''.join(parts),
                                 headers={'Content-Type': f'multipart/form-data; boundary={b}'})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        try:
            return False, json.load(e).get('description', f'HTTP {e.code}')
        except Exception:
            return False, f'HTTP {e.code}'
    except Exception as e:
        return False, type(e).__name__
    return bool(r.get('ok')), r.get('description', '')


def send_doc(path, caption):
    """PDF 첨부 게시(multipart). 토큰은 출력하지 않는다."""
    import uuid
    tok = open(os.path.join(LOOP, 'telegram_bot_token.txt'), encoding='utf-8-sig').read().strip()
    chat = open(os.path.join(LOOP, 'telegram_chat_id.txt'), encoding='utf-8-sig').read().strip()
    b = uuid.uuid4().hex; fn = 'daily_etf_briefing_' + os.path.basename(path)[6:16] + '.pdf'
    parts = []
    for k, v in (('chat_id', chat), ('caption', caption)):
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append((f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{fn}"\r\n'
                  'Content-Type: application/pdf\r\n\r\n').encode() + open(path, 'rb').read() + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendDocument', data=b''.join(parts),
                                 headers={'Content-Type': f'multipart/form-data; boundary={b}'})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        try:
            return False, json.load(e).get('description', f'HTTP {e.code}')
        except Exception:
            return False, f'HTTP {e.code}'
    except Exception as e:
        return False, type(e).__name__
    return bool(r.get('ok')), r.get('description', '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=datetime.now(KST).strftime('%Y%m%d'))
    ap.add_argument('--send', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--no-pdf', action='store_true', help='PDF 첨부 생략')
    ap.add_argument('--test', action='store_true', help='시험 게시: 머리말을 붙이고 게시 로그에 남기지 않는다')
    ap.add_argument('--legacy', action='store_true', help='종전 방식(텍스트+PDF) — 2026-10-28 사용자 지시로 기본값에서 제외')
    a = ap.parse_args()
    T = a.date
    text = build(T)
    os.makedirs(PUB, exist_ok=True)
    day = f"{T[:4]}-{T[4:6]}-{T[6:]}"
    open(os.path.join(PUB, f'공개브리핑_{day}.md'), 'w', encoding='utf-8').write(text + "\n")
    idx = os.path.join(PUB, 'index.md')
    lines = open(idx, encoding='utf-8').read().splitlines() if os.path.exists(idx) else ["# 데일리 ETF 브리핑 아카이브", ""]
    item = f"- [{day}](공개브리핑_{day}.md)"
    if item not in lines:
        lines.insert(2, item)
        open(idx, 'w', encoding='utf-8').write("\n".join(lines) + "\n")
    print(text)
    if not a.send:
        print("\n[미리보기] 게시하지 않음 — --send 로 게시"); return 0
    done = (not a.test) and os.path.exists(LOG) and any(r and r[0] == T for r in csv.reader(open(LOG, encoding='utf-8')))
    if done and not a.force:
        print(f"[생략] {T} 이미 게시됨"); return 0
    for f in ('telegram_bot_token.txt', 'telegram_chat_id.txt'):
        if not os.path.exists(os.path.join(LOOP, f)):
            print(f"[결손] {f} 없음 — 게시 생략"); return 2
    if a.test:
        text = '🧪 [시험 게시] 채널 연결 확인용입니다. 아래는 이미 지난 ' + f"{T[4:6]}/{T[6:]}" + ' 아침 자료이며, 정식 게시는 다음 거래일 아침부터 시작합니다.\n\n' + text
    # 2026-10-28 사용자 지시: "앞으로 요약 정리 그림만 올려줘" — 텍스트 메시지·PDF 를 올리지 않고 요약 카드 PNG 1장만 게시한다.
    # 텍스트(build)는 웹 아카이브(public_site.py)·md 원본용으로만 만든다. 종전 방식은 --legacy 로만 쓴다.
    if not a.legacy:
        try:
            import public_card
            card = public_card.build_card(T)
        except Exception as e:  # noqa: BLE001
            print(f"[실패] 요약 카드 생성 실패: {type(e).__name__}: {e}"); return 2
        okp, mp = send_photo(card, ('[시험] ' if a.test else ''))
        if not okp:
            print(f"[실패] 텔레그램 이미지 게시 실패: {mp}"); return 2
        print(f'[이미지] 게시 {os.path.basename(card)}')
        if a.test:
            print('[완료] 시험 게시(로그 미기록)'); return 0
        with open(LOG, 'a', encoding='utf-8', newline='') as f:
            csv.writer(f).writerow([T, datetime.now(KST).isoformat(timespec='seconds')])
        print("[완료] 텔레그램 채널 게시(요약 그림)"); return 0
    ok, msg = send(text)
    if not ok:
        print(f"[실패] 텔레그램 게시 실패: {msg}"); return 2
    pdf_note = '생략'
    if not a.no_pdf:
        pdf = build_pdf(T)
        # 2026-10-21 사용자 지시: 원본 브리핑 PDF 도 올린다 → 1쪽 공개 요약(면책 포함)을 맨 앞에 붙인 합본.
        orig = os.path.join(FABLE, f"데일리브리핑_{T[:4]}-{T[4:6]}-{T[6:]}.pdf")
        # 2026-10-23 사용자 승인: 원본에서 트랙 D(9절 보유·평가손익)를 뺀 공개판만 붙인다. 가림 실패 시 원본은 붙이지 않는다.
        pub_orig = redact_original(orig, pdf[:-4] + '_원본공개판.pdf') if (pdf and os.path.exists(orig)) else None
        if pdf and pub_orig:
            import subprocess
            full = pdf[:-4] + '_전체.pdf'
            subprocess.run(['pdfunite', pdf, pub_orig, full], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            if os.path.exists(full):
                pdf = full
        if pdf:
            cap = ('[시험] ' if a.test else '') + f"데일리 ETF 브리핑 {T[4:6]}/{T[6:]} PDF (1쪽 요약 + 원본 브리핑, 개인 운용 트랙 제외) — 참고 정보이며 투자 권유가 아닙니다."
            okd, md = send_doc(pdf, cap)
            pdf_note = '게시' if okd else f'실패({md})'
        else:
            pdf_note = '생성 실패'
    print(f'[PDF] {pdf_note}')
    if a.test:
        print('[완료] 시험 게시(로그 미기록)'); return 0
    with open(LOG, 'a', encoding='utf-8', newline='') as f:
        csv.writer(f).writerow([T, datetime.now(KST).isoformat(timespec='seconds')])
    print("[완료] 텔레그램 채널 게시"); return 0


if __name__ == '__main__':
    sys.exit(main())
