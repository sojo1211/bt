from typing import Dict, Any
from .base import BaseBusinessVerifierService

class MockBusinessVerifierService(BaseBusinessVerifierService):
    def __init__(self):
        # 모의 사업자 정보 데이터베이스
        self.business_db = {
            "120-81-12345": {
                "is_valid": True,
                "status": "계속사업자",
                "owner_name": "홍길동",
                "start_date": "20200510",
                "company_name": "(주)안전트레이드"
            },
            "220-81-67890": {
                "is_valid": True,
                "status": "휴업자",
                "owner_name": "이영희",
                "start_date": "20180415",
                "company_name": "영희컴퍼니"
            },
            "320-81-11111": {
                "is_valid": True,
                "status": "폐업자",
                "owner_name": "김철수",
                "start_date": "20150101",
                "company_name": "철수철물점"
            }
        }

    async def verify_business(self, business_number: str, start_date: str = None, owner_name: str = None) -> Dict[str, Any]:
        clean_num = business_number.replace("-", "").replace(" ", "")
        
        for key, value in self.business_db.items():
            clean_key = key.replace("-", "").replace(" ", "")
            if clean_num == clean_key:
                # 선택 파라미터가 있는 경우 추가 검증 매치
                if owner_name and value["owner_name"] != owner_name:
                    return {
                        "is_valid": False,
                        "status": "정보 불일치 (대표자명 상이)",
                        "details": f"입력된 대표자명({owner_name})과 국세청 등록 대표자명이 일치하지 않습니다."
                    }
                
                return {
                    "is_valid": value["status"] == "계속사업자",
                    "status": value["status"],
                    "details": f"국세청 확인 결과 [{value['company_name']}]은(는) {value['status']} 상태입니다."
                }
                
        return {
            "is_valid": False,
            "status": "등록되지 않은 번호",
            "details": "국세청에 등록되지 않았거나 유효하지 않은 사업자등록번호입니다."
        }
