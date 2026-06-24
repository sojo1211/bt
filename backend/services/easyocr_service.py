import os
import re
import numpy as np
import cv2
import easyocr
from typing import Dict, Any
from .base import BaseOCRService

class EasyOCRService(BaseOCRService):
    def __init__(self, custom_model_path: str = None, custom_model_name: str = None):
        # 전이학습된 커스텀 가중치가 제공될 경우 우선 로드 (Transfer Learning 연계)
        if custom_model_path and custom_model_name and os.path.exists(custom_model_path):
            print(f"커스텀 EasyOCR 모델 로드 중: {custom_model_name}")
            self.reader = easyocr.Reader(
                lang_list=['ko', 'en'],
                rec_network=custom_model_name,
                model_storage_directory=os.path.dirname(custom_model_path),
                user_network_directory=os.path.dirname(custom_model_path)
            )
        else:
            # 한국어(ko)와 영어(en) 인식 지원 기본 리더기 로드
            self.reader = easyocr.Reader(['ko', 'en'])

    async def extract_identity(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            # 바이트 데이터를 OpenCV 이미지 객체로 디코딩
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("올바르지 않은 이미지 형식입니다.")

            # EasyOCR을 사용해 이미지에서 텍스트 감지
            results = self.reader.readtext(img)
            
            # 감지된 텍스트들을 공백 포함 전체 하나의 문자열 및 리스트로 가공
            extracted_texts = [res[1] for res in results]
            full_text = "\n".join(extracted_texts)
            
            # 기본 반환 구조 정의
            parsed_data = {
                "name": "미확인",
                "id_number": "미확인",
                "type": "미확인",
                "extracted_text": full_text
            }

            # 1. 문서 타입 및 정보 추출 (사업자등록증 체크)
            business_number_match = re.search(r"(\d{3}-\d{2}-\d{5})", full_text.replace(" ", ""))
            id_number_match = re.search(r"(\d{6}-\d{7})|(\d{6}-\d{1}\*{6})", full_text.replace(" ", ""))
            
            if business_number_match:
                parsed_data["type"] = "사업자등록증"
                parsed_data["id_number"] = business_number_match.group(1)
                # 사업자명 / 상호명 추출 (상호 또는 대표자 근처 단어 탐색)
                name_match = re.search(r"(?:상호|대표자|대표자명)\s*:\s*([가-힣\w\s\(\)]+)", full_text)
                if name_match:
                    parsed_data["name"] = name_match.group(1).split()[0]
                else:
                    # 차선책: 한국어 단어 중 적절한 명칭 탐색
                    korean_words = re.findall(r"[가-힣]{2,10}", full_text)
                    if korean_words:
                        parsed_data["name"] = korean_words[0]
            
            # 2. 주민등록증 또는 운전면허증 체크
            elif id_number_match:
                parsed_data["id_number"] = id_number_match.group(0)
                if "주민등록" in full_text or "주민" in full_text:
                    parsed_data["type"] = "주민등록증"
                elif "운전" in full_text or "면허" in full_text:
                    parsed_data["type"] = "운전면허증"
                else:
                    parsed_data["type"] = "신분증"

                # 한글 이름 추출 고도화: 주민등록번호 위치 앵커 기반 탐색
                lines = [line.strip() for line in extracted_texts if line.strip()]
                id_index = -1
                for i, line in enumerate(lines):
                    if re.search(r"(\d{6}-\d{7})|(\d{6}-\d{1}\*{6})", line.replace(" ", "")):
                        id_index = i
                        break
                
                found_name = False
                # 1. 주민등록번호 윗줄부터 역순으로 탐색 (이름이 주민번호 바로 위나 그 근처에 위치함)
                if id_index > 0:
                    for i in range(id_index - 1, -1, -1):
                        clean_line = re.sub(r"[^가-힣]", "", lines[i])
                        if 2 <= len(clean_line) <= 4 and clean_line not in ["주민등록증", "운전면허증", "자동차운전면허증", "국가유공자증"]:
                            parsed_data["name"] = clean_line
                            found_name = True
                            break
                
                # 2. 찾지 못했다면 기존처럼 위에서부터 순방향 탐색
                if not found_name:
                    for line in lines:
                        clean_line = re.sub(r"[^가-힣]", "", line)
                        if 2 <= len(clean_line) <= 4 and clean_line not in ["주민등록증", "운전면허증", "자동차운전면허증", "발급일", "국가유공자증"]:
                            parsed_data["name"] = clean_line
                            break
            
            # 아무것도 탐색되지 않았을 때 기본값
            if parsed_data["type"] == "미확인" and len(extracted_texts) > 0:
                # 텍스트가 추출은 되었으나 정규식 매치에 실패한 경우
                korean_words = re.findall(r"[가-힣]{2,4}", full_text)
                if korean_words:
                    parsed_data["name"] = korean_words[0]
                parsed_data["type"] = "기타문서"

            # 보안 마스킹 처리 (Privacy by Design)
            parsed_data["masked_id_number"] = self._mask_sensitive_info(parsed_data["id_number"], parsed_data["type"])
            
            return parsed_data

        except Exception as e:
            # 상세 오류는 로깅하고, 상위 컨트롤러로 전달
            raise RuntimeError(f"EasyOCR 추출 실패: {str(e)}")

    def _mask_sensitive_info(self, id_number: str, id_type: str) -> str:
        if id_number == "미확인":
            return "미확인"
            
        clean_number = id_number.replace(" ", "")
        if id_type in ["주민등록증", "운전면허증", "신분증"]:
            # 900101-1020304 -> 900101-1******
            match = re.match(r"^(\d{6}-\d{1})[\d\*]{6}$", clean_number)
            if match:
                return f"{match.group(1)}******"
        elif id_type == "사업자등록증":
            # 120-81-12345 -> 120-81-*****
            match = re.match(r"^(\d{3}-\d{2}-)\d{5}$", clean_number)
            if match:
                return f"{match.group(1)}*****"
        return "******"
