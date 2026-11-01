#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[8-2] 수출입 '속보(잠정)' — 산업통상부 매월 1일 「YYYY년 M월 수출입 동향」 보도자료 파싱 (2026-10-03 신설).

왜 필요한가: trade_ref.py 가 쓰는 관세청 품목별 API 는 매월 15일경에야 전월 확정치를 올린다.
그런데 산업통상부는 매월 1일 전월 잠정치를 발표하고 언론이 같은 날 다 보도한다.
그 사이 약 2주 동안 브리핑 표가 '두 달 전' 숫자로 남아 업데이트 누락처럼 보였다(2026-10-03 사용자 지적).
→ 잠정치가 확정월보다 새로우면 [8-2] 표 위에 '속보(잠정)'로 붙이고, 관세청 확정치가 들어오면 자동으로 빠진다.

성격: 참고 전용 — 선정 반영 금지(fable CLAUDE.md 18-(f)). 실패해도 확정표는 그대로 나온다.
사용: python3 trade_flash.py [--force]   # 확인용 출력
"""
import os, re, sys, json, html, datetime, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '_trade_flash_cache.json')
SITE = 'https://www.motir.go.kr'
BOARD = '/kor/article/ATCL3f49a5a8c'
UA = {'User-Agent': 'Mozilla/5.0'}

# 표에 실을 품목(보도자료 20대 품목 명칭 그대로) — 확정표 10품목과 대응되는 것 + 컴퓨터. 본문 서술에서 못 찾은 품목은 표에서 빠진다
SHOW = ['반도체', '컴퓨터', '자동차', '이차전지', '선박', '철강', '석유제품',
        '바이오헬스', '화장품', '일반기계']


def _get(path, timeout=25):
    req = urllib.request.Request(SITE + path, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'ignore')


def _text(t):
    t = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', t, flags=re.S)
    s = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    return re.sub(r'\s+', ' ', s)


def _num(x):
    x = x.replace(',', '').replace(' ', '')
    neg = '△' in x or x.startswith('-')
    v = float(x.replace('△', '').replace('+', '').replace('-', ''))
    return -v if neg else v


def find_latest():
    """검색 목록에서 최신 「YYYY년 M월 (및 …) 수출입 동향」(ICT 제외) → (ym, 글번호, 제목)."""
    q = urllib.parse.quote('수출입 동향')
    t = _get(f'{BOARD}?searchCondition=1&searchKeyword={q}')
    best = None
    for m in re.finditer(r'href="[^"]*ATCL3f49a5a8c/(\d+)/view[^"]*"[^>]*>(.*?)</a>', t, re.S):
        title = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()
        if '정보통신' in title or 'ICT' in title or '수출입' not in title or '동향' not in title:
            continue
        ym = re.search(r'(\d{4})년\D{0,12}?(\d{1,2})월', title)
        if not ym:
            continue
        key = f"{ym.group(1)}{int(ym.group(2)):02d}"
        if best is None or key > best[0]:
            best = (key, m.group(1), title)
    if not best:
        raise RuntimeError('목록에서 수출입 동향 글을 찾지 못함')
    return best


def _pdf_text(page_html):
    """본문이 '보도자료입니다.' 한 줄뿐인 달(2026-07 이전 형식) — 첨부 .pdf 앞 3쪽을 읽는다."""
    import subprocess, tempfile
    for m in re.finditer(r'href="(/attach/down[^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        if '.pdf' not in re.sub(r'<[^>]+>', '', m.group(2)).lower():
            continue
        req = urllib.request.Request(SITE + m.group(1), headers=UA)
        b = urllib.request.urlopen(req, timeout=60).read()
        fd, path = tempfile.mkstemp(suffix='.pdf')
        os.write(fd, b); os.close(fd)
        try:
            t = subprocess.run(['pdftotext', '-l', '3', path, '-'], capture_output=True,
                               text=True, timeout=60).stdout
        except Exception:
            from pypdf import PdfReader
            t = ' '.join((pg.extract_text() or '') for pg in PdfReader(path).pages[:3])
        finally:
            os.remove(path)
        return re.sub(r'\s+', ' ', t)
    return ''


def parse(ym, no):
    page = _get(f'{BOARD}/{no}/view')
    m = int(ym[4:])
    V = r'([\d,\.]+)\s*억\s*달러\s*\(\s*([+\-△]?\s*[\d\.]+)\s*%\s*\)'
    HEAD = rf'{m}\s*월\s*수출\s*{V}\s*,\s*수입\s*{V}\s*,\s*수지\s*([\d,\.]+)\s*억\s*달러\s*(흑자|적자)'
    src = 'html'
    s = _text(page)
    h = re.search(HEAD, s)
    if not h:
        src = 'pdf'
        s = _pdf_text(page)
        h = re.search(HEAD, s)
    if not h:
        raise RuntimeError('헤드라인(수출·수입·수지) 파싱 실패(본문·PDF 모두)')
    bal = _num(h.group(5)) * (1 if h.group(6) == '흑자' else -1)
    out = {'data_month': ym, 'article': no, 'src': src,
           'url': f'{SITE}{BOARD}/{no}/view',
           '총수출': _num(h.group(1)), '총수출YoY': _num(h.group(2)),
           '총수입': _num(h.group(3)), '총수입YoY': _num(h.group(4)), '무역수지': bal,
           'items': {}}
    # 품목별: 본문 서술 "반도체 수출(603.0억 달러, +262.8%)" — 표보다 형식이 안정적이고 소수 1자리
    body = s[h.end():]
    for k in SHOW:
        mm = re.search(rf'{k}\s*(?:수출액?)?\s*\(\s*([\d,\.]+)\s*억\s*달러\s*,\s*([+\-△]?\s*[\d\.]+)\s*%?\s*\)', body)
        if mm:
            out['items'][k] = [_num(mm.group(1)), _num(mm.group(2))]
    # 보조: 본문 서술에 없는 품목은 웹 본문의 【20대 주요품목별 수출액】 표(이름 7개→값 7개 반복)에서 채운다(정수 반올림값)
    i = s.find('주요품목별 수출액') if src == 'html' else -1
    if i > 0 and len(out['items']) < len(SHOW):
        seg = s[s.find('】', i) + 1: i + 1500].replace('총 수출액', '총수출액')
        names, tab = [], {}
        for tok in re.finditer(r'([\d,\.]+)\s*\(\s*([+\-△]?\s*[\d\.]+)\s*\)|([^\s\d()]+)', seg):
            if tok.group(3):
                if tok.group(3).startswith('('):
                    break
                names.append(tok.group(3))
            elif names:
                tab[names.pop(0)] = [_num(tok.group(1)), _num(tok.group(2))]
            else:
                break
        for k in SHOW:
            if k not in out['items'] and k in tab:
                out['items'][k] = tab[k]
    # 헤드라인만 확실하면 싣는다. 빠진 품목은 표에서 행이 없을 뿐 — 확정표가 15일경 전부 채운다
    out['partial'] = [k for k in SHOW if k not in out['items']]
    return out


def _load():
    try:
        return json.load(open(CACHE, encoding='utf-8'))
    except Exception:
        return None


def build(force=False):
    """최신 잠정치. 캐시가 이미 전월이면 네트워크 호출 없음. 실패 시 캐시+stale."""
    today = datetime.date.today()
    y, mo = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    want = f"{y}{mo:02d}"
    cache = _load()
    if cache and not force and cache.get('data_month', '') >= want:
        cache['stale'] = False
        return cache
    try:
        ym, no, title = find_latest()
        if cache and not force and cache.get('data_month') == ym:
            cache['stale'] = False          # 아직 새 달 보도자료 없음(1일 이전 등)
            return cache
        out = parse(ym, no)
        out['title'] = title
        out['fetched_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        out['stale'] = False
        json.dump(out, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
        return out
    except Exception as e:
        if cache:
            cache['stale'] = True
            cache['error'] = str(e)
            return cache
        return {'error': str(e), 'stale': True}


def rows(f):
    it = f.get('items', {})
    return [{'품목': k, '수출': it[k][0] / 10, 'YoY': it[k][1]} for k in SHOW if k in it]


def summary(f):
    ym = f['data_month']
    r = sorted(rows(f), key=lambda x: -x['YoY'])
    top = ', '.join(f"{x['품목']} {x['YoY']:+.0f}%" for x in r[:3])
    bot = ', '.join(f"{x['품목']} {x['YoY']:+.0f}%" for x in r[-2:])
    return (f"{ym[:4]}년 {int(ym[4:])}월 수출(잠정) {f['총수출']:,.1f}억$ {f['총수출YoY']:+.1f}% · "
            f"무역수지 {f['무역수지']:+,.1f}억$ — 증가 상위 {top} / 부진 {bot}")


if __name__ == '__main__':
    f = build(force='--force' in sys.argv)
    if f.get('error') and 'items' not in f:
        print('실패:', f['error']); sys.exit(1)
    print(json.dumps({k: v for k, v in f.items() if k != 'items'}, ensure_ascii=False))
    for r in rows(f):
        print(f"  {r['품목']:<8}{r['수출']:>8.1f} 십억$ {r['YoY']:+.0f}%")
    print(summary(f))
