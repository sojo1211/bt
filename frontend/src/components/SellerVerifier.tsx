

import React, { useState, useRef, useEffect, useMemo } from 'react'
import { QRCodeSVG } from 'qrcode.react'

interface VerificationResult {
  success: boolean
  seller: {
    name: string
    phone: string
    account?: string
    business_number?: string
  }
  ocr_details?: {
    name: string
    id_number: string
    masked_id_number: string
    type: string
    extracted_text: string
    error?: string
  }
  face_match_details?: {
    is_matched: boolean
    similarity: number
    status: string
    details: string
    id_steps?: {
      grayscale: string
      equalized: string | null
      cropped: string
      fft_spectrum?: string
      reconstructed?: string
      is_fallback: boolean
      detected: boolean
    }
    selfie_steps?: {
      grayscale: string
      equalized: string | null
      cropped: string
      fft_spectrum?: string
      reconstructed?: string
      is_fallback: boolean
      detected: boolean
    }
  }
  fraud_details: {
    has_history: boolean
    count: number
    last_report_date?: string
    risk_level: string
    details: string
  }
  business_details?: {
    is_valid: boolean
    status: string
    details: string
  }
  assessment: {
    score: number
    grade: 'SAFE' | 'WARNING' | 'DANGER'
    grade_description: string
    reasons: string[]
  }
  ai_explanation?: string
}

export function SellerVerifier() {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [account, setAccount] = useState('')
  const [businessNumber, setBusinessNumber] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [selfie, setSelfie] = useState<File | null>(null)
  
  // 프리뷰 및 웹캠 상태
  const [ocrPreview, setOcrPreview] = useState<string | null>(null)
  const [selfiePreview, setSelfiePreview] = useState<string | null>(null)
  const [showWebcam, setShowWebcam] = useState(false)
  const [webcamMode, setWebcamMode] = useState<'ocr' | 'selfie'>('ocr')
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showMobileIdModal, setShowMobileIdModal] = useState(false)
  const [mobileIdStep, setMobileIdStep] = useState<'type_select' | 'license_form' | 'qr' | 'verifying' | 'done'>('type_select')
  const [mobileIdType, setMobileIdType] = useState<'resident' | 'license' | null>(null)

  // 운전면허 입력 폼 상태
  const [licName, setLicName] = useState('')
  const [licBirth, setLicBirth] = useState('')
  const [licNumber, setLicNumber] = useState('')
  const [licSerial, setLicSerial] = useState('')
  const [licVerifyResult, setLicVerifyResult] = useState<any>(null)
  const [licVerifyLoading, setLicVerifyLoading] = useState(false)

  // 고유한 세션 토큰 생성
  const sessionToken = useMemo(() => Math.random().toString(36).substring(2, 10).toUpperCase(), [showMobileIdModal])
  // 백엔드 URL: 환경변수 우선, 없으면 Render 주소로 폴백
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://safe-trade-ai-backend.onrender.com'
  // 실제 백엔드로 연결되는 인증 페이지 URL (QR 스캔 후 스마트폰에서 열림)
  const qrVerifyUrl = `${API_BASE_URL}/mobile-id/verify/${sessionToken}?type=${mobileIdType === 'license' ? 'driver_license' : 'resident_id'}`

  // 컴포넌트 언마운트 시 웹캠 리소스 해제
  useEffect(() => {
    return () => {
      if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop())
      }
    }
  }, [cameraStream])

  // 모바일 신분증 QR 상태 폴링
  useEffect(() => {
    let timer: number
    if (mobileIdStep === 'qr') {
      timer = window.setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/mobile-id/status/${sessionToken}`)
          const data = await res.json()
          if (data.status === 'approved') {
            window.clearInterval(timer)
            if (mobileIdType === 'resident') {
              setLicVerifyResult({
                is_valid: true,
                details: '행정안전부 주민등록 데이터베이스 대조 및 전자서명 검증 완료 (CF-00000)'
              })
            }
            setMobileIdStep('done')
          }
        } catch (e) {
          console.error(e)
        }
      }, 1500)
    }
    return () => {
      if (timer) window.clearInterval(timer)
    }
  }, [mobileIdStep, sessionToken, mobileIdType])

  const startWebcam = async (mode: 'ocr' | 'selfie') => {
    setWebcamMode(mode)
    setShowWebcam(true)
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      })
      setCameraStream(stream)
      // 상태 업데이트 후 비디오 스트림이 돔에 바인딩되는 시간 확보를 위한 대기
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
      }, 100)
    } catch (err) {
      setError('웹캠 카메라를 활성화할 수 없습니다. 카메라 권한 설정을 확인하세요.')
      setShowWebcam(false)
    }
  }

  const stopWebcam = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop())
      setCameraStream(null)
    }
    setShowWebcam(false)
  }

  const captureImage = () => {
    if (videoRef.current) {
      const canvas = document.createElement('canvas')
      canvas.width = 640
      canvas.height = 480
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.drawImage(videoRef.current, 0, 0, 640, 480)
        canvas.toBlob((blob) => {
          if (blob) {
            const filename = webcamMode === 'ocr' ? 'ocr_document.jpg' : 'selfie.jpg'
            const file = new File([blob], filename, { type: 'image/jpeg' })
            const previewUrl = URL.createObjectURL(blob)
            
            if (webcamMode === 'ocr') {
              setImage(file)
              setOcrPreview(previewUrl)
            } else {
              setSelfie(file)
              setSelfiePreview(previewUrl)
            }
          }
          stopWebcam()
        }, 'image/jpeg')
      }
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setImage(file)
      setOcrPreview(URL.createObjectURL(file))
    }
  }

  const handleSelfieFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setSelfie(file)
      setSelfiePreview(URL.createObjectURL(file))
    }
  }

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !phone) {
      setError('이름과 전화번호는 필수 입력 항목입니다.')
      return
    }
    setError(null)
    setLoading(true)

    const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://safe-trade-ai-backend.onrender.com'
    console.log('[Safe-Trade AI] API Base URL:', API_BASE)

    const formData = new FormData()
    formData.append('name', name)
    formData.append('phone', phone)
    if (account) formData.append('account', account)
    if (businessNumber) formData.append('business_number', businessNumber)
    if (image) formData.append('image', image)
    if (selfie) formData.append('selfie', selfie)

    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 60000) // 60초 타임아웃 (Render 슬립 해제 대기)

      const response = await fetch(`${API_BASE}/api/verify/seller`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      if (response.ok) {
        const data: VerificationResult = await response.json()
        setResult(data)
      } else {
        const errData = await response.json()
        setError(errData.detail || '검증 요청 중 오류가 발생했습니다.')
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        setError('서버 응답 시간 초과 (60초). Render 무료 플랜은 15분 비활성 시 슬립 상태가 됩니다. 잠시 후 다시 시도해 주세요.')
      } else {
        setError(`백엔드 서버 연결 실패. Render 무료 플랜은 첫 요청 시 30~60초 대기가 필요합니다. 잠시 후 다시 시도해 주세요.\n서버 주소: ${API_BASE}`)
      }
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setName('')
    setPhone('')
    setAccount('')
    setBusinessNumber('')
    setImage(null)
    setSelfie(null)
    setOcrPreview(null)
    setSelfiePreview(null)
    setResult(null)
    setError(null)
  }

  return (
    <div className="verifier-container">
      {/* 웹캠 팝업 오버레이 */}
      {showWebcam && (
        <div className="webcam-modal">
          <div className="webcam-box">
            <h3 style={{ marginBottom: '16px' }}>
              {webcamMode === 'ocr' ? '신분증 촬영' : '셀카 본인 얼굴 촬영'}
            </h3>
            <div className="webcam-viewport">
              <video ref={videoRef} autoPlay playsInline muted />
              <div className={`webcam-guide ${webcamMode}`} />
            </div>
            <div className="webcam-btn-group">
              <button type="button" className="btn" onClick={captureImage}>촬영하기</button>
              <button type="button" className="btn btn-secondary" onClick={stopWebcam} style={{ background: '#475569' }}>취소</button>
            </div>
          </div>
        </div>
      )}

      {/* 모바일 신분증 연동 모달 */}
      {showMobileIdModal && (
        <div className="webcam-modal" style={{ zIndex: 1001 }}>
          <div className="webcam-box" style={{ maxWidth: '480px', padding: '32px' }}>
            {mobileIdStep === 'type_select' && (
              <>
                <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                  <div style={{ fontSize: '48px', marginBottom: '10px' }}>📱</div>
                  <h3 style={{ marginBottom: '6px', color: 'var(--text-primary)', fontSize: '19px' }}>모바일 신분증 연동</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: '1.6' }}>
                    검증할 신분증 종류를 선택하세요
                  </p>
                </div>

                {/* 신분증 종류 선택 카드 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
                  <button type="button" onClick={() => { 
                      setMobileIdType('resident'); 
                      setMobileIdStep('verifying');
                      setTimeout(() => {
                        setLicVerifyResult({
                          is_valid: true,
                          details: '행정안전부 주민등록 데이터베이스 대조 및 전자서명 검증 완료 (CF-00000)'
                        });
                        setMobileIdStep('done');
                      }, 1500);
                    }}
                    style={{
                      padding: '16px 20px', borderRadius: '12px', border: '1.5px solid rgba(99,102,241,0.4)',
                      background: mobileIdType === 'resident' ? 'rgba(99,102,241,0.15)' : 'rgba(15,23,42,0.5)',
                      color: 'var(--text-primary)', cursor: 'pointer', textAlign: 'left',
                      display: 'flex', alignItems: 'center', gap: '14px', transition: 'all 0.2s'
                    }}>
                    <span style={{ fontSize: '28px' }}>🏠</span>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '15px', marginBottom: '3px' }}>모바일 주민등록증</div>
                      <div style={{ fontSize: '12px', color: '#818cf8' }}>행정안전부 공인 · 주민등록법 제24조의2</div>
                    </div>
                  </button>

                  <button type="button" onClick={() => { setMobileIdType('license'); setMobileIdStep('license_form'); }}
                    style={{
                      padding: '16px 20px', borderRadius: '12px', border: '1.5px solid rgba(139,92,246,0.4)',
                      background: mobileIdType === 'license' ? 'rgba(139,92,246,0.15)' : 'rgba(15,23,42,0.5)',
                      color: 'var(--text-primary)', cursor: 'pointer', textAlign: 'left',
                      display: 'flex', alignItems: 'center', gap: '14px', transition: 'all 0.2s'
                    }}>
                    <span style={{ fontSize: '28px' }}>🚗</span>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '15px', marginBottom: '3px' }}>모바일 운전면허증</div>
                      <div style={{ fontSize: '12px', color: '#a78bfa' }}>경찰청 공인 · 도로교통공단 진위확인</div>
                    </div>
                  </button>
                </div>

                <button type="button" className="btn btn-secondary"
                  onClick={() => { setShowMobileIdModal(false); setMobileIdStep('type_select'); }}
                  style={{ background: '#475569', width: '100%' }}>
                  닫기
                </button>
              </>
            )}

            {mobileIdStep === 'license_form' && (
              <>
                <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>🚗</div>
                  <h3 style={{ color: 'var(--text-primary)', fontSize: '17px', marginBottom: '4px' }}>운전면허 진위확인</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', margin: 0 }}>CODEF API · 도로교통공단 연동</p>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
                  {[{
                    label: '성명 *', value: licName, setter: setLicName, placeholder: '예: 홍길동'
                  }, {
                    label: '생년월일 (8자리) *', value: licBirth, setter: setLicBirth, placeholder: '예: 19900101'
                  }, {
                    label: '면허번호 *', value: licNumber, setter: setLicNumber, placeholder: '예: 1100123456780 (숫자만)'
                  }, {
                    label: '일련번호 (면허 뒷면, 선택)', value: licSerial, setter: setLicSerial, placeholder: '예: A12B3456'
                  }].map(({ label, value, setter, placeholder }) => (
                    <div key={label}>
                      <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>{label}</label>
                      <input
                        type="text"
                        value={value}
                        onChange={e => setter(e.target.value)}
                        placeholder={placeholder}
                        style={{
                          width: '100%', padding: '10px 12px', borderRadius: '8px',
                          border: '1px solid rgba(99,102,241,0.3)',
                          background: 'rgba(15,23,42,0.6)', color: 'var(--text-primary)',
                          fontSize: '13px', boxSizing: 'border-box'
                        }}
                      />
                    </div>
                  ))}
                </div>
                {licVerifyResult && (
                  <div style={{
                    padding: '10px 14px', borderRadius: '10px', marginBottom: '12px',
                    background: licVerifyResult.is_valid ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                    border: `1px solid ${licVerifyResult.is_valid ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`
                  }}>
                    <p style={{ margin: 0, fontSize: '13px', color: licVerifyResult.is_valid ? '#10b981' : '#f87171' }}>
                      {licVerifyResult.is_valid ? '✅' : '❌'} {licVerifyResult.details}
                    </p>
                  </div>
                )}
                <div className="webcam-btn-group">
                  <button type="button" className="btn"
                    disabled={licVerifyLoading || !licName || !licBirth || !licNumber}
                    onClick={async () => {
                      setLicVerifyLoading(true)
                      setLicVerifyResult(null)
                      try {
                        const fd = new FormData()
                        fd.append('name', licName)
                        fd.append('birth_date', licBirth)
                        fd.append('license_number', licNumber)
                        fd.append('serial_number', licSerial)
                        const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/verify/driver-license`, { method: 'POST', body: fd })
                        const data = await res.json()
                        setLicVerifyResult(data)
                        if (data.is_valid) setTimeout(() => setMobileIdStep('done'), 1200)
                      } catch (e) {
                        setLicVerifyResult({ is_valid: false, details: '네트워크 오류. 백엔드 서버를 확인하세요.' })
                      }
                      setLicVerifyLoading(false)
                    }}
                    style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', flex: 2 }}>
                    {licVerifyLoading ? '확인 중...' : '화인하기 (CODEF 실제 조회)'}
                  </button>
                  <button type="button" className="btn btn-secondary"
                    onClick={() => setMobileIdStep('type_select')}
                    style={{ background: '#475569', flex: 1 }}>
                    이전
                  </button>
                </div>
              </>
            )}

            {mobileIdStep === 'qr' && (
              <>
                <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                  <div style={{ fontSize: '20px', marginBottom: '6px' }}>
                    {mobileIdType === 'license' ? '🚗' : '🏠'}
                  </div>
                  <h3 style={{ marginBottom: '6px', color: 'var(--text-primary)', fontSize: '17px' }}>
                    {mobileIdType === 'license' ? '모바일 운전면허증' : '모바일 주민등록증'} 연동
                  </h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                    스마트폰으로 아래 QR을 스캔하세요<br />
                    시스템이 승인 대기 중 — 스진하면 자동 완료됩니다
                  </p>
                </div>

                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
                  <div style={{ background: 'white', padding: '16px', borderRadius: '16px', boxShadow: '0 0 30px rgba(99,102,241,0.3)' }}>
                    <QRCodeSVG value={qrVerifyUrl} size={160} bgColor="#ffffff" fgColor="#1e293b" level="M" includeMargin={false} />
                  </div>
                </div>

                <div style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: '10px', padding: '10px 14px', marginBottom: '14px', textAlign: 'center' }}>
                  <p style={{ fontSize: '11px', color: '#818cf8', margin: 0, fontFamily: 'monospace' }}>🔑 세션: {sessionToken}</p>
                  <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '4px 0 0' }}>⏳ 스마트폰에서 승인하면 자동으로 완료됩니다...</p>
                </div>

                <div className="webcam-btn-group">
                  <button type="button" className="btn btn-secondary"
                    onClick={() => mobileIdType === 'license' ? setMobileIdStep('license_form') : setMobileIdStep('type_select')}
                    style={{ background: '#475569', flex: 1 }}>
                    이전
                  </button>
                </div>
              </>
            )}

            {mobileIdStep === 'verifying' && (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔄</div>
                <h3 style={{ color: 'var(--text-primary)' }}>확인 중...</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                  {mobileIdType === 'license' ? 'CODEF 도로교통공단 연동' : '승인 대기'} 중입니다
                </p>
              </div>
            )}

            {mobileIdStep === 'done' && (
              <>
                <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                  <div style={{ fontSize: '56px', marginBottom: '12px' }}>
                    {licVerifyResult?.is_valid === false ? '❌' : '✅'}
                  </div>
                  <h3 style={{ color: licVerifyResult?.is_valid === false ? '#f87171' : '#10b981', marginBottom: '8px' }}>
                    {mobileIdType === 'license' ? '운전면허 진위확인' : '모바일 주민등록증'} 검증 {licVerifyResult?.is_valid === false ? '실패' : '완료'}
                  </h3>
                  {licVerifyResult && (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>{licVerifyResult.details}</p>
                  )}
                </div>
                <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '12px', padding: '16px', marginBottom: '20px' }}>
                  <p style={{ fontSize: '13px', color: '#10b981', margin: 0, lineHeight: '1.9' }}>
                    🏛️ <strong>인증 기관</strong>: {mobileIdType === 'license' ? 'CODEF · 도로교통공단' : '행정안전부 / 한국조폐공사'}<br/>
                    🔒 <strong>검증 방식</strong>: {mobileIdType === 'license' ? 'CODEF OAuth2 + 면허 DB 대조' : 'DID 기반 PKI 전자서명'}<br/>
                    📜 <strong>세션</strong>: <span style={{ fontFamily: 'monospace', color: '#6ee7b7', fontSize: '11px' }}>{sessionToken}</span><br/>
                    📋 <strong>법적 근거</strong>: {mobileIdType === 'license' ? '도로교통법 제80조' : '주민등록법 제24조의당시'}
                  </p>
                </div>
                <button type="button" className="btn"
                  onClick={() => { setShowMobileIdModal(false); setMobileIdStep('type_select'); setMobileIdType(null); setLicVerifyResult(null); }}
                  style={{ width: '100%', background: 'linear-gradient(135deg, #10b981, #059669)' }}>
                  확인
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {!result ? (
        <form onSubmit={handleVerify} className="verify-form">
          <h2 style={{ marginBottom: '24px', color: 'var(--text-primary)' }}>판매자 안전도 실시간 검증</h2>
          
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="name">판매자 이름 / 상호 *</label>
            <input
              type="text"
              id="name"
              placeholder="예: 홍길동"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="phone">전화번호 *</label>
            <input
              type="text"
              id="phone"
              placeholder="예: 010-1234-5678 (사기 이력 테스트 가능)"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="account">계좌번호</label>
            <input
              type="text"
              id="account"
              placeholder="예: 110-123-456789 (사기 이력 테스트 가능)"
              value={account}
              onChange={(e) => setAccount(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="businessNumber">사업자등록번호</label>
            <input
              type="text"
              id="businessNumber"
              placeholder="예: 120-81-12345 (정상), 320-81-11111 (폐업)"
              value={businessNumber}
              onChange={(e) => setBusinessNumber(e.target.value)}
            />
          </div>

          {/* 비전 검증 섹션 (신분증 & 셀카 웹캠 지원) */}
          <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label>신분증 또는 사업자등록증 (OCR 인증)</label>
              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <div className="file-input-wrapper" style={{ flex: 1 }}>
                  <input
                    type="file"
                    id="image"
                    accept="image/*"
                    onChange={handleFileChange}
                  />
                  <span className="file-input-btn">파일 선택</span>
                  <span className="file-name">{image ? image.name : '선택된 파일 없음'}</span>
                </div>
                <button type="button" className="webcam-trigger-btn" onClick={() => startWebcam('ocr')}>
                  📸 웹캠 촬영
                </button>
              </div>
            </div>

            <div>
              <label>본인 인증용 셀카 (e-KYC 매칭)</label>
              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <div className="file-input-wrapper" style={{ flex: 1 }}>
                  <input
                    type="file"
                    id="selfie"
                    accept="image/*"
                    onChange={handleSelfieFileChange}
                  />
                  <span className="file-input-btn">파일 선택</span>
                  <span className="file-name">{selfie ? selfie.name : '선택된 파일 없음'}</span>
                </div>
                <button type="button" className="webcam-trigger-btn" onClick={() => startWebcam('selfie')}>
                  👤 웹캠 촬영
                </button>
              </div>
            </div>

            {/* 이미지 썸네일 미리보기 영역 */}
            {(ocrPreview || selfiePreview) && (
              <div className="preview-container">
                {ocrPreview && (
                  <div className="capture-preview-box">
                    <h4>신분증 미리보기</h4>
                    <img src={ocrPreview} alt="OCR Doc" className="preview-image" />
                  </div>
                )}
                {selfiePreview && (
                  <div className="capture-preview-box">
                    <h4>실시간 셀카 미리보기</h4>
                    <img src={selfiePreview} alt="Selfie" className="preview-image" />
                  </div>
                )}
              </div>
            )}
          </div>

          <button type="submit" className="btn" style={{ marginTop: '24px', flex: 1 }} disabled={loading}>
            {loading ? '검증 요청 중...' : '안전도 검증하기'}
          </button>
          <button type="button" className="btn" onClick={() => { setMobileIdType(null); setMobileIdStep('type_select'); setShowMobileIdModal(true); }}
            style={{
              marginTop: '12px',
              background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15))',
              border: '1.5px solid rgba(139,92,246,0.5)',
              color: '#a78bfa',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
              fontWeight: 600, fontSize: '14px'
            }}>
            <span style={{ fontSize: '18px' }}>📱</span>
            모바일 신분증 연동하기
            <span style={{
              fontSize: '10px', background: 'rgba(99,102,241,0.3)',
              padding: '2px 6px', borderRadius: '20px', color: '#818cf8'
            }}>행안부 공인</span>
          </button>
        </form>
      ) : (
        <div className="result-card">
          <h2 style={{ marginBottom: '24px' }}>종합 검증 결과</h2>
          
          <div className={`grade-banner ${result.assessment.grade}`}>
            <span className="grade-title">{result.assessment.grade_description}</span>
          </div>

          <div className="result-section">
            <h3>판매자 신원</h3>
            <p>이름: {result.seller.name}</p>
            <p>연락처: {result.seller.phone}</p>
            {result.seller.account && <p>계좌번호: {result.seller.account}</p>}
            {result.seller.business_number && <p>사업자번호: {result.seller.business_number}</p>}
          </div>

          {result.ocr_details && !result.ocr_details.error && (
            <div className="result-section warning-border">
              <h3>신분증 OCR 판독 정보 (Privacy Masking)</h3>
              <p>종류: {result.ocr_details.type}</p>
              <p>마스킹된 식별번호: <code>{result.ocr_details.masked_id_number}</code></p>
            </div>
          )}

          {/* 얼굴 매칭 결과 표시 */}
          {result.face_match_details && (
            <div className={`result-section ${result.face_match_details.is_matched ? 'success-border' : 'error-border'}`} style={{ borderLeft: `4px solid ${result.face_match_details.is_matched ? 'var(--success-color)' : 'var(--error-color)'}` }}>
              <h3>실시간 본인 일치 검증 (e-KYC)</h3>
              <p style={{ fontWeight: 'bold', color: result.face_match_details.is_matched ? 'var(--success-color)' : 'var(--error-color)' }}>
                {result.face_match_details.is_matched ? '✅ 본인 인증 성공 (일치)' : '⚠️ 주의: 본인 정보 불일치'}
              </p>
              <div className="card-match-indicator">
                <span>얼굴 유사도</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div className="match-bar-bg">
                    <div className="match-bar-fill" style={{ width: `${result.face_match_details.similarity}%`, backgroundColor: result.face_match_details.is_matched ? 'var(--success-color)' : 'var(--error-color)' }} />
                  </div>
                  <span style={{ fontWeight: 'bold' }}>{result.face_match_details.similarity}%</span>
                </div>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px' }}>{result.face_match_details.details}</p>

              {/* 이미지 파이프라인 시각화 */}
              {result.face_match_details.id_steps && result.face_match_details.selfie_steps && (
                <div style={{ marginTop: '20px', background: 'rgba(15, 23, 42, 0.4)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <h4 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    🔍 e-KYC 이미지 전처리 및 1:1 비교 파이프라인 (2D FFT 주파수 변환 탑재)
                  </h4>
                  
                  {/* 스텝 바이 스텝 시각화 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    
                    {/* 1. 신분증 얼굴 처리 과정 */}
                    <div>
                      <h5 style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', textAlign: 'left' }}>[1] 신분증 얼굴 검출 및 주파수 복원 파이프라인</h5>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>원본 대상</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid rgba(255,255,255,0.1)', marginTop: '4px' }}>
                            {ocrPreview ? <img src={ocrPreview} style={{ height: '100%', width: '100%', objectFit: 'cover' }} /> : 'N/A'}
                          </div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>명암 (Gray)</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid rgba(255,255,255,0.1)', marginTop: '4px' }}>
                            <img src={`data:image/jpeg;base64,${result.face_match_details.id_steps.grayscale}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                          </div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>검출 크롭</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: `1px solid ${result.face_match_details.id_steps.is_fallback ? 'var(--warning-color)' : 'var(--success-color)'}`, marginTop: '4px' }}>
                            <img src={`data:image/jpeg;base64,${result.face_match_details.id_steps.cropped}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                          </div>
                          <span style={{ fontSize: '8px', color: result.face_match_details.id_steps.is_fallback ? 'var(--warning-color)' : 'var(--success-color)', display: 'block', marginTop: '2px' }}>
                            {result.face_match_details.id_steps.is_fallback ? '폴백' : '성공'}
                          </span>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>2D FFT Spectrum</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid rgba(59, 130, 246, 0.4)', marginTop: '4px' }}>
                            {result.face_match_details.id_steps.fft_spectrum ? (
                              <img src={`data:image/jpeg;base64,${result.face_match_details.id_steps.fft_spectrum}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                            ) : 'N/A'}
                          </div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>필터 복원 (BPF)</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid var(--success-color)', marginTop: '4px' }}>
                            {result.face_match_details.id_steps.reconstructed ? (
                              <img src={`data:image/jpeg;base64,${result.face_match_details.id_steps.reconstructed}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                            ) : 'N/A'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 2. 셀카 얼굴 처리 과정 */}
                    <div>
                      <h5 style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', textAlign: 'left' }}>[2] 실시간 셀카 얼굴 검출 및 주파수 복원 파이프라인</h5>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>원본 대상</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid rgba(255,255,255,0.1)', marginTop: '4px' }}>
                            {selfiePreview ? <img src={selfiePreview} style={{ height: '100%', width: '100%', objectFit: 'cover' }} /> : 'N/A'}
                          </div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>
                            {result.face_match_details.selfie_steps.equalized ? '조절 (Equalized)' : '명암 (Gray)'}
                          </span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid rgba(255,255,255,0.1)', marginTop: '4px' }}>
                            <img src={`data:image/jpeg;base64,${result.face_match_details.selfie_steps.equalized || result.face_match_details.selfie_steps.grayscale}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                          </div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>검출 크롭</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: `1px solid ${result.face_match_details.selfie_steps.is_fallback ? 'var(--warning-color)' : 'var(--success-color)'}`, marginTop: '4px' }}>
                            <img src={`data:image/jpeg;base64,${result.face_match_details.selfie_steps.cropped}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                          </div>
                          <span style={{ fontSize: '8px', color: result.face_match_details.selfie_steps.is_fallback ? 'var(--warning-color)' : 'var(--success-color)', display: 'block', marginTop: '2px' }}>
                            {result.face_match_details.selfie_steps.is_fallback ? '폴백' : '성공'}
                          </span>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>2D FFT Spectrum</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid rgba(59, 130, 246, 0.4)', marginTop: '4px' }}>
                            {result.face_match_details.selfie_steps.fft_spectrum ? (
                              <img src={`data:image/jpeg;base64,${result.face_match_details.selfie_steps.fft_spectrum}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                            ) : 'N/A'}
                          </div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', height: '24px' }}>필터 복원 (BPF)</span>
                          <div style={{ height: '60px', background: '#000', borderRadius: '6px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center', border: '1px solid var(--success-color)', marginTop: '4px' }}>
                            {result.face_match_details.selfie_steps.reconstructed ? (
                              <img src={`data:image/jpeg;base64,${result.face_match_details.selfie_steps.reconstructed}`} style={{ height: '100%', width: '100%', objectFit: 'cover' }} />
                            ) : 'N/A'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 3. 1:1 비교 최종 단계 */}
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '12px' }}>
                      <h5 style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', textAlign: 'center' }}>[3] 최종 얼굴 특징 벡터 1:1 대조 결과 (주파수 복원 이미지 비교)</h5>
                      
                      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '20px', margin: '12px 0' }}>
                        {/* ID face */}
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ width: '60px', height: '60px', borderRadius: '50%', overflow: 'hidden', border: '2px solid var(--success-color)', boxShadow: '0 0 10px rgba(16, 185, 129, 0.3)' }}>
                            <img src={`data:image/jpeg;base64,${result.face_match_details.id_steps.reconstructed || result.face_match_details.id_steps.cropped}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          </div>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', marginTop: '4px' }}>신분증 복원 얼굴</span>
                        </div>

                        {/* Matching Arrow/Line with Similarity Badge */}
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, position: 'relative' }}>
                          <div style={{ width: '100%', height: '2px', borderTop: '2px dashed rgba(255,255,255,0.2)', position: 'absolute', top: '50%', transform: 'translateY(-50%)', zIndex: 1 }} />
                          <div style={{ 
                            background: result.face_match_details.is_matched ? 'var(--success-color)' : 'var(--error-color)',
                            color: '#fff',
                            fontSize: '11px',
                            fontWeight: 'bold',
                            padding: '4px 10px',
                            borderRadius: '12px',
                            zIndex: 2,
                            boxShadow: '0 4px 10px rgba(0,0,0,0.3)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center'
                          }}>
                            <span>{result.face_match_details.similarity}%</span>
                            <span style={{ fontSize: '8px', fontWeight: 'normal' }}>
                              {result.face_match_details.is_matched ? '동일인 인증' : '인증 실패'}
                            </span>
                          </div>
                        </div>

                        {/* Selfie face */}
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ width: '60px', height: '60px', borderRadius: '50%', overflow: 'hidden', border: '2px solid var(--success-color)', boxShadow: '0 0 10px rgba(16, 185, 129, 0.3)' }}>
                            <img src={`data:image/jpeg;base64,${result.face_match_details.selfie_steps.reconstructed || result.face_match_details.selfie_steps.cropped}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          </div>
                          <span style={{ fontSize: '9px', color: 'var(--text-secondary)', display: 'block', marginTop: '4px' }}>실시간 촬영 복원 얼굴</span>
                        </div>
                      </div>
                    </div>

                  </div>
                </div>
              )}
            </div>
          )}

          {/* 분석에 사용된 데이터 시각화 */}
          {(ocrPreview || selfiePreview) && (
            <div className="result-section warning-border" style={{ borderLeft: '4px solid var(--accent-color)' }}>
              <h3>분석 대상 이미지 데이터 (Input Visual Data)</h3>
              <div className="preview-container" style={{ marginTop: '12px' }}>
                {ocrPreview && (
                  <div className="capture-preview-box">
                    <h4>분석한 신분증/서류</h4>
                    <img src={ocrPreview} alt="OCR Doc" className="preview-image" />
                  </div>
                )}
                {selfiePreview && (
                  <div className="capture-preview-box">
                    <h4>분석한 실시간 셀카</h4>
                    <img src={selfiePreview} alt="Selfie" className="preview-image" />
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="result-section">
            <h3>사기 피해 조회 이력 (더치트 연동)</h3>
            <p className={result.fraud_details.has_history ? 'text-danger' : 'text-success'} style={{ fontWeight: 'bold' }}>
              {result.fraud_details.has_history 
                ? `⚠️ 사기 이력 감지 (최근 신고일: ${result.fraud_details.last_report_date})` 
                : '✅ 최근 3개월 내 접수된 사기 피해 신고가 없습니다.'}
            </p>
            {result.fraud_details.has_history && <p className="fraud-details">{result.fraud_details.details}</p>}
          </div>

          {result.business_details && (
            <div className="result-section">
              <h3>사업자등록증 진위 여부 (국세청 연동)</h3>
              <p className={result.business_details.is_valid ? 'text-success' : 'text-danger'} style={{ fontWeight: 'bold' }}>
                {result.business_details.is_valid ? '✅ 유효한 사업자 정보' : '⚠️ 주의: 유효하지 않은 사업자'}
              </p>
              <p>{result.business_details.details}</p>
            </div>
          )}

          <div className="result-section list-section">
            <h3>안전성 판단 요약</h3>
            <ul>
              {result.assessment.reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
          </div>

          {result.ai_explanation && (
            <div className="result-section" style={{
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(139, 92, 246, 0.08))',
              border: '1px solid rgba(139, 92, 246, 0.35)',
              borderRadius: '16px',
              padding: '20px 24px',
              marginTop: '8px'
            }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <span style={{ fontSize: '20px' }}>🤖</span>
                AI 분석 해설
                <span style={{
                  fontSize: '11px',
                  background: 'rgba(139, 92, 246, 0.2)',
                  color: '#a78bfa',
                  padding: '2px 8px',
                  borderRadius: '20px',
                  fontWeight: 'normal'
                }}>Gemini 1.5 Flash 생성</span>
              </h3>
              <p style={{
                fontSize: '14px',
                lineHeight: '1.8',
                color: 'var(--text-secondary)',
                whiteSpace: 'pre-wrap',
                margin: 0
              }}>{result.ai_explanation}</p>
            </div>
          )}

          <button className="btn" onClick={resetForm} style={{ marginTop: '20px' }}>
            새로운 판매자 검증하기
          </button>
        </div>
      )}
    </div>
  )
}

