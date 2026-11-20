import React, { useState } from 'react'
import { KeyRound, Lock, ArrowRight, Bot, AlertCircle } from 'lucide-react'
import { verifyAdminPasscode } from '../api/admin'

interface AdminAuthGateProps {
  onAuthenticated: () => void
}

export const AdminAuthGate: React.FC<AdminAuthGateProps> = ({ onAuthenticated }) => {
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim() || loading) return

    setLoading(true)
    setError(null)
    try {
      const isValid = await verifyAdminPasscode(password)
      if (isValid) {
        sessionStorage.setItem('edusync_admin_auth', 'authenticated')
        onAuthenticated()
      } else {
        setError('Incorrect administrator passcode. Please try again.')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to authenticate with backend server.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f9fa] flex flex-col items-center justify-center p-4 font-['Inter',sans-serif]">
      <div className="w-full max-w-md bg-white border border-[#e4e4e7] rounded-2xl p-6 sm:p-8 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 bg-[#18181b] text-white rounded-xl flex items-center justify-center mx-auto shadow-sm">
            <Lock className="w-5 h-5" />
          </div>
          <h1 className="text-xl font-bold text-[#18181b] tracking-tight">Admin Dashboard Access</h1>
          <p className="text-xs text-neutral-500">
            Enter the shared institutional administrative passcode to manage document sources, conflict resolutions, and system analytics.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-700 block">
              Passcode
            </label>
            <div className="relative">
              <KeyRound className="w-4 h-4 text-neutral-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                placeholder="Enter admin passcode (e.g. edusync-admin-2026)..."
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (error) setError(null)
                }}
                className="w-full pl-10 pr-4 py-2.5 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-sm text-[#18181b] focus:outline-none focus:border-neutral-900 transition"
                autoFocus
              />
            </div>
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={!password.trim() || loading}
            className="w-full py-2.5 bg-[#18181b] hover:bg-black text-white text-xs sm:text-sm font-semibold rounded-xl shadow-sm transition flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <span>{loading ? 'Verifying...' : 'Unlock Admin Dashboard'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="pt-2 border-t border-[#f0f0f2] flex items-center justify-between text-xs text-neutral-500">
          <a
            href="/"
            className="inline-flex items-center gap-1.5 text-neutral-600 hover:text-neutral-900 transition"
          >
            <Bot className="w-3.5 h-3.5" />
            <span>Return to Student Assistant</span>
          </a>
          <span className="text-[11px] text-neutral-400">EduSync Security Gate</span>
        </div>
      </div>
    </div>
  )
}
