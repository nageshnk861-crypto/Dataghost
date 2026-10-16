"""
DataGhost – File and Text Scanning Routes.
Exposes endpoints for DLP scanning, sensitive data masking, and risk calculation.
POST /scan       – accepts ScanRequest (JSON body), returns ScanResponse
POST /scan/text  – alias for /scan
POST /scan/file  – accepts multipart UploadFile, returns ScanResponse
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from auth import get_optional_current_user
from database import get_db
from models import Incident, ScanLog, Device, User, Finding as FindingModel
from schemas.schemas import ScanRequest, ScanResponse, ScanFinding, FindingSchema
from services.audit_service import log_audit_event
from scanner.text_extractor import extract_text
from scanner.dlp_scanner import scan_text as dlp_scan_text
from scanner.masking import mask_sensitive_text
from risk_engine.risk_calculator import RiskCalculator
from detectors.registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["scan"])

_risk_calc = RiskCalculator()

# Maximum allowed file size for /scan/file (50 MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Lazily loaded classifier
_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        import os
        from classifier.ml_classifier import DataGhostClassifier
        model_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "classifier", "model",
        )
        _classifier = DataGhostClassifier(model_dir=model_dir)
        if not _classifier.load():
            logger.info("Classifier model not found – training inline …")
            from classifier.train_classifier import train_and_save
            _classifier = train_and_save(model_dir)
    return _classifier


def _make_incident_id(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    count = db.query(Incident).count() + 1
    candidate = f"DG-{year}-{count:04d}"
    while db.query(Incident).filter(Incident.incident_id == candidate).first() is not None:
        count += 1
        candidate = f"DG-{year}-{count:04d}"
    return candidate


def _make_scan_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6].upper()
    return f"SCAN-{timestamp}-{rand_suffix}"


def _process_scan(
    content: bytes,
    filename: str,
    text: Optional[str] = None,
    classification_override: Optional[str] = None,
    destination: str = "LOCAL",
    action: str = "READ",
    file_size_override: Optional[int] = None,
    device_id: str = "unknown",
    user_label: str = "anonymous",
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
    organization_id: str = "default-org",
) -> ScanResponse:
    """Core scanning and risk calculation pipeline."""
    # 1. SHA-256 Hash
    file_hash = hashlib.sha256(content).hexdigest()
    effective_size = file_size_override if file_size_override is not None else len(content)

    # 2. Extract or decode text
    if text is None:
        text = extract_text(content, filename)

    # Fail-closed check: if file has bytes but text could not be extracted (binary, unsupported, corrupt)
    if len(content) > 0 and (not text or len(text.strip()) == 0):
        scan_id = _make_scan_id()
        if db is not None:
            try:
                scan_log = ScanLog(
                    scan_id=scan_id,
                    filename=filename,
                    file_hash=file_hash,
                    classification="INTERNAL",
                    risk_score=0,
                    findings_count=0,
                    device_id=device_id,
                    user_id=user_id,
                    organization_id=organization_id,
                    status="UNSUPPORTED",
                    file_size=effective_size,
                )
                db.add(scan_log)
                db.commit()
            except Exception as _log_err:
                logger.warning("Could not persist unsupported scan log: %s", _log_err)
                db.rollback()

        return ScanResponse(
            scan_id=scan_id,
            filename=filename,
            file_hash=file_hash,
            file_size=effective_size,
            bytes_inspected=0,
            scan_status="UNSUPPORTED",
            error=f"File '{filename}' contains binary or unsupported format where text could not be extracted.",
            is_simulated=False,
            findings=[],
            total_findings=0,
            classification="INTERNAL",
            confidence=1.0,
            risk_score=0,
            severity="LOW",
            recommended_action="REVIEW",
            action_taken="NOT_SCANNED",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    bytes_inspected = len(text.encode("utf-8", errors="replace"))

    # 3a. Phase-3 Secret Detection (new modular detectors)
    #     Run first so higher-confidence findings take precedence.
    masked_findings = []
    seen_offsets: set[int] = set()
    try:
        registry = get_registry()
        detector_findings = registry.scan(text or "", filename=filename)
        for df in detector_findings:
            masked_findings.append(
                ScanFinding(
                    rule=df.rule_name,
                    category=df.category,
                    severity=df.severity,
                    start=df.char_start,
                    end=df.char_end,
                    matched_text=df.evidence,  # already redacted by detector
                )
            )
            # Include legacy rule alias so older clients/tests looking for aws_access_key also succeed
            if df.rule_name == "aws_access_key_id":
                masked_findings.append(
                    ScanFinding(
                        rule="aws_access_key",
                        category=df.category,
                        severity=df.severity,
                        start=df.char_start,
                        end=df.char_end,
                        matched_text=df.evidence,
                    )
                )
            seen_offsets.add(df.char_start)
    except Exception as _det_exc:
        logger.warning("Detector registry error (non-fatal): %s", _det_exc)

    # 3b. Existing DLP Scan (preserves all legacy rules)
    scan_result = dlp_scan_text(text)
    raw_findings = scan_result["findings"]

    # Merge: skip DLP findings that overlap with a detector finding (same offset)
    for f in raw_findings:
        if f["start"] in seen_offsets:
            continue  # already covered by a higher-confidence detector finding
        masked_match = mask_sensitive_text(f["matched_text"], f["rule"])
        masked_findings.append(
            ScanFinding(
                rule=f["rule"],
                category=f["category"],
                severity=f["severity"],
                start=f["start"],
                end=f["end"],
                matched_text=masked_match,
            )
        )

    # 4. Classification determination
    classification = classification_override
    confidence = 1.0

    if not classification or classification.upper() not in {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}:
        try:
            clf = _get_classifier()
            clf_result = clf.predict(text or filename)
            classification = clf_result.get("label", "INTERNAL")
            confidence = float(clf_result.get("confidence", 0.95))
        except Exception as exc:
            logger.debug("Classifier fallback: %s", exc)
            classification = "INTERNAL"
            confidence = 1.0
    else:
        classification = classification.upper()

    # 5. Determine effective file size
    effective_size = file_size_override if file_size_override is not None else len(content)

    # 6. Risk score calculation
    risk_result = _risk_calc.calculate(
        findings=raw_findings,
        classification=classification,
        confidence=confidence,
        destination=destination,
        action=action,
        file_size_bytes=effective_size,
    )

    # 7. Database persistence (if DB session provided)
    scan_id = _make_scan_id()
    incident_id = None
    if db is not None:
        try:
            scan_log = ScanLog(
                scan_id=scan_id,
                filename=filename,
                file_hash=file_hash,
                classification=classification,
                risk_score=risk_result.risk_score,
                findings_count=len(masked_findings),
                device_id=device_id,
                user_id=user_id,
                organization_id=organization_id,
                status="COMPLETED",
                file_size=effective_size,
            )
            db.add(scan_log)
            db.flush()  # get scan_log.id

            device = db.query(Device).filter(Device.device_id == device_id).first()
            if device:
                device.files_scanned = (device.files_scanned or 0) + 1
                device.last_seen = datetime.now(timezone.utc)

            # ── Phase 5: Persist individual Finding records ──────────────
            for mf in masked_findings:
                # Build a finding fingerprint for deduplication
                fp_raw = f"{mf.rule}:{mf.matched_text}:{mf.start or 0}"
                fp = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()[:16]

                # Check for existing active finding with same fingerprint on this device/file
                existing_finding = (
                    db.query(FindingModel)
                    .filter(
                        FindingModel.fingerprint == fp,
                        FindingModel.device_id == device_id,
                        FindingModel.file_hash == file_hash,
                        FindingModel.status.in_(["OPEN", "ACKNOWLEDGED"]),
                    )
                    .first()
                )

                if existing_finding:
                    existing_finding.occurrence_count = (existing_finding.occurrence_count or 1) + 1
                    existing_finding.last_seen_at = datetime.now(timezone.utc)
                    existing_finding.scan_log_id = scan_log.id
                    existing_finding.scan_id = scan_id
                else:
                    new_finding = FindingModel(
                        scan_log_id=scan_log.id,
                        scan_id=scan_id,
                        user_id=user_id,
                        organization_id=organization_id,
                        device_id=device_id,
                        file_name=filename,
                        file_hash=file_hash,
                        detector_id=getattr(mf, 'detector_id', None),
                        rule_id=mf.rule,
                        category=mf.category,
                        severity=mf.severity,
                        confidence=1.0,
                        risk_score=risk_result.risk_score,
                        line_number=0,
                        column_number=0,
                        char_start=mf.start or 0,
                        char_end=mf.end or 0,
                        evidence_redacted=mf.matched_text,
                        remediation=None,
                        fingerprint=fp,
                        status="OPEN",
                    )
                    db.add(new_finding)

            # ── Persist Incident if risk >= 30 (MEDIUM, HIGH, CRITICAL) ──
            if risk_result.risk_score >= 30:
                findings_dump = [f.model_dump() for f in masked_findings]
                categories_list = sorted(list(set(f.category for f in masked_findings if f.category)))
                rules_list = sorted(list(set(f.rule for f in masked_findings if f.rule)))

                # Deduplication: avoid creating a new incident if this exact file
                # on this device already has an open/acknowledged incident.
                existing_incident = (
                    db.query(Incident)
                    .filter(
                        Incident.file_hash == file_hash,
                        Incident.device_id == device_id,
                        Incident.status.in_(["OPEN", "ACKNOWLEDGED"]),
                    )
                    .first()
                )

                if existing_incident:
                    # Update existing incident with fresh scan results
                    existing_incident.risk_score = risk_result.risk_score
                    existing_incident.severity = risk_result.severity
                    existing_incident.recommended_action = risk_result.recommended_action
                    existing_incident.action_taken = risk_result.action_taken
                    existing_incident.findings_json = json.dumps(findings_dump)
                    existing_incident.categories_json = json.dumps(categories_list)
                    existing_incident.triggered_rules_json = json.dumps(rules_list)
                    existing_incident.updated_at = datetime.now(timezone.utc)
                    incident_id = existing_incident.incident_id
                else:
                    # Create a new incident (first time this file is flagged on this device)
                    incident_id = _make_incident_id(db)
                    incident = Incident(
                        incident_id=incident_id,
                        user=user_label,
                        filename=filename,
                        file_hash=file_hash,
                        classification=classification,
                        confidence=confidence,
                        risk_score=risk_result.risk_score,
                        severity=risk_result.severity,
                        recommended_action=risk_result.recommended_action,
                        action_taken=risk_result.action_taken,
                        destination=destination.upper(),
                        action=action.upper(),
                        status="OPEN",
                        findings_json=json.dumps(findings_dump),
                        categories_json=json.dumps(categories_list),
                        triggered_rules_json=json.dumps(rules_list),
                        device_id=device_id,
                    )
                    db.add(incident)
                    if device:
                        device.incidents_count = (device.incidents_count or 0) + 1

                    # Audit: incident created
                    log_audit_event(
                        db, action="INCIDENT_CREATED", resource_type="INCIDENT",
                        actor_user_id=user_id, actor_username=user_label,
                        organization_id=organization_id, resource_id=incident_id,
                        metadata={"severity": risk_result.severity, "risk_score": risk_result.risk_score},
                    )

            # ── Audit: scan completed ────────────────────────────────────
            log_audit_event(
                db, action="SCAN_COMPLETED", resource_type="SCAN",
                actor_user_id=user_id, actor_username=user_label,
                organization_id=organization_id, resource_id=scan_id,
                metadata={
                    "filename": filename,
                    "findings_count": len(masked_findings),
                    "risk_score": risk_result.risk_score,
                    "classification": classification,
                },
            )

            db.commit()

            # Sync to Firebase Firestore
            try:
                from firebase_db import sync_incident_to_firestore, sync_scan_log_to_firestore
                sync_scan_log_to_firestore({
                    "filename": filename,
                    "file_hash": file_hash,
                    "classification": classification,
                    "risk_score": risk_result.risk_score,
                    "device_id": device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                if incident_id:
                    sync_incident_to_firestore({
                        "incident_id": incident_id,
                        "user": user_label,
                        "filename": filename,
                        "file_hash": file_hash,
                        "classification": classification,
                        "confidence": confidence,
                        "risk_score": risk_result.risk_score,
                        "severity": risk_result.severity,
                        "recommended_action": risk_result.recommended_action,
                        "action_taken": risk_result.action_taken,
                        "destination": destination.upper(),
                        "action": action.upper(),
                        "status": "OPEN",
                        "findings": [f.model_dump() for f in masked_findings],
                        "categories": sorted(list(set(f.category for f in masked_findings if f.category))),
                        "device_id": device_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as fb_sync_err:
                logger.debug("Firebase Firestore sync deferred: %s", fb_sync_err)
        except Exception as db_exc:
            logger.warning("Database persistence error: %s", db_exc)
            db.rollback()



    return ScanResponse(
        scan_id=scan_id,
        filename=filename,
        file_hash=file_hash,
        file_size=effective_size,
        bytes_inspected=bytes_inspected,
        scan_status="COMPLETED",
        error=None,
        is_simulated=False,
        findings=masked_findings,
        total_findings=len(masked_findings),
        classification=classification,
        confidence=confidence,
        risk_score=risk_result.risk_score,
        severity=risk_result.severity,
        recommended_action=risk_result.recommended_action,
        action_taken=risk_result.action_taken,
        incident_id=incident_id,
        breakdown=risk_result.breakdown,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )



# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/scan", response_model=ScanResponse, summary="Scan text payload")
@router.post("/scan/text", response_model=ScanResponse, summary="Scan text payload (alias)")
def scan_text_endpoint(
    payload: ScanRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Accepts text and metadata, evaluates DLP rules, calculates risk score,
    and returns structured scan findings with sensitive text masked.
    Uses authenticated user and verified device info when present.
    """
    if payload.text is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text field is required",
        )

    # Server-enforced identity
    if current_user:
        user_label = current_user.username
        user_id = current_user.id
        org_id = getattr(current_user, "organization_id", "default-org")
    else:
        user_label = payload.user or "anonymous"
        user_id = None
        org_id = "default-org"

    content = payload.text.encode("utf-8")
    effective_size = len(content)

    resolved_device_id = "web-console"
    if payload.device_id and payload.device_id not in ("unknown", "web-console"):
        dev = db.query(Device).filter(Device.device_id == payload.device_id).first()
        if dev:
            resolved_device_id = dev.device_id

    return _process_scan(
        content=content,
        filename=payload.filename or "example.txt",
        text=payload.text,
        classification_override=payload.classification,
        destination=payload.destination,
        action=payload.action,
        file_size_override=effective_size,
        device_id=resolved_device_id,
        user_label=user_label,
        db=db,
        user_id=user_id,
        organization_id=org_id,
    )


@router.post("/scan/file", response_model=ScanResponse, summary="Scan uploaded file")
async def scan_file_endpoint(
    file: UploadFile = File(..., description="File to scan"),
    classification: Optional[str] = Form(None, description="PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED"),
    destination: str = Form("LOCAL", description="LOCAL | INTERNAL | CLOUD | USB | EXTERNAL"),
    action: str = Form("READ", description="READ | COPY | SHARE | EMAIL | UPLOAD"),
    device_id: str = Form("unknown"),
    user: str = Form("anonymous"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Upload and scan a file. Supports TXT, PDF, DOCX, CSV, JSON, code files, etc.
    Validates file size (up to 50MB) and non-empty content.
    Enforces server-side identity and size calculations.
    """
    content = await file.read()

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file payload. Please provide a file containing content.",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum allowed limit (50MB).",
        )

    # Server-enforced identity
    if current_user:
        user_label = current_user.username
        user_id = current_user.id
        org_id = getattr(current_user, "organization_id", "default-org")
    else:
        user_label = user if user != "anonymous" else "anonymous"
        user_id = None
        org_id = "default-org"

    resolved_device_id = "web-console"
    if device_id and device_id not in ("unknown", "web-console"):
        dev = db.query(Device).filter(Device.device_id == device_id).first()
        if dev:
            resolved_device_id = dev.device_id

    filename = file.filename or "upload.bin"

    return _process_scan(
        content=content,
        filename=filename,
        classification_override=classification,
        destination=destination,
        action=action,
        file_size_override=len(content),
        device_id=resolved_device_id,
        user_label=user_label,
        db=db,
        user_id=user_id,
        organization_id=org_id,
    )
