import { useState, useEffect } from 'react'
import { SellerVerifier } from './components/SellerVerifier'

function App() {
  const [backendStatus, setBackendStatus] = useState<'loading' | 'online' | 'offline'>('loading')
  const [lastChecked, setLastChecked] = useState<string>('-')

  const checkHealth = async () => {
    setBackendStatus('loading')
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/health`)
      if (response.ok) {
        const data = await response.json()
        if (data.status === 'healthy') {
          setBackendStatus('online')
        } else {
          setBackendStatus('offline')
        }
      } else {
        setBackendStatus('offline')
      }
    } catch (error) {
      setBackendStatus('offline')
    }
    setLastChecked(new Date().toLocaleTimeString())
  }

  useEffect(() => {
    checkHealth()
  }, [])

  return (
    <div className="container">
      <div className="logo-section">
        <div className="shield-icon">🔐</div>
        <h1>e-KYC 비대면 신원 인증</h1>
        <p className="subtitle">금융급 보안 · AI 기반 신원 검증 시스템</p>
      </div>

      <div className="status-card">
        <div className="status-info">
          <div className="status-label">Backend Connection</div>
          <div className="status-value">
            {backendStatus === 'online' && 'FastAPI Server 연결 성공'}
            {backendStatus === 'offline' && '연결 끊김 (서버 미작동)'}
            {backendStatus === 'loading' && '연결 확인 중...'}
          </div>
        </div>
        <div className={`status-indicator ${backendStatus === 'online' ? 'online' : 'offline'}`}>
          <span className="dot"></span>
          {backendStatus === 'online' ? 'Online' : backendStatus === 'loading' ? 'Checking' : 'Offline'}
        </div>
      </div>

      {backendStatus === 'online' ? (
        <SellerVerifier />
      ) : (
        <div style={{ padding: '20px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '12px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
          <p style={{ color: 'var(--error-color)', fontSize: '14px', marginBottom: '16px' }}>
            백엔드 API 서버가 응답하지 않습니다. 검증 서비스를 이용하시려면 백엔드 서버를 켜주세요.
          </p>
          <button className="btn" onClick={checkHealth} disabled={backendStatus === 'loading'}>
            연결 상태 재확인
          </button>
        </div>
      )}

      <div style={{ marginTop: '24px', fontSize: '12px', color: 'var(--text-secondary)' }}>
        최근 연결 확인: {lastChecked}
      </div>
    </div>
  )
}

export default App
