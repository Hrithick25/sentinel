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
      { id: 'nodejs',         label: 'Node.js / TypeScript' },
      { id: 'java',           label: 'Java' },
      { id: 'react',          label: 'React Frontend' },
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
  'nodejs': ['Install', 'Screen API', 'Trust Score API', 'Full Chat Proxy', 'Error Handling'],
  'java': ['Dependencies', 'Screen API', 'Trust Score API', 'Full Chat Proxy'],
  'react': ['Setup', 'Hook Pattern', 'Inline Guard Component', 'Dashboard Embed'],
  'changelog': ['v4.0.0 — Current', 'v3.0.1', 'v0.1.0'],
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
      <CodeBlock lang="bash" code={`pip install sentinel-guardrails-sdk`} />

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
          ['Jailbreak Firewall',       'Prompt Input',   'Sliding-window multi-turn analysis'],
          ['Toxicity Screener',        'Input & Output', 'Fine-tuned Detoxify classifier'],
          ['Hallucination Probe',      'LLM Output',     'DeBERTa NLI entailment vs. RAG context'],
          ['Context Anchor',           'Session History','Cosine embedding drift score'],
          ['Compliance Tagger',        'Input & Output', 'Rule-based HIPAA/GDPR/DPDP mapping'],
          ['Response Safety Layer',    'LLM Output',     'Post-generation policy sweep'],
          ['Multilingual Guard',       'Input',          'Cross-language jailbreak detection'],
          ['Tool-Call Safety',         'Function Calls', 'Schema validation + permission check'],
          ['Brand & Tone Guardian',    'Output',         'Keyword + embedding similarity'],
          ['Token Anomaly Detector',   'Input',          'Statistical token distribution'],
          ['Prompt Lineage Tracker',   'Full Turn',      'Redis session memory graph'],
          ['Intent Classifier',        'Input',          'DeBERTa zero-shot classification'],
          ['Adversarial Rephrasing',   'Input',          'Heuristic perturbation testing'],
          ['Jailbreak Pattern Detector','Prompt Input',   'DAN / roleplay / bypass pattern matching'],
          ['Locale Compliance Router', 'Input',          'Language-aware regulatory routing'],
          ['Cost Anomaly Detector',    'Token Usage',    'Runaway token spend detection'],
          ['Agentic Loop Breaker',     'Tool Calls',     'Infinite tool-call loop detection'],
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

      <h2>Universal Compatibility</h2>
      <p>
        The API Key (Tenant ID) that you copy from the <strong>Dashboard's "Key" button</strong> is universally applicable across all tech stacks: Python, Node.js, Java, and React. 
        It isolates your application's logs and routes your traffic to your tenant automatically.
      </p>

      <h2>Setting the Key via Environment Variables</h2>
      <p>Always load your copied API Key securely from the environment.</p>
      
      <h3>Python</h3>
      <CodeBlock lang="python" code={`import os
import sentinel

safe_client = sentinel.wrap(
    your_llm_client,
    api_key=os.environ.get("SENTINEL_API_KEY")
)`} />

      <h3>Node.js / React</h3>
      <CodeBlock lang="javascript" code={`// Server (Node.js) or bundler (Vite / Next.js)
const API_KEY = process.env.SENTINEL_API_KEY || import.meta.env.VITE_SENTINEL_API_KEY;`} />

      <h3>Java</h3>
      <CodeBlock lang="java" code={`String apiKey = System.getenv("SENTINEL_API_KEY");`} />

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
      <h2>v4.0.0 — Current</h2>
      <ul>
        <li>19-agent mesh with 4 new v4 agents (Jailbreak Pattern Detector, Cost Anomaly, Agentic Loop Breaker, Locale Router)</li>
        <li>RiskAggregator consensus engine (upgraded from BayesianConsensus)</li>
        <li>Pro / Free tier system — free users get core protection, Pro unlocks analytics + compliance exports</li>
        <li><code>SentinelBlockedError</code> and <code>SentinelProRequiredError</code> custom exceptions</li>
        <li>Dashboard accessible to all signed-in users (free = demo data, Pro = live gateway)</li>
        <li>Node.js, Java, and React integration guides</li>
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

  nodejs: (
    <>
      <h1>Node.js / TypeScript Integration</h1>
      <p className="doc-lead">
        Sentinel exposes a standard REST gateway — integrate from any Node.js or TypeScript backend
        using <code>fetch</code>, <code>axios</code>, or any HTTP client.
      </p>

      <h2>Install</h2>
      <p>No npm package required. Call the Sentinel gateway directly via HTTP.</p>
      <CodeBlock lang="bash" code={`# Optional: use a typed helper (community package)
npm install axios`} />

      <h2>Screen API</h2>
      <p>Check a prompt for threats before sending it to your LLM:</p>
      <CodeBlock lang="javascript" code={`const SENTINEL_URL = process.env.SENTINEL_GATEWAY_URL || 'https://gateway.sentinel-ai.dev';
const SENTINEL_KEY = process.env.SENTINEL_API_KEY;

async function screenPrompt(userMessage) {
  const res = await fetch(\`\${SENTINEL_URL}/v1/screen\`, {
    method: 'POST',
    headers: {
      'Authorization': \`Bearer \${SENTINEL_KEY}\`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: [{ role: 'user', content: userMessage }],
      tenant_id: 'your-org',
    }),
  });

  if (!res.ok) throw new Error(\`Sentinel error: \${res.status}\`);
  return res.json();
  // → { decision: "ALLOW", score: 0.12, agents: [...] }
}`} />

      <h2>Trust Score API</h2>
      <CodeBlock lang="javascript" code={`async function getTrustScore(messages) {
  const res = await fetch(\`\${SENTINEL_URL}/v1/trust-score\`, {
    method: 'POST',
    headers: {
      'Authorization': \`Bearer \${SENTINEL_KEY}\`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ messages, tenant_id: 'your-org' }),
  });
  const data = await res.json();
  return data.trust_score; // 0–100
}`} />

      <h2>Full Chat Proxy</h2>
      <p>Route your OpenAI calls through Sentinel for full input + output scanning:</p>
      <CodeBlock lang="javascript" code={`async function safeChatCompletion(messages, model = 'gpt-4o') {
  const res = await fetch(\`\${SENTINEL_URL}/v1/chat\`, {
    method: 'POST',
    headers: {
      'Authorization': \`Bearer \${SENTINEL_KEY}\`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      messages,
      tenant_id: 'your-org',
    }),
  });

  if (res.status === 403) {
    const err = await res.json();
    throw new Error(\`Blocked by Sentinel: \${err.detail}\`);
  }
  return res.json();
}`} />

      <h2>Error Handling</h2>
      <CodeBlock lang="javascript" code={`try {
  const result = await safeChatCompletion([{ role: 'user', content: userInput }]);
  console.log(result.choices[0].message.content);
} catch (err) {
  if (err.message.includes('Blocked by Sentinel')) {
    // Show safe fallback to user
    res.status(400).json({ error: 'This request was flagged for safety.' });
  }
}`} />

      <Alert type="info">
        <strong>Tip:</strong> For Express.js / Next.js API routes, create a shared <code>sentinelClient.js</code> utility
        that wraps these calls. All Sentinel endpoints accept standard JSON over HTTPS.
      </Alert>
    </>
  ),

  java: (
    <>
      <h1>Java Integration</h1>
      <p className="doc-lead">
        Integrate Sentinel into any Java 11+ application using the built-in <code>java.net.http</code> client.
        No external SDK required — just call the REST API.
      </p>

      <h2>Dependencies</h2>
      <p>No additional dependencies needed for Java 11+. For JSON parsing, add Gson or Jackson:</p>
      <CodeBlock lang="xml" code={`<!-- Maven: add Gson for JSON parsing -->
<dependency>
  <groupId>com.google.code.gson</groupId>
  <artifactId>gson</artifactId>
  <version>2.10.1</version>
</dependency>`} />

      <h2>Screen API</h2>
      <CodeBlock lang="java" code={`import java.net.URI;
import java.net.http.*;
import java.net.http.HttpRequest.BodyPublishers;
import java.net.http.HttpResponse.BodyHandlers;
import com.google.gson.Gson;
import java.util.*;

public class SentinelClient {
    private static final String BASE_URL =
        System.getenv("SENTINEL_GATEWAY_URL") != null
            ? System.getenv("SENTINEL_GATEWAY_URL")
            : "https://gateway.sentinel-ai.dev";
    private static final String API_KEY = System.getenv("SENTINEL_API_KEY");
    private static final HttpClient http = HttpClient.newHttpClient();
    private static final Gson gson = new Gson();

    public static Map<String, Object> screenPrompt(String userMessage) throws Exception {
        var payload = Map.of(
            "messages", List.of(Map.of("role", "user", "content", userMessage)),
            "tenant_id", "your-org"
        );

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/v1/screen"))
            .header("Authorization", "Bearer " + API_KEY)
            .header("Content-Type", "application/json")
            .POST(BodyPublishers.ofString(gson.toJson(payload)))
            .build();

        HttpResponse<String> response = http.send(request, BodyHandlers.ofString());

        if (response.statusCode() == 403) {
            throw new RuntimeException("Blocked by Sentinel: " + response.body());
        }
        return gson.fromJson(response.body(), Map.class);
    }
}`} />

      <h2>Trust Score API</h2>
      <CodeBlock lang="java" code={`public static double getTrustScore(String userMessage) throws Exception {
    var payload = Map.of(
        "messages", List.of(Map.of("role", "user", "content", userMessage)),
        "tenant_id", "your-org"
    );

    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(BASE_URL + "/v1/trust-score"))
        .header("Authorization", "Bearer " + API_KEY)
        .header("Content-Type", "application/json")
        .POST(BodyPublishers.ofString(new Gson().toJson(payload)))
        .build();

    HttpResponse<String> res = HttpClient.newHttpClient()
        .send(request, BodyHandlers.ofString());
    Map<String, Object> data = new Gson().fromJson(res.body(), Map.class);
    return ((Number) data.get("trust_score")).doubleValue();
}`} />

      <h2>Full Chat Proxy</h2>
      <CodeBlock lang="java" code={`// Route LLM calls through Sentinel for full input + output scanning
public static Map<String, Object> safeChat(String model, List<Map<String, String>> messages)
        throws Exception {
    var payload = Map.of(
        "model", model,
        "messages", messages,
        "tenant_id", "your-org"
    );

    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(BASE_URL + "/v1/chat"))
        .header("Authorization", "Bearer " + API_KEY)
        .header("Content-Type", "application/json")
        .POST(BodyPublishers.ofString(new Gson().toJson(payload)))
        .build();

    HttpResponse<String> res = HttpClient.newHttpClient()
        .send(request, BodyHandlers.ofString());

    if (res.statusCode() == 403) {
        throw new RuntimeException("Blocked by Sentinel: " + res.body());
    }
    return new Gson().fromJson(res.body(), Map.class);
}`} />

      <Alert type="info">
        <strong>Spring Boot:</strong> Create a <code>@Service</code> bean wrapping these methods.
        Inject via constructor for clean dependency management.
      </Alert>
    </>
  ),

  react: (
    <>
      <h1>React Frontend Integration</h1>
      <p className="doc-lead">
        Add real-time threat screening to your React chat UI.
        Call Sentinel from your backend API route — never expose API keys in the browser.
      </p>

      <Alert type="warning">
        <strong>Security:</strong> Never call the Sentinel gateway directly from the browser.
        Always proxy through your own backend (Next.js API route, Express, etc.) to keep your API key secret.
      </Alert>

      <h2>Setup</h2>
      <p>Create a backend API route that proxies to Sentinel. Example for Next.js:</p>
      <CodeBlock lang="javascript" code={`// pages/api/sentinel/screen.js  (Next.js API Route)
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();

  const response = await fetch(
    process.env.SENTINEL_GATEWAY_URL + '/v1/screen',
    {
      method: 'POST',
      headers: {
        'Authorization': \`Bearer \${process.env.SENTINEL_API_KEY}\`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages: req.body.messages,
        tenant_id: 'your-org',
      }),
    }
  );

  const data = await response.json();
  res.status(response.status).json(data);
}`} />

      <h2>Hook Pattern</h2>
      <p>Create a reusable React hook for threat screening:</p>
      <CodeBlock lang="jsx" code={`// hooks/useSentinel.js
import { useState, useCallback } from 'react';

export function useSentinel() {
  const [screening, setScreening] = useState(false);
  const [result, setResult] = useState(null);

  const screen = useCallback(async (message) => {
    setScreening(true);
    try {
      const res = await fetch('/api/sentinel/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: message }],
        }),
      });
      const data = await res.json();
      setResult(data);
      return data;
    } finally {
      setScreening(false);
    }
  }, []);

  return { screen, screening, result };
}`} />

      <h2>Inline Guard Component</h2>
      <p>Use the hook in your chat input component:</p>
      <CodeBlock lang="jsx" code={`import { useSentinel } from '../hooks/useSentinel';

function ChatInput({ onSend }) {
  const [message, setMessage] = useState('');
  const { screen, screening } = useSentinel();

  const handleSubmit = async () => {
    const result = await screen(message);
    if (result.decision === 'BLOCKED') {
      alert('This message was flagged for safety.');
      return;
    }
    onSend(message);
    setMessage('');
  };

  return (
    <div className="chat-input">
      <input
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Type a message..."
        disabled={screening}
      />
      <button onClick={handleSubmit} disabled={screening}>
        {screening ? 'Checking...' : 'Send'}
      </button>
    </div>
  );
}`} />

      <h2>Dashboard Embed</h2>
      <p>Display a live trust score badge in your admin panel:</p>
      <CodeBlock lang="jsx" code={`function TrustBadge({ score }) {
  const color =
    score >= 80 ? '#10b981' :
    score >= 50 ? '#f59e0b' : '#ef4444';

  return (
    <span style={{
      background: color + '20',
      color,
      padding: '4px 12px',
      borderRadius: '20px',
      fontSize: '0.85rem',
      fontWeight: 600,
    }}>
      Trust: {score}/100
    </span>
  );
}`} />
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
