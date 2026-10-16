"""
DataGhost – API Key and Token Detector (Phase 3).

Detects well-known API key formats using specific, vendor-defined patterns.
Entropy checks prevent false positives on low-entropy placeholder strings.
Credentials are always redacted before being included in findings.

Covered formats:
  - AWS Access Key ID (AKIA…)
  - AWS Secret Access Key (context-based)
  - GitHub tokens (ghp_, gho_, ghu_, ghr_, github_pat_)
  - Stripe keys (sk_live_, rk_live_, pk_live_)
  - Google API keys (AIza…)
  - Azure SAS / connection strings
  - OpenAI (sk- / sk-proj-)
  - Anthropic (sk-ant-)
  - HuggingFace (hf_)
  - Slack (xox[bparo]-)
  - Generic high-entropy API key assignments
"""
from __future__ import annotations

import re
from typing import List, Optional

from detectors.base import BaseDetector, DetectorFinding, _line_col, _redact, _has_high_entropy

# ─── Vendor patterns ──────────────────────────────────────────────────────────
_PATTERNS = [
    # (rule_name, regex, severity, confidence, keep_prefix)
    ("aws_access_key_id",
     re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     "CRITICAL", 0.98, 4),

    ("aws_secret_access_key",
     re.compile(
         r"(?:aws[_\-]?secret[_\-]?(?:access[_\-]?)?key|AWS_SECRET_ACCESS_KEY)"
         r"\s*[=:\"'\s]+\s*([A-Za-z0-9/+]{40})\b",
         re.IGNORECASE,
     ),
     "CRITICAL", 0.95, 4),

    ("github_token",
     re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{82,255})\b"),
     "CRITICAL", 0.98, 4),

    ("stripe_secret_key",
     re.compile(r"\b(sk_live_[A-Za-z0-9]{20,}|rk_live_[A-Za-z0-9]{20,})\b"),
     "CRITICAL", 0.99, 7),

    ("stripe_publishable_key",
     re.compile(r"\bpk_live_[A-Za-z0-9]{20,}\b"),
     "HIGH", 0.90, 7),

    ("google_api_key",
     re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"),
     "CRITICAL", 0.97, 4),

    ("azure_sas_token",
     re.compile(
         r"(?:sig=)[A-Za-z0-9%+/]{43,}={0,2}",
         re.IGNORECASE,
     ),
     "CRITICAL", 0.88, 4),

    ("azure_connection_string",
     re.compile(
         r"DefaultEndpointsProtocol=https?;AccountName=[^;]{1,50};"
         r"AccountKey=[A-Za-z0-9+/]{43,}={0,2}",
         re.IGNORECASE,
     ),
     "CRITICAL", 0.96, 26),

    ("openai_api_key",
     re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b"),
     "CRITICAL", 0.96, 7),

    ("anthropic_api_key",
     re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
     "CRITICAL", 0.97, 7),

    ("huggingface_token",
     re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"),
     "CRITICAL", 0.95, 4),

    ("slack_token",
     re.compile(r"\bxox[bparo]-[0-9A-Za-z\-]{10,}\b"),
     "CRITICAL", 0.97, 4),

    # Generic high-entropy API key assignment – lowest confidence, requires entropy check
    ("api_key_assignment",
     re.compile(
         r"""(?:api[_\-]?key|apikey|access[_\-]?key|secret[_\-]?key|auth[_\-]?token)\s*"""
         r"""[=:\s]+\s*["']?([A-Za-z0-9_\-/+.]{32,})["']?""",
         re.IGNORECASE,
     ),
     "HIGH", 0.70, 4),
]


class APIKeyDetector(BaseDetector):
    detector_id = "api_key"
    name = "API Key & Token Detector"
    categories = ["CREDENTIALS", "AI_MODELS"]

    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        if not text or not isinstance(text, str):
            return []
        findings: List[DetectorFinding] = []
        seen_offsets: set[int] = set()

        for rule_name, pattern, severity, confidence, keep_prefix in _PATTERNS:
            for m in pattern.finditer(text):
                if m.start() in seen_offsets:
                    continue

                # Extract the actual secret value (group 1 if capturing, else full match)
                raw_value = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)

                # For generic assignment rule: require high entropy to avoid placeholders
                if rule_name == "api_key_assignment":
                    if self.is_placeholder(raw_value):
                        continue
                    if not self.has_high_entropy(raw_value, threshold=3.5):
                        continue

                line, col = _line_col(text, m.start())
                evidence = _redact(m.group(0), keep_prefix=keep_prefix)

                # Determine category
                category = "AI_MODELS" if rule_name in (
                    "openai_api_key", "anthropic_api_key", "huggingface_token"
                ) else "CREDENTIALS"

                findings.append(DetectorFinding(
                    detector_id=self.detector_id,
                    rule_name=rule_name,
                    category=category,
                    severity=severity,
                    confidence=confidence,
                    filename=filename,
                    line_number=line,
                    column_start=col,
                    char_start=m.start(),
                    char_end=m.end(),
                    evidence=evidence,
                ))
                seen_offsets.add(m.start())

        return findings
