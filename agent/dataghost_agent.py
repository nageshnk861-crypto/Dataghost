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

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
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

    # Expand ~ in watch_dirs
    cfg["watch_dirs"] = [
        str(Path(d).expanduser().resolve()) for d in cfg.get("watch_dirs", [])
    ]
    return cfg



# ---------------------------------------------------------------------------
# Inline DLP rules (mirrors backend/scanner/dlp_rules.py)
# ---------------------------------------------------------------------------
def _c(pattern: str, flags: int = 0) -> re.Pattern:
    return re.compile(pattern, flags | re.MULTILINE)


DLP_RULES: List[Dict[str, Any]] = [
    {"name": "email_address",        "pattern": _c(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),              "severity": "MEDIUM",   "category": "PII"},
    {"name": "phone_india",          "pattern": _c(r"\b[6-9]\d{9}\b"),                                                  "severity": "MEDIUM",   "category": "PII"},
    {"name": "aadhaar",              "pattern": _c(r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b|\b[2-9]\d{3}-\d{4}-\d{4}\b"),       "severity": "HIGH",     "category": "PII"},
    {"name": "pan_card",             "pattern": _c(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                                      "severity": "HIGH",     "category": "PII"},
    {"name": "credit_card",          "pattern": _c(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"), "severity": "HIGH", "category": "FINANCIAL"},
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
        matches = list(rule["pattern"].finditer(text))
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
    print(Fore.RED + Style.BRIGHT + "╔══════════════════════════════════════╗")
    print(Fore.RED + Style.BRIGHT + "║  🚨 DATA EXFILTRATION DETECTED  🚨  ║")
    print(Fore.RED + Style.BRIGHT + "╠══════════════════════════════════════╣")
    print(Fore.RED + Style.BRIGHT + f"║  File: {fn} ║")
    print(Fore.RED + Style.BRIGHT + f"║  Risk: {rs}/100 {sv} ║")
    print(Fore.RED + Style.BRIGHT + "║  Action: BLOCKED                     ║")
    print(Fore.RED + Style.BRIGHT + "╚══════════════════════════════════════╝")


def print_high_warning(filepath: str, risk_score: int, findings: List[Dict[str, Any]]) -> None:
    cats = ", ".join({f["category"] for f in findings})
    print(Fore.YELLOW + Style.BRIGHT + f"⚠️  SENSITIVE DATA DETECTED")
    print(Fore.YELLOW + f"   File     : {filepath}")
    print(Fore.YELLOW + f"   Risk     : {risk_score}/100  [HIGH]")
    print(Fore.YELLOW + f"   Data     : {cats}")
    print(Fore.YELLOW + f"   Action   : ALERT")


def print_info(filepath: str, classification: str, risk_score: int, severity: str) -> None:
    color = Fore.GREEN if severity == "LOW" else Fore.CYAN
    print(color + f"✔  {os.path.basename(filepath)}  |  {classification}  |  Risk {risk_score}/100  [{severity}]")


# ---------------------------------------------------------------------------
# Backend client & enrollment
# ---------------------------------------------------------------------------
def enroll_device(api_url: str, enrollment_code_or_token: str) -> Optional[str]:
    """Enroll device with backend using an enrollment code or raw token."""
    try:
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
            "agent_version": "1.0.0",
        }
        resp = requests.post(
            f"{api_url}/api/devices/enrollment/register",
            json=payload,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            assigned_id = data.get("device_id")
            print(Fore.GREEN + Style.BRIGHT + "\n  ✔  Device Enrolled Successfully!")
            print(Fore.GREEN + f"      Assigned Device ID : {assigned_id}")
            print(Fore.GREEN + f"      Platform           : {data.get('platform')}")
            print(Fore.GREEN + f"      Status             : {data.get('status')}\n")

            # Persist assigned device_id into config.json
            cfg = load_config()
            cfg["device_id"] = assigned_id
            try:
                with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
                logger.info("Saved assigned device_id '%s' to config.json", assigned_id)
            except Exception as e:
                logger.warning("Could not save device_id to config.json: %s", e)
            return assigned_id
        else:
            detail = resp.json().get("detail", resp.text) if "application/json" in resp.headers.get("content-type", "") else resp.text
            print(Fore.RED + f"\n  ✗  Enrollment failed ({resp.status_code}): {detail}\n")
            return None
    except Exception as exc:
        print(Fore.RED + f"\n  ✗  Enrollment request error: {exc}\n")
        return None


def register_device(api_url: str, device_id: str, user: str, token: Optional[str]) -> None:
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        sys_plat = "Windows" if sys.platform == "win32" else ("macOS" if sys.platform == "darwin" else "Linux")
        payload = {
            "device_name": socket.gethostname(),
            "device_id": device_id,
            "ip_address": socket.gethostbyname(socket.gethostname()),
            "os_type": sys.platform,
            "platform": sys_plat,
            "os_name": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "agent_version": "1.0.0",
        }
        resp = requests.post(
            f"{api_url}/api/devices/register",
            json=payload,
            headers=headers,
            timeout=5,
        )
        if resp.status_code in (200, 201):
            logger.info("Device registered: %s", device_id)
        else:
            logger.warning("Device registration returned %s", resp.status_code)
    except Exception as exc:
        logger.warning("Could not register device: %s", exc)


def start_heartbeat_loop(cfg: Dict[str, Any], token: Optional[str]) -> None:
    """Start background thread sending periodic heartbeats to backend."""
    def _heartbeat_worker():
        api_url = cfg["api_url"]
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        while True:
            try:
                device_id = cfg.get("device_id", "agent-001")
                with _COUNTERS_LOCK:
                    scanned = SCANNED_FILES_COUNT
                    incidents = INCIDENTS_COUNT

                payload = {
                    "device_id": device_id,
                    "agent_version": "1.0.0",
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
                    logger.debug("Heartbeat acknowledged for %s", device_id)
                else:
                    logger.debug("Heartbeat returned status %s", resp.status_code)
            except Exception as exc:
                logger.debug("Heartbeat failed: %s", exc)

            time.sleep(25)

    t = threading.Thread(target=_heartbeat_worker, daemon=True)
    t.start()


def post_scan(
    api_url: str,
    token: Optional[str],
    filepath: str,
    file_content: bytes,
    destination: str,
    action: str,
    device_id: str,
    user: str,
) -> Optional[Dict[str, Any]]:
    """POST file to /api/scan/file and return the JSON response."""
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        files = {"file": (os.path.basename(filepath), io.BytesIO(file_content), "application/octet-stream")}
        data = {
            "destination": destination,
            "action": action,
            "device_id": device_id,
            "user": user,
        }
        resp = requests.post(
            f"{api_url}/api/scan/file",
            files=files,
            data=data,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Backend scan POST failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core scan logic (runs locally AND optionally sends to backend)
# ---------------------------------------------------------------------------
def process_file(filepath: str, cfg: Dict[str, Any], token: Optional[str]) -> None:
    api_url   = cfg["api_url"]
    device_id = cfg["device_id"]
    user      = cfg["user"]
    excluded  = set(cfg.get("excluded_extensions", []))
    max_mb    = cfg.get("max_file_size_mb", 50)

    # --- Skip checks --------------------------------------------------------
    basename = os.path.basename(filepath)
    ext = _ext(basename)

    if ext in excluded:
        return
    if basename.startswith(".") or basename.startswith("~"):
        return

    try:
        size = os.path.getsize(filepath)
    except OSError:
        return

    if size > max_mb * 1024 * 1024:
        logger.info("Skipping large file: %s (%d MB)", filepath, size // (1024 * 1024))
        return

    # Wait briefly — file may still be writing
    time.sleep(0.5)

    # --- Read file ----------------------------------------------------------
    try:
        with open(filepath, "rb") as fh:
            file_content = fh.read()
    except (PermissionError, FileNotFoundError) as exc:
        logger.debug("Skipping %s: %s", filepath, exc)
        return

    # --- Hash ---------------------------------------------------------------
    sha256 = hashlib.sha256(file_content).hexdigest()

    # --- Extract text -------------------------------------------------------
    text = extract_text(file_content, basename)

    # --- Scan ---------------------------------------------------------------
    findings = scan_text(text)

    # --- Classify (local keyword-based) ------------------------------------
    classification = classify_findings(findings)

    # --- Risk score ---------------------------------------------------------
    risk = calculate_risk(findings, classification, file_size_bytes=len(file_content))
    risk_score = risk["score"]
    severity   = risk["severity"]

    # --- Send to backend (best-effort) -------------------------------------
    backend_result = post_scan(api_url, token, filepath, file_content, "INTERNAL", "READ", device_id, user)
    if backend_result:
        # Prefer backend's authoritative score if available
        risk_score   = backend_result.get("risk_score", risk_score)
        severity     = backend_result.get("severity", severity)
        classification = backend_result.get("classification", classification)

    # --- Print output -------------------------------------------------------
    global SCANNED_FILES_COUNT, INCIDENTS_COUNT
    with _COUNTERS_LOCK:
        SCANNED_FILES_COUNT += 1
        if severity in ("HIGH", "CRITICAL"):
            INCIDENTS_COUNT += 1

    if severity == "CRITICAL":
        print_critical_banner(basename, risk_score, severity)
    elif severity == "HIGH":
        print_high_warning(filepath, risk_score, findings)
    else:
        print_info(filepath, classification, risk_score, severity)

    logger.info(
        "Scanned: %s | sha256=%s | class=%s | risk=%d | severity=%s",
        filepath, sha256[:12], classification, risk_score, severity,
    )


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------
class DataGhostHandler(FileSystemEventHandler):
    def __init__(self, cfg: Dict[str, Any], token: Optional[str]) -> None:
        super().__init__()
        self._cfg   = cfg
        self._token = token

    def on_created(self, event):
        if not event.is_directory:
            process_file(event.src_path, self._cfg, self._token)

    def on_modified(self, event):
        if not event.is_directory and self._cfg.get("scan_on_modify", True):
            process_file(event.src_path, self._cfg, self._token)


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------
def print_startup_banner(watch_dirs: List[str]) -> None:
    print(Fore.CYAN + Style.BRIGHT + """
  ██████╗  █████╗ ████████╗ █████╗  ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗
  ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝
  ██║  ██║███████║   ██║   ███████║██║  ███╗███████║██║   ██║███████╗   ██║
  ██║  ██║██╔══██║   ██║   ██╔══██║██║   ██║██╔══██║██║   ██║╚════██║   ██║
  ██████╔╝██║  ██║   ██║   ██║  ██║╚██████╔╝██║  ██║╚██████╔╝███████║   ██║
  ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝
""")
    print(Fore.WHITE + Style.BRIGHT + "  DataGhost Agent v1.0.0 — AI-Powered Data Leakage Detection")
    print(Fore.WHITE + "  Watching directories:")
    for d in watch_dirs:
        exists = os.path.isdir(d)
        status = Fore.GREEN + "✔" if exists else Fore.RED + "✗ (not found)"
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
    args = parser.parse_args()

    # Load config
    cfg = load_config()
    if args.api_url:
        cfg["api_url"] = args.api_url

    api_url = cfg["api_url"]

    # Handle enrollment flag if specified
    if args.enroll:
        print_startup_banner(cfg["watch_dirs"])
        assigned_id = enroll_device(api_url, args.enroll.strip())
        if not assigned_id:
            sys.exit(1)
        # Reload updated config with assigned device_id
        cfg = load_config()

    watch_dirs = cfg["watch_dirs"]
    print_startup_banner(watch_dirs)

    # Attempt to authenticate with backend for a JWT token
    token: Optional[str] = None
    dg_user = os.environ.get("DATAGHOST_USER", "admin")
    dg_pass = os.environ.get("DATAGHOST_PASS", "dataghost123")
    try:
        resp = requests.post(
            f"{api_url}/api/auth/login",
            json={"username": dg_user, "password": dg_pass},
            timeout=5,
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print(Fore.GREEN + f"  ✔  Authenticated with backend as '{dg_user}'")
        else:
            print(Fore.YELLOW + f"  ⚠  Backend auth failed ({resp.status_code}) — running in local-only mode")
    except Exception as exc:
        print(Fore.YELLOW + f"  ⚠  Backend unreachable ({exc}) — running in local-only mode")
    print()

    # Register device and start heartbeat loop
    register_device(api_url, cfg["device_id"], cfg["user"], token)
    start_heartbeat_loop(cfg, token)

    # Start observers
    handler  = DataGhostHandler(cfg, token)
    observer = Observer()

    started_any = False
    for watch_dir in watch_dirs:
        if os.path.isdir(watch_dir):
            observer.schedule(handler, watch_dir, recursive=True)
            print(Fore.GREEN + f"  ✔  Watching: {watch_dir}")
            started_any = True
        else:
            print(Fore.YELLOW + f"  ⚠  Skipping (not found): {watch_dir}")

    if not started_any:
        print(Fore.RED + "\n  ✗  No valid watch directories found. Exiting.")
        sys.exit(1)

    observer.start()
    print(Fore.WHITE + Style.BRIGHT + f"\n  DataGhost Agent [{cfg['device_id']}] is active. Press Ctrl+C to stop.\n")

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
