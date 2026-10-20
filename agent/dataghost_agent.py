# -*- coding: utf-8 -*-
"""
DataGhost Agent v1.0.0
Monitors configured directories for sensitive data and reports to the DataGhost backend.
"""

import argparse
import hashlib
import io
import json
import logging
import os
import platform
import re
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import warnings
warnings.filterwarnings("ignore", category=Warning, module="requests")

import requests
from colorama import Fore, Style, init as colorama_init
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Global counters for heartbeat metrics
SCANNED_FILES_COUNT = 0
INCIDENTS_COUNT = 0
_COUNTERS_LOCK = threading.Lock()

# Ensure UTF-8 output on Windows consoles to prevent UnicodeEncodeError
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

colorama_init(autoreset=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("dataghost-agent")

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    # Environment variable overrides
    if "DATAGHOST_API_URL" in os.environ:
        cfg["api_url"] = os.environ["DATAGHOST_API_URL"]
    if "DATAGHOST_DEVICE_ID" in os.environ:
        cfg["device_id"] = os.environ["DATAGHOST_DEVICE_ID"]
    if "DATAGHOST_USER" in os.environ:
        cfg["user"] = os.environ["DATAGHOST_USER"]
    if "DATAGHOST_WATCH_DIRS" in os.environ:
        cfg["watch_dirs"] = [p.strip() for p in os.environ["DATAGHOST_WATCH_DIRS"].split(",") if p.strip()]

    # Default to standard user personal directories: Documents, Desktop, Downloads
    if not cfg.get("watch_dirs"):
        home = Path.home()
        defaults = [
            str(home / "Documents"),
            str(home / "Desktop"),
            str(home / "Downloads"),
        ]
        cfg["watch_dirs"] = [d for d in defaults if os.path.exists(d)]

    # Expand ~ in watch_dirs and resolve paths
    cfg["watch_dirs"] = [
        str(Path(d).expanduser().resolve()) for d in cfg.get("watch_dirs", [])
    ]
    return cfg



# ---------------------------------------------------------------------------
# Inline DLP rules (mirrors backend/scanner/dlp_rules.py)
# ---------------------------------------------------------------------------
def _c(pattern: str, flags: int = 0) -> re.Pattern:
    return re.compile(pattern, flags | re.MULTILINE)


def luhn_checksum_valid(number_str: str) -> bool:
    """Validate numeric string using Luhn algorithm (Mod 10)."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


DLP_RULES: List[Dict[str, Any]] = [
    {
        "name": "credit_card",
        "pattern": _c(
            r"\b(?:4[0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{1,4}"
            r"|5[1-5][0-9]{2}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}"
            r"|3[47][0-9]{2}[-\s]?[0-9]{6}[-\s]?[0-9]{5}"
            r"|6(?:011|5[0-9]{2})[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}"
            r"|4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
            r"|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "severity": "HIGH",
        "category": "FINANCIAL",
        "validator": luhn_checksum_valid,
    },
    {"name": "email_address",        "pattern": _c(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),              "severity": "MEDIUM",   "category": "PII"},
    {"name": "phone_india",          "pattern": _c(r"\b[6-9]\d{9}\b"),                                                  "severity": "MEDIUM",   "category": "PII"},
    {"name": "aadhaar",              "pattern": _c(r"(?<!\d)[2-9]\d{3}[\s-]\d{4}[\s-]\d{4}(?!\d|[\s-]\d)"),            "severity": "HIGH",     "category": "PII"},
    {"name": "pan_card",             "pattern": _c(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                                      "severity": "HIGH",     "category": "PII"},
    {"name": "api_key_generic",      "pattern": _c(r'(?:api[_\-]?key|apikey)\s*[=:\s]+\s*[\'"]?([A-Za-z0-9_\-]{32,})[\'"]?', re.IGNORECASE), "severity": "CRITICAL", "category": "CREDENTIALS"},
    {"name": "jwt_token",            "pattern": _c(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "severity": "CRITICAL", "category": "CREDENTIALS"},
    {"name": "private_key",          "pattern": _c(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),                "severity": "CRITICAL", "category": "CREDENTIALS"},
    {"name": "aws_access_key",       "pattern": _c(r"\bAKIA[0-9A-Z]{16}\b"),                                           "severity": "CRITICAL", "category": "CREDENTIALS"},
    {"name": "password_field",       "pattern": _c(r"(?:password|passwd|pwd)\s*[=:\s]+\s*[\S]{4,}", re.IGNORECASE),    "severity": "HIGH",     "category": "CREDENTIALS"},
    {"name": "confidential_marker",  "pattern": _c(r"\b(?:confidential|top secret|classified|do not distribute|internal use only|proprietary)\b", re.IGNORECASE), "severity": "HIGH", "category": "CORPORATE"},
    {"name": "employee_data_marker", "pattern": _c(r"\b(?:employee id|emp id|staff id|payroll|salary|ctc|annual package)\b", re.IGNORECASE), "severity": "HIGH", "category": "CORPORATE"},
    {"name": "customer_data_marker", "pattern": _c(r"\b(?:customer id|client id|customer database|crm|account holder)\b", re.IGNORECASE), "severity": "HIGH", "category": "CORPORATE"},
]

# ---------------------------------------------------------------------------
# Inline text extractor (mirrors backend/scanner/text_extractor.py)
# ---------------------------------------------------------------------------
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".xml", ".yaml", ".yml",
    ".env", ".cfg", ".ini", ".log", ".csv", ".html", ".htm", ".sh", ".bat",
    ".ps1", ".rb", ".go", ".java", ".c", ".cpp", ".h",
}
MAX_TEXT_LENGTH = 50_000


def _decode_bytes(data: bytes) -> str:
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        pass
    try:
        import chardet
        enc = (chardet.detect(data).get("encoding") or "utf-8")
        return data.decode(enc, errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")


def _ext(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def extract_text(file_content: bytes, filename: str) -> str:
    ext = _ext(filename)
    if ext in _TEXT_EXTENSIONS:
        text = _decode_bytes(file_content)
    elif ext == ".pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            parts = [p.extract_text() or "" for p in reader.pages]
            text = "\n".join(parts)
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", exc)
            text = ""
    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_content))
            paras = [p.text for p in doc.paragraphs if p.text]
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text:
                            paras.append(cell.text)
            text = "\n".join(paras)
        except Exception as exc:
            logger.warning("DOCX extraction failed: %s", exc)
            text = ""
    else:
        try:
            text = _decode_bytes(file_content)
        except Exception:
            text = ""
    return text[:MAX_TEXT_LENGTH]


# ---------------------------------------------------------------------------
# Inline scanner
# ---------------------------------------------------------------------------
def scan_text(text: str) -> List[Dict[str, Any]]:
    """Run DLP rules and return list of finding dicts."""
    findings = []
    for rule in DLP_RULES:
        validator = rule.get("validator")
        matches = list(rule["pattern"].finditer(text))
        if validator:
            matches = [m for m in matches if validator(m.group(0))]
        if not matches:
            continue
        findings.append({
            "rule_name": rule["name"],
            "severity": rule["severity"],
            "category": rule["category"],
            "matches_count": len(matches),
            "sample_match": matches[0].group(0)[:50],
        })
    return findings


# ---------------------------------------------------------------------------
# Inline classifier (keyword-based)
# ---------------------------------------------------------------------------
def classify_findings(findings: List[Dict[str, Any]]) -> str:
    """
    Simple keyword-based classifier that mirrors the backend ML result for the agent.
      RESTRICTED  – any CRITICAL finding
      CONFIDENTIAL – any HIGH finding
      INTERNAL    – any MEDIUM finding
      PUBLIC      – no findings
    """
    severities = {f["severity"] for f in findings}
    if "CRITICAL" in severities:
        return "RESTRICTED"
    if "HIGH" in severities:
        return "CONFIDENTIAL"
    if "MEDIUM" in severities:
        return "INTERNAL"
    return "PUBLIC"


# ---------------------------------------------------------------------------
# Inline risk calculator
# ---------------------------------------------------------------------------
_CLASSIFICATION_SCORES = {"PUBLIC": 0, "INTERNAL": 8, "CONFIDENTIAL": 15, "RESTRICTED": 20}
_DESTINATION_SCORES    = {"INTERNAL": 5, "CLOUD": 15, "EXTERNAL": 20, "USB": 18, "LOCAL": 0}
_ACTION_SCORES         = {"READ": 2, "COPY": 7, "EMAIL": 9, "UPLOAD": 10, "TRANSFER": 9, "SHARE": 8}
_SEVERITY_BANDS        = [(80, "CRITICAL"), (60, "HIGH"), (30, "MEDIUM"), (0, "LOW")]


def calculate_risk(
    findings: List[Dict[str, Any]],
    classification: str,
    destination: str = "INTERNAL",
    action: str = "READ",
    file_size_bytes: int = 0,
) -> Dict[str, Any]:
    # Sensitivity score (0-40)
    sev_map = {"CRITICAL": 35, "HIGH": 25, "MEDIUM": 10, "LOW": 1}
    sensitivity = 0
    for f in findings:
        sensitivity = max(sensitivity, sev_map.get(f["severity"], 1))
    sensitivity = min(sensitivity + max(len(findings) - 1, 0), 40)

    class_score = _CLASSIFICATION_SCORES.get(classification.upper(), 0)
    dest_score  = _DESTINATION_SCORES.get(destination.upper(), 5)
    action_score = _ACTION_SCORES.get(action.upper(), 5)
    volume_score = min(int(file_size_bytes / 50_000), 10)

    raw = sensitivity + class_score + dest_score + action_score + volume_score
    score = min(raw, 100)

    severity = "LOW"
    for threshold, sev_label in _SEVERITY_BANDS:
        if score >= threshold:
            severity = sev_label
            break

    return {"score": score, "severity": severity}


# ---------------------------------------------------------------------------
# Colored output helpers
# ---------------------------------------------------------------------------
def print_critical_banner(filename: str, risk_score: int, severity: str) -> None:
    fn = filename[:36].ljust(36)
    sv = severity.ljust(28)
    rs = str(risk_score).ljust(3)
    print(Fore.RED + Style.BRIGHT + "+--------------------------------------+")
    print(Fore.RED + Style.BRIGHT + "|  [!] DATA EXFILTRATION DETECTED [!]  |")
    print(Fore.RED + Style.BRIGHT + "+--------------------------------------+")
    print(Fore.RED + Style.BRIGHT + f"|  File: {fn}  |")
    print(Fore.RED + Style.BRIGHT + f"|  Risk: {rs}/100 {sv}|")
    print(Fore.RED + Style.BRIGHT + "|  Action: BLOCKED                     |")
    print(Fore.RED + Style.BRIGHT + "+--------------------------------------+")


def print_high_warning(filepath: str, risk_score: int, findings: List[Dict[str, Any]]) -> None:
    cats = ", ".join({f["category"] for f in findings})
    print(Fore.YELLOW + Style.BRIGHT + f"[!] SENSITIVE DATA DETECTED")
    print(Fore.YELLOW + f"   File     : {filepath}")
    print(Fore.YELLOW + f"   Risk     : {risk_score}/100  [HIGH]")
    print(Fore.YELLOW + f"   Data     : {cats}")
    print(Fore.YELLOW + f"   Action   : ALERT")


def print_info(filepath: str, classification: str, risk_score: int, severity: str) -> None:
    color = Fore.GREEN if severity == "LOW" else Fore.CYAN
    print(color + f"[OK]  {os.path.basename(filepath)}  |  {classification}  |  Risk {risk_score}/100  [{severity}]")


# ---------------------------------------------------------------------------
# Backend client & enrollment
# ---------------------------------------------------------------------------

def save_config(cfg: Dict[str, Any]) -> None:
    """Persist config back to config.json."""
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logger.warning("Could not save config.json: %s", e)


def enroll_device(api_url: str, enrollment_code_or_token: str) -> Optional[str]:
    """Enroll device with backend using an enrollment code or raw token."""
    sys_plat = "Windows" if sys.platform == "win32" else ("macOS" if sys.platform == "darwin" else "Linux")
    payload = {
        "token": enrollment_code_or_token,
        "enrollment_code": enrollment_code_or_token,
        "device_name": socket.gethostname(),
        "platform": sys_plat,
        "os_name": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "hostname": socket.gethostname(),
        "ip_address": socket.gethostbyname(socket.gethostname()),
        "agent_version": "2.0.0",
    }
    max_attempts = 10
    base_delay = 3
    max_delay = 60

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(
                f"{api_url}/api/devices/enrollment/register",
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                assigned_id = data.get("device_id")
                auth_token = data.get("auth_token", "")
                print(Fore.GREEN + Style.BRIGHT + "\n  [+] Device Enrolled Successfully!")
                print(Fore.GREEN + f"      Assigned Device ID : {assigned_id}")
                print(Fore.GREEN + f"      Platform           : {data.get('platform')}")
                print(Fore.GREEN + f"      Status             : {data.get('status')}\n")

                # Persist assigned device_id, api_url, and auth_token into config.json
                cfg = load_config()
                cfg["device_id"] = assigned_id
                cfg["api_url"] = api_url
                if auth_token:
                    cfg["auth_token"] = auth_token
                save_config(cfg)
                logger.info("Saved device_id '%s', api_url, and auth_token to config.json", assigned_id)
                return assigned_id
            elif resp.status_code in (502, 503, 504):
                sleep_sec = min(base_delay * (2 ** (attempt - 1)), max_delay)
                print(Fore.YELLOW + f"  [*] Backend waking up ({resp.status_code}), retrying in {sleep_sec}s (attempt {attempt}/{max_attempts})...")
                time.sleep(sleep_sec)
                continue
            else:
                detail = resp.json().get("detail", resp.text) if "application/json" in resp.headers.get("content-type", "") else resp.text
                print(Fore.RED + f"\n  [-] Enrollment failed ({resp.status_code}): {detail}\n")
                return None
        except (requests.ConnectionError, requests.Timeout) as net_err:
            if attempt < max_attempts:
                sleep_sec = min(base_delay * (2 ** (attempt - 1)), max_delay)
                print(Fore.YELLOW + f"  [*] Connecting to backend failed ({net_err.__class__.__name__}), retrying in {sleep_sec}s (attempt {attempt}/{max_attempts})...")
                time.sleep(sleep_sec)
            else:
                print(Fore.RED + f"\n  [-] Connection failed after {max_attempts} attempts: {net_err}\n")
                return None
        except Exception as exc:
            print(Fore.RED + f"\n  ✗  Enrollment request error: {exc}\n")
            return None
    return None


def _redact_evidence(text: str, match_start: int, match_end: int) -> str:
    """
    Return a strictly redacted snippet:
    - Masked match placeholder [REDACTED]
    - At most a few characters (up to 4) of surrounding context
    - No surrounding file text, no partial secrets or raw values
    - Strictly capped at <= 30 characters
    """
    context_chars = 3
    prefix_start = max(0, match_start - context_chars)
    suffix_end = min(len(text), match_end + context_chars)
    prefix = text[prefix_start:match_start].strip().replace("\n", " ")
    suffix = text[match_end:suffix_end].strip().replace("\n", " ")
    # Keep only punctuation or short delimiter if any
    prefix = prefix[-2:] if len(prefix) > 2 else prefix
    suffix = suffix[:2] if len(suffix) > 2 else suffix
    res = f"{prefix}[REDACTED]{suffix}".strip()
    return res[:30]


def scan_file_for_findings(
    filepath: str,
    file_content: bytes,
    device_id: str,
) -> List[Dict[str, Any]]:
    """
    Run DLP rules locally on file_content.
    Returns list of finding dicts with redacted evidence — NO raw secrets.
    """
    sha256 = hashlib.sha256(file_content).hexdigest()
    basename = os.path.basename(filepath)
    text = extract_text(file_content, basename)
    if not text:
        return []

    results = []
    for rule in DLP_RULES:
        validator = rule.get("validator")
        for m in rule["pattern"].finditer(text):
            if validator and not validator(m.group(0)):
                continue
            redacted = _redact_evidence(text, m.start(), m.end())
            line_num = text[:m.start()].count("\n") + 1
            results.append({
                "file_name": basename,
                "file_path": filepath,
                "file_hash": sha256,
                "file_size": len(file_content),
                "rule_id": rule["name"],
                "category": rule["category"],
                "severity": rule["severity"],
                "confidence": 1.0,
                "line_number": line_num,
                "column_number": 0,
                "char_start": m.start(),
                "char_end": m.end(),
                "evidence_redacted": redacted,
                "description": f"{rule['name']} detected in {basename}",
                "remediation": "Review, sanitize, or move sensitive credentials.",
            })
    return results


def upload_findings(
    api_url: str,
    device_id: str,
    auth_token: Optional[str],
    findings: List[Dict[str, Any]],
    scanned_files_count: int,
    total_bytes: int,
) -> bool:
    """Upload redacted finding metadata to POST /api/devices/{device_id}/findings in manageable batches."""
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
    if not findings:
        try:
            payload = {
                "scanned_files_count": scanned_files_count,
                "total_bytes_scanned": total_bytes,
                "findings": [],
            }
            resp = requests.post(
                f"{api_url}/api/devices/{device_id}/findings",
                json=payload,
                headers=headers,
                timeout=30,
            )
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("Findings upload error: %s", exc)
            return False

    batch_size = 150
    success = True
    total_persisted = 0
    total_incidents = 0
    latest_score = None
    latest_level = None

    for i in range(0, len(findings), batch_size):
        chunk = findings[i : i + batch_size]
        is_first_chunk = (i == 0)
        chunk_success = False
        for attempt in range(1, 6):
            try:
                payload = {
                    "scanned_files_count": scanned_files_count if is_first_chunk else 0,
                    "total_bytes_scanned": total_bytes if is_first_chunk else 0,
                    "findings": chunk,
                }
                resp = requests.post(
                    f"{api_url}/api/devices/{device_id}/findings",
                    json=payload,
                    headers=headers,
                    timeout=45,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    total_persisted += data.get("persisted_findings_count", 0)
                    total_incidents += data.get("incidents_created_count", 0)
                    latest_score = data.get("risk_score")
                    latest_level = data.get("risk_level")
                    chunk_success = True
                    break
                elif resp.status_code in (502, 503, 504):
                    sleep_sec = min(3 * (2 ** (attempt - 1)), 60)
                    logger.warning("Backend waking up (%s), retrying findings upload in %ds...", resp.status_code, sleep_sec)
                    time.sleep(sleep_sec)
                else:
                    logger.warning("Findings batch upload failed (%s): %s", resp.status_code, resp.text[:200])
                    break
            except Exception as exc:
                sleep_sec = min(3 * (2 ** (attempt - 1)), 60)
                logger.warning("Findings batch upload error (%s), retrying in %ds...", exc, sleep_sec)
                time.sleep(sleep_sec)

        if not chunk_success:
            success = False

    if latest_score is not None:
        logger.info(
            "Uploaded %d findings in batches -> backend: %d persisted, %d incidents, risk=%s %s",
            len(findings), total_persisted, total_incidents, latest_score, latest_level
        )
    return success


def run_full_scan(cfg: Dict[str, Any], auth_token: Optional[str]) -> None:
    """
    Perform a full local DLP scan of watch_dirs.
    Uploads ONLY redacted finding metadata. Raw file bytes never leave this device.
    """
    device_id = cfg.get("device_id", "unknown")
    api_url = cfg["api_url"]
    watch_dirs = cfg.get("watch_dirs", [])
    excluded = set(cfg.get("excluded_extensions", []))
    max_mb = cfg.get("max_file_size_mb", 50)
    max_size = max_mb * 1024 * 1024

    IGNORED_DIRS = {
        ".git", "node_modules", ".venv", "venv", ".next", "__pycache__",
        "AppData", ".gemini", "dist", "build", "target", ".idea", ".vscode",
    }

    print(Fore.CYAN + Style.BRIGHT + f"\n  [*] Starting full DLP scan of {len(watch_dirs)} director{'ies' if len(watch_dirs) != 1 else 'y'}...")

    all_findings: List[Dict[str, Any]] = []
    scanned_count = 0
    total_bytes = 0

    for watch_dir in watch_dirs:
        if not os.path.isdir(watch_dir):
            continue
        for root, dirs, files in os.walk(watch_dir, topdown=True):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
            for fname in files:
                fpath = os.path.join(root, fname)
                ext = _ext(fname)
                if ext in excluded:
                    continue
                if fname.startswith(".") or fname.startswith("~"):
                    continue
                try:
                    size = os.path.getsize(fpath)
                    if size == 0 or size > max_size:
                        continue
                    with open(fpath, "rb") as fh:
                        content = fh.read()
                    findings = scan_file_for_findings(fpath, content, device_id)
                    scanned_count += 1
                    total_bytes += size
                    if findings:
                        all_findings.extend(findings)
                        sev = max((f["severity"] for f in findings),
                                  key=lambda s: {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(s, 0))
                        color = Fore.RED if sev == "CRITICAL" else (Fore.YELLOW if sev == "HIGH" else Fore.CYAN)
                        print(color + f"  [!] {fname}: {len(findings)} finding(s) [{sev}]")
                    else:
                        print(Fore.GREEN + f"  [OK] {fname}: clean")
                except (PermissionError, OSError) as e:
                    logger.debug("Skip %s: %s", fpath, e)

    print(Fore.CYAN + f"\n  Scan complete: {scanned_count} files, {len(all_findings)} findings")

    # Upload redacted findings to backend
    if all_findings or scanned_count > 0:
        upload_findings(api_url, device_id, auth_token, all_findings, scanned_count, total_bytes)

    global SCANNED_FILES_COUNT, INCIDENTS_COUNT
    with _COUNTERS_LOCK:
        SCANNED_FILES_COUNT += scanned_count
        INCIDENTS_COUNT += sum(1 for f in all_findings if f["severity"] in ("HIGH", "CRITICAL"))


def process_file_event(filepath: str, cfg: Dict[str, Any], auth_token: Optional[str]) -> None:
    """Handle a single file event: scan locally and upload redacted findings."""
    device_id = cfg.get("device_id", "unknown")
    api_url = cfg["api_url"]
    excluded = set(cfg.get("excluded_extensions", []))
    max_mb = cfg.get("max_file_size_mb", 50)
    max_size = max_mb * 1024 * 1024

    basename = os.path.basename(filepath)
    ext = _ext(basename)
    if ext in excluded or basename.startswith(".") or basename.startswith("~"):
        return

    try:
        size = os.path.getsize(filepath)
    except OSError:
        return

    if size == 0 or size > max_size:
        return

    time.sleep(0.5)  # brief wait in case file is still being written

    try:
        with open(filepath, "rb") as fh:
            content = fh.read()
    except (PermissionError, FileNotFoundError) as exc:
        logger.debug("Skipping %s: %s", filepath, exc)
        return

    findings = scan_file_for_findings(filepath, content, device_id)

    global SCANNED_FILES_COUNT, INCIDENTS_COUNT
    with _COUNTERS_LOCK:
        SCANNED_FILES_COUNT += 1
        if any(f["severity"] in ("HIGH", "CRITICAL") for f in findings):
            INCIDENTS_COUNT += 1

    if findings:
        sev = max(findings, key=lambda f: {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(f["severity"], 0))["severity"]
        if sev == "CRITICAL":
            print_critical_banner(basename, 90, sev)
        elif sev == "HIGH":
            print_high_warning(filepath, 70, findings)
        upload_findings(api_url, device_id, auth_token, findings, 1, size)
    else:
        risk = calculate_risk([], "PUBLIC", file_size_bytes=size)
        print_info(filepath, "PUBLIC", risk["score"], risk["severity"])


def start_heartbeat_loop(cfg: Dict[str, Any], auth_token: Optional[str]) -> None:
    """Background thread sending periodic heartbeats; triggers on-demand scans."""
    def _worker():
        api_url = cfg["api_url"]
        while True:
            try:
                device_id = cfg.get("device_id", "unknown")
                current_token = cfg.get("auth_token") or auth_token
                headers = {"Authorization": f"Bearer {current_token}"} if current_token else {}
                with _COUNTERS_LOCK:
                    scanned = SCANNED_FILES_COUNT
                    incidents = INCIDENTS_COUNT

                payload = {
                    "device_id": device_id,
                    "agent_version": "2.0.0",
                    "status": "ACTIVE",
                    "ip_address": socket.gethostbyname(socket.gethostname()),
                    "files_scanned": scanned,
                    "incidents_count": incidents,
                }
                resp = requests.post(
                    f"{api_url}/api/devices/{device_id}/heartbeat",
                    json=payload,
                    headers=headers,
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    logger.debug("Heartbeat OK for %s", device_id)
                    # Check if dashboard requested a scan
                    if data.get("scan_requested"):
                        logger.info("Dashboard requested scan -- starting full scan...")
                        print(Fore.CYAN + Style.BRIGHT + "\n  [*] On-demand scan requested by dashboard. Scanning now...")
                        run_full_scan(cfg, current_token)
                else:
                    logger.debug("Heartbeat returned %s", resp.status_code)
            except Exception as exc:
                logger.debug("Heartbeat error: %s", exc)
            time.sleep(25)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------
class DataGhostHandler(FileSystemEventHandler):
    def __init__(self, cfg: Dict[str, Any], auth_token: Optional[str]) -> None:
        super().__init__()
        self._cfg = cfg
        self._auth_token = auth_token

    def on_created(self, event):
        if not event.is_directory:
            process_file_event(event.src_path, self._cfg, self._auth_token)

    def on_modified(self, event):
        if not event.is_directory and self._cfg.get("scan_on_modify", True):
            process_file_event(event.src_path, self._cfg, self._auth_token)


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------
def print_startup_banner(watch_dirs: List[str]) -> None:
    print(Fore.CYAN + Style.BRIGHT + r"""
  ==============================================================
    ____        __        ________               __ 
   / __ \____ _/ /_____ _/ ____/ /_  ____  _____/ /_
  / / / / __ `/ __/ __ `/ / __/ __ \/ __ \/ ___/ __/
 / /_/ / /_/ / /_/ /_/ / /_/ / / / / /_/ (__  ) /_  
/_____/\__,_/\__/\__,_/\____/_/ /_/\____/____/\__/  
  ==============================================================
""")
    print(Fore.WHITE + Style.BRIGHT + "  DataGhost Agent v2.0.0 -- AI-Powered Data Leakage Detection")
    print(Fore.WHITE + "  Watching directories:")
    for d in watch_dirs:
        exists = os.path.isdir(d)
        status = (Fore.GREEN + "[OK]") if exists else (Fore.RED + "[MISSING]")
        print(f"    {status}{Fore.WHITE}  {d}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dataghost_agent",
        description="DataGhost Agent — monitors directories for sensitive data leakage.",
    )
    parser.add_argument(
        "--config",
        default=str(_CONFIG_PATH),
        help="Path to config.json (default: same directory as this script)",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Override api_url from config",
    )
    parser.add_argument(
        "--enroll",
        default=None,
        help="Enrollment code or token (e.g. DG-XXXX-XXXX) to onboard this device",
    )
    parser.add_argument(
        "--scan-now",
        action="store_true",
        help="Run a one-shot full scan immediately after startup then exit",
    )
    args = parser.parse_args()

    # Load config
    cfg = load_config()
    if args.api_url:
        cfg["api_url"] = args.api_url

    api_url = cfg["api_url"]

    # Handle enrollment flag if specified
    if args.enroll:
        print_startup_banner(cfg.get("watch_dirs", []))
        assigned_id = enroll_device(api_url, args.enroll.strip())
        if not assigned_id:
            sys.exit(1)
        # Reload updated config with assigned device_id and auth_token
        cfg = load_config()
        if args.api_url:
            cfg["api_url"] = args.api_url

    watch_dirs = cfg.get("watch_dirs", [])
    print_startup_banner(watch_dirs)

    # Use device auth_token if available, otherwise no token (unauthenticated local testing only)
    auth_token: Optional[str] = cfg.get("auth_token")
    if auth_token:
        print(Fore.GREEN + f"  [+] Using device auth token for backend communication")
    else:
        print(Fore.YELLOW + "  [!] No device auth_token in config -- run with --enroll first for secure mode")
    print()

    # Start heartbeat loop (checks scan_requested flag every ~25 seconds)
    start_heartbeat_loop(cfg, auth_token)

    if args.scan_now:
        run_full_scan(cfg, auth_token)
        return

    # Start watchdog observers
    handler  = DataGhostHandler(cfg, auth_token)
    observer = Observer()

    started_any = False
    for watch_dir in watch_dirs:
        if os.path.isdir(watch_dir):
            observer.schedule(handler, watch_dir, recursive=True)
            print(Fore.GREEN + f"  [+] Watching: {watch_dir}")
            started_any = True
        else:
            print(Fore.YELLOW + f"  [!] Skipping (not found): {watch_dir}")

    if not started_any:
        print(Fore.RED + "\n  [-] No valid watch directories found. Exiting.")
        sys.exit(1)

    observer.start()
    print(Fore.WHITE + Style.BRIGHT + f"\n  DataGhost Agent [{cfg.get('device_id', 'unknown')}] is active. Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(Fore.CYAN + "\n  Shutting down DataGhost Agent...")
        observer.stop()

    observer.join()
    print(Fore.CYAN + "  DataGhost Agent stopped.")


if __name__ == "__main__":
    main()
