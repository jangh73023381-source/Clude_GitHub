# -*- coding: utf-8 -*-
"""카카오톡 '나에게 보내기' 1회 설정 — 장중 알림(realtime_watch.py)이 카톡으로 오도록 한다.

준비(한 번만):
 1) https://developers.kakao.com → 내 애플리케이션 → 애플리케이션 추가(이름 아무거나)
 2) [앱 키]의 'REST API 키'를 복사해 이 폴더의 kakao_rest_key.txt 에 한 줄로 저장
 3) [카카오 로그인] 활성화 ON · Redirect URI 에  https://localhost  등록
 4) [카카오 로그인 > 동의항목] '카카오톡 메시지 전송(talk_message)' 을 '선택 동의'로 설정
 5) (보안 > Client Secret 을 켰다면 끄거나, 값을 kakao_client_secret.txt 에 저장)
그다음 이 폴더에서:  py -3 kakao_setup.py
브라우저가 열리면 로그인·동의 → 주소창이 https://localhost/?code=... 로 바뀌며 '연결할 수 없음'이 뜨는데 정상이다.
그 주소 전체를 복사해 이 창에 붙여넣는다. 이후 토큰은 자동 갱신된다(약 2개월마다 이 설정을 다시 하라는 카톡이 오면 재실행).
토큰 파일(kakao_token.json)은 비밀번호와 같다 — 남에게 보내지 말 것.
"""
import json, os, time, urllib.parse, urllib.request, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.path.join(HERE, 'kakao_rest_key.txt')
SEC = os.path.join(HERE, 'kakao_client_secret.txt')
TOK = os.path.join(HERE, 'kakao_token.json')
REDIRECT = 'https://localhost'


def main():
    if not os.path.exists(KEY):
        print('kakao_rest_key.txt 가 없습니다. 파일 맨 위 설명의 1)~2)를 먼저 하십시오.'); input('엔터로 종료'); return
    key = open(KEY, encoding='utf-8').read().strip()
    url = ('https://kauth.kakao.com/oauth/authorize?' + urllib.parse.urlencode(
        {'client_id': key, 'redirect_uri': REDIRECT, 'response_type': 'code', 'scope': 'talk_message'}))
    print('브라우저에서 카카오 로그인·동의를 진행하십시오. 안 열리면 아래 주소를 직접 여십시오:\n' + url + '\n')
    webbrowser.open(url)
    back = input('이동된 주소(https://localhost/?code=...) 전체를 붙여넣고 엔터: ').strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(back).query).get('code', [back])[0]
    data = {'grant_type': 'authorization_code', 'client_id': key, 'redirect_uri': REDIRECT, 'code': code}
    if os.path.exists(SEC):
        data['client_secret'] = open(SEC, encoding='utf-8').read().strip()
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(
            'https://kauth.kakao.com/oauth/token', data=urllib.parse.urlencode(data).encode()), timeout=15))
    except urllib.error.HTTPError as e:
        print('토큰 발급 실패:', e.read().decode('utf-8', 'ignore')[:300]); input('엔터로 종료'); return
    json.dump({'access_token': r['access_token'], 'refresh_token': r['refresh_token'],
               'expires_at': time.time() + int(r.get('expires_in', 21599))}, open(TOK, 'w', encoding='utf-8'))
    print('토큰 저장 완료. 시험 메시지를 보냅니다...')
    import realtime_watch as rw
    rw.Notifier(kakao=True).send('장중 알림 카톡 연결 완료', '앞으로 장중 매수·매도 타점이 이 대화방(나와의 채팅)으로 옵니다.')
    input('카톡 "나와의 채팅"에 메시지가 왔는지 확인하고 엔터로 종료')


if __name__ == '__main__':
    main()
