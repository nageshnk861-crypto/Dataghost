"""
DataGhost – Detector Registry (Phase 3).

Central registry that:
  1. Holds all registered BaseDetector instances.
  2. Runs all detectors against a text payload.
  3. Deduplicates findings by fingerprint.
  4. Converts DetectorFinding objects into the dict format expected by
     the existing _process_scan pipeline (compatible with ScanFinding schema).

Usage:
    registry = DetectorRegistry.default()
    findings = registry.scan(text, filename="secrets.env")
    # findings is List[DetectorFinding], deduplicated

Integration with scan_routes.py:
    The registry is called inside _process_scan BEFORE the existing
    dlp_scanner.scan_text() call so that results are merged.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from detectors.base import BaseDetector, DetectorFinding

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """Thread-safe (stateless scan) registry for secret detectors."""

    def __init__(self) -> None:
        self._detectors: List[BaseDetector] = []

    def register(self, detector: BaseDetector) -> "DetectorRegistry":
        self._detectors.append(detector)
        return self

    def scan(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[DetectorFinding]:
        """
        Run all registered detectors and return deduplicated findings.
        Detector failures are isolated – one failing detector does not
        prevent others from running.
        """
        all_findings: List[DetectorFinding] = []
        seen_fingerprints: set[str] = set()

        for detector in self._detectors:
            try:
                found = detector._safe_detect(text, filename, context)
            except Exception as exc:
                logger.warning(
                    "Detector %s raised unexpectedly: %s",
                    detector.detector_id, exc
                )
                found = []

            for f in found:
                if f.fingerprint not in seen_fingerprints:
                    seen_fingerprints.add(f.fingerprint)
                    all_findings.append(f)

        return all_findings

    def to_scan_finding_dicts(
        self,
        text: str,
        filename: str = "",
        context: Optional[dict] = None,
    ) -> List[dict]:
        """
        Convenience method: run scan and convert to ScanFinding-compatible dicts.
        """
        return [f.to_scan_finding_dict() for f in self.scan(text, filename, context)]

    # ── Factory ───────────────────────────────────────────────────────────────
    @classmethod
    def default(cls) -> "DetectorRegistry":
        """
        Build and return the standard registry with all built-in detectors.
        Import is deferred so individual detector failures don't break import.
        """
        from detectors.api_key_detector import APIKeyDetector
        from detectors.database_url_detector import DatabaseURLDetector
        from detectors.password_detector import PasswordDetector
        from detectors.pii_detector import PIIDetector
        from detectors.private_key_detector import PrivateKeyDetector
        from detectors.jwt_detector import JWTDetector
        from detectors.ip_address_detector import IPAddressDetector

        registry = cls()
        registry.register(PrivateKeyDetector())   # highest priority (CRITICAL, unambiguous)
        registry.register(APIKeyDetector())
        registry.register(JWTDetector())
        registry.register(DatabaseURLDetector())
        registry.register(PasswordDetector())
        registry.register(PIIDetector())
        registry.register(IPAddressDetector())    # lowest priority (context-dependent)
        return registry


# Module-level singleton (lazy)
_default_registry: Optional[DetectorRegistry] = None


def get_registry() -> DetectorRegistry:
    """Return the lazily-initialised default registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = DetectorRegistry.default()
    return _default_registry
