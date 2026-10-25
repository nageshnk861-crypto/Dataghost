"""
DataGhost – Multi-File Upload Routes (Phase 2).
POST /api/v1/upload          – accept 1-10 files, validate, and queue them for scanning.
GET  /api/v1/upload/{id}     – check status / retrieve result for a given scan_log_id.

Each uploaded file is validated for:
  - Allowed extensions (.txt, .csv, .json, .pdf, .docx, .xlsx, .log, .env, .py, .js,
    .ts, .yaml, .yml, .sql, .sh, .bash, .conf, .cfg, .ini, .toml, .zip, .tar, .gz)
  - Maximum file size (10 MB per file; 50 MB total)
  - Non-empty content
  - ZIP/TAR magic bytes when extension claims archive format
  - No path-traversal sequences in archive member names

Validated files are immediately scanned via _process_scan (same pipeline as /scan/file),
so results are returned synchronously in the same response.
"""
from __future__ import annotations

import io
import logging
import zipfile
import tarfile
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User
from api.scan_routes import _process_scan
from schemas.schemas import ScanResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

# ─── Limits ───────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024      # 10 MB per file
MAX_TOTAL_SIZE_BYTES = 50 * 1024 * 1024     # 50 MB total
MAX_FILES = 10
MAX_ARCHIVE_DEPTH = 3

ALLOWED_EXTENSIONS = {
    ".txt", ".csv", ".json", ".pdf", ".docx", ".xlsx",
    ".log", ".env", ".py", ".js", ".ts", ".yaml", ".yml",
    ".sql", ".sh", ".bash", ".conf", ".cfg", ".ini", ".toml",
    ".zip", ".tar", ".gz",
}

ARCHIVE_MAGIC = {
    ".zip": b"PK\x03\x04",
    ".tar": None,   # Checked via tarfile.is_tarfile
    ".gz":  b"\x1f\x8b",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ext(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _validate_extension(filename: str) -> None:
    ext = _ext(filename)
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}' for '{filename}'. "
                   f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )


def _validate_magic(content: bytes, filename: str) -> None:
    """Check that archives have the correct magic bytes."""
    ext = _ext(filename)
    magic = ARCHIVE_MAGIC.get(ext)
    if magic and not content.startswith(magic):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{filename}' has extension '{ext}' but its content does not match "
                   f"the expected file format. The file may be corrupted or mis-named.",
        )
    if ext == ".tar":
        try:
            if not tarfile.is_tarfile(io.BytesIO(content)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{filename}' is not a valid TAR archive.",
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{filename}' could not be opened as a TAR archive.",
            ) from e


def _check_path_traversal(member_path: str, filename: str) -> None:
    """Reject archive member paths that contain '..' or absolute path components."""
    parts = member_path.replace("\\", "/").split("/")
    if any(p == ".." for p in parts) or os.path.isabs(member_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path traversal attack detected in '{filename}': "
                   f"member '{member_path}' contains unsafe path component.",
        )


def _extract_archive_text(content: bytes, filename: str) -> str:
    """
    Extract text from ZIP or TAR/GZ archives, with:
      - path-traversal protection
      - depth limiting (MAX_ARCHIVE_DEPTH levels)
      - symlink skipping
    Returns a concatenated text string of all readable members.
    """
    ext = _ext(filename)
    lines: List[str] = []

    if ext == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for info in zf.infolist():
                    _check_path_traversal(info.filename, filename)
                    depth = info.filename.count("/")
                    if depth > MAX_ARCHIVE_DEPTH:
                        logger.debug("Skipping deep archive member: %s", info.filename)
                        continue
                    if info.is_dir():
                        continue
                    try:
                        member_bytes = zf.read(info.filename)
                        lines.append(f"=== {info.filename} ===")
                        lines.append(member_bytes.decode("utf-8", errors="replace"))
                    except Exception:
                        logger.debug("Skipping unreadable ZIP member: %s", info.filename)
        except zipfile.BadZipFile as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{filename}' is not a valid ZIP archive: {e}",
            ) from e

    elif ext in (".tar", ".gz"):
        try:
            mode = "r:gz" if ext == ".gz" else "r:*"
            with tarfile.open(fileobj=io.BytesIO(content), mode=mode) as tf:
                for member in tf.getmembers():
                    _check_path_traversal(member.name, filename)
                    depth = member.name.count("/")
                    if depth > MAX_ARCHIVE_DEPTH:
                        continue
                    if member.issym() or member.islnk():
                        logger.debug("Skipping symlink in archive: %s", member.name)
                        continue
                    if not member.isfile():
                        continue
                    try:
                        f_obj = tf.extractfile(member)
                        if f_obj:
                            member_bytes = f_obj.read()
                            lines.append(f"=== {member.name} ===")
                            lines.append(member_bytes.decode("utf-8", errors="replace"))
                    except Exception:
                        logger.debug("Skipping unreadable TAR member: %s", member.name)
        except tarfile.TarError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{filename}' is not a valid TAR/GZ archive: {e}",
            ) from e

    return "\n".join(lines)


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    summary="Multi-file upload and DLP scan",
    response_model=List[ScanResponse],
    status_code=status.HTTP_200_OK,
)
async def upload_and_scan(
    files: List[UploadFile] = File(..., description="1–10 files to scan"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ScanResponse]:
    """
    Accept 1–10 files, validate each, and run the full DLP scan pipeline.
    Archives (.zip, .tar.gz) are extracted and their contents concatenated for scanning.
    Returns an ordered list of ScanResponse objects (one per uploaded file).
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided. Please upload at least one file.",
        )
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum {MAX_FILES} files per request.",
        )

    results: List[ScanResponse] = []
    total_bytes = 0

    for upload in files:
        filename = upload.filename or "upload.bin"
        content = await upload.read()

        # Size checks
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{filename}' is empty. Please provide a non-empty file.",
            )
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"'{filename}' exceeds the 10 MB per-file limit "
                       f"({len(content) / (1024*1024):.1f} MB).",
            )
        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Total upload size exceeds the 50 MB limit.",
            )

        # Extension + magic validation
        _validate_extension(filename)
        ext = _ext(filename)
        if ext in ARCHIVE_MAGIC:
            _validate_magic(content, filename)

        # For archives: extract text; for regular files: pass raw bytes
        text_override: Optional[str] = None
        if ext in (".zip", ".tar", ".gz"):
            text_override = _extract_archive_text(content, filename)

        result = _process_scan(
            content=content,
            filename=filename,
            text=text_override,
            destination="EXTERNAL",
            action="UPLOAD",
            file_size_override=len(content),
            device_id="WEB-CONSOLE",
            user_label=current_user.username,
            db=db,
            user_id=current_user.id,
            organization_id="default-org",
        )
        results.append(result)

    return results
