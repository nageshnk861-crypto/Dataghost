"""
DataGhost - DLP Scanner

Runs the rules defined in dlp_rules.py against text and
returns structured sensitive-data findings.
"""

from typing import Any, Dict, List

try:
    from .dlp_rules import DLP_RULES
except (ImportError, ValueError):
    from dlp_rules import DLP_RULES


def _has_context(text: str, start: int, end: int, keywords: List[str]) -> bool:
    """
    Check whether one of the rule's context keywords appears
    within 200 characters of the detected match.
    """
    context_start = max(0, start - 200)
    context_end = min(len(text), end + 200)

    context = text[context_start:context_end].lower()

    return any(keyword.lower() in context for keyword in keywords)


def scan_text(text: str) -> Dict[str, Any]:
    """
    Scan text using all configured DLP rules.

    Returns:
        {
            "findings": [...],
            "total_findings": int,
            "rules_triggered": [...]
        }
    """

    findings: List[Dict[str, Any]] = []
    rules_triggered = set()

    if not text or not isinstance(text, str):
        return {
            "findings": [],
            "total_findings": 0,
            "rules_triggered": [],
        }

    for rule in DLP_RULES:
        pattern = rule["pattern"]
        context_keywords = rule.get("context_keywords")

        for match in pattern.finditer(text):

            # Rules with context requirements only trigger
            # when the appropriate keyword is nearby.
            if context_keywords:
                if not _has_context(
                    text,
                    match.start(),
                    match.end(),
                    context_keywords,
                ):
                    continue

            finding = {
                "rule": rule["name"],
                "category": rule["category"],
                "severity": rule["severity"],
                "start": match.start(),
                "end": match.end(),
                "matched_text": match.group(0),
            }

            findings.append(finding)
            rules_triggered.add(rule["name"])

    return {
        "findings": findings,
        "total_findings": len(findings),
        "rules_triggered": sorted(rules_triggered),
    }


if __name__ == "__main__":
    test_text = """
    Name: Rahul Sharma
    Email: rahul@example.com
    Phone: 9876543210
    PAN: ABCDE1234F
    Aadhaar: 2345 6789 0123
    """

    result = scan_text(test_text)

    print("\n=== DATAGHOST DLP SCANNER ===")

    print(f"Total findings: {result['total_findings']}")

    for finding in result["findings"]:
        print(
            f"[{finding['severity']}] "
            f"{finding['rule']} -> "
            f"{finding['matched_text']}"
        )