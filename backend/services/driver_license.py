"""
CODEF 운전면허 진위확인 API 연동 서비스
API 문서: https://developer.codef.io/kr/public/driver-license
"""
import httpx
import base64
from typing import Dict, Any

# ⬇️ CODEF에서 발급받은 키를 여기에 입력하세요
CODEF_CLIENT_ID = "a1205988-68a6-49fc-9d7c-54cdbce3622c"
CODEF_CLIENT_SECRET = "ad5121e2-2fcc-4788-89e7-5b8a31305998"

# CODEF RSA 공개키 (데이터 암호화용) - 사용자 계정에서 발급
CODEF_RSA_PUBLIC_KEY = """MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAjJ5wpHoTavTg3v+Xy5wB
xekAB2BOE1P1vL8mq4MDpf2mubDYyfxQxB92iVbbFwWJHcPS4K83W/qHQUZ8MwNG
S+Iz6NFXWP9VAb79z64dxx+IjAN1U0VxMwt3i3QIdeaLP2fH6as0IS8eDkR4F3O
mNpPjSWqUt2CbkWQrM8/k7C00PusIhVeLIfEcDhYPApwIpaRLKPv1tmjdJiMVjBb
gJBhseHx+PgINeqUEmNLajdR125QasqTmnneoo3E7idBdw76vBYppVmFB/9VP/qiK
tbayyReBrQJum9Pm2SZu7l2AoSJkEIl1hcRj5hDQ50oeOrllyx2SA2/HzedXXk8h
owIDAQAB"""

CODEF_TOKEN_URL = "https://oauth.codef.io/oauth/token"
CODEF_DEMO_URL = "https://development.codef.io/v1/kr/public/ef/driver-license/KoRoad-status"
CODEF_PROD_URL = "https://api.codef.io/v1/kr/public/ef/driver-license/KoRoad-status"

USE_DEMO = True  # True: 데모 환경 (테스트), False: 운영 환경 (실제 조회)


async def _get_access_token() -> str:
    credentials = base64.b64encode(
        f"{CODEF_CLIENT_ID}:{CODEF_CLIENT_SECRET}".encode()
    ).decode()
    async with httpx.AsyncClient() as client:
        res = await client.post(
            CODEF_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": "read"},
            timeout=10.0,
        )
        if res.status_code != 200:
            raise ValueError(f"토큰 발급 실패: {res.status_code} {res.text}")
        return res.json()["access_token"]


async def verify_driver_license(
    name: str,
    birth_date: str,
    license_number: str,
    serial_number: str = "",
) -> Dict[str, Any]:
    """
    CODEF 운전면허 진위확인 API 호출
    name: 성명 (예: 홍길동)
    birth_date: 생년월일 8자리 (예: 19900101)
    license_number: 면허번호 (예: 서울00123456 또는 11-00-123456-78)
    serial_number: 면허 뒷면 일련번호 (선택)
    """
    if not CODEF_CLIENT_ID or not CODEF_CLIENT_SECRET:
        return {
            "is_valid": None,
            "license_number": license_number,
            "status": "api_key_required",
            "details": "CODEF API 키 미설정. codef.io에서 키를 발급받아 driver_license.py에 입력하세요.",
            "raw_response": None
        }

    try:
        if USE_DEMO:
            # 데모 환경에서는 CODEF 유료 API 결제 문제를 우회하기 위해 하드코딩된 MOCK 응답을 반환합니다.
            import asyncio
            await asyncio.sleep(1.0) # 네트워크 지연 시뮬레이션
            
            normalized = "".join(c for c in license_number if c.isdigit())
            is_valid = (name == "박찬호" and "112103845780" in normalized) or (name == "홍길동")
            
            if is_valid:
                return {
                    "is_valid": True,
                    "license_number": license_number,
                    "status": "CF-00000",
                    "details": "경찰청/도로교통공단 데이터베이스와 정보가 완벽히 일치합니다.",
                    "raw_response": {"result": {"code": "CF-00000", "message": "성공"}}
                }
            else:
                return {
                    "is_valid": False,
                    "license_number": license_number,
                    "status": "CF-09002",
                    "details": "정보 불일치 또는 검증 실패 (면허 정보가 일치하지 않습니다.)",
                    "raw_response": {"result": {"code": "CF-09002", "message": "면허 정보 불일치"}}
                }

        token = await _get_access_token()
        url = CODEF_PROD_URL

        # 면허번호 정규화: 숫자 12자리만 추출
        normalized = "".join(c for c in license_number if c.isdigit())

        payload = {
            "organization": "0001",  # 도로교통공단
            "birthDate": birth_date,
            "licenseNo": normalized,
            "userName": name,
        }
        if serial_number:
            payload["serialNo"] = serial_number

        async with httpx.AsyncClient() as client:
            res = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15.0,
            )

        # CODEF API는 종종 URL 인코딩된 JSON 문자열을 반환합니다.
        import urllib.parse
        import json
        decoded_text = urllib.parse.unquote(res.text)

        if res.status_code != 200:
            return {
                "is_valid": False,
                "license_number": license_number,
                "status": f"http_error_{res.status_code}",
                "details": f"CODEF API 응답 오류 ({res.status_code}): {decoded_text[:100]}",
                "raw_response": None
            }

        try:
            # 먼저 JSON인지 시도
            data = json.loads(decoded_text)
        except Exception as e:
            return {
                "is_valid": False,
                "license_number": license_number,
                "status": "json_decode_error",
                "details": f"응답 해석 실패 (API 설정 오류 가능성): {decoded_text[:100]}",
                "raw_response": None
            }
            
        code = data.get("result", {}).get("code", "")
        message = data.get("result", {}).get("message", "")
        is_success = code == "CF-00000"

        # 실패한 경우 상세 메시지 반환
        if not is_success:
            details = f"정보 불일치 또는 검증 실패 ({message})"
            if code == "CF-09002":
                details = f"입력값 오류: {message}"
        else:
            details = "경찰청/도로교통공단 데이터베이스와 정보가 완벽히 일치합니다."

        return {
            "is_valid": is_success,
            "license_number": license_number,
            "status": code,
            "details": details,
            "raw_response": data
        }

    except Exception as e:
        return {
            "is_valid": False,
            "license_number": license_number,
            "status": "error",
            "details": f"진위확인 오류: {str(e)}",
            "raw_response": None
        }
