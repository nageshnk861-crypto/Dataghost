"""
Tests for DataGhost Risk Engine (Phase 2).
Deterministic 0-100 risk scoring with DLP findings, document classification,
destination, action, volume scaling, boundary threshold tests, and actions.
All test samples use mock/fake values.
"""
import pytest
from risk_engine.risk_calculator import (
    RiskCalculator,
    RiskResult,
    calculate_risk,
    CLASSIFICATION_SCORES,
    DESTINATION_SCORES,
    ACTION_SCORES,
    RECOMMENDED_ACTIONS,
    ACTION_MAP,
)
from schemas.schemas import Finding
from scanner.dlp_scanner import scan_text


@pytest.fixture
def calc():
    return RiskCalculator()


# ---------------------------------------------------------------------------
# 1. Scoring Tables & Components Verification
# ---------------------------------------------------------------------------

def test_scoring_tables_integrity(calc):
    """Verify standard scoring tables match the specification."""
    # Classification (0-20)
    assert CLASSIFICATION_SCORES["PUBLIC"] == 0
    assert CLASSIFICATION_SCORES["INTERNAL"] == 8
    assert CLASSIFICATION_SCORES["CONFIDENTIAL"] == 15
    assert CLASSIFICATION_SCORES["RESTRICTED"] == 20

    # Destination (0-20)
    assert DESTINATION_SCORES["LOCAL"] == 0
    assert DESTINATION_SCORES["INTERNAL"] == 5
    assert DESTINATION_SCORES["CLOUD"] == 15
    assert DESTINATION_SCORES["USB"] == 18
    assert DESTINATION_SCORES["EXTERNAL"] == 20

    # Action (0-10)
    assert ACTION_SCORES["READ"] == 2
    assert ACTION_SCORES["COPY"] == 7
    assert ACTION_SCORES["SHARE"] == 8
    assert ACTION_SCORES["EMAIL"] == 9
    assert ACTION_SCORES["UPLOAD"] == 10

    # Action recommendations
    assert RECOMMENDED_ACTIONS["LOW"] == "ALLOW"
    assert RECOMMENDED_ACTIONS["MEDIUM"] == "ALERT"
    assert RECOMMENDED_ACTIONS["HIGH"] == "ALERT"
    assert RECOMMENDED_ACTIONS["CRITICAL"] == "BLOCK"


# ---------------------------------------------------------------------------
# 2. Document Classification Tests
# ---------------------------------------------------------------------------

class TestDocumentClassification:
    def test_clean_public_document(self, calc):
        """Public document read locally with no findings -> minimum risk."""
        res = calc.calculate(
            findings=[],
            classification="PUBLIC",
            destination="LOCAL",
            action="READ",
            file_size_bytes=1000,
        )
        # Data:0 + Class:0 + Dest:0 + Action:2 + Vol:0 = 2
        assert res.risk_score == 2
        assert res.severity == "LOW"
        assert res.recommended_action == "ALLOW"
        assert res.action_taken == "ALLOWED"
        assert res.breakdown["classification"] == 0

    def test_internal_document(self, calc):
        """Internal document -> +8 classification score."""
        res = calc.calculate(
            findings=[],
            classification="INTERNAL",
            destination="LOCAL",
            action="READ",
        )
        assert res.breakdown["classification"] == 8
        assert res.risk_score == 10  # 0 + 8 + 0 + 2 + 0
        assert res.severity == "LOW"
        assert res.recommended_action == "ALLOW"

    def test_confidential_document(self, calc):
        """Confidential document -> +15 classification score."""
        res = calc.calculate(
            findings=[],
            classification="CONFIDENTIAL",
            destination="INTERNAL",
            action="COPY",
        )
        # Data:0 + Class:15 + Dest:5 + Action:7 + Vol:0 = 27
        assert res.breakdown["classification"] == 15
        assert res.risk_score == 27
        assert res.severity == "LOW"
        assert res.recommended_action == "ALLOW"

    def test_restricted_document(self, calc):
        """Restricted document -> +20 classification score."""
        res = calc.calculate(
            findings=[],
            classification="RESTRICTED",
            destination="INTERNAL",
            action="READ",
        )
        # Data:0 + Class:20 + Dest:5 + Action:2 + Vol:0 = 27
        assert res.breakdown["classification"] == 20
        assert res.risk_score == 27


# ---------------------------------------------------------------------------
# 3. Data Sensitivity & Findings Tests
# ---------------------------------------------------------------------------

class TestDataSensitivityFindings:
    def test_high_sensitivity_findings(self, calc):
        """High sensitivity finding (PAN/Aadhaar/Credit Card) gives base 25-34."""
        findings = [
            Finding(
                rule_name="pan_card",
                severity="HIGH",
                matches_count=1,
                sample_match="ABCDE1234F",
                category="PII",
            )
        ]
        res = calc.calculate(
            findings=findings,
            classification="INTERNAL",
            destination="INTERNAL",
            action="READ",
        )
        # Sensitivity: 25 + Class: 8 + Dest: 5 + Action: 2 + Vol: 0 = 40
        assert res.breakdown["data_sensitivity"] == 25
        assert res.risk_score == 40
        assert res.severity == "MEDIUM"
        assert res.recommended_action == "ALERT"

    def test_critical_credentials(self, calc):
        """Critical credentials (e.g. AWS Key / Private Key) give base 35-40."""
        findings = [
            Finding(
                rule_name="aws_access_key",
                severity="CRITICAL",
                matches_count=1,
                sample_match="AKIAIOSFODNN7EXAMPLE",
                category="CREDENTIALS",
            )
        ]
        res = calc.calculate(
            findings=findings,
            classification="CONFIDENTIAL",
            destination="CLOUD",
            action="UPLOAD",
            file_size_bytes=100_000,
        )
        # Sensitivity: 35 + Class: 15 + Dest: 15 + Action: 10 + Vol: 2 = 77
        assert res.breakdown["data_sensitivity"] == 35
        assert res.risk_score == 77
        assert res.severity == "HIGH"
        assert res.recommended_action == "ALERT"

    def test_with_dlp_scanner_output(self, calc):
        """Direct integration with scanner output dicts."""
        scan_res = scan_text("API key: AKIAIOSFODNN7EXAMPLE and PAN: ABCDE1234F")
        res = calc.calculate(
            findings=scan_res["findings"],
            classification="RESTRICTED",
            destination="EXTERNAL",
            action="UPLOAD",
        )
        # Findings include CRITICAL and HIGH -> Base 35 + cross-tier bonus 1 = 36
        # Class: 20 + Dest: 20 + Action: 10 = 50 + 36 = 86
        assert res.breakdown["data_sensitivity"] >= 35
        assert res.risk_score >= 80
        assert res.severity == "CRITICAL"
        assert res.recommended_action == "BLOCK"
        assert res.action_taken == "BLOCKED"


# ---------------------------------------------------------------------------
# 4. Destinations and Actions Tests
# ---------------------------------------------------------------------------

class TestDestinationsAndActions:
    def test_local_read(self, calc):
        """Local destination (0) and read action (2)."""
        res = calc.calculate(
            findings=[],
            classification="PUBLIC",
            destination="LOCAL",
            action="READ",
        )
        assert res.breakdown["destination"] == 0
        assert res.breakdown["action"] == 2
        assert res.risk_score == 2

    def test_external_upload(self, calc):
        """External destination (20) and upload action (10)."""
        res = calc.calculate(
            findings=[],
            classification="INTERNAL",
            destination="EXTERNAL",
            action="UPLOAD",
        )
        assert res.breakdown["destination"] == 20
        assert res.breakdown["action"] == 10
        # Data:0 + Class:8 + Dest:20 + Action:10 = 38
        assert res.risk_score == 38
        assert res.severity == "MEDIUM"
        assert res.recommended_action == "ALERT"

    def test_usb_and_share(self, calc):
        """USB destination (18) and share action (8)."""
        res = calc.calculate(
            findings=[],
            classification="PUBLIC",
            destination="USB",
            action="SHARE",
        )
        assert res.breakdown["destination"] == 18
        assert res.breakdown["action"] == 8
        assert res.risk_score == 26


# ---------------------------------------------------------------------------
# 5. Volume and Large File Scaling Tests
# ---------------------------------------------------------------------------

class TestVolumeScaling:
    def test_small_file_zero_volume(self, calc):
        res = calc.calculate(file_size_bytes=10_000)
        assert res.breakdown["volume"] == 0

    def test_medium_file_volume(self, calc):
        # 150,000 bytes -> 3 points
        res = calc.calculate(file_size_bytes=150_000)
        assert res.breakdown["volume"] == 3

    def test_large_file_max_volume(self, calc):
        # 600,000 bytes (>= 500KB) -> clamped to 10 points
        res = calc.calculate(file_size_bytes=600_000)
        assert res.breakdown["volume"] == 10

    def test_direct_volume_override(self, calc):
        res = calc.calculate(volume=7)
        assert res.breakdown["volume"] == 7

        res_over = calc.calculate(volume=15)
        assert res_over.breakdown["volume"] == 10


# ---------------------------------------------------------------------------
# 6. Score Boundary Threshold Tests (<30, 30-59, 60-79, >=80)
# ---------------------------------------------------------------------------

class TestScoreBoundaries:
    @pytest.mark.parametrize(
        "score,expected_sev,expected_rec,expected_taken",
        [
            (0, "LOW", "ALLOW", "ALLOWED"),
            (15, "LOW", "ALLOW", "ALLOWED"),
            (29, "LOW", "ALLOW", "ALLOWED"),
            (30, "MEDIUM", "ALERT", "ALERTED"),
            (45, "MEDIUM", "ALERT", "ALERTED"),
            (59, "MEDIUM", "ALERT", "ALERTED"),
            (60, "HIGH", "ALERT", "ALERTED"),
            (70, "HIGH", "ALERT", "ALERTED"),
            (79, "HIGH", "ALERT", "ALERTED"),
            (80, "CRITICAL", "BLOCK", "BLOCKED"),
            (95, "CRITICAL", "BLOCK", "BLOCKED"),
            (100, "CRITICAL", "BLOCK", "BLOCKED"),
        ],
    )
    def test_exact_boundary_thresholds(self, calc, score, expected_sev, expected_rec, expected_taken):
        assert calc.get_severity(score) == expected_sev
        assert calc.get_recommended_action(expected_sev) == expected_rec
        assert calc.get_action_taken(expected_sev) == expected_taken

    def test_boundary_29_vs_30(self, calc):
        # 29: Class(15) + Dest(5) + Action(9) = 29 -> LOW
        res_29 = calc.calculate(
            classification="CONFIDENTIAL",  # 15
            destination="INTERNAL",         # 5
            action="EMAIL",                 # 9
            volume=0,
            data_sensitivity=0,
        )
        assert res_29.risk_score == 29
        assert res_29.severity == "LOW"
        assert res_29.recommended_action == "ALLOW"

        # 30: Class(20) + Dest(0) + Action(10) = 30 -> MEDIUM
        res_30 = calc.calculate(
            classification="RESTRICTED",    # 20
            destination="LOCAL",            # 0
            action="UPLOAD",                # 10
            volume=0,
            data_sensitivity=0,
        )
        assert res_30.risk_score == 30
        assert res_30.severity == "MEDIUM"
        assert res_30.recommended_action == "ALERT"

    def test_boundary_59_vs_60(self, calc):
        # 59: Sensitivity(35) + Class(8) + Dest(5) + Action(9) + Vol(2) = 59 -> MEDIUM
        res_59 = calc.calculate(
            data_sensitivity=35,
            classification="INTERNAL",      # 8
            destination="INTERNAL",         # 5
            action="EMAIL",                 # 9
            volume=2,
        )
        assert res_59.risk_score == 59
        assert res_59.severity == "MEDIUM"
        assert res_59.recommended_action == "ALERT"

        # 60: Sensitivity(35) + Class(15) + Dest(0) + Action(10) = 60 -> HIGH
        res_60 = calc.calculate(
            data_sensitivity=35,
            classification="CONFIDENTIAL",  # 15
            destination="LOCAL",            # 0
            action="UPLOAD",                # 10
            volume=0,
        )
        assert res_60.risk_score == 60
        assert res_60.severity == "HIGH"
        assert res_60.recommended_action == "ALERT"

    def test_boundary_79_vs_80(self, calc):
        # 79: Sensitivity(35) + Class(20) + Dest(15) + Action(9) = 79 -> HIGH
        res_79 = calc.calculate(
            data_sensitivity=35,
            classification="RESTRICTED",    # 20
            destination="CLOUD",            # 15
            action="EMAIL",                 # 9
            volume=0,
        )
        assert res_79.risk_score == 79
        assert res_79.severity == "HIGH"
        assert res_79.recommended_action == "ALERT"

        # 80: Sensitivity(35) + Class(20) + Dest(15) + Action(10) = 80 -> CRITICAL
        res_80 = calc.calculate(
            data_sensitivity=35,
            classification="RESTRICTED",    # 20
            destination="CLOUD",            # 15
            action="UPLOAD",                # 10
            volume=0,
        )
        assert res_80.risk_score == 80
        assert res_80.severity == "CRITICAL"
        assert res_80.recommended_action == "BLOCK"
        assert res_80.action_taken == "BLOCKED"


# ---------------------------------------------------------------------------
# 7. Maximum Clamping (100) & Over-Limit Clamping
# ---------------------------------------------------------------------------

class TestScoreClamping:
    def test_maximum_score_exact_100(self, calc):
        """Sens(40) + Class(20) + Dest(20) + Action(10) + Vol(10) = 100."""
        res = calc.calculate(
            data_sensitivity=40,
            classification="RESTRICTED",
            destination="EXTERNAL",
            action="UPLOAD",
            volume=10,
        )
        assert res.risk_score == 100
        assert res.severity == "CRITICAL"
        assert res.recommended_action == "BLOCK"
        assert res.action_taken == "BLOCKED"

    def test_clamping_above_100(self, calc):
        """Values exceeding maximums are strictly clamped to 100."""
        res = calc.calculate(
            data_sensitivity=50,  # exceeds 40 -> clamped to 40
            classification="RESTRICTED",
            destination="EXTERNAL",
            action="UPLOAD",
            volume=20,            # exceeds 10 -> clamped to 10
        )
        assert res.risk_score == 100
        assert res.risk_score <= 100
        assert res.breakdown["data_sensitivity"] == 40
        assert res.breakdown["volume"] == 10

    def test_functional_calculate_risk_helper(self):
        """Test convenience module function calculate_risk."""
        res = calculate_risk(
            classification="INTERNAL",
            destination="LOCAL",
            action="READ",
        )
        assert isinstance(res, RiskResult)
        assert res.risk_score == 10
