"""
DataGhost – Private Key Detector (Phase 3).

Detects PEM-encoded private key blocks. The key material (body of the block)
is NEVER stored in findings – only the header line and location are recorded.

Supported formats:
  -----BEGIN PRIVATE KEY-----          (PKCS#8 unencrypted)
  -----BEGIN RSA PRIVATE KEY-----      (PKCS#1)
  -----BEGIN EC PRIVATE KEY-----       (SEC 1 / RFC 5915)
  -----BEGIN DSA PRIVATE KEY-----      (DSA)
  -----BEGIN OPENSSH PRIVATE KEY-----  (OpenSSH)
  -----BEGIN ENCRYPTED PRIVATE KEY-----
"""
from __future__ import annotations

import re
from typing import List, Optional

from detectors.base import BaseDetector, DetectorFinding, _line_col

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?P<key_type>(?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----",
    re.IGNORECASE,
)


class PrivateKeyDetector(BaseDetector):
    detector_id = "private_key"
    name = "Private Key Detector"
    categories = ["CREDENTIALS"]

    def detect(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        seen: set[int] = set()

        for m in _PRIVATE_KEY_RE.finditer(text):
            if m.start() in seen:
                continue
            seen.add(m.start())

            key_type = m.group("key_type").strip().upper()
            rule_name = f"private_key_{key_type.lower().replace(' ', '_')}"
            # Evidence: show only the BEGIN header – never the key body
            evidence = m.group(0)
            line, col = _line_col(text, m.start())

            findings.append(DetectorFinding(
                detector_id=self.detector_id,
                rule_name=rule_name,
                category="CREDENTIALS",
                severity="CRITICAL",
                confidence=0.99,
                filename=filename,
                line_number=line,
                column_start=col,
                char_start=m.start(),
                char_end=m.end(),
                evidence=evidence,   # header only – no key material
            ))

        return findings
