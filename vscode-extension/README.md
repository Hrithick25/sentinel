# SENTINEL — LLM Trust & Safety for VS Code

![SENTINEL](https://img.shields.io/badge/SENTINEL-v5.0_Enterprise-22c55e?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSIjMjJjNTVlIj48cGF0aCBkPSJNMTIgMjJzOC00IDgtMTBWNWwtOC0zLTggM3Y3YzAgNiA4IDEwIDggMTB6Ii8+PC9zdmc+)
![Agents](https://img.shields.io/badge/Agents-19_Parallel_Mesh-3b82f6?style=for-the-badge)
![Latency](https://img.shields.io/badge/P99_Latency-<72ms-f59e0b?style=for-the-badge)

**Real-time LLM prompt security scanning directly in VS Code.**

Screen any text for prompt injection, PII leakage, jailbreak attacks, toxicity, hallucination, and 14+ other threat categories — powered by SENTINEL's 19-agent parallel security mesh.

## Features

### 🔍 Screen Selected Text
Right-click any selected text and choose **"SENTINEL: Screen Selected Text"** to instantly scan it through all 19 security agents.

### 📊 Trust Score
Get a 0-100 trust score for any highlighted text. Scores below 70 indicate potential threats.

### 📄 Full File Scan
Scan all string literals in the current file for potential prompt injection or PII leakage.

### 🛡️ Sidebar Dashboard
- **Gateway Status** — Live connection health, agent count, FAISS vector count
- **Scan Results** — History of all scans with decision/score/latency
- **Agent Mesh** — All 19 agents organized by version tier

### 🎨 Inline Decorations
After scanning, threat scores appear inline next to the scanned text:
- 🔴 `⛔ BLOCK 85%` — High-risk content blocked
- 🟡 `⚠️ WARN 45%` — Moderate risk, content sanitized
- 🟢 `✅ SAFE 12%` — Content is safe

### ⚡ Auto-Scan on Save
Enable in settings to automatically scan all string literals when you save a file.

## 19-Agent Security Mesh

| Tier | Agents | Capabilities |
|------|--------|-------------|
| **v1 Core** | InjectionScout, PIISentinel, JailbreakGuard, ToxicityScreener, HallucinationProbe, ContextAnchor, ComplianceTagger | FAISS ANN, SpaCy NER, Detoxify, NLI grounding |
| **v2 Enterprise** | ResponseSafety, MultilingualGuard, LocaleComplianceRouter, ToolCallSafety, BrandGuard, TokenAnomaly | Universal model support, SSRF detection |
| **v3 Intelligence** | PromptLineage, IntentClassifier, AdversarialRephrasing | 13-label intent, semantic mutation detection |
| **v4 Advanced** | JailbreakPatternDetector, CostAnomalyDetector, AgenticLoopBreaker | 65+ signatures, DAN attacks, loop detection |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `sentinel.gatewayUrl` | `http://localhost:8000` | SENTINEL Gateway URL |
| `sentinel.tenantId` | `""` | Your tenant ID |
| `sentinel.apiKey` | `""` | API key (Pro tier) |
| `sentinel.autoScan` | `false` | Auto-scan on save |
| `sentinel.showInlineScores` | `true` | Show inline decorations |
| `sentinel.blockThreshold` | `0.7` | Block threshold (0-1) |
| `sentinel.warnThreshold` | `0.35` | Warning threshold (0-1) |

## Getting Started

1. Install the extension
2. Start your SENTINEL Gateway (`uvicorn sentinel.gateway.main:app`)
3. Open Settings → search "SENTINEL" → set your Gateway URL
4. Select any text → Right Click → **Screen with SENTINEL**

## Requirements

- A running SENTINEL Gateway (self-hosted or cloud)
- `pip install sentinel-guardrails-sdk[server]` for self-hosted

## Links

- [GitHub](https://github.com/Hrithick25/sentinel)
- [Documentation](https://docs.sentinel-ai.dev)
- [PyPI Package](https://pypi.org/project/sentinel-guardrails-sdk/)

## License

MIT © SENTINEL Labs
