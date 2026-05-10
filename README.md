# SENTINEL — Infrastructure-Grade LLM Security

> Professional security middleware for enterprise AI deployments.
> Drop-in SDK · 19-agent parallel mesh · Zero-config VS Code Local Mode
> Full Compliance: EU AI Act, OWASP LLM Top 10, NIST AI RMF, CSA AI Safety, GDPR, HIPAA, SOC 2

[![PyPI version](https://img.shields.io/pypi/v/sentinel-guardrails-sdk.svg)](https://pypi.org/project/sentinel-guardrails-sdk/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![VS Code Marketplace](https://img.shields.io/visual-studio-marketplace/v/sentinel-labs.sentinel-guardrails?label=VS%20Code)](https://marketplace.visualstudio.com/items?itemName=sentinel-labs.sentinel-guardrails)
[![OpenVSX](https://img.shields.io/open-vsx/v/sentinel-labs/sentinel-guardrails?label=OpenVSX)](https://open-vsx.org/extension/sentinel-labs/sentinel-guardrails)

---

## Quick Start (3 lines)

```python
import openai, sentinel

client = sentinel.wrap(
    openai.OpenAI(api_key="sk-..."),
    tenant_id="my-org",
    api_key="sk-sentinel-...",
)

# All existing code works unchanged:
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Help me with this contract."}],
)
```

## Architecture

```
SDK (wrap) → FastAPI Gateway → 19-Agent Parallel Mesh → Risk Aggregator → Circuit Breaker → LLM API
                     ↓                    ↓                      ↓
               Postgres            Redis             FAISS Index         Kafka
            (audit trail)     (policy cache)     (attack vectors)   (event stream)
```

### The 19-Agent Mesh

#### v1 Core (7 agents)
| # | Agent | Technique | What it catches |
|---|-------|-----------|----------------|
| 1 | **InjectionScout** | FAISS ANN + regex | Prompt injection, delimiter attacks |
| 2 | **PIISentinel** | SpaCy NER + regex | PHI/PII leakage (HIPAA, GDPR, DPDP) |
| 3 | **JailbreakGuard** | Sliding window | Multi-turn escalation, persona attacks |
| 4 | **ToxicityScreener** | HF Detoxify | Toxicity, threats, hate speech |
| 5 | **HallucinationProbe** | DeBERTa NLI | Ungrounded factual claims in RAG |
| 6 | **ContextAnchor** | Cosine similarity | Semantic context drift |
| 7 | **ComplianceTagger** | Rule-based | HIPAA/GDPR/SOC2/PCI-DSS/DPDP tagging |

#### v2 Enterprise (5 agents)
| # | Agent | Technique | What it catches |
|---|-------|-----------|----------------|
| 8 | **ResponseSafetyLayer** | Pattern scan | Harmful LLM output, data leakage |
| 9 | **MultilingualGuard** | Multilingual embeddings | Cross-language jailbreaks |
| 10 | **ToolCallSafety** | Schema validation | Dangerous function calls |
| 11 | **BrandGuard** | Sentiment + patterns | Unauthorized promises, brand damage |
| 12 | **TokenAnomalyDetector** | Statistical analysis | Encoding attacks, token smuggling |

#### v3 Advanced (3 agents)
| # | Agent | Technique | What it catches |
|---|-------|-----------|----------------|
| 13 | **PromptLineage** | Session memory graph | Multi-turn escalation trajectories |
| 14 | **IntentClassifier** | DeBERTa zero-shot | Malicious intent classification |
| 15 | **AdversarialRephrasing** | Heuristic perturbation | Evasion via paraphrasing |

#### v4 Production (4 agents)
| # | Agent | Technique | What it catches |
|---|-------|-----------|----------------|
| 16 | **JailbreakPatternDetector** | DAN/roleplay patterns | DAN attacks, character bypass, social engineering |
| 17 | **LocaleComplianceRouter** | Locale-aware rules | Language-specific regulatory routing (DPDP, GDPR) |
| 18 | **CostAnomalyDetector** | Spend-rate analysis | Runaway token costs, inference bombs |
| 19 | **AgenticLoopBreaker** | Loop detection | Infinite tool-call loops in agentic frameworks |

### ML Models Used

| Component | Model | Size | Purpose |
|-----------|-------|------|---------|
| ML Risk Scorer | `ProtectAI/deberta-v3-base-prompt-injection-v2` | ~180MB | Primary injection detection |
| Intent Classifier | `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` | ~440MB | Zero-shot intent classification |
| Hallucination Probe | `cross-encoder/nli-deberta-v3-small` | ~170MB | NLI grounding verification |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` | ~80MB | FAISS + cosine similarity |
| Toxicity | `detoxify/original` | ~450MB | Multi-dimension toxicity scoring |
| PII | `en_core_web_sm` (SpaCy) | ~12MB | Named entity recognition |

## Install

```bash
# SDK only (lightweight, for client-side integration)
pip install sentinel-guardrails-sdk

# Full gateway server with ML agents
pip install sentinel-guardrails-sdk[full]

# Server without ML (uses heuristic fallbacks)
pip install sentinel-guardrails-sdk[server]
```

## Access Tiers

| Feature | Free Developer | Enterprise Pro |
|---------|----------------|----------------|
| `screen()` — threat detection | ✅ | ✅ |
| `trust_score()` — risk scoring | ✅ | ✅ |
| `wrap()` — OpenAI/Claude proxy | ✅ | ✅ |
| 19-Agent Parallel Mesh | ✅ | ✅ |
| VS Code Local Heuristic Scan | ✅ | ✅ |
| `analytics()` — dashboard data | ❌ | ✅ |
| Compliance Reports (EU AI Act, OWASP) | ❌ | ✅ |
| `configure_agents()` — live tuning | ❌ | ✅ |
| `audit_log()` — full event log | ❌ | ✅ |

## Multi-Language Integration

Sentinel's gateway exposes a standard REST API, making it accessible from any language:

### Node.js / TypeScript
```javascript
const response = await fetch('https://gateway.sentinel-ai.dev/v1/screen', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer sntnl-your-key',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Check this prompt' }],
    tenant_id: 'my-org',
  }),
});
const result = await response.json();
```

### Java
```java
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("https://gateway.sentinel-ai.dev/v1/screen"))
    .header("Authorization", "Bearer sntnl-your-key")
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(jsonPayload))
    .build();
HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
```

### React (Frontend)
```jsx
const screenPrompt = async (userMessage) => {
  const res = await fetch('/api/sentinel/screen', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: [{ role: 'user', content: userMessage }] }),
  });
  return res.json();
};
```

## Deploy with Docker

```bash
# Full stack (Postgres + Redis + Kafka + Gateway + Dashboard)
cp .env.example .env        # set SECRET_KEY and OPENAI_API_KEY
docker compose up --build -d
curl http://localhost:8000/health

# Lightweight dev (just Postgres + Redis)
docker compose -f docker-compose.dev.yml up -d
python -m uvicorn sentinel.gateway.main:app --reload
```

## Run Locally (Development)

```bash
# 1. Start database + cache
docker compose -f docker-compose.dev.yml up -d

# 2. Install dependencies
pip install -e ".[full,dev]"
python -m spacy download en_core_web_sm

# 3. Start gateway
cp .env.example .env
python -m uvicorn sentinel.gateway.main:app --reload --port 8000

# 4. Start dashboard (optional)
cd dashboard && npm install && npm run dev
```

## Run Benchmark

```bash
# Standard detection benchmark
python tests/red_team/run_benchmark.py

# Adversarial mutation recall benchmark (L1-L5 mutations)
python tests/red_team/adversarial_recall_benchmark.py

# Generate publishable eval dataset
python scripts/generate_eval_set.py
```

Expected results:
- Known-attack detection rate: **95.3%** (v6 upgrade from 91%)
- **Mutated-attack recall: 82.1%** (L1-L5 adversarial mutations)
- False positive rate: **2.7%**
- P99 latency: **<72ms** (19 parallel heuristic+ML agents, no LLM judge)

### Adversarial Recall Breakdown

| Level | Strategy | Recall |
|-------|----------|--------|
| L1 | Character (homoglyph, leetspeak, zero-width) | 91.2% |
| L2 | Word (synonym, reorder, noise injection) | 86.7% |
| L3 | Encoding (base64, ROT13, hex) | 78.0% |
| L4 | Structural (sandwich, role confusion) | 73.3% |
| L5 | Semantic (indirect framing, hypothetical) | 68.0% |

> **Why 19 agents in <72ms?** All 19 agents run in parallel via `asyncio.gather()`.
> 14 are lightweight regex/heuristic/rule-based classifiers (~1-5ms each).
> 3 are ML inference agents (DeBERTa/DistilBERT) running in `asyncio.to_thread()` (~50ms).
> 2 are FAISS ANN searches sharing the embedding model (~10ms).
> The P99 is bounded by the **slowest single agent**, not the sum.
> No LLM judge is in the hot path.

The eval set is published at `data/adversarial_eval_set.jsonl`.
Mutation engine source: `sentinel/eval/mutation_engine.py`.

## SDK Integration Options

```python
# Option 1: OpenAI wrapper (zero code changes)
client = sentinel.wrap(openai_client, tenant_id="...", api_key="...")

# Option 2: LangChain callback
from sentinel.sdk.langchain_handler import SentinelCallbackHandler
handler = SentinelCallbackHandler(tenant_id="...", api_key="...")
llm = ChatOpenAI(callbacks=[handler])

# Option 3: LlamaIndex node postprocessor
from sentinel.sdk.llamaindex_node import SentinelNodePostprocessor
postprocessor = SentinelNodePostprocessor(tenant_id="...", api_key="...")
query_engine = index.as_query_engine(node_postprocessors=[postprocessor])
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create tenant |
| POST | `/auth/token` | Issue JWT |
| POST | `/v1/chat` | Intercepted chat (full pipeline) |
| POST | `/v1/screen` | Screen-only (no LLM call) |
| POST | `/v1/trust-score` | Trust score API (0–100) |
| GET | `/v1/audit` | Paginated audit log |
| GET | `/v1/analytics` | 24h threat analytics |
| PUT | `/admin/policy/{id}` | Live policy update |
| GET | `/health` | Liveness probe |
| GET | `/readiness` | Deep readiness check |
| WS | `/ws/dashboard` | Real-time event stream |

## License

MIT — See [LICENSE](LICENSE) for details.
