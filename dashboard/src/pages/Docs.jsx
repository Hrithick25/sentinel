import { useState } from 'react'
import { BookOpen, Zap, Key, Code2, GitBranch, FileText, Package, Settings, Terminal, Copy, Check } from 'lucide-react'
import './Docs.css'

/* ── Sidebar nav structure ────────────────────────── */
const NAV = [
  {
    group: 'Getting Started',
    icon: <Zap size={14} />,
    items: [
      { id: 'quickstart',     label: 'Quickstart Guide' },
      { id: 'how-it-works',   label: 'How Sentinel Works' },
      { id: 'api-keys',       label: 'API Keys & Authentication' },
      { id: 'sandbox',        label: 'Sandbox / Test Mode' },
      { id: 'changelog',      label: 'Changelog / Versions' },
    ],
  },
  {
    group: 'Integration',
    icon: <Code2 size={14} />,
    items: [
      { id: 'openai',         label: 'OpenAI Client Wrap' },
      { id: 'anthropic',      label: 'Anthropic / Claude' },
      { id: 'error-handling', label: 'Error Handling' },
    ],
  },
  {
    group: 'Configuration',
    icon: <Settings size={14} />,
    items: [
      { id: 'policies',       label: 'Policy Profiles' },
      { id: 'thresholds',     label: 'Agent Thresholds' },
      { id: 'tenants',        label: 'Multi-Tenant Setup' },
    ],
  },
  {
    group: 'Compliance & Audit',
    icon: <FileText size={14} />,
    items: [
      { id: 'audit-logs',     label: 'Audit Log Format' },
      { id: 'hipaa',          label: 'HIPAA Export' },
      { id: 'gdpr',           label: 'GDPR Data Subject Requests' },
    ],
  },
  {
    group: 'Self-Hosted',
    icon: <GitBranch size={14} />,
    items: [
      { id: 'docker',         label: 'Docker Compose Setup' },
      { id: 'config',         label: 'Environment Variables' },
    ],
  },
]

const TOC_MAP = {
  'quickstart': ['Install the SDK', 'Obtain Your API Key', 'Wrap Your LLM Client', 'What Happens', 'Free vs Pro'],
  'how-it-works': ['Architecture', '19-Agent Decision Mesh'],
  'api-keys': ['Key Format', 'Environment Variables', 'Key Scopes'],
  'docker': ['Production Requirements', 'Quick Start', 'System Validation'],
  'sandbox': ['Sandbox Mode', 'Testing'],
  'error-handling': ['SentinelBlockedError', 'SentinelProRequiredError', 'Catching Errors'],
  'changelog': ['v3.1.0 — Current', 'v3.0.1', 'v0.1.0'],
}

/* ── Copy button ──────────────────────────────────── */
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const handle = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button className="copy-btn" onClick={handle} title="Copy to clipboard">
      {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} />}
    </button>
  )
}

/* ── Code block component ─────────────────────────── */
function CodeBlock({ code, lang = 'python' }) {
  return (
    <div className="code-block">
      <div className="cb-header">
        <span className="cb-lang">{lang}</span>
        <CopyButton text={code} />
      </div>
      <pre className="cb-pre"><code>{code}</code></pre>
    </div>
  )
}

/* ── Alert component ──────────────────────────────── */
function Alert({ type = 'info', children }) {
  const colors = {
    info:    { bg: 'rgba(79,70,229,0.1)',  border: 'rgba(99,102,241,0.35)',  color: '#818cf8' },
    success: { bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.35)', color: '#10b981' },
    warning: { bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.35)', color: '#f59e0b' },
  }
  const c = colors[type]
  return (
    <div className="doc-alert" style={{ background: c.bg, borderColor: c.border, borderLeft: `3px solid ${c.color}` }}>
      {children}
    </div>
  )
}

/* ── Main content sections ────────────────────────── */
const CONTENT = {
  quickstart: (
    <>
      <h1>Quickstart Guide</h1>
      <p className="doc-lead">
        Get Sentinel running in your Python environment in under 5 minutes.
        Zero infrastructure required — our managed edge cluster handles all the heavy ML compute.
      </p>

      <h2>1. Install the SDK</h2>
      <p>Install the lightweight Sentinel client. It has zero heavy ML or CUDA dependencies.</p>
      <CodeBlock lang="bash" code={`pip install sentinel-ai-sdk`} />

      <Alert type="success">
        <strong>Tip:</strong> The SDK is under 500 KB. All 19-agent inference runs on Sentinel's edge cluster — not your machine.
      </Alert>

      <h2>2. Obtain Your API Key</h2>
      <p>
        Sign up at <code>sentinel-ai.dev</code> to receive your API key.
        Store it as an environment variable — never embed it in source code.
      </p>
      <CodeBlock lang="bash" code={`export SENTINEL_API_KEY="sntnl-your-key-here"`} />

      <h2>3. Wrap Your LLM Client</h2>
      <p>
        Sentinel acts as a transparent proxy. Your existing application code remains completely unchanged
        — you simply replace the client object.
      </p>
      <CodeBlock lang="python" code={`import sentinel
import openai

# Your standard OpenAI client
client = openai.OpenAI(api_key="sk-openai-...")

# Wrap with Sentinel — one line, fully protected
safe_client = sentinel.wrap(
    client,
    api_key="sntnl-your-key-here",
    tenant_id="your-org",
)

# Use exactly as before — Sentinel intercepts transparently
response = safe_client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.choices[0].message.content)`} />

      <h2>What Happens on Each Request</h2>
      <ol className="doc-list">
        <li>Your Python code calls <code>safe_client.chat.completions.create()</code> as normal.</li>
        <li>The SDK serialises the payload and forwards it to the Sentinel Gateway over HTTPS.</li>
        <li>19 security agents evaluate the prompt in parallel inside the edge cluster (typically &lt;70ms).</li>
        <li>If clean, the request is forwarded to OpenAI. If a threat is detected, a <code>SentinelBlockedError</code> is raised with the exact violation reason.</li>
        <li>The response is scanned by the output safety layer before being returned to your application.</li>
        <li>A signed, immutable audit record is written to your organisation's ledger.</li>
      </ol>

      <h2>Free vs Pro</h2>
      <p>The same pip package works on both tiers. Your plan is determined by your API key:</p>
      <div className="scope-table">
        <div className="scope-row"><code className="scope-name">Free</code><span className="scope-desc">screen(), trust_score(), wrap() — core AI protection with demo dashboard</span></div>
        <div className="scope-row"><code className="scope-name">Pro</code><span className="scope-desc">All Free features + analytics(), compliance_export(), configure_agents(), audit_log() + live dashboard</span></div>
      </div>
    </>
  ),

  'how-it-works': (
    <>
      <h1>How Sentinel Works</h1>
      <p className="doc-lead">
        Sentinel is a hybrid security middleware — a lightweight SDK on your side,
        a powerful 19-agent mesh on ours.
      </p>

      <h2>Architecture Overview</h2>
      <div className="arch-diagram">
        {[
          { label: 'Your Application', sub: 'Python / LangChain / FastAPI', color: '#4f46e5' },
          { label: 'Sentinel SDK', sub: 'pip install (lightweight)', color: '#818cf8' },
          { label: 'Sentinel Gateway', sub: 'Edge cluster · 19 agents · FAISS', color: '#06b6d4' },
          { label: 'LLM Provider', sub: 'OpenAI · Anthropic', color: '#10b981' },
        ].map((node, i) => (
          <div key={node.label} className="arch-node-wrap">
            <div className="arch-node" style={{ borderColor: node.color }}>
              <div className="arch-node-label">{node.label}</div>
              <div className="arch-node-sub">{node.sub}</div>
            </div>
            {i < 3 && <div className="arch-arrow">→</div>}
          </div>
        ))}
      </div>

      <h2>The 19-Agent Decision Mesh</h2>
      <p>Every request is evaluated in parallel by 19 specialised agents. A Bayesian-weighted consensus determines the final allow / block decision:</p>

      <div className="agent-table">
        <div className="at-header">
          <span>Agent</span><span>Scope</span><span>Method</span>
        </div>
        {[
          ['Injection Scout',          'Prompt Input',   'Vector-similarity + regex rules'],
          ['PII Sentinel',             'Input & Output', 'Named-entity recognition (NER)'],
          ['Jailbreak Firewall',       'Prompt Input',   'FAISS nearest-neighbour search'],
          ['Jailbreak Pattern Detector','Prompt Input',   'DAN / roleplay / bypass pattern matching'],
          ['Toxicity Screener',        'Input & Output', 'Fine-tuned classifier'],
          ['Hallucination Probe',      'LLM Output',     'NLI entailment vs. RAG context'],
          ['Context Drift Sensor',     'Session History','Semantic embedding drift score'],
          ['Compliance Tagger',        'Input & Output', 'Rule-based + NER mapping'],
          ['Response Safety Layer',    'LLM Output',     'Post-generation policy sweep'],
          ['Locale Compliance Router', 'Input',          'Language-aware regulatory routing'],
          ['Tool-Call Safety',         'Function Calls', 'Schema validation + permission check'],
          ['Brand & Tone Guardian',    'Output',         'Keyword + embedding similarity'],
          ['Token Anomaly Detector',   'Input',          'Statistical token distribution'],
          ['Prompt Lineage Tracker',   'Full Turn',      'Cryptographic event chaining'],
          ['Intent Classifier',        'Input',          'Multi-label intent classification'],
          ['Adversarial Rephrasing',   'Input',          'T5-based canonical normalisation'],
          ['Cost Anomaly Detector',    'Token Usage',    'Runaway token spend detection'],
          ['Agentic Loop Breaker',     'Tool Calls',     'Infinite tool-call loop detection'],
          ['Response Safety',          'LLM Output',     'Post-generation output scan'],
        ].map(([agent, scope, method]) => (
          <div className="at-row" key={agent}>
            <span className="at-agent">{agent}</span>
            <span className="at-scope">{scope}</span>
            <span className="at-method">{method}</span>
          </div>
        ))}
      </div>
    </>
  ),

  'api-keys': (
    <>
      <h1>API Keys & Authentication</h1>
      <p className="doc-lead">
        Sentinel uses API keys for SDK authentication and JWTs for the management dashboard.
        Keys are scoped per organisation and can be rotated without downtime.
      </p>

      <h2>Key Format</h2>
      <CodeBlock lang="text" code={`sntnl-live-xxxxxxxxxxxxxxxxxxxxxxxx   # Production key
sntnl-test-xxxxxxxxxxxxxxxxxxxxxxxx   # Sandbox / staging key`} />

      <Alert type="warning">
        <strong>Security:</strong> Treat your Sentinel API key like a database password.
        Store it exclusively in environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager).
        Never commit it to version control.
      </Alert>

      <h2>Setting the Key via Environment Variable</h2>
      <CodeBlock lang="python" code={`import os
import sentinel

safe_client = sentinel.wrap(
    your_llm_client,
    api_key=os.environ["SENTINEL_API_KEY"],  # recommended
)`} />

      <h2>Key Scopes</h2>
      <div className="scope-table">
        {[
          { scope: 'read:audit',    desc: 'Read audit logs and decision history' },
          { scope: 'write:request', desc: 'Submit requests through the gateway (SDK default)' },
          { scope: 'admin:policy',  desc: 'Update agent thresholds and policy profiles' },
          { scope: 'admin:tenant',  desc: 'Manage tenant configuration and billing' },
        ].map(s => (
          <div key={s.scope} className="scope-row">
            <code className="scope-name">{s.scope}</code>
            <span className="scope-desc">{s.desc}</span>
          </div>
        ))}
      </div>
    </>
  ),

  docker: (
    <>
      <h1>Self-Hosted Deployment</h1>
      <p className="doc-lead">
        Deploy Sentinel securely within your VPC using Docker Compose. All audit logs, processing, and compliance data remains entirely in your control.
      </p>

      <h2>Minimal Production Requirements</h2>
      <ul>
        <li>Docker 24.0+ & Docker Compose</li>
        <li>2 CPU Cores, 4GB RAM (Gateway Server)</li>
        <li>PostgreSQL Database (for persistent audit records)</li>
      </ul>

      <h2>Quick Start</h2>
      <p>Clone the enterprise repository and boot the core services:</p>
      <CodeBlock lang="bash" code={`git clone https://github.com/sentinel-ai/sentinel
cd sentinel

# Configure secrets
cp .env.example .env

# Boot the gateway + database
docker compose up -d postgres gateway`} />

      <h2>System Validation</h2>
      <CodeBlock lang="bash" code={`# Ensure gateway is actively loaded with all security modules
curl -s http://localhost:8000/health | grep '"status":"healthy"'`} />
    </>
  ),
  sandbox: (
    <>
      <h1>Sandbox / Test Mode</h1>
      <p className="doc-lead">Run end-to-end tests without triggering production policies or generating billable audit logs.</p>
      <h2>Sandbox Mode</h2>
      <p>Use your <code>sntnl-test-...</code> API key. This entirely isolates the requests from your production ledger.</p>
      <CodeBlock lang="python" code={`safe_client = sentinel.wrap(client, api_key="sntnl-test-xxx")`} />
      <h2>Testing</h2>
      <p>Pass the <code>x-sentinel-dry-run</code> header manually if you want to see what WOULD be blocked, without actually blocking it.</p>
    </>
  ),
  'error-handling': (
    <>
      <h1>Error Handling</h1>
      <p className="doc-lead">Catch and respond to AI threats programmatically in your application.</p>
      <h2>SentinelBlockedError</h2>
      <p>When the gateway blocks a request based on consensus, the SDK raises a <code>SentinelBlockedError</code> with the request ID, risk score, and triggering agent name.</p>
      <h2>SentinelProRequiredError</h2>
      <p>Raised when a free-tier user calls a Pro-only method like <code>analytics()</code> or <code>compliance_export()</code>.</p>
      <h2>Catching Errors</h2>
      <CodeBlock lang="python" code={`from sentinel import SentinelBlockedError, SentinelProRequiredError

try:
    response = safe_client.chat.completions.create(...)
except SentinelBlockedError as e:
    print(f"Blocked: request_id={e.request_id}, score={e.score}")
    print(f"Triggered by: {e.agent}")

# Pro feature guard
try:
    stats = client.analytics()
except SentinelProRequiredError as e:
    print(f"Pro required for: {e.feature}")
    # → "'analytics' requires a Sentinel Pro subscription."
    # → "Upgrade at https://sentinel-ai.dev/pricing"`} />
    </>
  ),
  changelog: (
    <>
      <h1>Changelog / Versions</h1>
      <p className="doc-lead">Keep track of updates to the Sentinel SDK and Gateway.</p>
      <h2>v3.1.0 — Current</h2>
      <ul>
        <li>19-agent mesh with 4 new v4 agents (Jailbreak Pattern Detector, Cost Anomaly, Agentic Loop Breaker, Locale Router)</li>
        <li>Pro / Free tier system — free users get core protection, Pro unlocks analytics + compliance exports</li>
        <li><code>SentinelBlockedError</code> and <code>SentinelProRequiredError</code> custom exceptions</li>
        <li>Dashboard accessible to all signed-in users (free = demo data, Pro = live gateway)</li>
        <li>Compliance export API (JSON / CSV / PDF)</li>
      </ul>
      <h2>v3.0.1</h2>
      <ul>
        <li>15-agent mesh with Bayesian consensus engine</li>
        <li>OpenAI and Anthropic wrappers</li>
        <li>Live dashboard with WebSocket streaming</li>
      </ul>
      <h2>v0.1.0</h2>
      <ul>
        <li>Initial public beta release</li>
        <li>Core injection, PII, and jailbreak detection</li>
      </ul>
    </>
  ),
  openai: (
    <>
      <h1>OpenAI Client Wrap</h1>
      <p className="doc-lead">Seamlessly secure your OpenAI client in one step.</p>
      <CodeBlock lang="python" code={`import sentinel
import openai
client = openai.OpenAI(api_key="...")
safe_client = sentinel.wrap(client)
res = safe_client.chat.completions.create(model="gpt-4", messages=[...])`} />
    </>
  ),
  anthropic: (
    <>
      <h1>Anthropic / Claude</h1>
      <p className="doc-lead">Wrap your Anthropic Claude client effortlessly.</p>
      <CodeBlock lang="python" code={`import sentinel
from anthropic import Anthropic
client = Anthropic(api_key="...")
safe_client = sentinel.wrap(client)
res = safe_client.messages.create(model="claude-3-opus", messages=[...])`} />
    </>
  ),
  policies: (
    <>
      <h1>Policy Profiles</h1>
      <p className="doc-lead">Define the strictness of your security guardrails using out-of-the-box profiles.</p>
      <CodeBlock lang="python" code={`# Options: "enterprise-strict", "hipaa", "gdpr", "permissive", "custom"
safe_client = sentinel.wrap(client, policy="hipaa")`} />
    </>
  ),
  thresholds: (
    <>
      <h1>Agent Thresholds</h1>
      <p className="doc-lead">Fine-tune the trigger sensitivity of individual AI agents.</p>
      <CodeBlock lang="python" code={`# Override individual thresholds programmatically
safe_client = sentinel.wrap(
    client,
    thresholds={
        "jailbreak": 0.85,
        "toxicity": 0.90
    }
)`} />
    </>
  ),
  tenants: (
    <>
      <h1>Multi-Tenant Setup</h1>
      <p className="doc-lead">Isolate policies and audit logs for your B2B customers automatically.</p>
      <CodeBlock lang="python" code={`safe_client = sentinel.wrap(client, tenant_id="org-acme-prod")`} />
    </>
  ),
  'audit-logs': (
    <>
      <h1>Audit Log Format</h1>
      <p className="doc-lead">View the immutable event structure captured in the database.</p>
      <CodeBlock lang="json" code={`{
  "id": "evt_9f3a4c2",
  "tenant_id": "org-acme-prod",
  "decision": "BLOCKED",
  "agent": "PIISentinel",
  "latency_ms": 42,
  "timestamp": "2026-04-07T12:00:00Z"
}`} />
    </>
  ),
  hipaa: (
    <>
      <h1>HIPAA Export</h1>
      <p className="doc-lead">Export PHI access logs for HIPAA audits.</p>
      <CodeBlock lang="bash" code={`curl -H "Auth: Bearer $KEY" https://gateway/v1/audit/export?format=hipaa`} />
    </>
  ),
  gdpr: (
    <>
      <h1>GDPR Data Subject Requests</h1>
      <p className="doc-lead">Query logs to fulfil GDPR Right to Access/Erasure.</p>
      <CodeBlock lang="bash" code={`# Find logs related to a specific user hash to wipe
curl -X DELETE https://gateway/v1/audit/user/hash123`} />
    </>
  ),
  config: (
    <>
      <h1>Environment Variables</h1>
      <p className="doc-lead">Full reference of all `.env` options available for the Gateway.</p>
      <CodeBlock lang="bash" code={`ENVIRONMENT="production"
SECRET_KEY="crypto-secure-key"
DATABASE_BACKEND="postgres"
DATABASE_URL="postgresql+asyncpg://..."
REDIS_URL="redis://..."`} />
    </>
  ),
}

export default function Docs() {
  const [active, setActive] = useState('quickstart')
  const content = CONTENT[active] || CONTENT.quickstart

  return (
    <div className="docs-page">
      {/* Sidebar */}
      <aside className="docs-sidebar">
        <div className="sidebar-search">
          <input type="search" placeholder="Search docs (Coming Soon)…" />
        </div>
        {NAV.map(section => (
          <div key={section.group} className="sidebar-group">
            <div className="sidebar-group-header">
              {section.icon}
              <h4>{section.group}</h4>
            </div>
            <ul>
              {section.items.map(item => (
                <li
                  key={item.id}
                  className={active === item.id ? 'active' : ''}
                  onClick={() => setActive(item.id)}
                >
                  {item.label}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>

      {/* Main content */}
      <main className="docs-content">
        <div className="docs-body">
          {content}
        </div>
      </main>

      {/* Right TOC (page outline) */}
      <aside className="docs-toc">
        <p className="toc-title">On This Page</p>
        <ul>
          {(TOC_MAP[active] || []).map((t, idx) => (
            <li key={idx}><a href="#">{t}</a></li>
          ))}
          {(!TOC_MAP[active] || TOC_MAP[active].length === 0) && (
            <li><span className="muted">No sub-sections</span></li>
          )}
        </ul>
        <div className="toc-divider" />
        <a href="#" className="toc-link-ext">
          <Package size={13} /> PyPI Package
        </a>
        <a href="#" className="toc-link-ext">
          <GitBranch size={13} /> GitHub Repo
        </a>
      </aside>
    </div>
  )
}
