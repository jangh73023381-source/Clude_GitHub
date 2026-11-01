# -*- coding: utf-8 -*-
"""장중 실시간 매수·매도 타점 알림 (2026-10-20 사용자 요청) — Windows PC 에서 장중에 켜 둔다.

plans/watch_plan_<오늘>.json(아침 루틴이 생성)을 읽고 키움 REST(ka10001, 조회 전용)로 20초마다
현재가를 확인해 브리핑의 규칙선에 닿으면 PC 팝업 + (설정 시) 카카오톡 '나에게 보내기'로 알린다.
새 규칙을 만들지 않는다 — 브리핑 5절(단기 케이스 ①~④·손절·목표), 6-3절(Rule CB 밴드),
9절(트랙 D 포기선·20일 청산)을 시각에 맞춰 알려줄 뿐이다. **주문 기능은 없다.**

    py -3 realtime_watch.py            # 실제 감시(08:55~15:30, 끝나면 자동 종료)
    py -3 realtime_watch.py --test     # 알림 수단 시험(팝업·카톡 1건)
    python3 realtime_watch.py --dry --once --at 0901   # 개발용: 출력만, 1회, 시각 가정
"""
import argparse, csv, datetime, json, os, subprocess, sys, threading, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, LOOP)
POLL = 20          # 초
KAKAO_TOKEN = os.path.join(HERE, 'kakao_token.json')     # kakao_setup.py 가 만든다(내용 출력 금지)
KAKAO_KEY = os.path.join(HERE, 'kakao_rest_key.txt')


def now_kst():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


# ------------------------------------------------------------------ 알림
class Notifier:
    def __init__(self, dry=False, kakao=True):
        self.dry = dry
        self.kakao = kakao and os.path.exists(KAKAO_TOKEN) and os.path.exists(KAKAO_KEY)
        self.win = os.name == 'nt'

    def send(self, title, body):
        stamp = now_kst().strftime('%H:%M:%S')
        print(f'[{stamp}] ■ {title}\n           {body}', flush=True)
        if self.dry:
            return
        if self.win:
            self._popup(title, body)
        if self.kakao:
            try:
                self._kakao(f'[{stamp}] {title}\n{body}')
            except Exception as e:
                print(f'           (카톡 전송 실패: {e})', flush=True)

    def _popup(self, title, body):
        try:
            import winsound
            winsound.MessageBeep(0x40)
        except Exception:
            pass
        esc = lambda s: s.replace("'", "''")
        ps = ("[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null;"
              "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
              f"$x=$t.GetElementsByTagName('text');$x.Item(0).AppendChild($t.CreateTextNode('{esc(title)}'))>$null;"
              f"$x.Item(1).AppendChild($t.CreateTextNode('{esc(body)}'))>$null;"
              "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
              "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show("
              "[Windows.UI.Notifications.ToastNotification]::new($t))")
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if r.returncode == 0:
                return
        except Exception:
            pass
        # 토스트가 막혀 있으면 메시지 상자(별도 스레드 — 감시를 멈추지 않는다)
        import ctypes
        threading.Thread(target=lambda: ctypes.windll.user32.MessageBoxW(0, body, title, 0x40 | 0x40000),
                         daemon=True).start()

    def _kakao(self, text):
        tok = json.load(open(KAKAO_TOKEN, encoding='utf-8'))
        if time.time() > tok.get('expires_at', 0) - 600:
            tok = kakao_refresh(tok)
        body = urllib.parse.urlencode({'template_object': json.dumps(
            {'object_type': 'text', 'text': text[:900], 'link': {'web_url': 'https://finance.naver.com', 'mobile_web_url': 'https://m.stock.naver.com'}},
            ensure_ascii=False)}).encode()
        req = urllib.request.Request('https://kapi.kakao.com/v2/api/talk/memo/default/send', data=body,
                                     headers={'Authorization': f"Bearer {tok['access_token']}"})
        urllib.request.urlopen(req, timeout=10).read()


def kakao_refresh(tok):
    key = open(KAKAO_KEY, encoding='utf-8').read().strip()
    body = urllib.parse.urlencode({'grant_type': 'refresh_token', 'client_id': key,
                                   'refresh_token': tok['refresh_token']}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request('https://kauth.kakao.com/oauth/token', data=body), timeout=10))
    tok['access_token'] = r['access_token']
    tok['expires_at'] = time.time() + int(r.get('expires_in', 21599))
    if r.get('refresh_token'):
        tok['refresh_token'] = r['refresh_token']
    json.dump(tok, open(KAKAO_TOKEN, 'w', encoding='utf-8'))
    return tok


# ------------------------------------------------------------------ 시세
def ibs_prev_pos():
    """ibs_shadow.csv 마지막 기록의 상태(어제 종가 이후). 없으면 0(현금)."""
    pth = os.path.join(os.path.dirname(HERE), 'references', 'ibs_shadow.csv')
    try:
        rows = list(csv.DictReader(open(pth, encoding='utf-8')))
        return int(rows[-1]['pos']) if rows else 0
    except Exception:
        return 0


def quote(code):
    import kiwoom_api as k
    d = k.get_basic_info(code)
    f = lambda key: abs(float(str(d.get(key, '0')).replace(',', '') or 0))
    flu = float(str(d.get('flu_rt', '0')).replace(',', '') or 0)
    return {'cur': f('cur_prc'), 'open': f('open_pric'), 'high': f('high_pric'), 'low': f('low_pric'),
            'base': f('base_pric'), 'flu': flu}


# ------------------------------------------------------------------ 규칙
class Watch:
    def __init__(self, plan, nt, logpath):
        self.p, self.nt, self.logpath = plan, nt, logpath
        self.sent = set(json.load(open(logpath, encoding='utf-8'))) if os.path.exists(logpath) else set()
        self.filled = {}

    def once(self, key, title, body):
        if key in self.sent:
            return
        self.sent.add(key)
        if not self.nt.dry:  # 2026-10-21: 시험(--dry) 실행은 발송 기록을 남기지 않는다
            json.dump(sorted(self.sent), open(self.logpath, 'w', encoding='utf-8'), ensure_ascii=False)
        self.nt.send(title, body)

    def tick(self, hm, q):
        P, cons = self.p, self.p['mode'] == '보수'
        won = lambda v: f'{v:,.0f}원'
        # ---------------- 단기 5종
        if hm >= 901:
            for s in P['short']:
                x = q.get(s['code'])
                if not x or not x['open']:
                    continue
                c, nm = s['code'], f"{s['name']}({s['code']})"
                o = x['open']
                if o <= s['upper'] and o >= s['gapdown']:
                    self.filled[c] = True
                    self.once(f'S1-{c}', f'단기 매수 ① 정상 출발 — {nm}',
                              f"시가 {won(o)} ≤ 매수상단 {won(s['upper'])} → 지금 매수(종목당 금액 {'평소의 2/3' if cons else '평소'}). 손절 {won(s['stop'])} · 목표 {won(s['target'])}")
                elif o < s['gapdown']:
                    self.filled[c] = True
                    self.once(f'S4-{c}', f'단기 ④ 갭하락 — {nm}',
                              f"시가 {won(o)} < 갭하락 기준 {won(s['gapdown'])} → 절반만 시가 매수, 나머지는 분할. 손절 {won(s['stop'])} 그대로")
                else:
                    self.once(f'S2-{c}', f'단기 ② 갭상승 — {nm} 대기',
                              f"시가 {won(o)} > 매수상단 {won(s['upper'])} → 바로 사지 말고 되눌림 대기. 매수상단 터치 시 다시 알림")
                    if x['cur'] <= s['upper'] and not self.filled.get(c):
                        self.filled[c] = True
                        self.once(f'S2F-{c}', f'단기 매수 ② 되눌림 도달 — {nm}',
                                  f"현재가 {won(x['cur'])} ≤ 매수상단 {won(s['upper'])} → 매수상단 이하 지정가로 매수")
                if hm >= 1430 and f'S2-{c}' in self.sent and f'S2F-{c}' not in self.sent and not self.filled.get(c):
                    if cons:
                        self.once(f'S3-{c}', f'단기 ③ 미체결 — {nm} 오늘 매수 포기',
                                  '보수 모드라 케이스 ③(종가 무렵 시장가)을 적용하지 않습니다. 현금으로 둡니다.')
                    elif hm >= 1510:
                        self.once(f'S3-{c}', f'단기 매수 ③ 종가 무렵 시장가 — {nm}',
                                  f"14:30까지 미체결 → 포기하지 말고 종가 무렵 시장가로 담습니다(현재가 {won(x['cur'])}).")
                if x['cur'] <= s['stop']:
                    self.once(f'SL-{c}', f'단기 손절선 도달 — {nm}',
                              f"현재가 {won(x['cur'])} ≤ 손절 {won(s['stop'])}({s['stop_basis']}) — 보유 중이면 손절 검토")
                if x['cur'] >= s['target']:
                    self.once(f'TG-{c}', f'단기 목표가 도달 — {nm}',
                              f"현재가 {won(x['cur'])} ≥ 목표 {won(s['target'])}(+3%) — 보유 중이면 이익 실현 검토")
        if hm >= 1510 and P['short_sells']:
            self.once('SS', '단기 종가 청산 — 오늘 추천에서 빠진 종목',
                      ' · '.join(f"{s['name']}({s['code']})" for s in P['short_sells']) +
                      ' → 보유 중이면 오늘 종가(15:20~15:30 단일가)에 매도. 오늘 5종에 남은 종목은 팔지 않습니다.')
        # ---------------- 중기 5종 (Rule CB 밴드) — 15:05 예비, 15:17 확정
        for tag, t0 in (('pre', 1505), ('fin', 1517)):
            if hm >= t0 and P['mid']:
                lo, hi = P['mid_band']
                rows = [(m, q.get(m['code'])) for m in P['mid'] if q.get(m['code'])]
                ok = [(m, x) for m, x in rows if lo <= x['flu'] < hi]
                stage = 1
                if not ok:
                    lo2, hi2 = P['mid_band2']
                    ok = [(m, x) for m, x in rows if lo2 <= x['flu'] < hi2]
                    stage = 2
                txt = ' · '.join(f"{m['name']} {x['flu']:+.2f}%" for m, x in rows)
                if ok:
                    msg = (f"{stage}단계 밴드 통과 {len(ok)}종 → 종가 단일가(15:20~15:30) 매수: " +
                           ', '.join(f"{m['name']}({m['code']})" for m, _ in ok) + f" | 전체: {txt}")
                else:
                    msg = f"밴드 통과 0종 → 오늘은 현금 관망(차순위 편입 금지) | 전체: {txt}"
                self.once(f'MID-{tag}', ('중기 종가 매수 판정 [확정]' if tag == 'fin' else '중기 종가 매수 판정 [예비 — 15:17에 확정]'), msg)
        if hm >= 1505:
            if P['mid_sells']:
                self.once('MIDSELL', '중기 종가 청산 — 추천에서 빠진 종목',
                          ' · '.join(f"{m['name']}({m['code']})" for m in P['mid_sells']) + ' → 보유 중이면 오늘 종가에 매도')
            if P['mode'] == '보수':
                self.once('MIDGATE', '중기 — 게이트 발동 국면 청산 규정',
                          '게이트 발동일에는 어제 종가에 산 중기 종목을 오늘 종가에 청산합니다(14번 규칙).')
        # ---------------- 트랙 D
        D = P.get('trackD') or {}
        if hm >= 1510:
            for s in D.get('sells', []):
                self.once(f'DS-{s["code"]}', f'트랙 D 20거래일 청산 — {s["name"]}({s["code"]})',
                          '오늘 종가(15:20~15:30)에 매도. 손절·연장 없음(v1.1).')
            buys = D.get('buys', [])[:D.get('n_buy', 0)]
            for b in buys:
                x = q.get(b['code'])
                if not x:
                    continue
                give = (b['give_up_above'] and x['cur'] >= b['give_up_above']) or (b['ma20'] and x['cur'] < b['ma20'])
                half = ' · 약세 국면 — 비중 평소의 1/2' if D.get('regime_half') else ''
                self.once(f'DB-{b["code"]}', f'트랙 D 매수 {"포기" if give else "— 종가 단일가"} — {b["name"]}({b["code"]})',
                          f"현재가 {won(x['cur'])} ({x['flu']:+.2f}%) · 포기선 {won(b['give_up_above'] or 0)} / MA20 {won(b['ma20'] or 0)}"
                          + (' → 조건 위반, 매수하지 않음' if give else ' → 15:20~15:30 종가 매수' + half))
            if not buys and D.get('buys'):
                self.once('DB-none', '트랙 D — 신호는 있으나 매수 0건',
                          f"신호 {len(D['buys'])}건 · 슬롯 여유 없음 → 오늘 매수하지 않습니다.")

        # ---------------- Rule IBS shadow 참고 (2026-10-21 등록) — KODEX200 IBS<0.2 진입 · >0.8 청산, 상태가 바뀔 때만
        if hm >= 1517:
            x = q.get('069500')
            if x and x['high'] > x['low']:
                ibs = (x['cur'] - x['low']) / (x['high'] - x['low'])
                prev = ibs_prev_pos()
                if prev == 0 and ibs < 0.2:
                    self.once('IBS', 'IBS 진입 신호 [shadow·참고] — KODEX200',
                              f"15:17 IBS {ibs:.2f} < 0.2 → 규칙상 오늘 종가 진입(현금→보유). 기록·관찰 단계라 실매수 규칙이 아닙니다.")
                elif prev == 1 and ibs > 0.8:
                    self.once('IBS', 'IBS 청산 신호 [shadow·참고] — KODEX200',
                              f"15:17 IBS {ibs:.2f} > 0.8 → 규칙상 오늘 종가 청산(보유→현금). 기록·관찰 단계라 실매수 규칙이 아닙니다.")

    def codes(self, hm):
        P = self.p
        cs = [s['code'] for s in P['short']]
        if hm >= 1517:
            cs.append('069500')
        if hm >= 1500:
            cs += [m['code'] for m in P['mid']]
            D = P.get('trackD') or {}
            cs += [b['code'] for b in D.get('buys', [])[:D.get('n_buy', 0)]]
        return list(dict.fromkeys(cs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date')
    ap.add_argument('--dry', action='store_true', help='팝업·카톡 없이 출력만')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--at', help='HHMM 시각 가정(개발·시험용)')
    ap.add_argument('--test', action='store_true', help='알림 수단 시험')
    ap.add_argument('--no-kakao', action='store_true')
    a = ap.parse_args()
    nt = Notifier(dry=a.dry, kakao=not a.no_kakao)
    if a.test:
        nt.send('장중 알림 시험', '이 알림이 보이면 정상입니다. (카톡 ' + ('사용' if nt.kakao else '미설정') + ')')
        return
    T = a.date or now_kst().strftime('%Y%m%d')
    pp = os.path.join(HERE, 'plans', f'watch_plan_{T}.json')
    if not os.path.exists(pp):
        nt.send('장중 알림 — 오늘 계획 없음', f'{os.path.basename(pp)} 이 없습니다. 아침 루틴이 아직 안 돌았거나 휴장일입니다.')
        return
    plan = json.load(open(pp, encoding='utf-8'))
    w = Watch(plan, nt, os.path.join(HERE, 'plans', f'sent_{T}.json'))
    print(f"[장중 알림] {T} · 모드 {plan['mode']} · 단기 {len(plan['short'])} · 중기 {len(plan['mid'])} · 카톡 {'사용' if nt.kakao else '미설정'}", flush=True)
    if not a.once and not a.at:
        nt.send(f"장중 알림 시작 ({plan['mode']} 모드)",
                '단기: ' + ', '.join(f"{s['name']} 상단 {s['upper']:,}" for s in plan['short']))
    while True:
        hm = int(a.at) if a.at else int(now_kst().strftime('%H%M'))
        if hm >= 1531:
            print('[장중 알림] 장 마감 — 종료', flush=True)
            break
        if hm >= 900:
            q = {}
            for c in w.codes(hm):
                try:
                    q[c] = quote(c)
                except Exception as e:
                    print(f'  조회 실패 {c}: {e}', flush=True)
                time.sleep(0.3)
            w.tick(hm, q)
        if a.once:
            break
        time.sleep(POLL)


if __name__ == '__main__':
    main()
