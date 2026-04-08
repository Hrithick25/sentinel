import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  auth,
  googleProvider,
  signInWithPopup,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  onAuthStateChanged,
} from '../firebase'
import SentinelLogo from '../components/SentinelLogo'
import './SignIn.css'

export default function SignIn() {
  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  // Redirect if already signed in
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, u => {
      if (u) navigate('/app')
    })
    return unsub
  }, [navigate])

  const clearError = () => setError('')

  const handleGoogleSignIn = async () => {
    setLoading(true)
    clearError()
    try {
      await signInWithPopup(auth, googleProvider)
      navigate('/app')
    } catch (err) {
      setError(friendlyError(err.code))
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    clearError()

    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.')
      setLoading(false)
      return
    }

    try {
      if (mode === 'signup') {
        await createUserWithEmailAndPassword(auth, email, password)
      } else {
        await signInWithEmailAndPassword(auth, email, password)
      }
      navigate('/app')
    } catch (err) {
      setError(friendlyError(err.code))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="signin-page">
      {/* Background */}
      <div className="signin-bg">
        <div className="signin-glow1" />
        <div className="signin-glow2" />
        <div className="signin-grid" />
      </div>

      {/* Card */}
      <div className="signin-card">
        {/* Logo */}
        <Link to="/" className="signin-logo-link">
          <SentinelLogo size={36} />
          <span className="signin-brand">SENTINEL</span>
        </Link>

        <h1 className="signin-title">
          {mode === 'signin' ? 'Welcome back' : 'Create your account'}
        </h1>
        <p className="signin-sub">
          {mode === 'signin'
            ? 'Sign in to your Sentinel dashboard'
            : 'Start protecting your AI with Sentinel'}
        </p>

        {/* Google */}
        <button
          className="btn-google"
          onClick={handleGoogleSignIn}
          disabled={loading}
          id="google-signin-btn"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
            <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>

        <div className="signin-divider">
          <span />
          <p>or continue with email</p>
          <span />
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="signin-form">
          <div className="form-group">
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">
              Password
              {mode === 'signin' && (
                <button type="button" className="forgot-link" tabIndex={-1}>
                  Forgot password?
                </button>
              )}
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder={mode === 'signup' ? 'Minimum 6 characters' : '••••••••'}
              required
              minLength={6}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            />
          </div>

          {mode === 'signup' && (
            <div className="form-group">
              <label htmlFor="confirm-password">Confirm password</label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                required
              />
            </div>
          )}

          {error && (
            <div className="signin-error" role="alert">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-primary w-full signin-submit"
            disabled={loading}
            id="email-signin-btn"
          >
            {loading
              ? 'Please wait…'
              : mode === 'signin'
              ? 'Sign In'
              : 'Create Account'}
          </button>
        </form>

        <p className="signin-switch">
          {mode === 'signin' ? "Don't have an account? " : 'Already have an account? '}
          <button
            className="switch-link"
            onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); clearError() }}
          >
            {mode === 'signin' ? 'Sign up free' : 'Sign in'}
          </button>
        </p>

        <p className="signin-terms">
          By continuing, you agree to our{' '}
          <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a>.
        </p>
      </div>
    </div>
  )
}

function friendlyError(code) {
  const map = {
    'auth/user-not-found': 'No account found with this email.',
    'auth/wrong-password': 'Incorrect password. Please try again.',
    'auth/email-already-in-use': 'An account with this email already exists.',
    'auth/invalid-email': 'Please enter a valid email address.',
    'auth/weak-password': 'Password must be at least 6 characters.',
    'auth/too-many-requests': 'Too many attempts. Please try again later.',
    'auth/popup-closed-by-user': 'Sign-in popup was closed. Please try again.',
    'auth/network-request-failed': 'Network error. Check your connection.',
    'auth/invalid-credential': 'Invalid email or password.',
  }
  return map[code] || 'Something went wrong. Please try again.'
}
