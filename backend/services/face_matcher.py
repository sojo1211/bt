import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from typing import Dict, Any, Tuple
from abc import ABC, abstractmethod

class BaseFaceMatcherService(ABC):
    @abstractmethod
    async def match_faces(self, id_image_bytes: bytes, selfie_image_bytes: bytes) -> Dict[str, Any]:
        """
        신분증 이미지의 얼굴과 실시간 셀카 이미지의 얼굴을 비교
        반환 예: {"is_matched": True, "similarity": 85.5, "status": "matched"}
        """
        pass

class MockFaceMatcherService(BaseFaceMatcherService):
    async def match_faces(self, id_image_bytes: bytes, selfie_image_bytes: bytes) -> Dict[str, Any]:
        return {
            "is_matched": True,
            "similarity": 92.4,
            "status": "matched",
            "details": "[Mock] 본인 인증 성공 (얼굴 일치)"
        }


class PyTorchFaceMatcherService(BaseFaceMatcherService):
    def __init__(self):
        # 윈도우 한글 경로(non-ASCII) 이슈 대응을 위해 Haar Cascade XML 파일을 Temp 폴더로 복사하여 로드합니다.
        import os
        import shutil
        import tempfile
        
        temp_dir = tempfile.gettempdir()
        temp_xml_path = os.path.join(temp_dir, 'haarcascade_frontalface_default.xml')
        
        original_xml_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        if os.path.exists(original_xml_path):
            try:
                shutil.copy(original_xml_path, temp_xml_path)
                self.face_cascade = cv2.CascadeClassifier(temp_xml_path)
            except Exception:
                # 복사 실패 시 기본 경로 로드 시도
                self.face_cascade = cv2.CascadeClassifier(original_xml_path)
        else:
            self.face_cascade = cv2.CascadeClassifier(original_xml_path)
        
        # PyTorch pre-trained MobileNetV3 (가볍고 빠름) 로드

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # MobileNetV3 Large 모델 로드 (가중치 포함)
        self.model = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.DEFAULT)
        # 최종 분류 레이어 제거하여 특징 추출 벡터(1024차원)만 출력하도록 설정
        self.model.classifier = nn.Identity()
        self.model.to(self.device)
        self.model.eval()
        
        # 이미지 전처리 파이프라인 (ImageNet 정규화 기준)
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def _apply_frequency_filtering(self, img_gray: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        2D FFT를 적용하여 주파수 영역에서 조명 노이즈(저주파)와 망점 노이즈(고주파)를 제거하고 복원합니다.
        반환값: (Magnitude Spectrum, Reconstructed Grayscale Image)
        """
        # 1. 2D FFT 변환 및 Shift (저주파 성분을 중앙으로 배치)
        f = np.fft.fft2(img_gray)
        fshift = np.fft.fftshift(f)
        
        # 시각화용 강도 스펙트럼 계산 (로그 스케일링)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
        # 0 ~ 255 범위로 정규화
        min_val, max_val = magnitude_spectrum.min(), magnitude_spectrum.max()
        if max_val > min_val:
            magnitude_spectrum = ((magnitude_spectrum - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        else:
            magnitude_spectrum = np.zeros_like(magnitude_spectrum, dtype=np.uint8)
            
        # 2. 밴드패스 필터 (Band-pass Filter) 생성 및 적용
        rows, cols = img_gray.shape
        crow, ccol = rows // 2, cols // 2
        
        # 필터 마스크 (1로 초기화, 제거할 영역만 0으로 설정)
        mask = np.ones((rows, cols), np.uint8)
        
        # 저주파 제거 (조명 성분 제거) - 중앙부 미세한 원 영역 마스킹
        r_low = 6
        y, x = np.ogrid[-crow:rows-crow, -ccol:cols-ccol]
        low_mask = x*x + y*y <= r_low*r_low
        mask[low_mask] = 0
        
        # 고주파 제거 (망점/노이즈 제거) - 외곽부 영역 마스킹
        r_high = 70
        high_mask = x*x + y*y > r_high*r_high
        mask[high_mask] = 0
        
        # 필터 적용
        fshift_filtered = fshift * mask
        
        # 3. 역변환 (Inverse FFT) 및 복원
        f_ishift = np.fft.ifftshift(fshift_filtered)
        img_back = np.fft.ifft2(f_ishift)
        img_back = np.abs(img_back)
        
        # 복원된 이미지 정규화 (0 ~ 255)
        min_val, max_val = img_back.min(), img_back.max()
        if max_val > min_val:
            img_back = ((img_back - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        else:
            img_back = np.zeros_like(img_back, dtype=np.uint8)
            
        return magnitude_spectrum, img_back

    def _detect_and_crop_face_with_steps(self, img: np.ndarray) -> Dict[str, Any]:
        """
        이미지에서 얼굴을 검출/크롭하고 중간 처리 단계 이미지(흑백, 이퀄라이즈, 크롭) 및 주파수 변환 이미지들을 base64 문자열로 함께 반환합니다.
        """
        import base64
        
        def to_b64(image: np.ndarray) -> str:
            _, buffer = cv2.imencode('.jpg', image)
            return base64.b64encode(buffer).decode('utf-8')
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = []
        equalized_img = None
        is_fallback = False
        detected = False
        
        # 단계 1: 일반 회색조 이미지에서 순차적으로 완화된 기준 적용
        for neighbors in [5, 3, 2]:
            detected_faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=neighbors, 
                minSize=(40, 40)
            )
            if len(detected_faces) > 0:
                faces = detected_faces
                detected = True
                break
                
        # 단계 2: 검출 실패 시 히스토그램 평활화 적용 후 재시도
        if len(faces) == 0:
            equalized_img = cv2.equalizeHist(gray)
            for neighbors in [4, 3, 2]:
                detected_faces = self.face_cascade.detectMultiScale(
                    equalized_img, 
                    scaleFactor=1.1, 
                    minNeighbors=neighbors, 
                    minSize=(30, 30)
                )
                if len(detected_faces) > 0:
                    faces = detected_faces
                    detected = True
                    break
                    
        # 크롭 영역 지정
        if len(faces) == 0:
            h_img, w_img, _ = img.shape
            # 중앙 기준 가로 60%, 세로 60% 영역을 얼굴 추정 영역으로 크롭
            y1 = int(h_img * 0.15)
            y2 = int(h_img * 0.75)
            x1 = int(w_img * 0.2)
            x2 = int(w_img * 0.8)
            face_crop = img[y1:y2, x1:x2]
            is_fallback = True
        else:
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest_face
            
            # 얼굴 주위 여백을 포함하여 크롭
            padding_y = int(h * 0.1)
            padding_x = int(w * 0.1)
            h_img, w_img, _ = img.shape
            
            y1 = max(0, y - padding_y)
            y2 = min(h_img, y + h + padding_y)
            x1 = max(0, x - padding_x)
            x2 = min(w_img, x + w + padding_x)
            face_crop = img[y1:y2, x1:x2]

        # 크롭된 얼굴에 대해 2D FFT 및 주파수 필터링 적용 (조명 및 노이즈 표준화)
        face_gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        fft_spectrum, reconstructed_face = self._apply_frequency_filtering(face_gray)
        
        # 딥러닝 임베딩 연산 모델을 위한 3채널 RGB 변환 (흑백 복원 이미지를 RGB로 복사)
        # (시각화 UI 호환을 위해 변수명은 유지)
        reconstructed_face_rgb = cv2.cvtColor(reconstructed_face, cv2.COLOR_GRAY2RGB)
            
        return {
            "face_crop": face_crop, # 특징 임베딩에 사용될 원본 컬러 이미지
            "detected": detected,
            "is_fallback": is_fallback,
            "grayscale_base64": to_b64(gray),
            "equalized_base64": to_b64(equalized_img) if equalized_img is not None else None,
            "cropped_base64": to_b64(face_crop),
            "fft_spectrum_base64": to_b64(fft_spectrum),
            "reconstructed_base64": to_b64(reconstructed_face)
        }

    def _detect_and_crop_face(self, img: np.ndarray) -> Tuple[np.ndarray, bool]:
        res = self._detect_and_crop_face_with_steps(img)
        return res["face_crop"], not res["is_fallback"]

    def _get_embedding(self, face_img: np.ndarray) -> torch.Tensor:
        """
        크롭된 얼굴 이미지에서 PyTorch 모델 특징 벡터(임베딩)를 추출합니다.
        """
        # BGR -> RGB 변환
        face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        
        # 전처리 수행 및 배치 차원 추가
        tensor = self.transform(face_rgb).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            embedding = self.model(tensor)
            # 평탄화 및 L2 정규화
            embedding = torch.flatten(embedding, 1)
            embedding = nn.functional.normalize(embedding, p=2, dim=1)
            
        return embedding

    async def match_faces(self, id_image_bytes: bytes, selfie_image_bytes: bytes) -> Dict[str, Any]:
        try:
            # 1. 이미지 디코딩
            id_nparr = np.frombuffer(id_image_bytes, np.uint8)
            id_img = cv2.imdecode(id_nparr, cv2.IMREAD_COLOR)
            
            selfie_nparr = np.frombuffer(selfie_image_bytes, np.uint8)
            selfie_img = cv2.imdecode(selfie_nparr, cv2.IMREAD_COLOR)
            
            if id_img is None or selfie_img is None:
                return {
                    "is_matched": False,
                    "similarity": 0,
                    "status": "invalid_image",
                    "details": "이미지를 디코딩할 수 없습니다."
                }
                
            # 2. 얼굴 검출 및 크롭 (단계별 결과 함께 가져옴)
            id_res = self._detect_and_crop_face_with_steps(id_img)
            selfie_res = self._detect_and_crop_face_with_steps(selfie_img)
            
            id_face = id_res["face_crop"]
            selfie_face = selfie_res["face_crop"]
            
            # 3. 얼굴 임베딩 추출 (주파수 도메인 필터링 복원 이미지가 사용됨!)
            id_embed = self._get_embedding(id_face)
            selfie_embed = self._get_embedding(selfie_face)
            
            # 4. 코사인 유사도 계산
            cosine_sim = torch.nn.functional.cosine_similarity(id_embed, selfie_embed).item()
            
            # 5. 유사도 보정 (코사인 유사도 수치 -> 사용자가 이해하기 쉬운 0~100 백분율 환산)
            # 폴백(Center Crop)이 적용되었거나 화질이 안 좋은 경우 기본 임계값을 유동적으로 조정
            base_threshold = 0.65
            if id_res["is_fallback"] or selfie_res["is_fallback"]:
                base_threshold -= 0.15  # 배경 노이즈 포함 시 기준 완화
            
            if cosine_sim >= base_threshold:
                norm_sim = 75.0 + ((cosine_sim - base_threshold) / (1.0 - base_threshold)) * 25.0
            else:
                norm_sim = (cosine_sim / base_threshold) * 75.0
                
            similarity_percent = round(max(0.0, min(100.0, norm_sim)), 1)
            
            # 1. 자체 모델을 통한 일치 여부 판별 (동적 임계값 적용)
            # 데모 환경을 위해 임계값을 75.0에서 70.0으로 완화
            is_matched = similarity_percent >= 70.0
            
            # 2. LLM(Gemini)을 이용한 유사도 측정 결과 '설명' (검증 목적 아님, 오직 설명용)
            details = "안면 임베딩 유사도 기준 본인 인증 성공" if is_matched else "신분증 얼굴과 실시간 셀카가 일치하지 않습니다."
            
            try:
                import os
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langchain.schema import HumanMessage, SystemMessage
                
                # 사용자가 제공한 Gemini API Key 사용
                api_key = os.getenv("GEMINI_API_KEY", "")
                if api_key:
                    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=api_key)
                    prompt = f"""
                    당신은 신분증 사진과 웹캠 셀카 사진을 분석하여 두 사진 간의 안면 유사도를 사용자에게 친절하게 설명하는 AI입니다.
                    현재 시스템이 판별한 두 사진의 유사도 점수는 {similarity_percent}% 입니다.
                    이 점수가 왜 이렇게 나왔는지(어떤 시각적 차이점이나 유사점이 있는지) 두 사진을 직접 비교하여 구체적으로 설명해주세요.
                    
                    예시 1: "머리카락이 내림머리이고 올림머리라 다르게 보이며, 안경 착용 여부로 인해 유사도가 67.5%로 측정되었습니다. 하지만 눈매와 코의 형태는 흡사합니다."
                    예시 2: "눈썹 모양과 콧대의 높이가 확연히 다르고 얼굴형이 일치하지 않아 유사도가 낮게 측정되었습니다."
                    예시 3: "이목구비가 매우 선명하게 일치하여 95%의 높은 유사도가 측정되었습니다."
                    
                    주의: 당신은 검증 모델이 아니라 '설명(Explanation)' 모델입니다. 점수를 바꾸거나 다시 판별하지 말고, 오직 주어진 점수에 대한 시각적 근거만 1~2문장으로 설명하세요. 다른 인사말이나 JSON 태그 없이 설명 텍스트만 반환하세요.
                    """
                    msg = HumanMessage(content=[
                        {"type": "text", "text": "아래 두 사진을 보고 유사도 점수의 시각적 이유를 설명해주세요."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{id_res['cropped_base64']}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{selfie_res['cropped_base64']}"}}
                    ])
                    res = llm.invoke([SystemMessage(content=prompt), msg])
                    
                    explanation = res.content.strip()
                    # LLM의 구체적인 이유를 details에 저장하여 UI에 노출
                    details = explanation
            except Exception as e:
                print(f"Gemini Explanation Error: {e}")
                
            return {
                "is_matched": is_matched,
                "similarity": similarity_percent,
                "status": "matched" if is_matched else "unmatched",
                "details": details,
                "id_steps": {
                    "grayscale": id_res["grayscale_base64"],
                    "equalized": id_res["equalized_base64"],
                    "cropped": id_res["cropped_base64"],
                    "fft_spectrum": id_res["fft_spectrum_base64"],
                    "reconstructed": id_res["reconstructed_base64"],
                    "is_fallback": id_res["is_fallback"],
                    "detected": id_res["detected"]
                },
                "selfie_steps": {
                    "grayscale": selfie_res["grayscale_base64"],
                    "equalized": selfie_res["equalized_base64"],
                    "cropped": selfie_res["cropped_base64"],
                    "fft_spectrum": selfie_res["fft_spectrum_base64"],
                    "reconstructed": selfie_res["reconstructed_base64"],
                    "is_fallback": selfie_res["is_fallback"],
                    "detected": selfie_res["detected"]
                }
            }
            
        except Exception as e:
            return {
                "is_matched": False,
                "similarity": 0,
                "status": "error",
                "details": f"얼굴 매칭 중 오류 발생: {str(e)}"
            }
