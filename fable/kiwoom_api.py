# -*- coding: utf-8 -*-
"""
키움증권 Open API (REST) 조회 전용 헬퍼.

- 용도: 한국 주식 시세/기본정보 등 "조회"에만 사용. 주문·매매 실행 함수는
  의도적으로 구현하지 않음(실수로 매매가 일어나는 것을 방지).
- 키 위치: 이 파일과 같은 폴더의 46238499_appkey.txt / 46238499_secretkey.txt
  (실전 계좌용 키. 모의투자 도메인(mockapi.kiwoom.com)에서는 사용 불가 — 확인됨)
- 토큰은 발급 빈도 제한이 있으므로 .kiwoom_token_cache.json에 캐싱하여 재사용.

사용 예:
    from kiwoom_api import get_stock_basic_info
    info = get_stock_basic_info("005930")
    print(info["cur_prc"], info["flu_rt"])
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
_APPKEY_FILE = os.path.join(_DIR, "46238499_appkey.txt")
_SECRETKEY_FILE = os.path.join(_DIR, "46238499_secretkey.txt")
_TOKEN_CACHE_FILE = os.path.join(_DIR, ".kiwoom_token_cache.json")

BASE_URL = "https://api.kiwoom.com"  # 실전 도메인 (이 키는 실전 전용으로 확인됨)


def _load_keys():
    with open(_APPKEY_FILE, "r", encoding="utf-8") as f:
        appkey = f.read().strip()
    with open(_SECRETKEY_FILE, "r", encoding="utf-8") as f:
        secretkey = f.read().strip()
    return appkey, secretkey


def _request(url, body, headers, method="POST", timeout=15):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"error": raw}


def get_access_token(force_refresh=False):
    """토큰 발급/캐시 조회. expires_dt(yyyyMMddHHmmss) 기준 만료 전이면 캐시 재사용."""
    if not force_refresh and os.path.exists(_TOKEN_CACHE_FILE):
        try:
            with open(_TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            exp = datetime.strptime(cached["expires_dt"], "%Y%m%d%H%M%S")
            if datetime.now() < exp:
                return cached["token"]
        except Exception:
            pass

    appkey, secretkey = _load_keys()
    status, resp = _request(
        f"{BASE_URL}/oauth2/token",
        {"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
        {"content-type": "application/json"},
    )
    if status != 200 or resp.get("return_code") != 0:
        raise RuntimeError(f"키움 토큰 발급 실패: status={status} resp={resp}")

    with open(_TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(resp, f, ensure_ascii=False)
    return resp["token"]


def call_tr(api_id, path, body, cont_yn="N", next_key=""):
    """
    범용 TR 호출 (조회성 TR만 사용할 것).
    api_id: 예) 'ka10001' (주식기본정보요청)
    path:   예) '/api/dostk/stkinfo'
    body:   요청 바디 dict
    """
    token = get_access_token()
    headers = {
        "content-type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}",
        "api-id": api_id,
        "cont-yn": cont_yn,
        "next-key": next_key,
    }
    status, resp = _request(f"{BASE_URL}{path}", body, headers)
    if status != 200:
        # 토큰 만료/무효 가능성 -> 1회 재발급 후 재시도
        token = get_access_token(force_refresh=True)
        headers["authorization"] = f"Bearer {token}"
        status, resp = _request(f"{BASE_URL}{path}", body, headers)
    return status, resp


def get_stock_basic_info(stk_cd):
    """주식기본정보요청 (ka10001) — 현재가(cur_prc), 등락률(flu_rt), PER/PBR 등 포함.
    stk_cd: 6자리 종목코드 (예: '005930')
    """
    status, resp = call_tr("ka10001", "/api/dostk/stkinfo", {"stk_cd": stk_cd})
    if status != 200:
        raise RuntimeError(f"종목정보 조회 실패({stk_cd}): status={status} resp={resp}")
    return resp


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "005930"
    info = get_stock_basic_info(code)
    print(json.dumps(info, ensure_ascii=False, indent=2))
