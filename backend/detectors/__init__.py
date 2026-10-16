"""
DataGhost – Secret Detection Engine (Phase 3).

Modular, extensible detector architecture that integrates with the
existing DLP scan pipeline. Detectors produce normalized DetectorFinding
objects that are merged into the existing ScanFinding schema.

Usage:
    from detectors.registry import DetectorRegistry
    registry = DetectorRegistry.default()
    findings = registry.scan(text, filename="config.env")
"""
from detectors.base import BaseDetector, DetectorFinding
from detectors.registry import DetectorRegistry

__all__ = ["BaseDetector", "DetectorFinding", "DetectorRegistry"]
