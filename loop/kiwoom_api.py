#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
키움증권(Kiwoom) REST Open API 클라이언트 - 실전투자 계좌용
앞으로 주식 관련 조회(현재가/기본정보, 일봉차트 등)는 이 모듈을 통해 키움 REST API를 사용한다.

키 파일 위치: C:\\agent\\Claude\\loop\\46238499_appkey.txt / 46238499_secretkey.txt
토큰은 발급 후 캐시 파일(.kiwoom_token.json)에 저장해 재사용한다.

엔드포인트 정리 (키움 REST API, base: https://api.kiwoom.com):
  - 토큰 발급: POST /oauth2/token   body: {grant_type, appkey, secretkey} -> resp.token
  - 주식기본정보(ka10001): POST /api/dostk/stkinfo   body: {stk_cd}
  - 주식일봉차트(ka10081): POST /api/dostk/chart      body: {stk_cd, base_dt, upd_stkpc_tp}
  헤더(조회류 공통): content-type, authorization: Bearer <token>, api-id, cont-yn, next-key

사용 예:
    python kiwoom_api.py info 005930
    python kiwoom_api.py daily 005930 20260629
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

LOOP_DIR = os.path.dirname(os.path.abspath(__file__))  # 세션마다 마운트 경로가 바뀌므로 스크립트 위치 기준으로 자동 결정
ACCOUNT_PREFIX = "46238499"
APPKEY_FILE = os.path.join(LOOP_DIR, f"{ACCOUNT_PREFIX}_appkey.txt")
SECRETKEY_FILE = os.path.join(LOOP_DIR, f"{ACCOUNT_PREFIX}_secretkey.txt")
TOKEN_CACHE = os.path.join(LOOP_DIR, ".kiwoom_token.json")

BASE_URL = "https://api.kiwoom.com"  # 실전투자. 모의투자는 https://mockapi.kiwoom.com


def _read_keys():
    with open(APPKEY_FILE, encoding="utf-8") as f:
        appkey = f.read().strip()
    with open(SECRETKEY_FILE, encoding="utf-8") as f:
        secretkey = f.read().strip()
    return appkey, secretkey


def _post(path, headers, body):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8')}")


def get_access_token(force=False):
    """캐시된 토큰이 유효하면 재사용, 아니면 새로 발급."""
    if not force and os.path.exists(TOKEN_CACHE):
        try:
            with open(TOKEN_CACHE, encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("expires_at", 0) > time.time() + 60:
                return cached["token"]
        except Exception:
            pass

    appkey, secretkey = _read_keys()
    body = {"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey}
    headers = {"content-type": "application/json;charset=UTF-8"}
    res = _post("/oauth2/token", headers, body)
    token = res.get("token")
    if not token:
        raise RuntimeError(f"토큰 발급 실패: {res}")

    expires_at = time.time() + 86400
    if res.get("expires_dt"):
        try:
            from datetime import datetime, timezone, timedelta
            # expires_dt 는 KST 문자열이다. naive strptime().timestamp() 는 VM 로컬(UTC)로
            # 해석해 만료를 9시간 늦게 잡고, 그 사이 발급 요청이 없어 8005(Token 무효)로
            # 아침 루틴 패널 연장이 실패한다(2026-09-04 실측). KST 로 명시 파싱한다.
            expires_at = datetime.strptime(res["expires_dt"], "%Y%m%d%H%M%S").replace(
                tzinfo=timezone(timedelta(hours=9))).timestamp()
        except Exception:
            pass
    elif res.get("expires_in"):
        expires_at = time.time() + int(res["expires_in"])

    with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
        json.dump({"token": token, "expires_at": expires_at}, f)
    return token


def _call(resource_url, api_id, body, cont_yn="N", next_key=""):
    # 2026-09-04: 캐시 토큰의 expires_at 이 남아 있어도 서버가 8005(Token 무효)를 내는 사례 실측
    # (09-03 발급분이 09-04 07:43 에 무효 — 아침 루틴 패널 연장이 통째로 실패했다).
    # 8005 를 만나면 강제 재발급 후 1회만 재시도한다.
    for attempt in (0, 1):
        token = get_access_token(force=(attempt == 1))
        headers = {
            "content-type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        res = _post(resource_url, headers, body)
        if str(res.get("return_code", 0)) in ("0", "0.0"):
            return res
        if attempt == 0 and "8005" in str(res.get("return_msg", "")):
            continue
        raise RuntimeError(f"Kiwoom API error: {res.get('return_msg')} (raw={res})")


def get_basic_info(stock_code):
    """주식기본정보요청 (ka10001) - 현재가 포함 기본 정보"""
    return _call("/api/dostk/stkinfo", "ka10001", {"stk_cd": stock_code})


def get_daily_chart(stock_code, base_dt="00000000", adjusted=True):
    """주식일봉차트조회요청 (ka10081)
    base_dt: 기준일자 YYYYMMDD (00000000 = 최근)
    adjusted: 수정주가 반영 여부
    """
    body = {"stk_cd": stock_code, "base_dt": base_dt, "upd_stkpc_tp": "1" if adjusted else "0"}
    return _call("/api/dostk/chart", "ka10081", body)


def get_foreign_trend(stock_code, dt="", amt_qty_tp="1"):
    """주식외국인종목별매매동향 (ka10008) - 종목별 외국인 순매매(일자별 시계열, 최근 약 50거래일)
    dt: 기준일자 YYYYMMDD ("" = 최근부터)
    amt_qty_tp: 1=수량, 2=금액 (문서 미확정 시 기본값 사용, 실측으로 확인)
    응답: stk_frgnr 배열, 각 원소에 dt(일자)·cur_prc(종가)·trde_qty(거래량)·
    chg_qty(외국인 순매매 수량, 부호=+매수/-매도 추정) 등 포함(실측 확인 필요).
    """
    body = {"stk_cd": stock_code}
    return _call("/api/dostk/frgnistt", "ka10008", body)


def get_institution_trend(stock_code, strt_dt, end_dt, orgn_prsm_unp_tp="1", for_prsm_unp_tp="1"):
    """종목별기관매매추이요청 (ka10045) - 종목별 기관·외국인 순매매(일자별 시계열, 기간 지정 가능)
    strt_dt/end_dt: YYYYMMDD 조회 시작/종료일자
    응답: stk_orgn_trde_trnsn 배열, 각 원소에 dt(일자)·close_pric(종가)·
    orgn_daly_nettrde_qty(기관 순매매 수량, +매수/-매도)·for_daly_nettrde_qty(외국인 순매매 수량) 등.
    """
    body = {
        "stk_cd": stock_code,
        "strt_dt": strt_dt,
        "end_dt": end_dt,
        "orgn_prsm_unp_tp": orgn_prsm_unp_tp,
        "for_prsm_unp_tp": for_prsm_unp_tp,
    }
    return _call("/api/dostk/mrkcond", "ka10045", body)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: kiwoom_api.py info <code> | daily <code> [YYYYMMDD] | foreign <code> | orgn <code> <strt_dt> <end_dt>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "foreign":
        print(json.dumps(get_foreign_trend(sys.argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "orgn":
        print(json.dumps(get_institution_trend(sys.argv[2], sys.argv[3], sys.argv[4]), ensure_ascii=False, indent=2))
    elif cmd == "info":
        print(json.dumps(get_basic_info(sys.argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "daily":
        base_dt = sys.argv[3] if len(sys.argv) > 3 else "00000000"
        print(json.dumps(get_daily_chart(sys.argv[2], base_dt), ensure_ascii=False, indent=2))
    else:
        print("unknown command")
        sys.exit(1)
