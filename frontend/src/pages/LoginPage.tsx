import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { LedgrLogo } from '../components/LedgrLogo'
import { useApp } from '../context/AppContext'
import {
  ArrowRightIcon,
  EyeIcon,
  EyeOffIcon,
  LockIcon,
  MailIcon,
} from '../components/icons'

const DEMO_EMAIL = 'demo@acmecorp.com'
const DEMO_PASSWORD = 'Lx7#Recon@2026Kq'

export function LoginPage() {
  const { login, merchant } = useApp()
  const navigate = useNavigate()
  const emailId = useId()
  const passwordId = useId()
  const rememberId = useId()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    email?: string
    password?: string
  }>({})

  function validate() {
    const next: { email?: string; password?: string } = {}

    if (!email.trim()) {
      next.email = 'Enter your email address'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = 'Enter a valid email address'
    }

    if (!password) {
      next.password = 'Enter your password'
    }

    setFieldErrors(next)
    return Object.keys(next).length === 0
  }

  if (merchant) {
    return <Navigate to="/dashboard" replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (!validate()) return

    setIsSubmitting(true)
    const result = await login(email, password)
    setIsSubmitting(false)

    if (result.ok) {
      navigate('/dashboard')
      return
    }

    setError(result.message)
  }

  function handleDemoAccess() {
    setEmail(DEMO_EMAIL)
    setPassword(DEMO_PASSWORD)
    setFieldErrors({})
    setError(null)
  }

  return (
    <div
      className="relative min-h-screen overflow-hidden text-ledgr-ink"
      style={{ background: 'var(--ledgr-login-bg)' }}
    >

      {/* Centered login stage — optimized for 1440×900 */}
      <main className="relative flex min-h-screen items-center justify-center px-6 py-16">
        <div className="w-full max-w-[400px]">
          <article
            className="rounded-[14px] border border-ledgr-card-border bg-ledgr-card shadow-ledgr-card"
            style={{
              boxShadow:
                '0 1px 3px rgba(26, 35, 53, 0.04), 0 8px 32px rgba(26, 35, 53, 0.07), inset 0 1px 0 rgba(255, 255, 255, 0.9)',
            }}
          >
            <div className="px-9 pb-9 pt-10">
              {/* Branding */}
              <header className="mb-8 text-center">
                <div className="mb-5 flex justify-center">
                  <LedgrLogo />
                </div>
                <h1 className="mb-1.5 text-[22px] font-semibold tracking-[-0.025em] text-ledgr-ink">
                  Welcome back
                </h1>
                <p className="text-[13.5px] leading-relaxed text-ledgr-muted">
                  Sign in to continue to Ledgr
                </p>
              </header>

              {/* Form */}
              <form onSubmit={handleSubmit} noValidate className="space-y-5">
                {error && (
                  <div
                    role="alert"
                    className="rounded-lg border border-ledgr-error-border bg-ledgr-error-soft px-3.5 py-2.5 text-[13px] leading-snug text-ledgr-error"
                  >
                    {error}
                  </div>
                )}

                {/* Email */}
                <div>
                  <label
                    htmlFor={emailId}
                    className="mb-1.5 block text-[13px] font-medium text-ledgr-ink"
                  >
                    Email address
                  </label>
                  <div className="relative">
                    <MailIcon className="pointer-events-none absolute left-3.5 top-1/2 h-[17px] w-[17px] -translate-y-1/2 text-ledgr-muted" />
                    <input
                      id={emailId}
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value)
                        if (fieldErrors.email) {
                          setFieldErrors((prev) => ({ ...prev, email: undefined }))
                        }
                        setError(null)
                      }}
                      placeholder="you@company.com"
                      aria-invalid={Boolean(fieldErrors.email)}
                      aria-describedby={
                        fieldErrors.email ? `${emailId}-error` : undefined
                      }
                      className={`w-full rounded-[9px] border bg-ledgr-field py-[11px] pl-10 pr-3.5 text-[14px] text-ledgr-ink outline-none transition-[border-color,box-shadow] placeholder:text-[#a0a8b4] ${
                        fieldErrors.email
                          ? 'border-ledgr-error-border focus:border-ledgr-error focus:ring-2 focus:ring-ledgr-error/15'
                          : 'border-ledgr-card-border focus:border-ledgr-primary focus:ring-2 focus:ring-ledgr-primary-soft'
                      }`}
                    />
                  </div>
                  {fieldErrors.email && (
                    <p
                      id={`${emailId}-error`}
                      className="mt-1.5 text-[12.5px] text-ledgr-error"
                    >
                      {fieldErrors.email}
                    </p>
                  )}
                </div>

                {/* Password */}
                <div>
                  <label
                    htmlFor={passwordId}
                    className="mb-1.5 block text-[13px] font-medium text-ledgr-ink"
                  >
                    Password
                  </label>
                  <div className="relative">
                    <LockIcon className="pointer-events-none absolute left-3.5 top-1/2 h-[17px] w-[17px] -translate-y-1/2 text-ledgr-muted" />
                    <input
                      id={passwordId}
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value)
                        if (fieldErrors.password) {
                          setFieldErrors((prev) => ({
                            ...prev,
                            password: undefined,
                          }))
                        }
                        setError(null)
                      }}
                      placeholder="Enter your password"
                      aria-invalid={Boolean(fieldErrors.password)}
                      aria-describedby={
                        fieldErrors.password ? `${passwordId}-error` : undefined
                      }
                      className={`w-full rounded-[9px] border bg-ledgr-field py-[11px] pl-10 pr-11 text-[14px] text-ledgr-ink outline-none transition-[border-color,box-shadow] placeholder:text-[#a0a8b4] ${
                        fieldErrors.password
                          ? 'border-ledgr-error-border focus:border-ledgr-error focus:ring-2 focus:ring-ledgr-error/15'
                          : 'border-ledgr-card-border focus:border-ledgr-primary focus:ring-2 focus:ring-ledgr-primary-soft'
                      }`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-ledgr-muted transition-colors hover:text-ledgr-body"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? (
                        <EyeOffIcon className="h-[17px] w-[17px]" />
                      ) : (
                        <EyeIcon className="h-[17px] w-[17px]" />
                      )}
                    </button>
                  </div>
                  {fieldErrors.password && (
                    <p
                      id={`${passwordId}-error`}
                      className="mt-1.5 text-[12.5px] text-ledgr-error"
                    >
                      {fieldErrors.password}
                    </p>
                  )}
                </div>

                {/* Remember + Forgot */}
                <div className="flex items-center justify-between pt-0.5">
                  <label
                    htmlFor={rememberId}
                    className="flex cursor-pointer select-none items-center gap-2 text-[13px] text-ledgr-body"
                  >
                    <input
                      id={rememberId}
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="h-[15px] w-[15px] rounded-[4px] border-[rgba(26,35,53,0.22)] text-ledgr-primary focus:ring-2 focus:ring-ledgr-primary-soft"
                    />
                    Remember me
                  </label>
                  <a
                    href="#"
                    className="text-[13px] text-ledgr-muted transition-colors hover:text-ledgr-primary"
                    onClick={(e) => e.preventDefault()}
                  >
                    Forgot password?
                  </a>
                </div>

                {/* Primary CTA */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="mt-1 flex w-full items-center justify-center gap-2 rounded-[9px] bg-ledgr-primary px-4 py-[12px] text-[14px] font-medium text-white transition-[background-color,opacity] hover:bg-ledgr-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSubmitting ? (
                    'Signing in…'
                  ) : (
                    <>
                      Sign in
                      <ArrowRightIcon className="h-[17px] w-[17px]" />
                    </>
                  )}
                </button>

                {/* Demo access */}
                <button
                  type="button"
                  onClick={handleDemoAccess}
                  className="w-full rounded-[9px] border border-[rgba(26,35,53,0.14)] bg-transparent px-4 py-[10px] text-[13.5px] font-medium text-ledgr-body transition-[border-color,background-color,color] hover:border-[rgba(26,35,53,0.22)] hover:bg-[rgba(26,35,53,0.03)]"
                >
                  Try demo account
                </button>
              </form>
            </div>
          </article>

          <p className="mt-7 text-center text-[11.5px] leading-relaxed tracking-[0.01em] text-ledgr-muted">
            Secured reconciliation workspace
          </p>
        </div>
      </main>
    </div>
  )
}
