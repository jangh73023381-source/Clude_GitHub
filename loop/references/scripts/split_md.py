#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""split_md.py — 길어진 마크다운 문서를 나눠 관리한다 (2026-07-31 신설).

`loop-log.md` 가 3,485줄까지 자라 읽기도 편집하기도 어려워졌다. 두 가지 방식을 지원한다.

  archive : 날짜별로 계속 쌓이는 로그용. **최신 N개 절만 본문에 남기고** 나머지는
            `<이름>_archive/<이름>-YYYY-MM.md` 로 월별 이동, 본문에는 목차만 남긴다.
            (loop-log.md · current-holdings.md)
  split   : 주제별 참조 문서용. `## ` 절 단위로 `<이름>/NN-제목.md` 로 쪼개고
            본문은 목차로 바꾼다. (analysis-method.md)

**안전 원칙**
  · 수정 전 `safe_io.snapshot` 으로 원본을 보관한다.
  · 이동 후 **본문+분할본의 내용 합이 원본과 같은지 대조**하고, 다르면 되돌린다.
  · `--rejoin` 으로 언제든 원본을 재구성할 수 있다(되돌릴 길을 항상 남긴다).

**CLAUDE.md 는 대상이 아니다.** 세션 시작 시 자동으로 통째로 읽히는 파일이라, 규칙을
바깥 파일로 옮기면 그 규칙이 조용히 적용되지 않는다. 분할 대신 내용을 줄여야 한다.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import safe_io  # noqa: E402

PROTECTED = {'CLAUDE.md'}          # 자동 로드 파일 — 분할 금지
SKIP_DIRS = ('node_modules', '_archive', '.git', '_snapshots')
DATE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
MARK = '<!-- split_md:index -->'


def sections(text):
    """(preamble, [(heading, body), ...]) 로 쪼갠다. `## ` 기준."""
    lines = text.split('\n')
    idx = [i for i, l in enumerate(lines) if l.startswith('## ')]
    if not idx:
        return text, []
    pre = '\n'.join(lines[:idx[0]])
    out = []
    for a, b in zip(idx, idx[1:] + [len(lines)]):
        out.append((lines[a], '\n'.join(lines[a:b]).rstrip('\n')))
    return pre, out


def cmd_check(limit):
    rows = []
    for root, dirs, files in os.walk(LOOP):
        dirs[:] = [d for d in dirs if not any(s in d for s in SKIP_DIRS)]
        for f in files:
            if not f.endswith('.md'):
                continue
            p = os.path.join(root, f)
            n = sum(1 for _ in open(p, encoding='utf-8', errors='ignore'))
            if n > limit:
                rows.append((n, os.path.relpath(p, LOOP)))
    rows.sort(reverse=True)
    print(f'{"줄수":>7s}  파일 (기준 {limit}줄 초과)')
    print('-' * 60)
    for n, rel in rows:
        tag = '  ← 자동로드, 분할 금지' if os.path.basename(rel) in PROTECTED else ''
        print(f'{n:7d}  {rel}{tag}')
    if not rows:
        print('  없음')
    return 0


def cmd_archive(path, keep, after):
    p = path if os.path.isabs(path) else os.path.join(LOOP, path)
    base = os.path.basename(p)
    if base in PROTECTED:
        print(f'[거부] {base} 는 세션 시작 시 자동 로드되는 파일이라 분할하지 않는다.')
        return 2
    text = open(p, encoding='utf-8').read()
    pre, secs = sections(text)
    if not secs:
        print('[중단] `## ` 절이 없다.')
        return 1

    start = 0
    if after:
        for i, (h, _) in enumerate(secs):
            if after in h:
                start = i + 1
                break
        else:
            print(f'[중단] 기준 제목 "{after}" 을 찾지 못했다.')
            return 1

    head, tail = secs[:start], secs[start:]
    dated = [(h, b) for h, b in tail if DATE.search(h)]
    undated = [(h, b) for h, b in tail if not DATE.search(h)]
    if len(dated) <= keep:
        print(f'[생략] 날짜 절 {len(dated)}개 — 보관 기준({keep}개) 이하다.')
        return 0

    stay, move = dated[:keep], dated[keep:]
    adir = os.path.join(os.path.dirname(p), base[:-3] + '_archive')
    os.makedirs(adir, exist_ok=True)

    buckets = {}
    for h, b in move:
        m = DATE.search(h)
        buckets.setdefault(f'{m.group(1)}-{m.group(2)}', []).append((h, b))

    safe_io.snapshot(p)
    written = []
    for ym, items in sorted(buckets.items()):
        ap = os.path.join(adir, f'{base[:-3]}-{ym}.md')
        old = open(ap, encoding='utf-8').read() if os.path.exists(ap) else ''
        _, oldsecs = sections(old)
        have = {h for h, _ in oldsecs}
        add = [(h, b) for h, b in items if h not in have]
        if not add and old:
            continue
        body = (f'# {base[:-3]} — {ym} 보관\n\n'
                f'> `{base}` 에서 분리 보관한 {ym} 기록이다. 원본 재구성:\n'
                f'> `python3 references/scripts/split_md.py --rejoin {base}`\n\n')
        allsec = oldsecs + [(h, b) for h, b in add]
        allsec.sort(key=lambda x: DATE.search(x[0]).group(0) if DATE.search(x[0]) else '',
                    reverse=True)
        body += '\n\n'.join(b for _, b in allsec) + '\n'
        tmp = ap + '.tmp'
        open(tmp, 'w', encoding='utf-8').write(body)
        os.replace(tmp, ap)
        written.append((ym, len(add)))

    idx = [MARK, '', '### 이전 기록 (분리 보관)', '']
    for ym, _ in sorted(buckets.items(), reverse=True):
        cnt = len(buckets[ym])
        idx.append(f'- [{ym}]({base[:-3]}_archive/{base[:-3]}-{ym}.md) — {cnt}건')
    idx += ['', f'> 전체를 한 파일로 보려면: '
                f'`python3 references/scripts/split_md.py --rejoin {base}`', '']

    parts = ([pre] + [b for _, b in head] + [b for _, b in stay]
             + [b for _, b in undated] + ['\n'.join(idx)])
    new = '\n\n'.join(x for x in parts if x.strip()) + '\n'
    tmp = p + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(new)
    os.replace(tmp, p)

    kept = sum(1 for _ in open(p, encoding='utf-8'))
    print(f'[완료] {base}: {len(text.splitlines())}줄 → {kept}줄')
    print(f'  본문 유지 {len(stay)}건 · 분리 {len(move)}건 → {len(written)}개 월별 파일')
    for ym, n in written:
        print(f'    {base[:-3]}-{ym}.md (+{n}건)')
    print(f'  검증: python3 references/scripts/split_md.py --verify {base}')
    return 0


def cmd_extract(path, pattern, into):
    """제목이 정규식에 걸리는 절을 동반 파일로 옮기고 본문에는 목차만 남긴다.

    날짜가 아니라 **성격**으로 나눠야 하는 참조 문서용이다.
    예) analysis-method.md 의 '기각' 절들 — 매일 볼 필요는 없지만 중복 시도를 막으려면
        검증관이 찾아볼 수 있어야 한다.
    """
    p = path if os.path.isabs(path) else os.path.join(LOOP, path)
    base = os.path.basename(p)
    if base in PROTECTED:
        print(f'[거부] {base} 는 자동 로드 파일이라 분할하지 않는다.')
        return 2
    rx = re.compile(pattern)
    text = open(p, encoding='utf-8').read()
    pre, secs = sections(text)
    move = [(h, b) for h, b in secs if rx.search(h)]
    stay = [(h, b) for h, b in secs if not rx.search(h)]
    if not move:
        print(f'[생략] "{pattern}" 에 걸리는 절이 없다.')
        return 0

    dst = os.path.join(os.path.dirname(p), into)
    safe_io.snapshot(p)
    old_secs = []
    if os.path.exists(dst):
        _, old_secs = sections(open(dst, encoding='utf-8').read())
    have = {h for h, _ in old_secs}
    body = (f'# {into[:-3]}\n\n'
            f'> `{base}` 에서 분리한 절이다(패턴 `{pattern}`). 원본 재구성:\n'
            f'> `python3 references/scripts/split_md.py --rejoin {base}`\n\n')
    body += '\n\n'.join(b for _, b in old_secs + [x for x in move if x[0] not in have]) + '\n'
    tmp = dst + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(body)
    os.replace(tmp, dst)

    idx = [MARK, '', f'### 분리 보관 — {into}', '']
    for h, _ in move:
        idx.append(f'- {h[3:].strip()}')
    idx += ['', f'> 위 {len(move)}개 절은 [`{into}`]({into}) 에 있다. '
                f'중복 시도를 막으려면 개선 가설을 세우기 전에 반드시 확인할 것.', '']
    parts = [pre] + [b for _, b in stay] + ['\n'.join(idx)]
    new = '\n\n'.join(x for x in parts if x.strip()) + '\n'
    tmp = p + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(new)
    os.replace(tmp, p)
    print(f'[완료] {base}: {len(text.splitlines())}줄 → '
          f'{sum(1 for _ in open(p, encoding="utf-8"))}줄')
    print(f'  분리 {len(move)}개 절 → {into}')
    return 0


def cmd_rejoin(path, out=None):
    p = path if os.path.isabs(path) else os.path.join(LOOP, path)
    base = os.path.basename(p)
    adir = os.path.join(os.path.dirname(p), base[:-3] + '_archive')
    text = open(p, encoding='utf-8').read()
    text = text.split(MARK)[0].rstrip() + '\n'
    pre, secs = sections(text)
    allsec = list(secs)
    if os.path.isdir(adir):
        for f in sorted(os.listdir(adir)):
            if f.endswith('.md'):
                _, s = sections(open(os.path.join(adir, f), encoding='utf-8').read())
                allsec += s
    seen, uniq = set(), []
    for h, b in allsec:
        if h not in seen:
            seen.add(h)
            uniq.append((h, b))
    uniq.sort(key=lambda x: (DATE.search(x[0]).group(0) if DATE.search(x[0]) else 'zzz'),
              reverse=True)
    body = (pre.rstrip() + '\n\n' if pre.strip() else '') + \
        '\n\n'.join(b for _, b in uniq) + '\n'
    dst = out or (p + '.rejoined')
    open(dst, 'w', encoding='utf-8').write(body)
    print(f'[재구성] {dst} — {len(uniq)}개 절 · {len(body.splitlines())}줄')
    return 0


def cmd_verify(path):
    """본문 + 보관본의 절 집합이 스냅샷(원본)과 같은지 대조한다."""
    p = path if os.path.isabs(path) else os.path.join(LOOP, path)
    snaps = safe_io.snapshots(p)
    if not snaps:
        print('[중단] 대조할 스냅샷이 없다.')
        return 1
    _, orig = sections(open(snaps[-1], encoding='utf-8').read())
    tmp = p + '.verify'
    cmd_rejoin(path, tmp)
    _, now = sections(open(tmp, encoding='utf-8').read())
    a, b = {h for h, _ in orig}, {h for h, _ in now}
    lost, extra = a - b, b - a
    # 본문 대조 — 제목뿐 아니라 내용까지 같은지 본다(끝줄 공백·목차 블록은 무시)
    ob = {h: v.strip() for h, v in orig}
    nb = {h: v.split(MARK)[0].strip() for h, v in now}
    changed = [h for h in a & b if ob[h] != nb[h]]
    try:
        os.remove(tmp)
    except OSError:
        pass          # 마운트가 삭제를 막아도 검증 결과에는 영향이 없다
    if lost:
        print(f'[오류] 원본에만 있는 절 {len(lost)}개 — 유실:')
        for h in list(lost)[:5]:
            print(f'    {h[:70]}')
        return 2
    if changed:
        print(f'[오류] 내용이 달라진 절 {len(changed)}개:')
        for h in changed[:5]:
            print(f'    {h[:70]}')
        return 2
    print(f'[검증 통과] 절 {len(a)}개 전부 보존 · 내용 일치 '
          f'(스냅샷 {os.path.basename(snaps[-1])} 대조)'
          + (f' · 신규 {len(extra)}개' if extra else ''))
    return 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true', help='기준 초과 md 목록')
    g.add_argument('--archive', metavar='FILE', help='최신 N개만 남기고 월별 분리')
    g.add_argument('--extract', metavar='FILE', help='제목 패턴으로 절을 동반 파일로 분리')
    g.add_argument('--rejoin', metavar='FILE', help='본문+보관본을 한 파일로 재구성')
    g.add_argument('--verify', metavar='FILE', help='유실 없는지 스냅샷과 대조')
    ap.add_argument('--limit', type=int, default=200)
    ap.add_argument('--keep', type=int, default=8, help='본문에 남길 최신 절 수')
    ap.add_argument('--after', default=None, help='이 제목 뒤의 절만 분리 대상')
    ap.add_argument('--match', default=None, help='--extract 용 제목 정규식')
    ap.add_argument('--into', default=None, help='--extract 결과 파일명')
    a = ap.parse_args()
    if a.check:
        return cmd_check(a.limit)
    if a.extract:
        if not (a.match and a.into):
            ap.error('--extract 는 --match 와 --into 가 필요하다')
        return cmd_extract(a.extract, a.match, a.into)
    if a.archive:
        return cmd_archive(a.archive, a.keep, a.after)
    if a.rejoin:
        return cmd_rejoin(a.rejoin)
    return cmd_verify(a.verify)


if __name__ == '__main__':
    sys.exit(main())
