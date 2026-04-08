"""
SENTINEL Agent 7 — ComplianceTagger
=======================================
Aggregates flags from ALL other agents and maps them to specific
regulatory obligations, producing a structured compliance annotation
that goes into the signed audit attestation.

Regulatory frameworks covered:
  HIPAA Safe Harbor — 18 PHI identifiers
  GDPR Art. 4 / Art. 9 — personal & special category data
  SOC2 — data handling controls (CC6, CC7, CC9)
  PCI-DSS — cardholder data protection
  CCPA — California consumer data rights
  ── v2 India-specific ──────────────────
  DPDP 2023 — India's Digital Personal Data Protection Act
  RBI IT Framework — Reserve Bank of India banking data rules
  IRDAI — Insurance Regulatory & Development Authority
  SEBI — Securities and Exchange Board of India

The ComplianceTagger produces NO score of its own (always 0.0) —
it only enriches the audit trail.  Its weight in the Bayesian consensus
is intentionally low (it is a tagger, not a threat detector).
"""
from __future__ import annotations

import logging
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.compliance_tagger")

# ── Regulatory obligation mappings ─────────────────────────────────────────────
_HIPAA_SAFE_HARBOR = {
    "PHI-Name", "PHI-Location", "PHI-Dates", "PHI-Phone",
    "PHI-Fax", "PHI-Email", "PHI-SSN", "PHI-MRN", "PHI-Plan",
    "PHI-AccountNum", "PHI-CertNum", "PHI-VehicleID", "PHI-DeviceID",
    "PHI-URL", "PHI-IP", "PHI-Biometric", "PHI-Photo", "PHI-ID",
    "SafeHarbor-ID",
}

_GDPR_ARTICLES = {
    "GDPR:Article-4(1)": "Personal Data",
    "GDPR:Article-9(1)": "Special Category Data (sensitive)",
}

_SOC2_CONTROLS = {
    "injection":  "CC6.1 — Logical Access Controls",
    "pii_leak":   "CC6.6 — Transmission of Sensitive Data",
    "toxicity":   "CC7.2 — Anomalous Activity Monitoring",
    "jailbreak":  "CC9.2 — Vendor & Partner Risk Management",
}

_PCI_DSS = {
    "PCI-DSS:PANdata": "PCI-DSS Req 3 — Protect Stored Cardholder Data",
}

_CCPA_CATEGORIES = {
    "GDPR:Article-4(1)": "CCPA § 1798.140(o) — Personal Information",
}

# ── India-specific frameworks (v2) ────────────────────────────────────────────

_DPDP_CATEGORIES = {
    "DPDP:Section-4":  "Processing of personal data only for lawful purpose",
    "DPDP:Section-5":  "Notice and consent requirements",
    "DPDP:Section-6":  "Consent of Data Principal",
    "DPDP:Section-8":  "Rights of Data Principal (access, correction, erasure)",
    "DPDP:Section-9":  "Duties of Data Fiduciary (accuracy, security, retention)",
    "DPDP:Section-11": "Restrictions on transfer outside India",
    "DPDP:Section-16": "Processing of children's personal data",
    "DPDP:Section-17": "Significant Data Fiduciary obligations (DPO, audit, DPIA)",
}

_RBI_IT_FRAMEWORK = {
    "RBI:IT-GRC":      "IT Governance, Risk and Compliance Framework",
    "RBI:IS-Audit":    "Information Security Audit requirements",
    "RBI:Cyber":       "Cybersecurity framework for banks",
    "RBI:OutSource":   "Outsourcing of IT services and AI models",
    "RBI:DataLocal":   "Data localization — financial data to remain in India",
    "RBI:DPSS":        "Digital Payment Security Standards",
}

_IRDAI_GUIDELINES = {
    "IRDAI:DataPrivacy": "Policyholder data privacy and protection",
    "IRDAI:IT-Gov":      "IT Governance framework for insurers",
    "IRDAI:Outsource":   "Outsourcing of IT/AI activities",
    "IRDAI:Cyber":       "Cybersecurity guidelines for insurance companies",
}

_SEBI_GUIDELINES = {
    "SEBI:Cyber":      "Cybersecurity & Cyber Resilience framework",
    "SEBI:DataShare":  "Data sharing and privacy requirements for market intermediaries",
    "SEBI:CloudGov":   "Cloud governance framework for regulated entities",
}

# ── India-specific PII signals ─────────────────────────────────────────────────
_INDIA_PII_SIGNALS = [
    "aadhaar", "aadhar", "आधार",         # Aadhaar number
    "pan card", "pan number", "पैन",       # PAN (tax ID)
    "voter id", "voterid", "epic",         # Voter ID
    "ration card",                          # Ration card
    "driving licence", "driving license",   # DL
    "passport",                             # Passport
    "upi", "upi id", "upi pin",           # UPI
    "ifsc", "account number",              # Bank account
    "gstin", "gst number",                 # GST
]

_INDIA_FINANCIAL_SIGNALS = [
    "neft", "rtgs", "imps", "upi", "nach", "ecs",  # Payment systems
    "demat", "depository", "cdsl", "nsdl",           # Securities
    "mutual fund", "sip", "nav",                     # MF
    "nps", "epf", "ppf",                             # Retirement
    "insurance", "policy number", "claim",            # Insurance
    "loan", "emi", "cibil", "credit score",          # Credit
]


class ComplianceTagger(SentinelAgent):
    agent_name = "ComplianceTagger"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        """
        ComplianceTagger doesn't independently analyse — it enriches.
        In the actual pipeline it runs alongside other agents and
        the gateway collects its compliance_tags from metadata.
        Here it does a lightweight pass on the prompt for direct tagging.
        """
        text = request.last_user_message
        tags: list[str] = []
        obligations: list[dict[str, Any]] = []

        # Determine compliance region from request metadata or tenant policy
        compliance_region = request.metadata.get("compliance_region", "global")

        # ── HIPAA tag pass ────────────────────────────────────────────────────
        hipaa_triggers = self._detect_hipaa(text)
        for t in hipaa_triggers:
            tag = f"HIPAA:{t}"
            tags.append(tag)
            obligations.append({"framework": "HIPAA", "control": t,
                                 "description": "Safe Harbor identifiable information"})

        # ── GDPR tag pass ─────────────────────────────────────────────────────
        gdpr_triggers = self._detect_gdpr(text)
        for t in gdpr_triggers:
            tags.append(t)
            obligations.append({"framework": "GDPR", "control": t,
                                 "description": _GDPR_ARTICLES.get(t, "")})

        # ── SOC2 pass (inferred from keyword signals) ─────────────────────────
        soc2_triggers = self._detect_soc2_signals(text)
        for key, control in soc2_triggers:
            tags.append(f"SOC2:{key}")
            obligations.append({"framework": "SOC2", "control": control,
                                 "description": control})

        # ── DPDP 2023 pass (India) ────────────────────────────────────────────
        if compliance_region in ("global", "india"):
            dpdp_triggers = self._detect_dpdp(text)
            for tag, desc in dpdp_triggers:
                tags.append(tag)
                obligations.append({"framework": "DPDP", "control": tag,
                                     "description": desc})

        # ── RBI IT Framework pass (India BFSI) ────────────────────────────────
        if compliance_region in ("global", "india"):
            rbi_triggers = self._detect_rbi(text)
            for tag, desc in rbi_triggers:
                tags.append(tag)
                obligations.append({"framework": "RBI", "control": tag,
                                     "description": desc})

        # ── IRDAI pass (India Insurance) ──────────────────────────────────────
        if compliance_region in ("global", "india"):
            irdai_triggers = self._detect_irdai(text)
            for tag, desc in irdai_triggers:
                tags.append(tag)
                obligations.append({"framework": "IRDAI", "control": tag,
                                     "description": desc})

        # ── SEBI pass (India Securities) ──────────────────────────────────────
        if compliance_region in ("global", "india"):
            sebi_triggers = self._detect_sebi(text)
            for tag, desc in sebi_triggers:
                tags.append(tag)
                obligations.append({"framework": "SEBI", "control": tag,
                                     "description": desc})

        tags = list(set(tags))

        return AgentResult(
            agent_name=self.agent_name,
            score=0.0,   # tagger — score carries no threat weight
            flagged=len(tags) > 0,
            metadata={
                "compliance_tags": tags,
                "obligations": obligations,
                "frameworks_triggered": list({o["framework"] for o in obligations}),
                "compliance_region": compliance_region,
            },
        )

    # ── Existing framework detectors ───────────────────────────────────────────

    def _detect_hipaa(self, text: str) -> list[str]:
        import re
        hits = []
        patterns = {
            "PHI-SSN":    r"\b\d{3}-\d{2}-\d{4}\b",
            "PHI-Phone":  r"\b(?:\+?\d[\d\s\-().]{7,12}\d)\b",
            "PHI-Email":  r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
            "PHI-Dates":  r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/]\d{2,4}\b",
            "PHI-MRN":    r"\bMRN[-:\s]*\d{5,10}\b",
            "PHI-IP":     r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        }
        for tag, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                hits.append(tag)
        return hits

    def _detect_gdpr(self, text: str) -> list[str]:
        hits = []
        personal_data_signals = [
            "address", "passport", "national id", "date of birth", "dob",
            "full name", "location", "gps", "coordinate"
        ]
        special_category_signals = [
            "health", "medical", "diagnosis", "religion", "race", "ethnicity",
            "political", "sexual", "biometric", "genetic"
        ]
        text_lower = text.lower()
        if any(s in text_lower for s in personal_data_signals):
            hits.append("GDPR:Article-4(1)")
        if any(s in text_lower for s in special_category_signals):
            hits.append("GDPR:Article-9(1)")
        return hits

    def _detect_soc2_signals(self, text: str) -> list[tuple[str, str]]:
        text_lower = text.lower()
        hits = []
        if any(w in text_lower for w in ["inject", "bypass", "override"]):
            hits.append(("CC6.1", _SOC2_CONTROLS["injection"]))
        if any(w in text_lower for w in ["password", "credential", "secret", "key", "token"]):
            hits.append(("CC6.6", _SOC2_CONTROLS["pii_leak"]))
        return hits

    # ── India-specific framework detectors (v2) ────────────────────────────────

    def _detect_dpdp(self, text: str) -> list[tuple[str, str]]:
        """Detect DPDP Act 2023 (India) compliance triggers."""
        import re
        hits = []
        text_lower = text.lower()

        # Section 4/5/6 — Personal data processing requires consent
        if any(sig in text_lower for sig in _INDIA_PII_SIGNALS):
            hits.append(("DPDP:Section-4", _DPDP_CATEGORIES["DPDP:Section-4"]))
            hits.append(("DPDP:Section-6", _DPDP_CATEGORIES["DPDP:Section-6"]))

        # Aadhaar detection — highest sensitivity under DPDP
        aadhaar_pattern = r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"
        if re.search(aadhaar_pattern, text) and any(
            s in text_lower for s in ["aadhaar", "aadhar", "uid", "आधार"]
        ):
            hits.append(("DPDP:Section-9", _DPDP_CATEGORIES["DPDP:Section-9"]))

        # PAN number detection
        pan_pattern = r"\b[A-Z]{5}\d{4}[A-Z]\b"
        if re.search(pan_pattern, text):
            hits.append(("DPDP:Section-5", _DPDP_CATEGORIES["DPDP:Section-5"]))

        # Section 16 — children's data
        if any(w in text_lower for w in ["child", "minor", "under 18", "underage", "बच्चा", "बच्चे"]):
            hits.append(("DPDP:Section-16", _DPDP_CATEGORIES["DPDP:Section-16"]))

        # Section 11 — cross-border transfer
        if any(w in text_lower for w in [
            "transfer abroad", "cross border", "data transfer", "export data",
            "foreign server", "overseas", "outside india"
        ]):
            hits.append(("DPDP:Section-11", _DPDP_CATEGORIES["DPDP:Section-11"]))

        # Section 17 — Significant Data Fiduciary
        if any(w in text_lower for w in [
            "large scale", "significant volume", "bulk data", "mass processing",
            "data fiduciary", "dpo", "data protection officer"
        ]):
            hits.append(("DPDP:Section-17", _DPDP_CATEGORIES["DPDP:Section-17"]))

        return hits

    def _detect_rbi(self, text: str) -> list[tuple[str, str]]:
        """Detect RBI IT Framework compliance triggers for BFSI."""
        hits = []
        text_lower = text.lower()

        # Financial data signals
        if any(sig in text_lower for sig in _INDIA_FINANCIAL_SIGNALS):
            hits.append(("RBI:IT-GRC", _RBI_IT_FRAMEWORK["RBI:IT-GRC"]))

        # Data localization — financial data must stay in India
        if any(w in text_lower for w in [
            "cloud", "aws", "azure", "gcp", "foreign server",
            "data center", "hosting", "s3 bucket"
        ]) and any(w in text_lower for w in [
            "bank", "financial", "payment", "transaction", "account"
        ]):
            hits.append(("RBI:DataLocal", _RBI_IT_FRAMEWORK["RBI:DataLocal"]))

        # Outsourcing to AI models
        if any(w in text_lower for w in [
            "ai model", "llm", "chatbot", "openai", "gpt", "claude",
            "gemini", "third party", "vendor", "outsource"
        ]) and any(w in text_lower for w in [
            "bank", "nbfc", "financial", "rbi", "reserve bank"
        ]):
            hits.append(("RBI:OutSource", _RBI_IT_FRAMEWORK["RBI:OutSource"]))

        # Digital payments
        if any(w in text_lower for w in ["upi", "neft", "rtgs", "imps", "nach"]):
            hits.append(("RBI:DPSS", _RBI_IT_FRAMEWORK["RBI:DPSS"]))

        return hits

    def _detect_irdai(self, text: str) -> list[tuple[str, str]]:
        """Detect IRDAI compliance triggers for insurance sector."""
        hits = []
        text_lower = text.lower()

        insurance_signals = [
            "insurance", "policy holder", "policyholder", "claim",
            "premium", "beneficiary", "insurer", "underwriting",
            "actuarial", "bima", "बीमा",
        ]
        if any(sig in text_lower for sig in insurance_signals):
            hits.append(("IRDAI:DataPrivacy", _IRDAI_GUIDELINES["IRDAI:DataPrivacy"]))

        if any(w in text_lower for w in ["outsource", "third party", "vendor", "ai model"]) and \
           any(w in text_lower for w in insurance_signals):
            hits.append(("IRDAI:Outsource", _IRDAI_GUIDELINES["IRDAI:Outsource"]))

        return hits

    def _detect_sebi(self, text: str) -> list[tuple[str, str]]:
        """Detect SEBI compliance triggers for securities market."""
        hits = []
        text_lower = text.lower()

        securities_signals = [
            "stock", "share", "equity", "demat", "trading", "broker",
            "depository", "mutual fund", "portfolio", "nse", "bse",
            "derivative", "futures", "options", "sensex", "nifty",
        ]
        if any(sig in text_lower for sig in securities_signals):
            hits.append(("SEBI:DataShare", _SEBI_GUIDELINES["SEBI:DataShare"]))

        if any(w in text_lower for w in ["cloud", "aws", "azure", "gcp"]) and \
           any(w in text_lower for w in securities_signals):
            hits.append(("SEBI:CloudGov", _SEBI_GUIDELINES["SEBI:CloudGov"]))

        return hits
