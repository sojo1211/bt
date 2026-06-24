from typing import Type
from .base import BaseOCRService, BaseCheatCheckerService, BaseBusinessVerifierService, BaseIdentityAnalyzerService, BaseFaceMatcherService, BaseRiskAnalyzerService
from .ocr import MockOCRService
from .cheat_checker import MockCheatCheckerService
from .business_verifier import MockBusinessVerifierService
from .identity_analyzer import IdentityAnalyzerService
from .risk_analyzer import RiskAnalyzerService

# EasyOCRService를 기본으로 사용하되, 의존성 미비 또는 초기화 에러 시 MockOCRService로 폴백합니다.
try:
    from .easyocr_service import EasyOCRService
    DEFAULT_OCR_SERVICE = EasyOCRService
except Exception as e:
    import warnings
    warnings.warn(f"EasyOCRService를 로드하지 못했습니다. MockOCRService를 사용합니다. 에러: {e}")
    DEFAULT_OCR_SERVICE = MockOCRService

# FaceMatcherService 로드 및 폴백 처리
try:
    from .face_matcher import PyTorchFaceMatcherService, BaseFaceMatcherService
    DEFAULT_FACE_MATCHER_SERVICE = PyTorchFaceMatcherService
except Exception as e:
    import warnings
    from .face_matcher import MockFaceMatcherService, BaseFaceMatcherService
    warnings.warn(f"FaceMatcherService를 로드하지 못했습니다. MockFaceMatcherService를 사용합니다. 에러: {e}")
    DEFAULT_FACE_MATCHER_SERVICE = MockFaceMatcherService

class ServiceContainer:
    """
    서비스 의존성 주입 컨테이너.
    원하는 구현체 클래스를 등록하여 뺐다 낄 수(Pluggable) 있도록 설계되었습니다.
    """
    _ocr_service_class: Type[BaseOCRService] = DEFAULT_OCR_SERVICE
    _cheat_checker_class: Type[BaseCheatCheckerService] = MockCheatCheckerService
    _business_verifier_class: Type[BaseBusinessVerifierService] = MockBusinessVerifierService
    _face_matcher_class: Type[BaseFaceMatcherService] = DEFAULT_FACE_MATCHER_SERVICE

    @classmethod
    def register_ocr_service(cls, service_class: Type[BaseOCRService]):
        cls._ocr_service_class = service_class

    @classmethod
    def register_cheat_checker(cls, service_class: Type[BaseCheatCheckerService]):
        cls._cheat_checker_class = service_class

    @classmethod
    def register_business_verifier(cls, service_class: Type[BaseBusinessVerifierService]):
        cls._business_verifier_class = service_class

    @classmethod
    def register_face_matcher(cls, service_class: Type[BaseFaceMatcherService]):
        cls._face_matcher_class = service_class

    def __init__(self):
        # 인스턴스 지연 생성
        self.ocr: BaseOCRService = self._ocr_service_class()
        self.cheat_checker: BaseCheatCheckerService = self._cheat_checker_class()
        self.business_verifier: BaseBusinessVerifierService = self._business_verifier_class()
        self.face_matcher: BaseFaceMatcherService = self._face_matcher_class()
        self.identity_analyzer: BaseIdentityAnalyzerService = IdentityAnalyzerService()
        self.risk_analyzer: BaseRiskAnalyzerService = RiskAnalyzerService()

# 싱글톤처럼 전역으로 사용할 수 있게 컨테이너 초기화 함수 정의
def get_services() -> ServiceContainer:
    return ServiceContainer()

