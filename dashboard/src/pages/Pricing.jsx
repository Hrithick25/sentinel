import { useState, useEffect } from 'react'
import { CheckCircle2, XCircle, Zap, Building2, Code2, ArrowRight, HelpCircle, ChevronDown } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { auth, db, doc, setDoc, onAuthStateChanged } from '../firebase'
import './Pricing.css'

/* ── Plans ──────────────────────────────── */
const PLANS_MONTHLY = [
  {
    id: 'free',
    name: 'Free',
    tagline: 'For developers and tinkerers',
    price: '₹0',
    sub: 'forever · self-hosted',
    color: '#10b981',
    cta: 'Download SDK',
    ctaHref: 'https://github.com',
    ctaStyle: 'secondary',
    features: [
      { text: 'Core threat protection (injection, jailbreak, PII)', yes: true },
      { text: 'Self-hosted via lightweight SDK', yes: true },
      { text: 'Works with OpenAI & Anthropic', yes: true },
      { text: 'Python SDK (pip install)', yes: true },
      { text: 'Community GitHub support', yes: true },
      { text: 'Managed cloud hosting', no: true },
      { text: 'Analytics dashboard', no: true },
      { text: 'Compliance log export', no: true },
    ],
  },
  {
    id: 'pro',
    name: 'Pro',
    tagline: 'For teams shipping to production',
    price: '₹4,500',
    sub: '/month · billed monthly',
    color: '#6366f1',
    cta: 'Upgrade to Pro',
    ctaHref: '/signin',
    ctaStyle: 'primary',
    popular: true,
    badge: 'MOST POPULAR',
    features: [
      { text: 'Everything in Free, hosted for you', yes: true },
      { text: 'No Docker or servers to manage', yes: true },
      { text: 'All threat protection agents', yes: true },
      { text: 'Real-time analytics dashboard', yes: true },
      { text: 'Multi-language support (50+ languages)', yes: true },
      { text: 'GDPR + DPDP 2023 compliance logs', yes: true },
      { text: '30-day audit log retention', yes: true },
      { text: 'Email support', yes: true },
    ],
    limit: 'Up to 100,000 requests / month included',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: 'For regulated organisations at scale',
    price: 'Custom',
    sub: 'talk to us · no hidden fees',
    color: '#06b6d4',
    cta: 'Contact Us',
    ctaHref: 'mailto:hello@sentinel.ai',
    ctaStyle: 'secondary',
    features: [
      { text: 'Everything in Pro', yes: true },
      { text: 'Private cloud or on-premise deployment', yes: true },
      { text: 'Unlimited requests', yes: true },
      { text: 'SSO / SAML login', yes: true },
      { text: 'Custom compliance policies', yes: true },
      { text: 'Unlimited audit log retention', yes: true },
      { text: '99.99% uptime SLA', yes: true },
      { text: 'Dedicated support & onboarding', yes: true },
    ],
  },
]

const PLANS_ANNUAL = PLANS_MONTHLY.map(p => {
  if (p.id === 'pro') {
    return {
      ...p,
      price: '₹43,200',
      sub: '/yr · billed annually (saves ₹10,800)',
      badge: 'BEST VALUE',
    }
  }
  return p
})

/* ── FAQ ────────────────────────────────── */
const FAQ = [
  {
    q: 'What exactly is a "request"?',
    a: 'Any single message you send to your AI (like "What is my account balance?") counts as one request. Sentinel checks both the message going in and the reply coming back — all within that one request.',
  },
  {
    q: 'Can I try Pro before paying?',
    a: 'Yes — every new account gets a 14-day free trial of Pro. No credit card required. You can cancel anytime.',
  },
  {
    q: 'Why is Pro ₹4,500/month?',
    a: 'We priced it to be fair. Building and maintaining an in-house low-latency security layer costs thousands of dollars a month. Sentinel provides enterprise-grade AI protection at a fraction of that cost.',
  },
  {
    q: 'What happens if I exceed 100,000 requests?',
    a: 'You\'ll receive a notification. Extra usage is charged at ₹0.02 per request (₹20 per 1,000). No service interruption.',
  },
  {
    q: 'Does Sentinel work with Indian languages?',
    a: 'Yes. Hindi, Tamil, Telugu, Bengali, Kannada, Malayalam, Marathi and 45+ more languages are supported. Threats and PII are detected across all of them.',
  },
  {
    q: 'Is there a self-hosted option for Pro?',
    a: 'Enterprise customers can run Sentinel entirely within their own infrastructure (AWS, GCP, Azure, or on-premise). Contact us for the enterprise self-hosted licence.',
  },
]

export default function Pricing() {
  const [cycle, setCycle]     = useState('monthly')
  const [faqOpen, setFaqOpen] = useState(null)
  const [user, setUser]       = useState(null)
  const [upgrading, setUpgrading] = useState(false)
  const navigate              = useNavigate()

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, u => setUser(u))
    return unsub
  }, [])

  const handleProUpgrade = async () => {
    if (!user) {
      navigate('/signin')
      return
    }
    setUpgrading(true)
    try {
      await setDoc(doc(db, 'users', user.uid), {
        plan: 'pro',
        updatedAt: new Date().toISOString()
      }, { merge: true })
      navigate('/app')
    } catch (err) {
      console.error(err)
      setUpgrading(false)
    }
  }

  const plans = cycle === 'annual' ? PLANS_ANNUAL : PLANS_MONTHLY

  return (
    <div className="pricing-page">

      {/* ── HEADER ── */}
      <div className="pricing-hero">
        <div className="pricing-hero-glow" />
        <div className="container">
          <div className="section-overline">PRICING</div>
          <h1>Simple, honest pricing.</h1>
          <p>
            Start free. Pay only when you need managed hosting.<br />
            No surprise bills, no per-agent pricing, no vendor lock-in.
          </p>

          {/* Toggle */}
          <div className="billing-toggle">
            <button
              className={`toggle-btn${cycle === 'monthly' ? ' active' : ''}`}
              onClick={() => setCycle('monthly')}
            >
              Monthly
            </button>
            <button
              className={`toggle-btn${cycle === 'annual' ? ' active' : ''}`}
              onClick={() => setCycle('annual')}
            >
              Annual
              <span className="toggle-save">Save 20%</span>
            </button>
          </div>
          {/* Alert */}
          <div style={{
            maxWidth: '600px', margin: '32px auto 0', padding: '14px',
            background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)',
            borderRadius: '12px', fontSize: '0.85rem', color: 'var(--text-muted)'
          }}>
            <strong>Testing Note:</strong> Clicking "Upgrade to Pro" will simulate a successful Stripe checkout and instantly upgrade your account to a Pro licence in Firestore, granting full access to the live dashboard.
          </div>
        </div>
      </div>

      {/* ── PLANS ── */}
      <section className="plans-section">
        <div className="container">
          <div className="plans-grid">
            {plans.map(plan => (
              <div
                key={plan.id}
                className={`plan-card glass-card${plan.popular ? ' plan-popular' : ''}`}
                style={{ '--plan-color': plan.color }}
              >
                {plan.badge && (
                  <div className="plan-badge">{plan.badge}</div>
                )}

                <div className="plan-header">
                  <div className="plan-icon" style={{ color: plan.color, background: `${plan.color}15`, borderColor: `${plan.color}30` }}>
                    {plan.id === 'free'       ? <Code2 size={20} /> :
                     plan.id === 'pro'        ? <Zap size={20} /> :
                                                <Building2 size={20} />}
                  </div>
                  <div>
                    <h3 className="plan-name">{plan.name}</h3>
                    <p className="plan-tagline">{plan.tagline}</p>
                  </div>
                </div>

                <div className="plan-price-block">
                  <span className="plan-price">{plan.price}</span>
                  <span className="plan-sub">{plan.sub}</span>
                </div>

                {plan.limit && (
                  <div className="plan-limit" style={{ borderColor: `${plan.color}25`, background: `${plan.color}08` }}>
                    <Zap size={11} color={plan.color} />
                    {plan.limit}
                  </div>
                )}

                <div className="plan-divider" style={{ background: `${plan.color}20` }} />

                <ul className="plan-features">
                  {plan.features.map(f => (
                    <li key={f.text} className={f.no ? 'feat-off' : 'feat-on'}>
                      {f.yes
                        ? <CheckCircle2 size={14} color={plan.color} />
                        : <XCircle size={14} color="rgba(255,255,255,0.15)" />
                      }
                      <span>{f.text}</span>
                    </li>
                  ))}
                </ul>

                <div className="plan-cta-wrap">
                  {plan.id === 'pro' ? (
                    <button onClick={handleProUpgrade} disabled={upgrading} className="btn-primary w-full plan-cta-btn">
                      {upgrading ? 'Upgrading...' : plan.cta} <ArrowRight size={15} />
                    </button>
                  ) : plan.ctaStyle === 'primary' ? (
                    <Link to={plan.ctaHref} className="btn-primary w-full plan-cta-btn">
                      {plan.cta} <ArrowRight size={15} />
                    </Link>
                  ) : (
                    <a href={plan.ctaHref} className="btn-secondary w-full plan-cta-btn">
                      {plan.cta}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* All plans note */}
          <div className="all-plans-note">
            <p>All plans include: OpenAI & Claude SDK compatibility · PII detection · Python SDK · HTTPS transport · Open-source core</p>
          </div>
        </div>
      </section>



      {/* ── FAQ ── */}
      <section className="faq-section">
        <div className="container">
          <div className="section-header">
            <div className="section-overline">FAQ</div>
            <h2>Common questions</h2>
          </div>

          <div className="faq-list">
            {FAQ.map((item, i) => (
              <div
                key={i}
                className={`faq-item glass-card${faqOpen === i ? ' faq-open' : ''}`}
                onClick={() => setFaqOpen(faqOpen === i ? null : i)}
              >
                <div className="faq-q">
                  <HelpCircle size={15} color="var(--accent-bright)" />
                  <strong>{item.q}</strong>
                  <ChevronDown size={16} className={`faq-chevron${faqOpen === i ? ' rotated' : ''}`} />
                </div>
                {faqOpen === i && (
                  <p className="faq-a">{item.a}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── ENTERPRISE CTA ── */}
      <section className="ent-cta-section">
        <div className="container">
          <div className="ent-cta-card glass-card">
            <Building2 size={28} color="var(--teal)" />
            <div className="ent-cta-text">
              <h3>Running at enterprise scale?</h3>
              <p>Custom contracts, private deployment, security questionnaires, and BAA signing — handled by our team. Typical response: 24 hours.</p>
            </div>
            <a href="mailto:hello@sentinel.ai" className="btn-teal">
              Contact Sales <ArrowRight size={15} />
            </a>
          </div>
        </div>
      </section>

    </div>
  )
}
