'use client'

import { createClient } from '@/lib/supabase/client'
import { useState } from 'react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSignUp, setIsSignUp] = useState(false)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const supabase = createClient()

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage('')

    const { error } = isSignUp
      ? await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: `${location.origin}/auth/callback` },
        })
      : await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setMessage(error.message)
    } else if (isSignUp) {
      setMessage('이메일을 확인해 주세요.')
    } else {
      location.href = '/'
    }
    setLoading(false)
  }

  const handleGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${location.origin}/auth/callback` },
    })
  }

  return (
    <div className="min-h-screen bg-white flex flex-col justify-center px-6">
      <div className="max-w-sm mx-auto w-full">
        {/* 로고 */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-[#1A1A1A]">투자노트</h1>
          <p className="text-sm text-[#8B95A1] mt-2">나만의 주식 매매일지</p>
        </div>

        {/* Google 로그인 */}
        <button
          onClick={handleGoogle}
          className="w-full flex items-center justify-center gap-3 py-3.5 border border-[#E5E8EB] rounded-2xl text-[#1A1A1A] text-sm font-medium mb-4 active:bg-gray-50"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Google로 계속하기
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 h-px bg-[#E5E8EB]" />
          <span className="text-xs text-[#8B95A1]">또는</span>
          <div className="flex-1 h-px bg-[#E5E8EB]" />
        </div>

        {/* 이메일 폼 */}
        <form onSubmit={handleEmailAuth} className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="이메일"
            required
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="비밀번호 (8자 이상)"
            minLength={8}
            required
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
          />

          {message && (
            <p className={`text-sm text-center ${message.includes('이메일') ? 'text-[#3366FF]' : 'text-[#F04452]'}`}>
              {message}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 bg-[#3366FF] text-white rounded-2xl text-sm font-semibold disabled:opacity-50"
          >
            {loading ? '처리 중...' : isSignUp ? '회원가입' : '로그인'}
          </button>
        </form>

        <button
          onClick={() => { setIsSignUp(!isSignUp); setMessage('') }}
          className="w-full text-center text-sm text-[#8B95A1] mt-4"
        >
          {isSignUp ? '이미 계정이 있으신가요? 로그인' : '계정이 없으신가요? 회원가입'}
        </button>
      </div>
    </div>
  )
}
