"""
DataGhost – sensitive data scanner.
Runs all DLP rules against extracted text and returns a list of Finding objects.
"""
import re
from typing import List

from schemas.schemas import Finding
from scanner.dlp_rules import DLP_RULES

# Financial context keywords used to validate bank_account matches.
_BANK_CONTEXT_WINDOW = 200  # chars to scan on each side of a match


class SensitiveScanner:
    """
    Runs all DLP rules against a text string and returns structured findings.
    """

    def __init__(self):
        self._rules = DLP_RULES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, text: str) -> List[Finding]:
        """
        Run all DLP rules against *text*.

        Returns a list of Finding objects – one per rule that matched at least once.
        """
        findings: List[Finding] = []

        for rule in self._rules:
            name: str = rule["name"]
            pattern: re.Pattern = rule["pattern"]
            severity: str = rule["severity"]
            category: str = rule["category"]
            context_kw: list = rule.get("context_keywords", [])

            matches = list(pattern.finditer(text))
            if not matches:
                continue

            # Special logic for bank_account: only count matches that have a
            # financial keyword within ±200 characters.
            if name == "bank_account" and context_kw:
                validated = []
                for m in matches:
                    start = max(0, m.start() - _BANK_CONTEXT_WINDOW)
                    end = min(len(text), m.end() + _BANK_CONTEXT_WINDOW)
                    window = text[start:end].lower()
                    if any(kw in window for kw in context_kw):
                        validated.append(m)
                matches = validated
                if not matches:
                    continue

            sample = matches[0].group(0)[:50]

            findings.append(
                Finding(
                    rule_name=name,
                    severity=severity,
                    matches_count=len(matches),
                    sample_match=sample,
                    category=category,
                )
            )

        return findings

    def get_severity_score(self, findings: List[Finding]) -> int:
        """
        Convert a list of findings into a 0-40 data-sensitivity score.

        Severity weights:
          CRITICAL → 35–40 base
          HIGH     → 25–34 base
          MEDIUM   → 10–24 base
          LOW      →  1–9  base
        Multiple findings of the same tier add bonus points up to the tier max.
        """
        if not findings:
            return 0

        _BASE = {"CRITICAL": 35, "HIGH": 25, "MEDIUM": 10, "LOW": 1}
        _MAX = {"CRITICAL": 40, "HIGH": 34, "MEDIUM": 24, "LOW": 9}

        # Group findings by severity.
        by_severity: dict = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for f in findings:
            if isinstance(f, dict):
                sev = f.get("severity", "LOW")
            else:
                sev = getattr(f, "severity", "LOW")
            tier = sev.upper() if isinstance(sev, str) and sev.upper() in by_severity else "LOW"
            by_severity[tier].append(f)

        best_score = 0

        for tier, tier_findings in by_severity.items():
            if not tier_findings:
                continue
            base = _BASE[tier]
            ceiling = _MAX[tier]
            # Each additional finding in the same tier adds 1 point up to ceiling.
            score = min(base + len(tier_findings) - 1, ceiling)
            if score > best_score:
                best_score = score

        # Bonus: if findings span multiple high tiers, add a small cross-tier bonus.
        active_tiers = [t for t, fl in by_severity.items() if fl]
        if len(active_tiers) >= 3:
            best_score = min(best_score + 3, 40)
        elif len(active_tiers) == 2:
            best_score = min(best_score + 1, 40)

        return best_score
