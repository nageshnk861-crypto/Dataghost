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
from models import Incident, ScanLog, Device, User
from schemas.schemas import ScanRequest, ScanResponse, ScanFinding, Finding
from scanner.text_extractor import extract_text
from scanner.dlp_scanner import scan_text as dlp_scan_text
from scanner.masking import mask_sensitive_text
from risk_engine.risk_calculator import RiskCalculator

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
) -> ScanResponse:
    """Core scanning and risk calculation pipeline."""
    # 1. SHA-256 Hash
    file_hash = hashlib.sha256(content).hexdigest()

    # 2. Extract or decode text
    if text is None:
        text = extract_text(content, filename)

    # 3. DLP Scan
    scan_result = dlp_scan_text(text)
    raw_findings = scan_result["findings"]

    # Build masked ScanFinding list
    masked_findings = []
    for f in raw_findings:
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
    incident_id = None
    if db is not None:
        try:
            scan_log = ScanLog(
                filename=filename,
                file_hash=file_hash,
                classification=classification,
                risk_score=risk_result.risk_score,
                findings_count=len(masked_findings),
                device_id=device_id,
            )
            db.add(scan_log)

            device = db.query(Device).filter(Device.device_id == device_id).first()
            if device:
                device.files_scanned = (device.files_scanned or 0) + 1
                device.last_seen = datetime.utcnow()

            # Persist Incident if risk >= 30 (MEDIUM, HIGH, CRITICAL)
            if risk_result.risk_score >= 30:
                incident_id = _make_incident_id(db)
                findings_dump = [f.model_dump() for f in masked_findings]
                categories_list = sorted(list(set(f.category for f in masked_findings if f.category)))
                rules_list = sorted(list(set(f.rule for f in masked_findings if f.rule)))
                
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
                    "timestamp": datetime.utcnow().isoformat(),
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
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            except Exception as fb_sync_err:
                logger.debug("Firebase Firestore sync deferred: %s", fb_sync_err)
        except Exception as db_exc:
            logger.warning("Database persistence error: %s", db_exc)
            db.rollback()


    scan_id = _make_scan_id()

    return ScanResponse(
        scan_id=scan_id,
        filename=filename,
        file_hash=file_hash,
        file_size=effective_size,
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
        timestamp=datetime.utcnow().isoformat(),
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
    """
    if payload.text is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text field is required",
        )

    user_label = current_user.username if current_user else payload.user
    content = payload.text.encode("utf-8")
    effective_size = payload.file_size or payload.file_size_bytes or len(content)

    return _process_scan(
        content=content,
        filename=payload.filename or "example.txt",
        text=payload.text,
        classification_override=payload.classification,
        destination=payload.destination,
        action=payload.action,
        file_size_override=effective_size,
        device_id=payload.device_id,
        user_label=user_label,
        db=db,
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

    user_label = current_user.username if current_user else user
    filename = file.filename or "upload.bin"

    return _process_scan(
        content=content,
        filename=filename,
        classification_override=classification,
        destination=destination,
        action=action,
        file_size_override=len(content),
        device_id=device_id,
        user_label=user_label,
        db=db,
    )
