#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""아침 루틴 산출물 2종 메일 발송기 (2026-07-30 신설, 사용자 지시).

루프 보고서(.docx)와 데일리 브리핑(.pdf)을 네이버 SMTP로 첨부 발송한다.
아침 루틴의 마지막 단계에서 자동 실행된다.

  python3 references/scripts/send_daily_mail.py              # 오늘자 발송
  python3 references/scripts/send_daily_mail.py --dry-run    # 파일·설정만 확인(발송 안 함)
  python3 references/scripts/send_daily_mail.py --date 2026-07-30
  python3 references/scripts/send_daily_mail.py --force      # 이미 보낸 날도 재발송

자격증명 (사용자가 직접 저장 — 에이전트는 내용을 읽지 않는다):
  loop/naver_smtp_id.txt   네이버 아이디 (예: jangh5171). @naver.com 없이 아이디만.
  loop/naver_smtp_pw.txt   네이버 '앱 비밀번호' (로그인 비밀번호 아님)
    발급: 네이버 > 내정보 > 보안설정 > 2단계 인증 > 애플리케이션 비밀번호 관리
    사전 설정: 네이버 메일 > 환경설정 > POP3/IMAP 설정 > SMTP 사용함

  ※ 이 스크립트는 두 파일의 내용을 화면·로그·보고서 어디에도 출력하지 않는다.
  ※ 발송 전용이며 메일 읽기·삭제 기능은 없다.
"""
import argparse
import mimetypes
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.abspath(os.path.join(HERE, '..'))
LOOP = os.path.abspath(os.path.join(REF, '..'))
FABLE = os.path.join(os.path.dirname(LOOP), 'fable')
KST = timezone(timedelta(hours=9))

SMTP_HOST, SMTP_PORT = 'smtp.naver.com', 587
TO = ['jangh5171@naver.com']
SENT_LOG = os.path.join(REF, 'mail_sent_log.csv')


def creds():
    """자격증명을 읽어 반환한다. 값은 절대 출력하지 않는다."""
    idp = os.path.join(LOOP, 'naver_smtp_id.txt')
    pwp = os.path.join(LOOP, 'naver_smtp_pw.txt')
    missing = [os.path.basename(p) for p in (idp, pwp) if not os.path.exists(p)]
    if missing:
        print(f'[중단] 자격증명 파일 없음: {", ".join(missing)}')
        print(f'       {LOOP} 에 저장하세요. 앱 비밀번호는 네이버 2단계 인증 메뉴에서 발급합니다.')
        return None, None
    uid = open(idp, encoding='utf-8').read().strip()
    pw = open(pwp, encoding='utf-8').read().strip()
    if not uid or not pw:
        print('[중단] 자격증명 파일이 비어 있습니다.')
        return None, None
    return uid, pw


def already_sent(date):
    if not os.path.exists(SENT_LOG):
        return False
    return any(line.startswith(date + ',') for line in open(SENT_LOG, encoding='utf-8'))


def mark_sent(date, n_att):
    new = not os.path.exists(SENT_LOG)
    with open(SENT_LOG, 'a', encoding='utf-8') as f:
        if new:
            f.write('date,sent_at,attachments\n')
        f.write(f'{date},{datetime.now(KST).isoformat()},{n_att}\n')


def find_files(date):
    """오늘자 산출물 2종을 찾는다. 파일명 규칙은 아침 루틴 스킬과 동일하다."""
    out = []
    loop_doc = os.path.join(LOOP, f'루프엔지니어링_{date}.docx')
    if not os.path.exists(loop_doc):                     # 회차 접미사(_opus 등) 폴백
        cand = sorted(f for f in os.listdir(LOOP)
                      if f.startswith(f'루프엔지니어링_{date}') and f.endswith('.docx'))
        loop_doc = os.path.join(LOOP, cand[-1]) if cand else None
    if loop_doc and os.path.exists(loop_doc):
        out.append(loop_doc)

    brief = os.path.join(FABLE, f'데일리브리핑_{date}.pdf')
    if os.path.exists(brief):
        out.append(brief)
    return out


def build(uid, date, files):
    m = EmailMessage()
    m['From'] = f'{uid}@naver.com'
    m['To'] = ', '.join(TO)
    m['Subject'] = f'[아침 루틴] 루프 엔지니어링 · 데일리 브리핑 — {date}'
    names = '\n'.join(f'  - {os.path.basename(p)} ({os.path.getsize(p)/1024:,.0f} KB)'
                      for p in files)
    m.set_content(
        f'{date} 아침 루틴 산출물입니다.\n\n'
        f'첨부 {len(files)}건:\n{names}\n\n'
        '- 루프 엔지니어링(.docx): 전일 추천 채점, 개선 루프, 검증관 판정, 확정 방법 상태\n'
        '- 데일리 브리핑(.pdf): 전일 시장 요약, 게이트 판정, ETF·단일종목 추천, 진입 전략\n\n'
        '본 자료는 정보 제공 목적이며 투자 자문이 아닙니다. '
        '모든 투자 판단과 책임은 투자자 본인에게 있습니다.\n')
    for p in files:
        ctype, _ = mimetypes.guess_type(p)
        maintype, _, subtype = (ctype or 'application/octet-stream').partition('/')
        with open(p, 'rb') as f:
            m.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                             filename=os.path.basename(p))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=datetime.now(KST).strftime('%Y-%m-%d'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()

    # 2026-10-21 사용자 지시: 네이버 메일 발송 중단(공개 채널 게시로 대체).
    # references/mail_disabled.txt 가 있으면 발송하지 않고 rc=0 으로 끝낸다. 재개하려면 그 파일을 지운다.
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mail_disabled.txt')) and not a.force:
        print('[메일] 발송 중단 상태(references/mail_disabled.txt) — 사용자 지시 2026-10-21. 생략')
        return 0

    files = find_files(a.date)
    print(f'[메일] {a.date} · 수신 {", ".join(TO)} · 첨부 {len(files)}건')
    for p in files:
        print(f'  - {os.path.basename(p)} ({os.path.getsize(p)/1024:,.0f} KB)')
    if len(files) < 2:
        print('[중단] 산출물 2종이 모두 준비되지 않았습니다 — 발송하지 않습니다.')
        return 1
    if already_sent(a.date) and not a.force:
        print('[생략] 이미 발송된 날짜입니다(멱등). 재발송하려면 --force.')
        return 0

    uid, pw = creds()
    if not uid:
        return 2
    msg = build(uid, a.date, files)
    total = sum(os.path.getsize(p) for p in files) / 1024 / 1024
    if total > 20:
        print(f'[중단] 첨부 합계 {total:.1f}MB — 네이버 첨부 한도에 근접합니다.')
        return 1
    if a.dry_run:
        print('[dry-run] 설정·파일 정상. 실제 발송은 하지 않았습니다.')
        return 0

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(uid, pw)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        print('[실패] SMTP 인증 거부 — 앱 비밀번호가 맞는지, 네이버 메일에서 SMTP 사용이 '
              '켜져 있는지 확인하세요.')
        return 2
    except Exception as e:
        print(f'[실패] {type(e).__name__}: {str(e)[:200]}')
        return 1

    mark_sent(a.date, len(files))
    print(f'[완료] 발송 성공 — 첨부 {len(files)}건, 합계 {total*1024:,.0f} KB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
