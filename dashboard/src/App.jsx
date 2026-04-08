import { BrowserRouter, Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Menu, X, LogOut, User, LayoutDashboard, ChevronDown } from 'lucide-react'
import { useEffect, useState, useRef } from 'react'

import Landing       from './pages/Landing'
import Pricing       from './pages/Pricing'
import Docs          from './pages/Docs'
import SignIn        from './pages/SignIn'
import AppDashboard  from './pages/AppDashboard'

import { auth, signOut, onAuthStateChanged } from './firebase'
import SentinelLogo from './components/SentinelLogo'
import './App.css'
import './index.css'

/* ── Scroll-to-top on route change ─────── */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

/* ══════════════════════════════════════════
   NAVBAR
══════════════════════════════════════════ */
function Navbar() {
  const [scrolled, setScrolled]   = useState(false)
  const [menuOpen, setMenuOpen]   = useState(false)
  const [user, setUser]           = useState(null)
  const [dropOpen, setDropOpen]   = useState(false)
  const dropRef                   = useRef(null)
  const navigate                  = useNavigate()

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, u => setUser(u))
    return unsub
  }, [])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropRef.current && !dropRef.current.contains(e.target)) setDropOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSignOut = async () => {
    await signOut(auth)
    setDropOpen(false)
    navigate('/')
  }

  const initials = user
    ? (user.displayName
        ? user.displayName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
        : user.email?.[0]?.toUpperCase() ?? 'U')
    : ''

  return (
    <nav className={`navbar-glass${scrolled ? ' scrolled' : ''}`}>
      <div className="nav-container">
        {/* Brand */}
        <NavLink to="/" className="brand">
          <SentinelLogo size={30} />
          <div className="brand-wordmark">
            <span className="brand-text">SENTINEL</span>
            <span className="brand-sub">AI Guardrail</span>
          </div>
        </NavLink>

        {/* Links */}
        <div className="nav-links">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Home
          </NavLink>
          <NavLink to="/docs" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            How It Works
          </NavLink>
          <NavLink to="/pricing" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Pricing
          </NavLink>
          {user && (
            <NavLink to="/app" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Dashboard
            </NavLink>
          )}
        </div>

        {/* Actions */}
        <div className="nav-actions">
          {user ? (
            <div className="user-pill" onClick={() => setDropOpen(!dropOpen)} ref={dropRef}>
              <div className="user-avatar">{initials}</div>
              <span>{user.displayName || user.email?.split('@')[0]}</span>
              <ChevronDown size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

              {dropOpen && (
                <div className="user-dropdown">
                  <button onClick={() => { navigate('/app'); setDropOpen(false) }}>
                    <LayoutDashboard size={14} /> Dashboard
                  </button>
                  <button onClick={() => setDropOpen(false)}>
                    <User size={14} /> Profile
                  </button>
                  <button className="signout-btn" onClick={handleSignOut}>
                    <LogOut size={14} /> Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <NavLink to="/signin" className="btn-ghost">Sign In</NavLink>
              <NavLink to="/pricing" className="btn-primary">Get Started</NavLink>
            </>
          )}

          <button
            className="btn-ghost nav-menu-toggle"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="nav-mobile-menu">
          <NavLink to="/"       end onClick={() => setMenuOpen(false)}>Home</NavLink>
          <NavLink to="/docs"       onClick={() => setMenuOpen(false)}>How It Works</NavLink>
          <NavLink to="/pricing"    onClick={() => setMenuOpen(false)}>Pricing</NavLink>
          {user ? (
            <NavLink to="/app" onClick={() => setMenuOpen(false)} style={{ color: 'var(--text)', fontWeight: 600 }}>
              Dashboard
            </NavLink>
          ) : (
            <NavLink to="/signin" onClick={() => setMenuOpen(false)} className="mobile-signin-link">
              Sign In
            </NavLink>
          )}
        </div>
      )}
    </nav>
  )
}

/* ══════════════════════════════════════════
   FOOTER
══════════════════════════════════════════ */
function Footer() {
  return (
    <footer className="footer">
      <div className="footer-container">
        {/* Brand col */}
        <div className="footer-brand">
          <div className="footer-brand-row">
            <SentinelLogo size={22} />
            <span className="footer-brand-name">SENTINEL</span>
          </div>
          <p className="footer-tagline">
            An AI guardrail that keeps your chatbots and AI apps safe, private,
            and compliant — without slowing them down.
          </p>
          <div className="footer-badges">
            <span className="cert-badge">GDPR</span>
            <span className="cert-badge">RBI</span>
            <span className="cert-badge">DPDP 2023</span>
          </div>
        </div>

        <div className="footer-col">
          <h4>Product</h4>
          <NavLink to="/docs">How It Works</NavLink>
          <NavLink to="/pricing">Pricing</NavLink>
          <a href="https://pypi.org/project/sentinel-guardrails-sdk/" target="_blank" rel="noopener noreferrer">Python SDK</a>
        </div>

        <div className="footer-col">
          <h4>Security</h4>
          <NavLink to="/docs">Prompt Protection</NavLink>
          <NavLink to="/docs">PII Masking</NavLink>
          <NavLink to="/docs">Jailbreak Guard</NavLink>
          <NavLink to="/docs">Compliance</NavLink>
        </div>

        <div className="footer-col">
          <h4>Company</h4>
          <a href="mailto:hello@sentinel.ai">Contact</a>
          <a href="#">Privacy Policy</a>
        </div>
      </div>

      <div className="footer-bottom">
        <p>© 2026 Sentinel AI. All rights reserved.</p>
        <div className="footer-bottom-links">
          <a href="#">Privacy</a>
          <a href="#">Terms</a>
          <a href="#">Security</a>
        </div>
      </div>
    </footer>
  )
}

/* ══════════════════════════════════════════
   APP ROOT
══════════════════════════════════════════ */
export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="app-wrapper">
        <Navbar />
        <main className="main-content">
          <Routes>
            <Route path="/"        element={<Landing />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/docs"    element={<Docs />} />
            <Route path="/signin"  element={<SignIn />} />
            <Route path="/app"     element={<AppDashboard />} />
            <Route path="*"        element={<Landing />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  )
}
