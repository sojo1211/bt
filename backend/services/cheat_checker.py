from typing import Dict, Any
from .base import BaseCheatCheckerService

class MockCheatCheckerService(BaseCheatCheckerService):
    def __init__(self):
        # 테스트용 사기 이력 합성 데이터베이스 (Synthetic Data)
        self.fraud_db = {
            "010-1234-5678": {
                "has_history": True,
                "count": 3,
                "last_report_date": "2026-05-15",
                "risk_level": "RED",
                "details": "중고나라론 사기 2건, 번개장터 티켓 사기 1건"
            },
            "010-9999-8888": {
                "has_history": True,
                "count": 1,
                "last_report_date": "2026-06-01",
                "risk_level": "YELLOW",
                "details": "단순 배송 지연 신고 1건"
            },
            "110-123-456789": { # 계좌번호 Mock
                "has_history": True,
                "count": 4,
                "last_report_date": "2026-05-28",
                "risk_level": "RED",
                "details": "허위 매물 등록 관련 동일 계좌 신고 다수 발생"
            }
        }

    async def check_fraud_history(self, phone: str = None, account: str = None) -> Dict[str, Any]:
        # 전화번호 및 계좌 번호 특수문자 제거 후 검증
        clean_phone = phone.replace("-", "").replace(" ", "") if phone else None
        clean_account = account.replace("-", "").replace(" ", "") if account else None
        
        # 조회
        for key, value in self.fraud_db.items():
            clean_key = key.replace("-", "").replace(" ", "")
            if (clean_phone and clean_phone == clean_key) or (clean_account and clean_account == clean_key):
                return {
                    "has_history": value["has_history"],
                    "count": value["count"],
                    "last_report_date": value["last_report_date"],
                    "risk_level": value["risk_level"],
                    "details": value["details"]
                }
        
        # 내역 없음 (안전)
        return {
            "has_history": False,
            "count": 0,
            "last_report_date": None,
            "risk_level": "GREEN",
            "details": "조회된 사기 신고 이력이 없습니다. 안전합니다."
        }
