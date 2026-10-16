"""
DataGhost – BaseDetector and DetectorFinding types (Phase 3).

All detectors inherit from BaseDetector and produce DetectorFinding objects.
DetectorFinding is mapped to the existing ScanFinding schema in scan_routes.py
so no DB migrations are required.

Design principles:
- Secrets are NEVER stored in plaintext in findings, logs, or DB.
- Evidence snippets are always redacted before leaving this module.
- Confidence is 0.0–1.0 (never a bool or severity-only flag).
- Line and column numbers are 1-indexed to match editor conventions.
- Fingerprints are stable SHA-256 digests of (rule, redacted_evidence, line)
  so duplicate findings across scans are correctly deduplicated.
"""
from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


# ─── Remediation catalogue ────────────────────────────────────────────────────
REMEDIATION: dict[str, str] = {
    "api_key":        "Remove this credential from the file. Rotate the key immediately. Store secrets in environment variables or a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault).",
    "database_url":   "Remove the database URL from the file. Use environment variables or a secrets manager. Rotate database credentials immediately if exposed.",
    "password":       "Remove the hardcoded password. Store credentials in environment variables or a secrets manager. Rotate the password if it was committed to version control.",
    "pii":            "Remove or pseudonymize personal data. Review data-minimisation policies and ensure data is processed only with a lawful basis.",
    "private_key":    "Remove the private key from the file immediately. Revoke and replace it. Never commit private keys to version control.",
    "jwt":            "Remove the JWT from the file. Revoke the token if possible. Rotate signing keys. Never hardcode tokens.",
    "ip_address":     "Remove or document the hardcoded IP address. Use DNS names or environment variables. Public IPs may expose infrastructure.",
    "default":        "Remove or rotate the detected secret. Use environment variables or a secrets manager.",
}


# ─── DetectorFinding ──────────────────────────────────────────────────────────
@dataclass
class DetectorFinding:
    """
    Normalized finding produced by a BaseDetector.

    All evidence fields are redacted – the raw secret value is never stored.
    """
    # Detector identity
    detector_id: str
    rule_name: str
    category: str                  # CREDENTIALS | PII | FINANCIAL | CORPORATE | AI_MODELS

    # Severity / confidence
    severity: str                  # LOW | MEDIUM | HIGH | CRITICAL
    confidence: float              # 0.0 – 1.0

    # Location
    filename: str = ""
    line_number: int = 0           # 1-indexed, 0 = unknown
    column_start: int = 0          # 1-indexed, 0 = unknown
    char_start: int = 0            # absolute character offset
    char_end: int = 0

    # Evidence (always redacted)
    evidence: str = ""             # short redacted snippet shown in UI
    remediation: str = ""

    # Deduplication
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.remediation:
            self.remediation = REMEDIATION.get(self.detector_id, REMEDIATION["default"])
        if not self.fingerprint:
            self.fingerprint = self._make_fingerprint()

    def _make_fingerprint(self) -> str:
        raw = f"{self.rule_name}:{self.evidence}:{self.line_number}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_scan_finding_dict(self) -> dict:
        """
        Convert to a dict compatible with the existing ScanFinding Pydantic model
        so no schema migration is needed for the DB layer.
        """
        return {
            "rule": self.rule_name,
            "category": self.category,
            "severity": self.severity,
            "start": self.char_start,
            "end": self.char_end,
            "matched_text": self.evidence,   # already redacted
            # Extension fields (tolerated as extras by Pydantic v2)
            "confidence": round(self.confidence, 3),
            "line_number": self.line_number,
            "column_start": self.column_start,
            "remediation": self.remediation,
            "fingerprint": self.fingerprint,
            "detector_id": self.detector_id,
        }


# ─── Utility helpers ──────────────────────────────────────────────────────────

def _line_col(text: str, char_offset: int) -> tuple[int, int]:
    """Return 1-indexed (line, column) for a character offset in text."""
    if char_offset <= 0:
        return 1, 1
    before = text[:char_offset]
    line = before.count("\n") + 1
    col = char_offset - before.rfind("\n")
    return line, col


def _redact(raw: str, keep_prefix: int = 4, keep_suffix: int = 0) -> str:
    """
    Return a redacted representation of a secret.
    Shows up to `keep_prefix` chars, masks the rest with *, optional suffix.
    Maximum total length is keep_prefix + 8 + keep_suffix.
    """
    if not raw:
        return "[REDACTED]"
    n = len(raw)
    prefix = raw[:min(keep_prefix, n)]
    if keep_suffix and n > keep_prefix + keep_suffix:
        suffix = raw[-keep_suffix:]
        return f"{prefix}{'*' * 8}{suffix}"
    return f"{prefix}{'*' * min(8, max(1, n - keep_prefix))}"


def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string (bits per character)."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    total = len(s)
    return -sum((v / total) * math.log2(v / total) for v in freq.values())


def _has_high_entropy(s: str, threshold: float = 3.5, min_len: int = 20) -> bool:
    """Return True if string has high entropy (likely a real token, not a placeholder)."""
    return len(s) >= min_len and _shannon_entropy(s) >= threshold


# ─── Placeholder detection ────────────────────────────────────────────────────
_PLACEHOLDER_RE = re.compile(
    r"(?i)^(?:"
    r"your[_-]?(?:password|secret|key|token|api[_-]?key)(?:[_-].+)?|"
    r"change[_-]?(?:me|this)(?:[_-].+)?|"
    r"(?:xxx+|aaa+|000+)|"
    r"(?:example|sample|test|demo|placeholder|dummy|fake|mock)(?:[_-].+)?|"
    r"<[^>]+>|"         # <password> style
    r"\$\{[^}]+\}|"     # ${DATABASE_PASSWORD}
    r"%[A-Z_]+%|"       # %ENV_VAR%
    r"env\.[A-Z_]+"     # env.SECRET_KEY
    r")$"
)


def _is_placeholder(value: str) -> bool:
    """Return True if the extracted value looks like a placeholder, not a real secret."""
    stripped = value.strip().strip("\"'`")
    return bool(_PLACEHOLDER_RE.match(stripped)) or len(stripped) < 4


# ─── BaseDetector ─────────────────────────────────────────────────────────────
class BaseDetector(ABC):
    """
    Abstract base for all DataGhost secret detectors.

    Subclasses must implement:
        detector_id: str  – stable lowercase identifier
        name: str         – human-readable label
        categories: list  – finding categories produced
        detect(text, filename, context) -> List[DetectorFinding]
    """

    @property
    @abstractmethod
    def detector_id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def categories(self) -> List[str]: ...

    @abstractmethod
    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]: ...

    # ── Helpers available to all subclasses ───────────────────────────────────
    @staticmethod
    def line_col(text: str, offset: int) -> tuple[int, int]:
        return _line_col(text, offset)

    @staticmethod
    def redact(raw: str, keep_prefix: int = 4, keep_suffix: int = 0) -> str:
        return _redact(raw, keep_prefix, keep_suffix)

    @staticmethod
    def has_high_entropy(s: str, threshold: float = 3.5, min_len: int = 20) -> bool:
        return _has_high_entropy(s, threshold, min_len)

    @staticmethod
    def is_placeholder(value: str) -> bool:
        return _is_placeholder(value)

    def _safe_detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        """Call detect() with error isolation."""
        if not text or not isinstance(text, str):
            return []
        try:
            return self.detect(text, filename, context)
        except Exception:
            return []
