import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Shield, ShieldAlert, ShieldCheck, Activity, Clock,
  TrendingUp, Users, Zap, AlertTriangle, CheckCircle,
  RefreshCw, Terminal, Eye, Lock, Filter, Download,
  ChevronRight, Wifi, WifiOff, BarChart3, FileText,
  Bot, Cpu
} from 'lucide-react'
import { auth, onAuthStateChanged, signOut, db, doc, getDoc } from '../firebase'
import './AppDashboard.css'

const GATEWAY = import.meta.env.VITE_GATEWAY_URL || 'http://localhost:8000'

/* ── helpers ─────────────────────────────────────────── */
function badge(decision) {
  if (decision === 'BLOCK')   return 'badge-block'
  if (decision === 'REWRITE') return 'badge-rewrite'
  return 'badge-allow'
}

function scoreColor(s) {
  if (s >= 0.7) return '#ef4444'
  if (s >= 0.4) return '#f59e0b'
  return '#10b981'
}

function fmtMs(ms) {
  if (!ms) return '—'
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtPercent(n, total) {
  if (!total) return '0%'
  return `${((n / total) * 100).toFixed(1)}%`
}

/* ── DEMO DATA (shown when gateway is offline) ────────── */
const DEMO_ANALYTICS = {
  total_requests: 2847,
  blocked: 312,
  rewritten: 89,
  allowed: 2446,
  avg_threat_score: 0.1423,
  avg_latency_ms: 87.4,
  p99_latency_ms: 312,
  detection_rate: 0.1096,
  faiss_vectors: 156,
}

const DEMO_AGENTS = {
  // v1 core agents
  injection_scout: 0.88,
  pii_sentinel: 0.91,
  jailbreak_guard: 0.84,
  toxicity_screener: 0.76,
  hallucination_probe: 0.72,
  context_anchor: 0.71,
  compliance_tagger: 0.79,
  // v2 agents
  response_safety: 0.85,
  locale_compliance_router: 0.81,  // formerly MultilingualGuard
  tool_call_safety: 0.74,
  brand_guard: 0.67,
  token_anomaly: 0.69,
  // v3 agents
  prompt_lineage: 0.65,
  intent_classifier: 0.83,
  adversarial_rephrasing: 0.77,
  // v4 new agents
  jailbreak_pattern_detector: 0.92, // DAN attacks, roleplay bypass
  cost_anomaly_detector: 0.70,      // runaway token spend
  agentic_loop_breaker: 0.68,       // infinite tool-call loop detection
}

const DEMO_AUDIT = [
  { audit_id: 'a1', timestamp: new Date(Date.now() - 30000).toISOString(), decision: 'BLOCK', aggregate_score: 0.93, triggering_agent: 'jailbreak_pattern_detector', latency_ms: 88, compliance_tags: ['DPDP'] },
  { audit_id: 'a2', timestamp: new Date(Date.now() - 65000).toISOString(), decision: 'ALLOW', aggregate_score: 0.04, triggering_agent: null, latency_ms: 74, compliance_tags: [] },
  { audit_id: 'a3', timestamp: new Date(Date.now() - 120000).toISOString(), decision: 'REWRITE', aggregate_score: 0.48, triggering_agent: 'pii_sentinel', latency_ms: 108, compliance_tags: ['GDPR'] },
  { audit_id: 'a4', timestamp: new Date(Date.now() - 200000).toISOString(), decision: 'BLOCK', aggregate_score: 0.85, triggering_agent: 'agentic_loop_breaker', latency_ms: 62, compliance_tags: [] },
  { audit_id: 'a5', timestamp: new Date(Date.now() - 310000).toISOString(), decision: 'BLOCK', aggregate_score: 0.87, triggering_agent: 'injection_scout', latency_ms: 96, compliance_tags: ['DPDP', 'GDPR'] },
  { audit_id: 'a6', timestamp: new Date(Date.now() - 450000).toISOString(), decision: 'ALLOW', aggregate_score: 0.11, triggering_agent: null, latency_ms: 68, compliance_tags: [] },
  { audit_id: 'a7', timestamp: new Date(Date.now() - 600000).toISOString(), decision: 'BLOCK', aggregate_score: 0.79, triggering_agent: 'cost_anomaly_detector', latency_ms: 45, compliance_tags: [] },
]

/* ── stat card ────────────────────────────────────────── */
function StatCard({ icon: Icon, label, value, sub, color, trend }) {
  return (
    <div className="stat-card">
      <div className="stat-icon" style={{ background: `${color}18`, color }}>
        <Icon size={18} />
      </div>
      <div className="stat-body">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
      {trend !== undefined && (
        <div className={`stat-trend ${trend >= 0 ? 'trend-up' : 'trend-down'}`}>
          <TrendingUp size={12} />
          {Math.abs(trend)}%
        </div>
      )}
    </div>
  )
}

/* ── agent row ────────────────────────────────────────── */
function AgentRow({ name, weight }) {
  const pct = Math.round(weight * 100)
  const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  return (
    <div className="agent-row">
      <div className="agent-name">
        <Bot size={12} />
        <span>{label}</span>
      </div>
      <div className="agent-bar-wrap">
        <div
          className="agent-bar"
          style={{ width: `${pct}%`, background: scoreColor(1 - weight + 0.2) }}
        />
      </div>
      <div className="agent-pct" style={{ color: scoreColor(1 - weight + 0.2) }}>
        {pct}%
      </div>
    </div>
  )
}

/* ════════════════════════════════════════
   MAIN PAGE
════════════════════════════════════════ */
export default function AppDashboard() {
  const [user, setUser]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [online, setOnline]       = useState(false)
  const [gatewayJwt, setGatewayJwt] = useState(null)

  const [analytics, setAnalytics] = useState(DEMO_ANALYTICS)
  const [audit, setAudit]         = useState(DEMO_AUDIT)
  const [weights, setWeights]     = useState(DEMO_AGENTS)
  const [events, setEvents]       = useState([])
  const [filter, setFilter]       = useState('ALL')
  const [refreshing, setRefreshing] = useState(false)
  const [lastRefresh, setLastRefresh] = useState(null)
  const wsRef                     = useRef(null)
  const navigate                  = useNavigate()

  /* ── Auth guard ─────────────────────────────── */
  const [isPro, setIsPro] = useState(false)

  /* ── Fetch all data ────────────────────────── */
  const fetchAll = useCallback(async (jwt) => {
    const headers = { Authorization: `Bearer ${jwt}` }
    try {
      const [aRes, auRes, wRes] = await Promise.all([
        fetch(`${GATEWAY}/v1/analytics`, { headers, signal: AbortSignal.timeout(5000) }),
        fetch(`${GATEWAY}/v1/audit?limit=20`, { headers, signal: AbortSignal.timeout(5000) }),
        fetch(`${GATEWAY}/admin/weights`, { headers, signal: AbortSignal.timeout(5000) }),
      ])
      if (aRes.ok)  setAnalytics(await aRes.json())
      if (auRes.ok) setAudit(await auRes.json())
      if (wRes.ok)  { const d = await wRes.json(); setWeights(d.weights || d) }
      setLastRefresh(new Date())
    } catch {
      /* keep demo data */
    }
  }, [])

  /* ── WebSocket for real-time events ─────────── */
  const openWs = useCallback((jwt) => {
    if (wsRef.current) wsRef.current.close()
    const wsUrl = GATEWAY.replace(/^http/, 'ws') + `/ws/dashboard?token=${jwt}`
    const ws = new WebSocket(wsUrl)
    ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data)
        setEvents(prev => [ev, ...prev].slice(0, 50))
      } catch {}
    }
    wsRef.current = ws
    return () => ws.close()
  }, [])

  /* ── Gateway bootstrap ─────────────────────── */
  const bootstrapGateway = useCallback(async (u) => {
    try {
      const regBody = {
        tenant_id: u.uid.slice(0, 32),
        name: u.displayName || u.email?.split('@')[0] || 'user',
        email: u.email || 'user@sentinel.ai',
        password: u.uid.slice(0, 16),
        use_case: 'dashboard',
      }
      await fetch(`${GATEWAY}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(regBody),
        signal: AbortSignal.timeout(1500),
      })

      const form = new URLSearchParams()
      form.append('username', u.uid.slice(0, 32))
      form.append('password', u.uid.slice(0, 16))
      const tokenRes = await fetch(`${GATEWAY}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString(),
        signal: AbortSignal.timeout(1500),
      })
      if (!tokenRes.ok) throw new Error('Token failed')
      const { access_token } = await tokenRes.json()
      setGatewayJwt(access_token)
      setOnline(true)
      await fetchAll(access_token)
      openWs(access_token)
    } catch {
      setOnline(false)
    }
  }, [fetchAll, openWs])

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (u) => {
      if (!u) {
        navigate('/signin')
        return
      }
      setUser(u)

      try {
        const userDoc = await getDoc(doc(db, 'users', u.uid))
        if (userDoc.exists() && userDoc.data().plan === 'pro') {
          setIsPro(true)
          await bootstrapGateway(u)
        } else {
          setIsPro(false)
          // Free users still see the dashboard, just with demo data
        }
      } catch (err) {
        console.error(err)
        setIsPro(false)
      }
      setLoading(false)
    })
    return unsub
  }, [navigate, bootstrapGateway])

  /* ── Manual refresh ────────────────────────── */
  const handleRefresh = async () => {
    if (!gatewayJwt) return
    setRefreshing(true)
    await fetchAll(gatewayJwt)
    setRefreshing(false)
  }

  useEffect(() => () => wsRef.current?.close(), [])

  const handleSignOut = async () => {
    wsRef.current?.close()
    await signOut(auth)
    navigate('/')
  }

  /* ── Filtered audit ────────────────────────── */
  const displayed = filter === 'ALL' ? audit : audit.filter(r => r.decision === filter)

  if (loading) {
    return (
      <div className="app-dash-loading">
        <div className="dash-spinner" />
        <p>Loading your dashboard…</p>
      </div>
    )
  }

  const blockRate = fmtPercent(analytics.blocked, analytics.total_requests)
  const rewriteRate = fmtPercent(analytics.rewritten, analytics.total_requests)
  const trustScore = Math.round((1 - analytics.avg_threat_score) * 100)

  return (
    <div className="app-dash">
      {/* ── Free-tier upgrade banner ─────────── */}
      {!isPro && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px',
          padding: '10px 20px', background: 'linear-gradient(90deg, rgba(99,102,241,0.15), rgba(6,182,212,0.1))',
          borderBottom: '1px solid rgba(99,102,241,0.2)', fontSize: '0.85rem', color: 'var(--text-muted)',
          flexWrap: 'wrap', textAlign: 'center',
        }}>
          <Zap size={14} color="#818cf8" />
          <span>You're viewing <strong style={{color:'var(--text)'}}>demo data</strong>. Upgrade to Pro for live threat analytics, compliance exports, and real-time monitoring.</span>
          <button onClick={() => navigate('/pricing')} className="btn-primary" style={{ padding: '5px 14px', fontSize: '0.8rem' }}>
            Upgrade to Pro
          </button>
        </div>
      )}

      {/* ── Header ─────────────────────────────── */}
      <div className="dash-header">
        <div className="dash-header-left">
          <div className="dash-title">
            <Shield size={22} color="#818cf8" />
            <h1>Security Dashboard</h1>
          </div>
          <div className="dash-user-info">
            <div className="dash-avatar">
              {user?.displayName?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
            </div>
            <div>
              <div className="dash-user-name">{user?.displayName || user?.email?.split('@')[0]}</div>
              <div className="dash-user-email">{user?.email}</div>
            </div>
          </div>
        </div>
        <div className="dash-header-right">
          <div className={`gateway-status ${online ? 'online' : 'offline'}`}>
            {online ? <Wifi size={13} /> : <WifiOff size={13} />}
            <span>{online ? 'Gateway connected' : (isPro ? 'Gateway offline — showing cached data' : 'Free tier — demo data')}</span>
          </div>
          <button
            className="dash-btn-ghost"
            onClick={() => {
              if (user?.uid) {
                navigator.clipboard.writeText(user.uid.slice(0, 32))
                alert('API Key (Tenant ID) copied to clipboard!')
              }
            }}
            title="Copy API Key for SDK"
          >
            <Lock size={15} /> Key
          </button>
          {online && (
            <button
              className="dash-btn-ghost"
              onClick={handleRefresh}
              disabled={refreshing}
              title="Refresh data"
            >
              <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
              {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Refresh'}
            </button>
          )}
          <button className="dash-btn-ghost dash-signout" onClick={handleSignOut}>
            Sign out
          </button>
        </div>
      </div>

      {/* ── Stat cards ─────────────────────────── */}
      <div className="stats-grid">
        <StatCard
          icon={Activity}
          label="Total Requests (24h)"
          value={analytics.total_requests.toLocaleString()}
          color="#818cf8"
        />
        <StatCard
          icon={ShieldAlert}
          label="Threats Blocked"
          value={analytics.blocked.toLocaleString()}
          sub={`${blockRate} of traffic`}
          color="#ef4444"
        />
        <StatCard
          icon={Eye}
          label="Rewrites Applied"
          value={analytics.rewritten.toLocaleString()}
          sub={`${rewriteRate} of traffic`}
          color="#f59e0b"
        />
        <StatCard
          icon={ShieldCheck}
          label="Trust Score"
          value={`${trustScore}/100`}
          sub="avg across all requests"
          color="#10b981"
        />
        <StatCard
          icon={Clock}
          label="Avg Latency"
          value={fmtMs(analytics.avg_latency_ms)}
          sub={`p99: ${fmtMs(analytics.p99_latency_ms)}`}
          color="#06b6d4"
        />
        <StatCard
          icon={Cpu}
          label="Threat Memory Vectors"
          value={analytics.faiss_vectors?.toLocaleString() ?? '—'}
          sub="known attack patterns cached"
          color="#a78bfa"
        />
      </div>

      {/* ── Main content ────────────────────────── */}
      <div className="dash-main-grid">

        {/* ── Audit log ──────────────────────────── */}
        <div className="dash-panel audit-panel">
          <div className="panel-header">
            <div className="panel-title">
              <FileText size={16} />
              <h2>Audit Log</h2>
              {!online && <span className="demo-tag">demo</span>}
            </div>
            <div className="audit-filters">
              {['ALL', 'BLOCK', 'REWRITE', 'ALLOW'].map(f => (
                <button
                  key={f}
                  className={`filter-btn ${filter === f ? 'active' : ''} ${f === 'BLOCK' ? 'filter-block' : f === 'REWRITE' ? 'filter-rewrite' : f === 'ALLOW' ? 'filter-allow' : ''}`}
                  onClick={() => setFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Decision</th>
                  <th>Score</th>
                  <th>Triggered By</th>
                  <th>Latency</th>
                  <th>Tags</th>
                </tr>
              </thead>
              <tbody>
                {displayed.length === 0 && (
                  <tr><td colSpan={6} className="empty-row">No records found</td></tr>
                )}
                {displayed.map((row) => (
                  <tr key={row.audit_id} className="audit-row">
                    <td className="audit-time">{fmtTime(row.timestamp)}</td>
                    <td>
                      <span className={`decision-badge ${badge(row.decision)}`}>
                        {row.decision}
                      </span>
                    </td>
                    <td>
                      <span
                        className="score-pill"
                        style={{ color: scoreColor(row.aggregate_score) }}
                      >
                        {(row.aggregate_score * 100).toFixed(0)}
                      </span>
                    </td>
                    <td className="audit-agent">
                      {row.triggering_agent
                        ? row.triggering_agent.replace(/_/g, ' ')
                        : <span className="muted">—</span>}
                    </td>
                    <td className="audit-latency">{fmtMs(row.latency_ms)}</td>
                    <td>
                      {(row.compliance_tags || []).map(t => (
                        <span key={t} className="compliance-tag">{t}</span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Right column ───────────────────────── */}
        <div className="dash-right-col">

          {/* Real-time stream */}
          <div className="dash-panel stream-panel">
            <div className="panel-header">
              <div className="panel-title">
                <Terminal size={16} />
                <h2>Live Event Stream</h2>
                {online && events.length > 0 && <div className="live-dot" />}
              </div>
            </div>
            <div className="stream-body">
              {events.length === 0 ? (
                <div className="stream-empty">
                  <WifiOff size={20} color="var(--text-muted)" />
                  <p>{online ? 'Waiting for events…' : (isPro ? 'Ensure your gateway is running (localhost:8000) to see live events.' : '⚡ Upgrade to Pro to connect your gateway and see live events.')}</p>
                </div>
              ) : (
                events.slice(0, 15).map((ev, i) => (
                  <div key={i} className="stream-event">
                    <span className={`stream-badge ${badge(ev.decision)}`}>{ev.decision}</span>
                    <span className="stream-agent">{ev.triggering_agent || 'none'}</span>
                    <span className="stream-score" style={{ color: scoreColor(ev.aggregate_score || 0) }}>
                      {((ev.aggregate_score || 0) * 100).toFixed(0)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Agent weights */}
          <div className="dash-panel agents-panel">
            <div className="panel-header">
              <div className="panel-title">
                <Bot size={16} />
                <h2>Agent Confidence <span style={{fontSize:'11px', color:'var(--text-muted)', fontWeight:400}}>(19 agents)</span></h2>
                {!online && <span className="demo-tag">demo</span>}
              </div>
            </div>
            <div className="agents-list">
              {Object.entries(weights)
                .sort((a, b) => b[1] - a[1])
                .map(([name, w]) => (
                  <AgentRow key={name} name={name} weight={w} />
                ))}
            </div>
          </div>

        </div>
      </div>

      {/* ── Gateway setup callout (when offline) ── */}
      {!online && (
        <div className="offline-callout">
          <AlertTriangle size={18} color="#f59e0b" />
          <div>
            <strong>Gateway not connected</strong> — You're viewing demo data. To connect your live gateway:
            <code>uvicorn sentinel.gateway.main:app --reload --port 8000</code>
            <span style={{display:'block', marginTop:'6px', color:'var(--text-muted)', fontSize:'12px'}}>
              Running 19-agent v4 mesh · Multi-Agent Consensus · Real-time WebSocket stream
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
