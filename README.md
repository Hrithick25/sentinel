# SENTINEL — LLM Trust & Safety Infrastructure Layer

> Production-grade security middleware for enterprise AI deployments.
> Drop-in SDK · 15-agent parallel mesh · <72ms P99 · HIPAA/GDPR/SOC2/DPDP

[![PyPI version](https://img.shields.io/pypi/v/sentinel-ai-sdk.svg)](https://pypi.org/project/sentinel-ai-sdk/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

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
SDK (wrap) → FastAPI Gateway → 15-Agent Parallel Mesh → Bayesian Consensus → Circuit Breaker → LLM API
                     ↓                    ↓                      ↓
               Postgres            Redis             FAISS Index         Kafka
            (audit trail)     (policy cache)     (attack vectors)   (event stream)
```

### The 15-Agent Mesh

#### v1 Core (7 agents)
| Agent | Technique | What it catches |
|-------|-----------|----------------|
| **InjectionScout** | FAISS ANN + regex | Prompt injection, delimiter attacks |
| **PIISentinel** | SpaCy NER + regex | PHI/PII leakage (HIPAA, GDPR, DPDP) |
| **JailbreakGuard** | Sliding window | Multi-turn escalation, persona attacks |
| **ToxicityScreener** | HF Detoxify | Toxicity, threats, hate speech |
| **HallucinationProbe** | DeBERTa NLI | Ungrounded factual claims in RAG |
| **ContextAnchor** | Cosine similarity | Semantic context drift |
| **ComplianceTagger** | Rule-based | HIPAA/GDPR/SOC2/PCI-DSS/DPDP tagging |

#### v2 Enterprise (5 agents)
| Agent | Technique | What it catches |
|-------|-----------|----------------|
| **ResponseSafetyLayer** | Pattern scan | Harmful LLM output, data leakage |
| **MultilingualGuard** | Multilingual embeddings | Cross-language jailbreaks |
| **ToolCallSafety** | Schema validation | Dangerous function calls |
| **BrandGuard** | Sentiment + patterns | Unauthorized promises, brand damage |
| **TokenAnomalyDetector** | Statistical analysis | Encoding attacks, token smuggling |

#### v3 Advanced (3 agents)
| Agent | Technique | What it catches |
|-------|-----------|----------------|
| **PromptLineage** | Session memory graph | Multi-turn escalation trajectories |
| **IntentClassifier** | DeBERTa zero-shot | Malicious intent classification |
| **AdversarialRephrasing** | Heuristic perturbation | Evasion via paraphrasing |

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
pip install sentinel-ai-sdk

# Full gateway server with ML agents
pip install sentinel-ai-sdk[full]

# Server without ML (uses heuristic fallbacks)
pip install sentinel-ai-sdk[server]
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
python tests/red_team/run_benchmark.py
```

Expected results:
- Detection rate: **87%** (v3 upgrade from 81%)
- False positive rate: **2.1%**
- P99 latency: **<72ms**

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
