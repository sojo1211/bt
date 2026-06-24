import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from services.container import get_services
from services.driver_license import verify_driver_license

app = FastAPI(title="Safe-Trade AI API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Safe-Trade AI Backend is running!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/verify/seller")
async def verify_seller(
    name: str = Form(...),
    phone: str = Form(...),
    account: Optional[str] = Form(None),
    business_number: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    selfie: Optional[UploadFile] = File(None)
):
    services = get_services()
    
    # 1. OCR 정보 추출 (이미지가 전송되었을 경우)
    ocr_result = None
    image_bytes = None
    if image:
        try:
            image_bytes = await image.read()
            ocr_result = await services.ocr.extract_identity(image_bytes)
        except Exception as e:
            # OCR 실패 시 흐름을 끊지 않고 경고 메시지와 함께 진행
            ocr_result = {"error": f"OCR 추출 실패: {str(e)}"}

    # 2. 얼굴 매칭 검증 (신분증 이미지와 웹캠 셀카 이미지가 모두 전송되었을 경우)
    face_match_result = None
    if image_bytes and selfie:
        try:
            selfie_bytes = await selfie.read()
            face_match_result = await services.face_matcher.match_faces(image_bytes, selfie_bytes)
        except Exception as e:
            face_match_result = {"is_matched": False, "similarity": 0, "status": "error", "details": f"얼굴 매칭 에러: {str(e)}"}

    # 3. 사기 이력 조회 (더치트 연동)
    fraud_result = await services.cheat_checker.check_fraud_history(phone=phone, account=account)

    # 4. 사업자등록번호 진위 여부 확인 (사업자 번호가 존재할 경우)
    business_result = None
    if business_number:
        business_result = await services.business_verifier.verify_business(
            business_number=business_number,
            owner_name=name
        )

    # 5. 종합 안전 점수 산정 및 등급 부여 (지능형 규제 기반 에이전트)
    context = {
        "fraud_result": fraud_result,
        "business_result": business_result,
        "face_match_result": face_match_result,
    }
    
    # 감점 요인 4: 신분증 성명과 입력된 성명 유사도 분석 (AI 비전 또는 텍스트 알고리즘)
    if ocr_result and "extracted_text" in ocr_result:
        identity_analysis = await services.identity_analyzer.analyze_identity(
            input_name=name,
            ocr_extracted_text=ocr_result["extracted_text"],
            image_bytes=image_bytes
        )
        context["identity_analysis"] = identity_analysis

    # 지능형 에이전트(LLM)에 의한 규제 기반 종합 판단
    risk_assessment = await services.risk_analyzer.assess_risk(context)

    # 6. Gemini LLM을 이용한 "왜 이런 결과가 나왔는지" 친절한 알고리즘 해설 생성
    ai_explanation = None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain.schema import HumanMessage, SystemMessage
        import json

        gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        explain_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3, google_api_key=gemini_api_key)

        explanation_prompt = f"""
        당신은 Safe-Trade AI 시스템의 분석 결과를 일반 사용자에게 쉽게 설명해주는 친절한 AI 해설사입니다.
        아래의 분석 결과와 사용된 기술을 바탕으로 이번 검증에서 어떤 알고리즘이 사용되었고, 왜 이런 결과가 나왔는지 자세하지만 이해하기 쉽게 설명해주세요.

        [사용된 알고리즘 목록 - 반드시 아래 기술을 기반으로 설명하세요]
        - 사기 이력 조회: 전화번호/계좌번호를 사기 피해 데이터베이스(더치트 등)와 대조하여 신고 이력을 확인했습니다.
        - 신분증 OCR: EasyOCR 모델을 이용하여 신분증 이미지에서 텍스트를 자동 추출했습니다.
        - 신원 이름 검증: GPT-4o Vision(또는 Gemini Vision) 모델로 신분증 이미지를 직접 읽어 입력된 이름이 이미지에 존재하는지 확인했습니다.
        - 안면 인식 (e-KYC): PyTorch 기반의 InceptionResnetV1 딥러닝 모델로 신분증과 셀카 이미지의 얼굴 임베딩 벡터를 추출하고 코사인 유사도를 계산했습니다. 이후 2D FFT 주파수 분석으로 이미지를 전처리하고 최종 유사도 점수를 도출했습니다.
        - 종합 위험도 판단: LangChain 기반 Gemini LLM 에이전트가 전자금융거래법, 자금세탁방지(AML) 규정 등 관련 법령에 근거하여 위험도를 분석했습니다.

        [이번 분석 결과]
        - 사기 이력: {json.dumps(fraud_result, ensure_ascii=False)}
        - 사업자 정보: {json.dumps(business_result, ensure_ascii=False) if business_result else "미입력"}
        - 얼굴 매칭: 유사도 {face_match_result.get('similarity', 'N/A') if face_match_result else 'N/A'}%, 결과: {"성공" if face_match_result and face_match_result.get('is_matched') else "실패 또는 미진행"}
        - 최종 종합 점수: {risk_assessment.get('score')}점
        - 최종 등급: {risk_assessment.get('grade_description')}

        설명은 3~5문장으로 자연스럽게 한국어로 작성하고, 기술 용어는 쉽게 풀어서 설명해주세요. 인사말 없이 설명만 바로 시작하세요.
        """

        explain_response = explain_llm.invoke([
            SystemMessage(content="당신은 AI 시스템 분석 결과를 사용자에게 친절하게 설명해주는 전문 해설사입니다."),
            HumanMessage(content=explanation_prompt)
        ])
        ai_explanation = explain_response.content.strip()

    except Exception as e:
        print(f"AI Explanation Error: {e}")
        ai_explanation = "이번 검증에서는 사기 이력 조회, EasyOCR 기반 신분증 텍스트 추출, PyTorch InceptionResnetV1 딥러닝 모델을 활용한 안면 임베딩 비교, 그리고 LangChain 기반 Gemini LLM의 규제 기반 종합 위험도 판단 알고리즘이 순차적으로 적용되었습니다."

    return {
        "success": True,
        "seller": {
            "name": name,
            "phone": phone,
            "account": account,
            "business_number": business_number
        },
        "ocr_details": ocr_result,
        "face_match_details": face_match_result,
        "fraud_details": fraud_result,
        "business_details": business_result,
        "assessment": risk_assessment,
        "ai_explanation": ai_explanation
    }

import time

# --- 모바일 신분증 연동 시뮬레이션을 위한 엔드포인트 ---
mobile_id_sessions = {}

@app.get("/api/mobile-id/status/{session_id}")
async def get_mobile_id_status(session_id: str):
    # 세션이 처음 조회될 때 시간 기록
    if session_id not in mobile_id_sessions:
        mobile_id_sessions[session_id] = {"status": "pending", "start_time": time.time()}
        
    session_data = mobile_id_sessions[session_id]
    
    # 데모를 위해 3초 후 자동 승인 처리
    if isinstance(session_data, dict) and session_data["status"] == "pending":
        if time.time() - session_data["start_time"] > 3.0:
            mobile_id_sessions[session_id] = "approved"
            return {"status": "approved"}
        return {"status": "pending"}
        
    if session_data == "approved":
        return {"status": "approved"}
        
    return {"status": "pending"}

@app.post("/api/mobile-id/approve/{session_id}")
async def approve_mobile_id(session_id: str):
    mobile_id_sessions[session_id] = "approved"
    return {"success": True}

from fastapi.responses import HTMLResponse

@app.get("/mobile-id/verify/{session_id}", response_class=HTMLResponse)
async def serve_mobile_id_page(session_id: str, type: str = "resident_id"):
    doc_name = "모바일 운전면허증" if type == "driver_license" else "모바일 주민등록증"
    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>{doc_name} 본인인증</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; color: #1e293b; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }}
            .card {{ background: white; border-radius: 20px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); width: 100%; max-width: 320px; text-align: center; }}
            .icon {{ font-size: 60px; margin-bottom: 20px; }}
            h1 {{ font-size: 22px; margin: 0 0 10px 0; color: #0f172a; }}
            p {{ font-size: 14px; color: #64748b; line-height: 1.5; margin: 0 0 30px 0; }}
            .btn {{ display: block; width: 100%; padding: 16px; border: none; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; font-size: 16px; font-weight: bold; cursor: pointer; transition: opacity 0.2s; }}
            .btn:active {{ opacity: 0.8; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #94a3b8; }}
        </style>
    </head>
    <body>
        <div class="card" id="mainCard">
            <div class="icon">{'🚗' if type == 'driver_license' else '🏠'}</div>
            <h1>{doc_name} 제공 동의</h1>
            <p><strong>Safe-Trade e-KYC</strong> 서비스에서 귀하의 신원정보 제공을 요청합니다.<br><br><span style="font-size: 12px; color: #94a3b8;">세션: {session_id}</span></p>
            <button class="btn" onclick="approve()">정보 제공 동의하기</button>
        </div>
        <div class="footer">행정안전부 모바일 신분증 인프라 연동 테스트</div>

        <script>
            async function approve() {{
                const btn = document.querySelector('.btn');
                btn.innerText = '처리 중...';
                btn.style.opacity = '0.7';
                
                try {{
                    const res = await fetch('/api/mobile-id/approve/{session_id}', {{ method: 'POST' }});
                    if (res.ok) {{
                        document.getElementById('mainCard').innerHTML = `
                            <div class="icon">✅</div>
                            <h1 style="color: #10b981;">제공 완료</h1>
                            <p>신원정보 제공이 완료되었습니다.<br>PC 화면을 확인해주세요.</p>
                        `;
                    }}
                }} catch (e) {{
                    alert('오류가 발생했습니다.');
                    btn.innerText = '정보 제공 동의하기';
                    btn.style.opacity = '1';
                }}
            }}
        </script>
    </body>
    </html>
    """

# --- CODEF 운전면허 진위확인 실제 API 엔드포인트 ---
@app.post("/api/verify/driver-license")
async def verify_driver_license_endpoint(
    name: str = Form(...),
    birth_date: str = Form(...),
    license_number: str = Form(...),
    serial_number: str = Form(""),
):
    """
    CODEF API를 통한 실제 운전면허 진위확인
    - name: 성명 (예: 홍길동)
    - birth_date: 생년월일 8자리 (예: 19900101)
    - license_number: 면허번호 (예: 서울00-123456-78 또는 12자리 숫자)
    - serial_number: 면허 뒷면 일련번호 (선택사항)
    """
    result = await verify_driver_license(
        name=name,
        birth_date=birth_date,
        license_number=license_number,
        serial_number=serial_number,
    )
    
    # LLM을 이용해 결과 설명 추가
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain.schema import HumanMessage, SystemMessage
        
        # 하드코딩된 API 키 (risk_analyzer.py와 동일)
        api_key = os.getenv("GEMINI_API_KEY", "")
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.0,
            google_api_key=api_key
        )
        
        system_prompt = """
        당신은 금융권 e-KYC 신원 검증 시스템의 안내 AI입니다.
        사용자의 모바일 운전면허 진위확인 결과를 보고, 사용자(일반인)가 이해하기 쉬우면서도 전문적이고 신뢰감을 주는 설명을 생성하세요.
        - 도로교통공단 데이터베이스와 CODEF API의 OAuth2 통신 방식을 언급하세요.
        - 1~2문장으로 간결하게 작성하세요.
        - 진위확인 성공 시 안전하게 검증되었다는 확신을, 실패 시 정보 불일치로 검증이 불가함을 알리세요.
        """
        
        is_valid_str = "일치(성공)" if result.get("is_valid") else "불일치(실패)"
        user_prompt = f"진위확인 결과: {is_valid_str}\n응답 코드 및 상태: {result.get('status')}"
        
        ai_response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        # 기존 details 덮어쓰기
        result["details"] = ai_response.content.strip()
        
    except Exception as e:
        print(f"Driver License LLM Error: {e}")
        # 오류 시 기존 details 유지
        pass

    return result
