import os
import json
from difflib import SequenceMatcher
from typing import Dict, Any

from .base import BaseIdentityAnalyzerService

# LangChain 관련 임포트 (실패 시 Fallback 사용)
try:
    from langchain_openai import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class IdentityAnalyzerService(BaseIdentityAnalyzerService):
    def __init__(self):
        # API Key 유무에 따라 LangChain 사용 여부 결정
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.use_langchain = LANGCHAIN_AVAILABLE and bool(self.api_key)
        
        if self.use_langchain:
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.0,
                openai_api_key=self.api_key
            )

    async def analyze_identity(self, input_name: str, ocr_extracted_text: str, image_bytes: bytes = None) -> Dict[str, Any]:
        """
        주어진 입력 성명과 OCR 추출 텍스트, 그리고 가능하다면 원본 신분증 이미지를 직접 분석하여 
        얼마나 동일한지(유사도 점수)와 사유를 반환합니다.
        """
        import base64
        
        # 1. LangChain (LLM) 기반 지능형 시각 분석
        if self.use_langchain:
            try:
                system_prompt = """
                당신은 신분증 이미지를 직접 분석하고 신원 일치 여부를 판별하는 초정밀 비전 AI 에이전트입니다.
                사용자가 입력한 이름과 신분증 이미지가 주어집니다. 
                기존의 일반 OCR 엔진이 이름을 잘못 읽었을 수 있으므로, 당신이 직접 이미지에서 텍스트를 읽고 판단해야 합니다.
                
                목표:
                입력된 이름이 신분증 이미지(또는 참고용 OCR 텍스트) 내에 존재하는지 확인하고, 
                얼마나 동일한 인물로 볼 수 있는지 0에서 100 사이의 점수(score)를 산출하세요.
                *주의사항: 베이스라인 OCR 엔진이 틀렸더라도, 이미지에 이름이 제대로 적혀있다면 100점을 주어야 합니다. 당신이 진짜 판별자입니다.*
                
                결과는 반드시 아래 JSON 형식으로만 반환하세요:
                {
                    "score": <0~100 사이 정수>,
                    "reason": "<왜 이 점수를 부여했는지에 대한 분석 사유 (한국어)>"
                }
                """
                
                user_text_prompt = f"입력된 이름: {input_name}\n참고용 기존 OCR 텍스트:\n{ocr_extracted_text}\n"
                
                message_content = [{"type": "text", "text": user_text_prompt}]
                
                if image_bytes:
                    base64_image = base64.b64encode(image_bytes).decode('utf-8')
                    message_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    })
                
                response = self.llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=message_content)
                ])
                
                # JSON 파싱 시도
                response_text = response.content.strip()
                # 마크다운 백틱 제거
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()
                    
                result = json.loads(response_text)
                return {
                    "score": int(result.get("score", 0)),
                    "reason": result.get("reason", "분석 사유가 제공되지 않았습니다.")
                }
                
            except Exception as e:
                print(f"LangChain 비전 분석 중 에러 발생, Fallback 로직 사용: {e}")
                # 에러 발생 시 아래의 규칙 기반 Fallback으로 넘어감

        # 2. Rule-based / Fuzzy Matching (Fallback 로직)
        # LLM 사용 불가 시 SequenceMatcher를 사용하여 가장 높은 유사도를 가진 단어를 찾음
        words = ocr_extracted_text.split()
        best_score = 0
        best_match = ""
        
        clean_input = input_name.replace(" ", "")
        
        for word in words:
            # 특수문자 제거 후 비교
            clean_word = "".join(filter(str.isalnum, word))
            if not clean_word:
                continue
                
            # difflib을 이용한 문자열 유사도 측정 (0.0 ~ 1.0)
            ratio = SequenceMatcher(None, clean_input, clean_word).ratio()
            score = int(ratio * 100)
            
            # 입력 이름이 텍스트에 완전히 포함된 경우 (예: "성명:오성준")
            if clean_input in clean_word:
                score = 100
                best_match = clean_word
                best_score = 100
                break
                
            if score > best_score:
                best_score = score
                best_match = clean_word
                
        # 점수 조정 및 리포트 작성
        if best_score >= 100:
            return {"score": 100, "reason": "입력된 이름이 텍스트 내에서 정확히 발견되었습니다."}
        elif best_score >= 70:
            return {"score": best_score, "reason": f"입력된 이름과 매우 유사한 텍스트('{best_match}')가 발견되어 오타/OCR 오류로 추정됩니다."}
        else:
            return {"score": best_score, "reason": f"입력된 이름과 일치하거나 유사한 텍스트를 찾지 못했습니다. 가장 비슷한 단어: '{best_match}'"}
