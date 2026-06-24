from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseOCRService(ABC):
    @abstractmethod
    async def extract_identity(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        신분증 혹은 사업자등록증 이미지로부터 정보 추출
        반환 예: {"name": "홍길동", "id_number": "900101-1******", "type": "주민등록증"}
        """
        pass

class BaseCheatCheckerService(ABC):
    @abstractmethod
    async def check_fraud_history(self, phone: str = None, account: str = None) -> Dict[str, Any]:
        """
        전화번호 혹은 계좌번호를 기준으로 사기 이력 조회
        반환 예: {"has_history": True, "count": 3, "last_report_date": "2026-05-20"}
        """
        pass

class BaseBusinessVerifierService(ABC):
    @abstractmethod
    async def verify_business(self, business_number: str, start_date: str = None, owner_name: str = None) -> Dict[str, Any]:
        """
        사업자등록번호 진위 여부 확인
        반환 예: {"is_valid": True, "status": "계속사업자"}
        """
        pass

class BaseIdentityAnalyzerService(ABC):
    @abstractmethod
    async def analyze_identity(self, input_name: str, ocr_extracted_text: str, image_bytes: bytes = None) -> Dict[str, Any]:
        """
        입력된 성명과 OCR에서 추출된 텍스트(또는 원본 이미지) 간의 일치도를 분석합니다.
        반환 예: {"score": 90, "reason": "OCR 텍스트 중 '오성쥰'이 발견되어 90% 유사함"}
        """
        pass

class BaseFaceMatcherService(ABC):
    @abstractmethod
    async def match_faces(self, id_image_bytes: bytes, selfie_image_bytes: bytes) -> Dict[str, Any]:
        """
        신분증 이미지의 얼굴과 실시간 셀카 이미지의 얼굴을 비교합니다.
        반환 예: {"is_matched": True, "similarity": 85.5, "status": "matched"}
        """
        pass

class BaseRiskAnalyzerService(ABC):
    @abstractmethod
    async def assess_risk(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        각종 검증 결과(사기, 사업자, 신원 일치도 등)를 종합하여 
        관련 법령 및 e-KYC 가이드라인에 근거한 위험도 평가를 수행합니다.
        """
        pass
