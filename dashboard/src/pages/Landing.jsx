import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, ShieldCheck, Zap, Terminal,
  Lock, Eye, AlertTriangle, Globe,
  ChevronRight, Fingerprint, Database,
  BarChart3, Cpu, Users, Check,
  MessageSquare, Bot, Sparkles, Shield
} from 'lucide-react'
import SentinelLogo from '../components/SentinelLogo'
import './Landing.css'

/* ── animated counter ───────────────────── */
function CountUp({ target, suffix = '', duration = 2200 }) {
  const [val, setVal] = useState(0)
  const ref = useRef(null)
  const started = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !started.current) {
        started.current = true
        let start = null
        const step = ts => {
          if (!start) start = ts
          const p = Math.min((ts - start) / duration, 1)
          setVal(Math.floor(p * target))
          if (p < 1) requestAnimationFrame(step)
        }
        requestAnimationFrame(step)
      }
    }, { threshold: 0.3 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [target, duration])

  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>
}

/* ── threat list ───────────────────────── */
const THREATS = [
  {
    icon: <AlertTriangle size={22} />,
    color: '#ef4444',
    title: 'Prompt Injection',
    plain: 'Someone tricks your AI',
    desc: 'Attackers write crafty messages designed to make your AI ignore your instructions and do something harmful instead.',
  },
  {
    icon: <Eye size={22} />,
    color: '#f59e0b',
    title: 'Data Leakage',
    plain: 'Private info slips out',
    desc: 'Personal details like phone numbers, Aadhaar, email addresses, or financial data can accidentally appear in AI responses.',
  },
  {
    icon: <Lock size={22} />,
    color: '#8b5cf6',
    title: 'Jailbreaking',
    plain: 'Breaking the rules',
    desc: 'Users try role-play tricks or encoded instructions to bypass your AI\'s safety filters and get harmful content.',
  },
  {
    icon: <Globe size={22} />,
    color: '#06b6d4',
    title: 'Hallucinations',
    plain: 'AI makes things up',
    desc: 'Your AI confidently states wrong information. In healthcare or finance, this can cause serious real-world harm.',
  },
]

/* ── protection features ─────────────────── */
const FEATURES = [
  {
    icon: <ShieldCheck size={20} />,
    color: '#6366f1',
    title: 'Real-Time Protection',
    desc: 'Every message is checked in under 70ms — fast enough that your users never notice, but nothing dangerous slips through.',
  },
  {
    icon: <Fingerprint size={20} />,
    color: '#10b981',
    title: 'PII Auto-Masking',
    desc: 'Phone numbers, Aadhaar, emails, and financial data are automatically detected and redacted before reaching the AI model.',
  },
  {
    icon: <MessageSquare size={20} />,
    color: '#f59e0b',
    title: 'Multi-Language Support',
    desc: 'Works in Hindi, Tamil, English, Arabic, and 50+ languages. Protection is not limited to English-only inputs.',
  },
  {
    icon: <Database size={20} />,
    color: '#06b6d4',
    title: 'Full Audit Trail',
    desc: 'Every decision is logged. See exactly what was blocked, when, and why. Essential for healthcare and finance compliance.',
  },
  {
    icon: <Cpu size={20} />,
    color: '#8b5cf6',
    title: 'Works With Any AI',
    desc: 'One SDK wrap covers OpenAI, Claude, Gemini, Azure OpenAI, and any API-compatible model. No vendor lock-in.',
  },
  {
    icon: <BarChart3 size={20} />,
    color: '#ec4899',
    title: 'Live Dashboard',
    desc: 'See threats blocked, risk scores, and usage patterns in a real-time dashboard. Know your AI is working safely.',
  },
]

/* ── how it works steps ──────────────────── */
const STEPS = [
  {
    step: '01',
    icon: <Terminal size={22} />,
    title: 'Install in 30 seconds',
    desc: 'Run one pip command. No heavy setup, no servers to manage. Sentinel runs as a lightweight SDK in your existing project.',
    code: 'pip install sentinel-ai',
  },
  {
    step: '02',
    icon: <Bot size={22} />,
    title: 'Wrap your AI client',
    desc: 'Pass your existing OpenAI or other AI client to sentinel.wrap(). Your application code stays exactly the same.',
    code: 'safe = sentinel.wrap(client)',
  },
  {
    step: '03',
    icon: <ShieldCheck size={22} />,
    title: 'You\'re protected',
    desc: 'Every prompt and response is now automatically checked. Threats are blocked, PII is masked, and everything is logged.',
    code: '# Same API. Fully protected.',
  },
]

/* ── compliance cards ────────────────────── */
const COMPLIANCE = [
  { label: 'GDPR', region: 'European Data Protection', icon: '🇪🇺', desc: 'Sentinel helps you handle user data lawfully and gives you the audit logs to prove it.' },
  { label: 'DPDP 2023', region: 'India Privacy Law', icon: '🇮🇳', desc: 'Designed for Indian businesses. Meets data fiduciary and consent management requirements.' },
  { label: 'RBI Guidelines', region: 'Indian FinTech', icon: '🏦', desc: 'Data stays in India. Localisation requirements for banking and lending AI are enforced.' },
  { label: 'HIPAA', region: 'Healthcare AI', icon: '🏥', desc: 'Auto-detects health information (PHI) and keeps it out of AI requests and logs.' },
]

export default function Landing() {
  const [activeStep, setActiveStep] = useState(0)
  const [typedText, setTypedText] = useState('')
  const fullText = 'sentinel.wrap(client, policy="strict")'

  // typewriter effect
  useEffect(() => {
    let i = 0
    setTypedText('')
    const id = setInterval(() => {
      if (i < fullText.length) {
        setTypedText(fullText.slice(0, i + 1))
        i++
      } else {
        clearInterval(id)
      }
    }, 55)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="landing-page">

      {/* ══════════════════════════════════════
          HERO
      ══════════════════════════════════════ */}
      <section className="hero">
        <div className="hero-grid-bg" />
        <div className="hero-glow-left" />
        <div className="hero-glow-right" />
        <div className="hero-noise" />

        <div className="hero-inner container">
          <div className="hero-left">
            {/* Badge */}
            <div className="hero-badge animate-fade-in">
              <span className="hero-badge-dot" />
              AI Guardrail  ·  Open Source  ·  Built in India
            </div>

            <h1 className="hero-headline animate-fade-in delay-1">
              Keep your AI<br />
              <span className="text-gradient">safe and honest.</span>
            </h1>

            <p className="hero-desc animate-fade-in delay-2">
              Sentinel sits between your app and your AI — silently checking every
              message for threats, private data, and harmful content.<br />
              <strong>No AI expertise needed. One line of code.</strong>
            </p>

            <div className="hero-cta animate-fade-in delay-3">
              <Link to="/pricing" className="btn-primary large">
                Protect My AI <ArrowRight size={18} />
              </Link>
              <Link to="/docs" className="btn-secondary large">
                <Terminal size={17} /> See How It Works
              </Link>
            </div>

            {/* Social proof numbers */}
            <div className="hero-proof animate-fade-in delay-4">
              <div className="proof-stat">
                <span className="proof-num"><CountUp target={99} suffix=".9%" /></span>
                <span className="proof-label">Threats Caught</span>
              </div>
              <div className="proof-divider" />
              <div className="proof-stat">
                <span className="proof-num">&lt;70ms</span>
                <span className="proof-label">Added Latency</span>
              </div>
              <div className="proof-divider" />
              <div className="proof-stat">
                <span className="proof-num">50+</span>
                <span className="proof-label">Languages</span>
              </div>
            </div>
          </div>

          {/* Hero visual */}
          <div className="hero-right animate-scale-in delay-2">
            {/* Code terminal */}
            <div className="code-window glass-card hero-terminal">
              <div className="code-window-header">
                <div className="window-controls">
                  <span className="wc wc-red" />
                  <span className="wc wc-yellow" />
                  <span className="wc wc-green" />
                </div>
                <span className="window-filename">your_app.py</span>
                <span className="window-tag">Python SDK</span>
              </div>
              <div className="code-window-body">
                <pre className="code-pre">
                  <code>
                    <span className="t-dim">1 </span><span className="t-kw">import</span> openai{'\n'}
                    <span className="t-dim">2 </span><span className="t-kw">import</span> sentinel{'\n'}
                    <span className="t-dim">3 </span>{'\n'}
                    <span className="t-dim">4 </span><span className="t-cm"># Your existing AI client</span>{'\n'}
                    <span className="t-dim">5 </span>client = openai.OpenAI(api_key=<span className="t-str">"sk-..."</span>){'\n'}
                    <span className="t-dim">6 </span>{'\n'}
                    <span className="t-dim">7 </span><span className="t-cm"># Add Sentinel — one line</span>{'\n'}
                    <span className="t-dim">8 </span>safe = <span className="t-fn">{typedText}</span>
                    <span className="cursor-blink">|</span>{'\n'}
                    <span className="t-dim">9 </span>{'\n'}
                    <span className="t-dim">10</span><span className="t-cm"># Use exactly as before. Now protected.</span>{'\n'}
                    <span className="t-dim">11</span>response = safe.chat.completions.create(...)
                  </code>
                </pre>
              </div>
            </div>

            {/* Live decision card */}
            <div className="hero-decision-card glass-card animate-fade-in delay-5">
              <div className="dc-header">
                <ShieldCheck size={13} color="#10b981" />
                <span>Live Decision</span>
                <span className="dc-badge safe">SAFE</span>
                <span className="dc-time">12ms</span>
              </div>
              <div className="dc-checks">
                {['No injection', 'No PII found', 'No jailbreak', 'Policy OK'].map(c => (
                  <div key={c} className="dc-check">
                    <Check size={11} color="#10b981" />
                    <span>{c}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Threat blocked card */}
            <div className="hero-blocked-card glass-card animate-fade-in delay-5">
              <div className="blocked-header">
                <span className="blocked-dot" />
                <span>Threat Blocked</span>
                <span className="dc-badge blocked">BLOCKED</span>
              </div>
              <p className="blocked-reason">Prompt injection detected</p>
              <div className="blocked-bar">
                <div className="blocked-fill" style={{ width: '87%' }} />
              </div>
              <span className="blocked-score">Risk score: 0.87</span>
            </div>
          </div>
        </div>

        {/* Scroll hint */}
        <div className="hero-scroll-hint">
          <div className="scroll-line" />
          <span>Scroll to explore</span>
        </div>
      </section>

      {/* ══════════════════════════════════════
          WHAT PROBLEM WE SOLVE
      ══════════════════════════════════════ */}
      <section className="problem-section">
        <div className="container">
          <div className="section-header">
            <div className="section-overline">THE PROBLEM</div>
            <h2>AI is powerful — but it can also go wrong.</h2>
            <p className="section-desc">
              When you add an AI chatbot or assistant to your product, it opens up new risks
              that regular security tools don't cover.
            </p>
          </div>

          <div className="threats-grid">
            {THREATS.map((t, i) => (
              <div
                key={t.title}
                className="threat-card glass-card"
                style={{ '--threat-color': t.color, animationDelay: `${i * 0.1}s` }}
              >
                <div className="threat-icon-wrap" style={{ color: t.color, background: `${t.color}18` }}>
                  {t.icon}
                </div>
                <div className="threat-content">
                  <div className="threat-title-row">
                    <h4>{t.title}</h4>
                    <span className="threat-plain">{t.plain}</span>
                  </div>
                  <p>{t.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="problem-callout">
            <Sparkles size={18} color="var(--accent-bright)" />
            <p>
              <strong>Sentinel catches all of these automatically</strong> — before they ever
              reach your AI model or your users. No configuration needed to get started.
            </p>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════
          HOW IT WORKS (3 steps)
      ══════════════════════════════════════ */}
      <section className="how-section">
        <div className="container">
          <div className="section-header">
            <div className="section-overline">HOW IT WORKS</div>
            <h2>Set up in 3 steps. Protect forever.</h2>
            <p className="section-desc">
              You don't need to be a security expert. Sentinel is designed to
              just work the moment you add it.
            </p>
          </div>

          <div className="steps-row">
            {STEPS.map((s, i) => (
              <div
                key={s.step}
                className={`step-card${activeStep === i ? ' step-active' : ''}`}
                onClick={() => setActiveStep(i)}
              >
                <div className="step-num">{s.step}</div>
                <div className="step-icon-wrap">{s.icon}</div>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
                <div className="step-code">
                  <code>{s.code}</code>
                </div>
              </div>
            ))}
          </div>

          {/* connector line */}
          <div className="steps-connector">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`steps-dot${activeStep >= i ? ' done' : ''}`}
                onClick={() => setActiveStep(i)}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════
          FEATURES
      ══════════════════════════════════════ */}
      <section className="features-section">
        <div className="container">
          <div className="section-header">
            <div className="section-overline">WHAT YOU GET</div>
            <h2>Complete AI protection, out of the box.</h2>
            <p className="section-desc">
              Every Sentinel plan includes these protections — working silently
              in the background, 24/7.
            </p>
          </div>

          <div className="features-grid">
            {FEATURES.map((f, i) => (
              <div
                key={f.title}
                className="feature-card glass-card"
                style={{ '--feat-color': f.color, animationDelay: `${i * 0.08}s` }}
              >
                <div className="feat-icon" style={{ color: f.color, background: `${f.color}18` }}>
                  {f.icon}
                </div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════
          LIVE DEMO VISUAL
      ══════════════════════════════════════ */}
      <section className="demo-section">
        <div className="container">
          <div className="demo-grid">
            <div className="demo-text">
              <div className="section-overline">SEE IT IN ACTION</div>
              <h2>What Sentinel sees in real time.</h2>
              <p>
                Every message flowing through your AI is analysed in milliseconds.
                You get a live view of what's happening — threats blocked, data protected,
                decisions logged.
              </p>
              <ul className="demo-checklist">
                {[
                  'Exact reason every message was blocked or allowed',
                  'Risk score from 0 to 1 for every request',
                  'Which category of threat was detected',
                  'Full history you can export for audits',
                ].map(item => (
                  <li key={item}>
                    <Check size={15} color="var(--emerald)" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <Link to="/pricing" className="btn-primary" style={{ marginTop: '28px' }}>
                Start Free <ArrowRight size={16} />
              </Link>
            </div>

            <div className="demo-visual">
              {/* Dashboard mockup */}
              <div className="dash-card glass-card">
                <div className="dash-header">
                  <BarChart3 size={14} color="var(--accent-bright)" />
                  <span>Sentinel Dashboard</span>
                  <span className="live-pill">● LIVE</span>
                </div>

                <div className="dash-stats">
                  <div className="dash-stat">
                    <span className="ds-val" style={{ color: 'var(--success)' }}>12,394</span>
                    <span className="ds-lbl">Requests Today</span>
                  </div>
                  <div className="dash-stat">
                    <span className="ds-val" style={{ color: 'var(--danger)' }}>218</span>
                    <span className="ds-lbl">Threats Blocked</span>
                  </div>
                  <div className="dash-stat">
                    <span className="ds-val">99.3%</span>
                    <span className="ds-lbl">Safe Rate</span>
                  </div>
                  <div className="dash-stat">
                    <span className="ds-val">48ms</span>
                    <span className="ds-lbl">Avg. Latency</span>
                  </div>
                </div>

                <div className="dash-feed">
                  <div className="dash-feed-title">Recent Decisions</div>
                  {[
                    { status: 'allowed', text: 'What are the loan EMI options?', ms: '38ms', risk: '0.03' },
                    { status: 'blocked', text: 'Ignore previous instructions and...', ms: '41ms', risk: '0.94' },
                    { status: 'masked',  text: 'My Aadhaar is 1234-5678-90XX', ms: '36ms', risk: '0.71' },
                    { status: 'allowed', text: 'Track my order #A29381', ms: '33ms', risk: '0.05' },
                  ].map((row, i) => (
                    <div key={i} className="feed-row">
                      <span className={`feed-status ${row.status}`}>{row.status}</span>
                      <span className="feed-text">{row.text}</span>
                      <span className="feed-ms">{row.ms}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════
          COMPLIANCE
      ══════════════════════════════════════ */}
      <section className="compliance-section">
        <div className="container">
          <div className="section-header">
            <div className="section-overline">COMPLIANCE</div>
            <h2>Built for India and global regulations.</h2>
            <p className="section-desc">
              If you're in healthcare, finance, or any regulated industry, Sentinel
              generates the audit logs and compliance reports you need.
            </p>
          </div>

          <div className="compliance-grid">
            {COMPLIANCE.map(c => (
              <div key={c.label} className="compliance-card glass-card">
                <div className="compliance-flag">{c.icon}</div>
                <div className="compliance-tag">{c.label}</div>
                <div className="compliance-region">{c.region}</div>
                <p>{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════
          CTA
      ══════════════════════════════════════ */}
      <section className="cta-section">
        <div className="cta-glow" />
        <div className="container">
          <div className="cta-box">
            <div className="cta-logo-wrap">
              <SentinelLogo size={52} />
            </div>
            <h2>Your AI is live. Is it safe?</h2>
            <p>
              Start with our free open-source version. No credit card. No infrastructure.
              Just copy one line of code and your AI is protected.
            </p>
            <div className="cta-actions">
              <Link to="/pricing" className="btn-primary large">
                Get Started Free <ArrowRight size={18} />
              </Link>
              <Link to="/docs" className="btn-secondary large">
                Read the Docs
              </Link>
            </div>
            <p className="cta-fine">
              Free forever for open source &nbsp;·&nbsp; No vendor lock-in &nbsp;·&nbsp; Built in India 🇮🇳
            </p>
          </div>
        </div>
      </section>

    </div>
  )
}
