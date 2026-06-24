import re
from typing import Dict, Any
from .base import BaseOCRService

class MockOCRService(BaseOCRService):
    async def extract_identity(self, image_bytes: bytes) -> Dict[str, Any]:
        # 실제 환경에서는 CLOVA OCR이나 Google Vision API 등을 호출하여 바이너리를 분석하게 됩니다.
        # 여기서는 파일 데이터의 시뮬레이션을 수행합니다.
        
        # 파일 내용을 검사하거나 가공하여 특정 이름이 발견되면 그에 맞는 Mock을 반환
        content_preview = image_bytes[:50].decode('utf-8', errors='ignore')
        
        # 기본 Mock 신분증 정보
        parsed_data = {
            "name": "홍길동",
            "id_number": "900101-1020304",
            "type": "주민등록증",
            "extracted_text": "주민등록증 홍길동 900101-1020304 발급일: 2020.05.10"
        }
        
        # 만약 "business" 라는 텍스트 등이 유도될 경우 사업자등록증으로 시뮬레이션
        if b"business" in image_bytes or "사업자" in content_preview:
            parsed_data = {
                "name": "(주)안전트레이드",
                "id_number": "120-81-12345",
                "type": "사업자등록증",
                "extracted_text": "등록번호: 120-81-12345 상호: (주)안전트레이드 대표자: 홍길동"
            }

        # 보안 마스킹 처리 (Privacy by Design)
        parsed_data["masked_id_number"] = self._mask_sensitive_info(parsed_data["id_number"], parsed_data["type"])
        
        return parsed_data

    def _mask_sensitive_info(self, id_number: str, id_type: str) -> str:
        if id_type == "주민등록증":
            # 900101-1020304 -> 900101-1******
            match = re.match(r"^(\d{6}-\d{1})\d{6}$", id_number.replace(" ", ""))
            if match:
                return f"{match.group(1)}******"
        elif id_type == "사업자등록증":
            # 120-81-12345 -> 120-81-*****
            match = re.match(r"^(\d{3}-\d{2}-)\d{5}$", id_number.replace(" ", ""))
            if match:
                return f"{match.group(1)}*****"
        return "******"
