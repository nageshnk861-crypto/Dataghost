"""
DataGhost – Risk Engine.
Deterministic risk calculation converting DLP findings, classification tier,
destination, action, and volume into a 0–100 clamped risk score with severity
and recommended action.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# ---------------------------------------------------------------------------
# Scoring lookup tables
# ---------------------------------------------------------------------------
CLASSIFICATION_SCORES: Dict[str, int] = {
    "PUBLIC": 0,
    "INTERNAL": 8,
    "CONFIDENTIAL": 15,
    "RESTRICTED": 20,
}

DESTINATION_SCORES: Dict[str, int] = {
    "LOCAL": 0,
    "INTERNAL": 5,
    "CLOUD": 15,
    "USB": 18,
    "EXTERNAL": 20,
}

ACTION_SCORES: Dict[str, int] = {
    "READ": 2,
    "COPY": 7,
    "SHARE": 8,
    "EMAIL": 9,
    "UPLOAD": 10,
    # Extended aliases for compatibility
    "TRANSFER": 9,
    "DOWNLOAD": 6,
}

# Severity bands: <30 = LOW, 30–59 = MEDIUM, 60–79 = HIGH, >=80 = CRITICAL
_SEVERITY_BANDS = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (30, "MEDIUM"),
    (0, "LOW"),
]

# Recommended action by severity
RECOMMENDED_ACTIONS: Dict[str, str] = {
    "LOW": "ALLOW",
    "MEDIUM": "ALERT",
    "HIGH": "ALERT",
    "CRITICAL": "BLOCK",
}

# Action taken (past-tense for persistence and UI compatibility)
ACTION_MAP: Dict[str, str] = {
    "LOW": "ALLOWED",
    "MEDIUM": "ALERTED",
    "HIGH": "ALERTED",
    "CRITICAL": "BLOCKED",
}


# ---------------------------------------------------------------------------
# Result Dataclass
# ---------------------------------------------------------------------------
@dataclass
class RiskResult:
    risk_score: int
    severity: str
    action_taken: str
    recommended_action: str = ""
    breakdown: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.recommended_action and self.severity in RECOMMENDED_ACTIONS:
            self.recommended_action = RECOMMENDED_ACTIONS[self.severity]


# ---------------------------------------------------------------------------
# Risk Calculator
# ---------------------------------------------------------------------------
class RiskCalculator:
    """
    Deterministic Risk Engine for DataGhost.

    Calculates risk score (0–100) based on:
      1. Data Sensitivity: 0–40 (from scanner findings)
      2. Classification:   0–20 (PUBLIC=0, INTERNAL=8, CONFIDENTIAL=15, RESTRICTED=20)
      3. Destination:      0–20 (LOCAL=0, INTERNAL=5, CLOUD=15, USB=18, EXTERNAL=20)
      4. Action:           0–10 (READ=2, COPY=7, SHARE=8, EMAIL=9, UPLOAD=10)
      5. Volume:           0–10 (file size / byte count contribution)
    """

    def calculate_data_sensitivity(
        self,
        findings: Optional[List[Any]] = None,
        direct_score: Optional[int] = None,
    ) -> int:
        """Calculate data sensitivity score (0–40)."""
        if direct_score is not None:
            return max(0, min(int(direct_score), 40))

        if not findings:
            return 0

        try:
            from scanner.sensitive_scanner import SensitiveScanner
            score = SensitiveScanner().get_severity_score(findings)
            return max(0, min(int(score), 40))
        except Exception:
            return 0

    def calculate_classification_score(self, classification: Optional[str]) -> int:
        """Calculate document classification contribution (0–20)."""
        if not classification or not isinstance(classification, str):
            return 0
        norm = classification.strip().upper()
        return CLASSIFICATION_SCORES.get(norm, 0)

    def calculate_destination_score(self, destination: Optional[str]) -> int:
        """Calculate destination contribution (0–20)."""
        if not destination or not isinstance(destination, str):
            return 0
        norm = destination.strip().upper()
        return DESTINATION_SCORES.get(norm, 0)

    def calculate_action_score(self, action: Optional[str]) -> int:
        """Calculate action contribution (0–10)."""
        if not action or not isinstance(action, str):
            return 0
        norm = action.strip().upper()
        return ACTION_SCORES.get(norm, 0)

    def calculate_volume_score(
        self,
        file_size_bytes: int = 0,
        volume: Optional[int] = None,
    ) -> int:
        """Calculate volume / file-size contribution (0–10)."""
        if volume is not None:
            return max(0, min(int(volume), 10))

        if not file_size_bytes or file_size_bytes <= 0:
            return 0

        # Linear proxy: 50KB per point up to 10 points (500KB+)
        return min(int(file_size_bytes / 50_000), 10)

    def get_severity(self, risk_score: int) -> str:
        """Determine severity band based on score: <30 LOW, 30-59 MEDIUM, 60-79 HIGH, >=80 CRITICAL."""
        clamped = max(0, min(int(risk_score), 100))
        for threshold, label in _SEVERITY_BANDS:
            if clamped >= threshold:
                return label
        return "LOW"

    def get_recommended_action(self, severity: str) -> str:
        """Determine recommended action: LOW->ALLOW, MEDIUM->ALERT, HIGH->ALERT, CRITICAL->BLOCK."""
        return RECOMMENDED_ACTIONS.get(severity.upper(), "ALLOW")

    def get_action_taken(self, severity: str) -> str:
        """Determine action taken (past-tense label): LOW->ALLOWED, MEDIUM->ALERTED, HIGH->ALERTED, CRITICAL->BLOCKED."""
        return ACTION_MAP.get(severity.upper(), "ALLOWED")

    def calculate(
        self,
        findings: Optional[List[Any]] = None,
        classification: str = "PUBLIC",
        confidence: float = 1.0,
        destination: str = "LOCAL",
        action: str = "READ",
        file_size_bytes: int = 0,
        volume: Optional[int] = None,
        data_sensitivity: Optional[int] = None,
    ) -> RiskResult:
        """
        Calculate total deterministic risk score and return structured RiskResult.
        Score is strictly clamped between 0 and 100.
        """
        # 1. Data Sensitivity (0–40)
        sens_score = self.calculate_data_sensitivity(findings=findings, direct_score=data_sensitivity)

        # 2. Classification (0–20)
        class_score = self.calculate_classification_score(classification)

        # 3. Destination (0–20)
        dest_score = self.calculate_destination_score(destination)

        # 4. Action (0–10)
        act_score = self.calculate_action_score(action)

        # 5. Volume (0–10)
        vol_score = self.calculate_volume_score(file_size_bytes=file_size_bytes, volume=volume)

        # Total Raw & Clamped Score (0–100)
        raw_total = sens_score + class_score + dest_score + act_score + vol_score
        risk_score = max(0, min(raw_total, 100))

        # Determine Severity and Action
        severity = self.get_severity(risk_score)
        rec_action = self.get_recommended_action(severity)
        act_taken = self.get_action_taken(severity)

        breakdown = {
            "data_sensitivity": sens_score,
            "classification": class_score,
            "destination": dest_score,
            "action": act_score,
            "volume": vol_score,
            "total_raw": raw_total,
        }

        return RiskResult(
            risk_score=risk_score,
            severity=severity,
            action_taken=act_taken,
            recommended_action=rec_action,
            breakdown=breakdown,
        )


def calculate_risk(
    findings: Optional[List[Any]] = None,
    classification: str = "PUBLIC",
    confidence: float = 1.0,
    destination: str = "LOCAL",
    action: str = "READ",
    file_size_bytes: int = 0,
    volume: Optional[int] = None,
    data_sensitivity: Optional[int] = None,
) -> RiskResult:
    """Convenience functional interface for RiskCalculator."""
    return RiskCalculator().calculate(
        findings=findings,
        classification=classification,
        confidence=confidence,
        destination=destination,
        action=action,
        file_size_bytes=file_size_bytes,
        volume=volume,
        data_sensitivity=data_sensitivity,
    )
