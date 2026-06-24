import os
import json
from typing import Dict, Any, Optional

from .base import BaseRiskAnalyzerService

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.schema import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class RiskAnalyzerService(BaseRiskAnalyzerService):
    def __init__(self):
        # 사용자가 제공한 Gemini API Key 하드코딩
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.use_langchain = LANGCHAIN_AVAILABLE and bool(self.api_key)
        
        if self.use_langchain:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.0,
                google_api_key=self.api_key
            )

    async def assess_risk(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        각종 검증 결과(사기, 사업자, 신원 일치도 등)를 종합하여 
        관련 법령 및 e-KYC 가이드라인에 근거한 위험도 평가를 수행합니다.
        """
        if not self.use_langchain:
            return self._fallback_assess_risk(context)

        try:
            system_prompt = """
            당신은 전자금융거래법, 자금세탁방지(AML) 규정, 전자상거래법 및 금융위원회 비대면 실명확인 가이드라인을 엄격히 준수하는 최고 컴플라이언스(Compliance) 심사역 AI입니다.
            제공된 사용자의 '검증 결과 데이터(Context)'를 바탕으로 종합적인 위험도 점수(0~100)와 안전 등급(SAFE, WARNING, DANGER), 그리고 이에 대한 상세한 법적/규제적 근거를 산정하세요.

            [규제 참조 기준]
            1. 사기 이력이 존재하는 경우: '통신사기피해환급법' 및 '자금세탁방지(AML) 가이드라인 고위험 거래'에 의거하여 강력한 감점을 부여하고 즉시 DANGER 등급을 부여해야 합니다.
            2. 사업자 진위 확인 실패: '전자상거래 등에서의 소비자보호에 관한 법률 제12조(신원정보의 제공)' 위반 소지가 있으므로 상당한 감점 및 WARNING 이상 등급이 필요합니다.
            3. 신원/안면 인증(e-KYC) 실패: '금융위원회 비대면 실명확인 관련 구체적 적용방안'의 본인확인 의무 불충족 사유로 판단하여 감점합니다.

            평가 후, 반드시 아래 JSON 형식으로만 반환하세요.
            {
                "score": <최종 점수 0~100 사이 정수>,
                "grade": "<SAFE, WARNING, DANGER 중 하나>",
                "grade_description": "<매우 안전, 거래 주의, 위험 등 한국어 설명>",
                "reasons": [
                    "<어떤 규제/법령에 근거하여 어떤 문제가 있는지 설명하는 문장 1>",
                    "<문장 2>"
                ]
            }

            *주의사항*: 점수 산정 시 임의로 부여하지 말고 반드시 규제에 기반하여 서술하세요. 위반 사항이 전혀 없으면 100점과 함께 "모든 관련 금융 및 전자상거래 규정을 충족하며, 자금세탁방지(AML) 및 비대면 실명확인 가이드라인에 따른 위험 요소가 발견되지 않았습니다." 등의 전문적인 이유를 반환하세요.
            """

            # 컨텍스트에서 이미지 바이너리 데이터와 Base64 등 너무 큰 데이터는 제외하고 전달
            filtered_context = {}
            for k, v in context.items():
                if isinstance(v, dict):
                    filtered_v = {}
                    for k2, v2 in v.items():
                        if "base64" not in k2.lower() and "steps" not in k2.lower():
                            filtered_v[k2] = v2
                    filtered_context[k] = filtered_v
                else:
                    filtered_context[k] = v

            user_prompt = f"다음은 사용자의 검증 데이터입니다. 평가를 진행해주세요.\n\n{json.dumps(filtered_context, ensure_ascii=False, indent=2)}"

            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            response_text = response.content.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()

            result = json.loads(response_text)
            
            # 응답 스키마 보정
            return {
                "score": int(result.get("score", 0)),
                "grade": result.get("grade", "DANGER"),
                "grade_description": result.get("grade_description", "위험"),
                "reasons": result.get("reasons", ["평가 결과 반환 실패"])
            }

        except Exception as e:
            print(f"Risk Analyzer LLM Error: {e}")
            return self._fallback_assess_risk(context)

    def _fallback_assess_risk(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """LLM 호출 실패 시 기존과 유사한 하드코딩 룰 기반 대체 분석 (에러 방지용)"""
        score = 100
        reasons = []

        fraud = context.get("fraud_result", {})
        if fraud.get("has_history"):
            score -= 50
            reasons.append("통신사기피해환급법 등에 의거하여 사기 이력이 확인되어 거래 위험도가 높습니다.")

        business = context.get("business_result")
        if business and not business.get("is_valid"):
            score -= 30
            reasons.append("전자상거래법 신원정보 제공 의무 위반 소지 (사업자 진위 불일치).")

        face = context.get("face_match_result", {})
        if face and not face.get("is_matched"):
            score -= 40
            reasons.append("금융위 비대면 실명확인 가이드라인 미충족 (안면 인증 불일치).")

        grade = "SAFE"
        grade_desc = "매우 안전"
        if score < 60:
            grade = "DANGER"
            grade_desc = "위험 (사기 연루 가능성 높음)"
        elif score < 90:
            grade = "WARNING"
            grade_desc = "거래 주의"

        if score == 100:
            reasons.append("자금세탁방지(AML) 및 비대면 실명확인 가이드라인 상 위험 요소 없음.")

        return {
            "score": max(0, score),
            "grade": grade,
            "grade_description": grade_desc,
            "reasons": reasons
        }
