"""
DataGhost – IP Address Detector (Phase 3).

Detects hardcoded IPv4 and IPv6 addresses and classifies them:
  - LOOPBACK   (127.0.0.0/8, ::1)          → LOW severity, informational
  - PRIVATE    (RFC 1918: 10/8, 172.16/12, 192.168/16) → LOW–MEDIUM
  - LINK_LOCAL (169.254/16, fe80::/10)     → LOW
  - PUBLIC     (routable)                  → MEDIUM–HIGH depending on context
  - RESERVED   (0.0.0.0, 255.255.255.255, multicast) → LOW

IPv6 detection is limited to full, unambiguous addresses.
Single octets (e.g. version numbers like "1.2.3") are excluded.
IP addresses alone are not treated as credential leaks.
Severity is contextual – a hardcoded public IP is MEDIUM, not CRITICAL.
"""
from __future__ import annotations

import ipaddress
import re
from typing import List, Optional

from detectors.base import BaseDetector, DetectorFinding, _line_col

# IPv4: strict 4-octet dotted decimal, word boundaries to avoid version strings
_IPV4_RE = re.compile(
    r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)(?!\d)"
)

# IPv6: full colon-hex notation (not link-local abbreviations to reduce noise)
_IPV6_RE = re.compile(
    r"(?<![:\w])"
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r"|:(?::[0-9a-fA-F]{1,4}){1,7}"
    r"|::(?:[fF]{4}(?::0{1,4})?:)?"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)){3}"
    r"(?![:\w])"
)

# Version strings that look like IPs but are not
_VERSION_CONTEXT_RE = re.compile(
    r"(?:version|v|ver|release|revision|build|kernel|os)\s*[:=]?\s*"
    r"(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){1,3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)",
    re.IGNORECASE,
)


def _classify_ipv4(addr: ipaddress.IPv4Address) -> tuple[str, str, float]:
    """Return (ip_class, severity, confidence)."""
    if addr.is_loopback:
        return "LOOPBACK", "LOW", 0.50
    if addr.is_private:
        return "PRIVATE", "LOW", 0.60
    if addr.is_link_local:
        return "LINK_LOCAL", "LOW", 0.50
    if addr.is_multicast:
        return "MULTICAST", "LOW", 0.45
    if addr.is_unspecified or addr == ipaddress.IPv4Address("255.255.255.255"):
        return "RESERVED", "LOW", 0.40
    # Routable public IP
    return "PUBLIC", "MEDIUM", 0.70


def _classify_ipv6(addr: ipaddress.IPv6Address) -> tuple[str, str, float]:
    if addr.is_loopback:
        return "LOOPBACK", "LOW", 0.50
    if addr.is_private:
        return "PRIVATE", "LOW", 0.60
    if addr.is_link_local:
        return "LINK_LOCAL", "LOW", 0.50
    if addr.is_multicast:
        return "MULTICAST", "LOW", 0.45
    return "PUBLIC", "MEDIUM", 0.65


def _near_version_keyword(text: str, start: int, window: int = 60) -> bool:
    """Return True if this address appears right after a version keyword."""
    ctx = text[max(0, start - window): start + window]
    return bool(_VERSION_CONTEXT_RE.search(ctx))


class IPAddressDetector(BaseDetector):
    detector_id = "ip_address"
    name = "Hardcoded IP Address Detector"
    categories = ["CREDENTIALS"]

    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        seen: set[int] = set()

        # IPv4
        for m in _IPV4_RE.finditer(text):
            if m.start() in seen:
                continue
            raw = m.group(0)
            try:
                addr = ipaddress.IPv4Address(raw)
            except ValueError:
                continue

            if addr.is_loopback or addr.is_unspecified:
                continue  # Loopback/unspecified never actionable

            if _near_version_keyword(text, m.start()):
                continue  # Likely a version string

            ip_class, severity, confidence = _classify_ipv4(addr)
            if severity == "LOW":
                continue  # private/link-local only reported at MEDIUM+

            seen.add(m.start())
            line, col = _line_col(text, m.start())

            findings.append(DetectorFinding(
                detector_id=self.detector_id,
                rule_name=f"hardcoded_ip_{ip_class.lower()}",
                category="CREDENTIALS",
                severity=severity,
                confidence=confidence,
                filename=filename,
                line_number=line,
                column_start=col,
                char_start=m.start(),
                char_end=m.end(),
                evidence=raw,     # IPs themselves are not secrets; no redaction needed
            ))

        # IPv6
        for m in _IPV6_RE.finditer(text):
            if m.start() in seen:
                continue
            raw = m.group(0)
            try:
                addr = ipaddress.IPv6Address(raw)
            except ValueError:
                continue
            if addr.is_loopback:
                continue

            ip_class, severity, confidence = _classify_ipv6(addr)
            if severity == "LOW":
                continue

            seen.add(m.start())
            line, col = _line_col(text, m.start())

            findings.append(DetectorFinding(
                detector_id=self.detector_id,
                rule_name=f"hardcoded_ip_v6_{ip_class.lower()}",
                category="CREDENTIALS",
                severity=severity,
                confidence=confidence,
                filename=filename,
                line_number=line,
                column_start=col,
                char_start=m.start(),
                char_end=m.end(),
                evidence=raw,
            ))

        return findings
