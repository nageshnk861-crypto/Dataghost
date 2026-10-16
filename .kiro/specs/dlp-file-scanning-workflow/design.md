# Design Document: DataGhost DLP File Scanning Workflow

## Overview

This document provides the architectural and detailed design for the DataGhost DLP File Scanning Workflow, implementing 13 requirements across 7 phases plus cross-cutting concerns. The design specifies system architecture, authentication flows, file processing pipelines, detection engines, risk scoring algorithms, persistence layer, and audit infrastructure.

---

## 1. System Architecture

### 1.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
├─────────────────────────────────────────────────────────────────────┤
│  Landing Page │ Login │ Upload │ Dashboard │ Audit Logs (Admin)    │
│  AuthContext (Role, JWT Token, User ID)                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS / API Calls
┌────────────────────────────▼────────────────────────────────────────┐
│                  Backend (FastAPI - Python)                        │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│ │  Auth Routes    │  │ Upload Routes    │  │ Scan Routes      │   │
│ │  /auth/me       │  │ /upload          │  │ /detect          │   │
│ │  /login         │  │ /upload/status   │  │ /findings        │   │
│ │  /logout        │  │                  │  │ /findings/{id}   │   │
│ └─────────────────┘  └──────────────────┘  └──────────────────┘   │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐   │
│ │         Secret Detection & Risk Scoring Engine              │   │
│ ├─────────────────────────────────────────────────────────────┤   │
│ │  Detector Registry                                          │   │
│ │  ├─ API Key Detector        ├─ JWT Detector                │   │
│ │  ├─ Database URL Detector   ├─ Hardcoded IP Detector       │   │
│ │  ├─ Password Detector       ├─ Private Key Detector        │   │
│ │  └─ PII Detector                                           │   │
│ │                                                             │   │
│ │  Risk Calculator (Sensitivity × Exposure × Confidence / 100)  │   │
│ │  Severity Mapper (Low / Medium / High / Critical)          │   │
│ └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│ ┌──────────────────────┐  ┌──────────────────────┐               │
│ │   Audit Logger       │  │  File Lifecycle Mgr  │               │
│ │  (All actions)       │  │  (Upload→Extract→   │               │
│ │                      │  │   Process→Cleanup)  │               │
│ └──────────────────────┘  └──────────────────────┘               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│           Database (PostgreSQL / SQLite)                           │
├─────────────────────────────────────────────────────────────────────┤
│  Users │ Devices │ Incidents │ ScanLogs │ Findings │ AuditLogs     │
│                                                                     │
│  Indices: (user_id, created_at), (scan_log_id), (status)          │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Pipeline

```
User Upload
    │
    ▼
┌─────────────────────────┐
│  File Validation        │
│  ├─ Extension check     │
│  ├─ Size check (10MB)   │
│  └─ Format check        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  File Extraction        │
│  ├─ ZIP/TAR.GZ extract  │
│  ├─ Path-traversal chk  │
│  └─ In-memory storage   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Multi-Detector Scanning (Parallel)                             │
│  ├─ API Key Detector      ├─ JWT Detector                       │
│  ├─ Database URL Detector ├─ IP Detector                        │
│  ├─ Password Detector     ├─ Private Key Detector               │
│  └─ PII Detector                                                │
│                                                                 │
│  Output: List[Finding] with (file_path, line_num, category,    │
│           confidence_score, masked_preview)                     │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Risk Scoring                                                   │
│  For each Finding:                                              │
│    sensitivity ← type_sensitivity_table[finding.category]      │
│    exposure ← location_exposure_table[file_location]           │
│    risk_score ← (sensitivity × exposure × confidence) / 100    │
│    severity ← severity_map[risk_score]                         │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Persistence                                                    │
│  ├─ Create ScanLog record                                       │
│  ├─ Create Finding records with status="Open"                  │
│  └─ Create AuditLog record (Scan Completed)                    │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────┐
│  File Cleanup           │
│  ├─ Delete temp files   │
│  └─ Log deletion        │
└─────────────────────────┘
    │
    ▼
Frontend: Display Findings Dashboard
```

---

## 2. Authentication & Authorization (Phase 0, 10, 13)

### 2.1 AuthContext Architecture

**Client-side state management (`frontend/context/AuthContext.tsx`):**

```typescript
interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  role: "Admin" | "Analyst" | null;  // Phase 0: Persist role
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;  // Phase 0: Verify on reload
}

interface User {
  id: string;
  email: string;
  username: string;
  role: "Admin" | "Analyst";
}
```

**AuthContext Behavior:**

1. **Initial Load**: 
   - Load token from `localStorage` (if exists)
   - Call `GET /auth/me` to verify role and load user data
   - If 401: clear localStorage and redirect to login
   - If role mismatch: clear AuthContext and redirect to login
   - Set `loading=false` when complete

2. **Navigation**:
   - Retain role in memory without re-fetching (Phase 0 requirement)
   - Continue using cached role until reload

3. **Page Reload** (Phase 0):
   - Call `GET /auth/me` to verify role matches stored data
   - If mismatch or 401: clear AuthContext and redirect to login
   - If match: restore AuthContext with verified role

4. **Token Refresh**:
   - Refresh JWT token 5 minutes before expiration
   - If refresh fails: logout and redirect to login

### 2.2 JWT Token Structure

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "username": "username",
  "role": "Admin|Analyst",
  "exp": 1704067200,
  "iat": 1704063600,
  "token_type": "Bearer"
}
```

**Token Lifecycle:**
- Issued by `POST /auth/login` with 1-hour expiry (60 minutes)
- Validated on every protected endpoint
- Refreshed on inactivity timer reset
- Cleared on logout or session expiration

### 2.3 RBAC Matrix

| Action | Admin | Analyst | Viewer | Unauthenticated |
|--------|-------|---------|--------|-----------------|
| View own findings | ✓ | ✓ | ✗ | ✗ |
| View all findings | ✓ | ✗ | ✗ | ✗ |
| Update own finding status | ✓ | ✓ | ✗ | ✗ |
| Update any finding status | ✓ | ✗ | ✗ | ✗ |
| Upload file | ✓ | ✓ | ✗ | ✗ |
| View audit logs | ✓ | ✗ | ✗ | ✗ |
| Access dashboard | ✓ | ✓ | ✗ | ✗ |
| Access landing page | ✓ | ✓ | ✓ | ✓ |

### 2.4 Session Management (Phase 13)

**Inactivity Timeout: 1 hour (60 minutes)**

**Frontend Implementation:**

```typescript
// Session timeout logic
useEffect(() => {
  let inactivityTimer: NodeJS.Timeout;
  let warningTimer: NodeJS.Timeout;

  const resetTimeout = () => {
    clearTimeout(inactivityTimer);
    clearTimeout(warningTimer);

    // Show warning 5 minutes before expiration
    warningTimer = setTimeout(() => {
      showInactivityWarning();
    }, 55 * 60 * 1000);  // 55 minutes

    // Logout after 60 minutes inactivity
    inactivityTimer = setTimeout(() => {
      logout();
      redirect("/login?reason=session-expired");
    }, 60 * 60 * 1000);  // 60 minutes
  };

  // Reset timeout on user activity
  const events = ["mousedown", "keydown", "scroll", "touchstart"];
  events.forEach(event => {
    document.addEventListener(event, resetTimeout);
  });

  return () => {
    events.forEach(event => {
      document.removeEventListener(event, resetTimeout);
    });
    clearTimeout(inactivityTimer);
    clearTimeout(warningTimer);
  };
}, []);
```

**Backend Implementation:**

```python
# In FastAPI middleware or dependency
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError

def verify_token(token: str, settings: Settings) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        exp_timestamp = payload.get("exp")
        
        if not exp_timestamp:
            raise HTTPException(status_code=401, detail="Token missing expiration")
        
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        
        if current_time > exp_datetime:
            raise HTTPException(status_code=401, detail="Token expired")
        
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## 3. File Upload Pipeline (Phase 2)

### 3.1 Upload Component Flow

**Frontend Component (`frontend/components/FileUpload.tsx`):**

```typescript
interface UploadProps {
  onComplete: (scanLogId: string) => void;
  onError: (error: string) => void;
}

const ALLOWED_EXTENSIONS = [".zip", ".tar.gz", ".env", ".json", ".sql", ".py", ".js", ".yaml", ".yml", ".log", ".txt"];
const MAX_FILE_SIZE = 10 * 1024 * 1024;  // 10MB

const FileUpload: React.FC<UploadProps> = ({ onComplete, onError }) => {
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  const validateFile = (file: File): boolean => {
    // Check extension
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext) && !file.name.endsWith(".tar.gz")) {
      onError(`Unsupported file type: ${ext}`);
      return false;
    }

    // Check size
    if (file.size > MAX_FILE_SIZE) {
      onError(`File exceeds 10MB limit (${(file.size / 1024 / 1024).toFixed(2)}MB)`);
      return false;
    }

    return true;
  };

  const handleUpload = async (file: File) => {
    if (!validateFile(file)) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/v1/upload", {
        method: "POST",
        body: formData,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const { scan_log_id } = await response.json();
        onComplete(scan_log_id);
      } else {
        const error = await response.json();
        onError(error.detail || "Upload failed");
      }
    } catch (error) {
      onError(String(error));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-container">
      <input
        type="file"
        onChange={(e) => e.target.files && handleUpload(e.target.files[0])}
        disabled={uploading}
        accept={ALLOWED_EXTENSIONS.join(",")}
      />
      {uploading && <ProgressBar value={progress} />}
    </div>
  );
};
```

### 3.2 Upload Endpoint Implementation

**Backend Endpoint (`backend/api/upload_routes.py`):**

```python
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import ScanLog, User
from app.core.auth import get_current_user
import shutil
import zipfile
import tarfile
import os
from pathlib import Path
from datetime import datetime, timezone

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".zip", ".tar.gz", ".env", ".json", ".sql", ".py", ".js", ".yaml", ".yml", ".log", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_EXTRACTION_DEPTH = 3
TEMP_UPLOAD_DIR = "/tmp/dataghost_uploads"

@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a file or archive for scanning.
    Validates file type and size, extracts if ZIP/TAR.GZ.
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS and not file.filename.endswith(".tar.gz"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")

    # Read and validate file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit")

    try:
        # Create temporary directory for extraction
        upload_id = str(uuid.uuid4())
        temp_dir = Path(TEMP_UPLOAD_DIR) / upload_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Extract files
        extracted_files = await extract_archive(file, temp_dir, file.filename)

        # Validate no path traversal attacks
        for extracted_path in extracted_files:
            if ".." in extracted_path.parts:
                raise HTTPException(status_code=400, detail="Path traversal detected in archive")

        # Create ScanLog record
        scan_log = ScanLog(
            user_id=current_user.id,
            status="In Progress",
            file_count=len(extracted_files),
            created_at=datetime.now(timezone.utc),
            temp_dir=str(temp_dir),
        )
        db.add(scan_log)
        db.commit()
        db.refresh(scan_log)

        # Audit log: Upload Started
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Upload Started",
            target_resource="file",
            created_at=datetime.now(timezone.utc),
            details_json={"file_name": file.filename, "file_size": len(file_content)},
        )
        db.add(audit_log)
        db.commit()

        # Trigger detection in background task (optional) or sync
        await scan_files(scan_log.id, extracted_files, db, current_user.id)

        return {"scan_log_id": scan_log.id, "status": "Scanning"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")


async def extract_archive(file: UploadFile, temp_dir: Path, filename: str) -> list[Path]:
    """Extract ZIP or TAR.GZ archive, with path-traversal and depth protection."""
    extracted_files = []

    try:
        # Save uploaded file temporarily
        temp_file = temp_dir / filename
        with open(temp_file, "wb") as f:
            f.write(await file.read())

        if filename.endswith(".zip"):
            with zipfile.ZipFile(temp_file, "r") as zip_ref:
                for member in zip_ref.namelist():
                    # Skip directories and symbolic links
                    if member.endswith("/") or ".." in member:
                        continue
                    
                    # Extract with depth check
                    extract_path = temp_dir / member
                    if len(extract_path.relative_to(temp_dir).parts) > MAX_EXTRACTION_DEPTH:
                        continue
                    
                    extract_path.parent.mkdir(parents=True, exist_ok=True)
                    with zip_ref.open(member) as source, open(extract_path, "wb") as target:
                        target.write(source.read())
                    
                    extracted_files.append(extract_path)

        elif filename.endswith(".tar.gz"):
            with tarfile.open(temp_file, "r:gz") as tar_ref:
                for member in tar_ref.getmembers():
                    if member.issym() or member.isdir() or ".." in member.name:
                        continue
                    
                    if len(Path(member.name).parts) > MAX_EXTRACTION_DEPTH:
                        continue
                    
                    extract_path = temp_dir / member.name
                    extract_path.parent.mkdir(parents=True, exist_ok=True)
                    tar_ref.extract(member, path=temp_dir)
                    extracted_files.append(extract_path)

        # Delete uploaded temp file
        temp_file.unlink()
        return extracted_files

    except (zipfile.BadZipFile, tarfile.ReadError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid archive format: {str(e)}")


@router.get("/status/{scan_log_id}")
async def get_upload_status(
    scan_log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get status of an ongoing or completed scan."""
    scan_log = db.query(ScanLog).filter(ScanLog.id == scan_log_id).first()
    
    if not scan_log:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # RBAC: User can only view their own scans (unless Admin)
    if current_user.role != "Admin" and scan_log.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "scan_log_id": scan_log.id,
        "status": scan_log.status,
        "file_count": scan_log.file_count,
        "findings_count": db.query(Finding).filter(Finding.scan_log_id == scan_log_id).count(),
        "created_at": scan_log.created_at,
    }
```

---

## 4. Secret Detection Pipeline (Phase 3)

### 4.1 Detector Interface & Registry

**Abstract Base Detector (`backend/detection/base_detector.py`):**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
import re

@dataclass
class DetectionMatch:
    """Result of a detection attempt."""
    line_number: int
    column_start: int
    matched_text: str
    confidence_score: int  # 0-100

class BaseDetector(ABC):
    """Base class for all secret detectors."""
    
    def __init__(self, category: str):
        self.category = category
        self.patterns: List[re.Pattern] = []
    
    @abstractmethod
    def detect(self, file_content: str, file_path: str) -> List[DetectionMatch]:
        """Scan file content and return list of matches."""
        pass
    
    def mask_preview(self, text: str) -> str:
        """Mask sensitive text: show first 4 and last 4 chars, mask middle."""
        if len(text) <= 8:
            return "*" * len(text)
        return f"{text[:4]}{'*' * (len(text) - 8)}{text[-4:]}"
```

**Detector Registry (`backend/detection/detector_registry.py`):**

```python
from typing import Dict, Type, List
from backend.detection.base_detector import BaseDetector
from backend.detection.detectors import (
    APIKeyDetector, DatabaseURLDetector, PasswordDetector,
    PIIDetector, PrivateKeyDetector, JWTDetector, HardcodedIPDetector
)

class DetectorRegistry:
    """Central registry of all available detectors."""
    
    def __init__(self):
        self.detectors: Dict[str, BaseDetector] = {}
        self._register_default_detectors()
    
    def _register_default_detectors(self):
        """Register built-in detectors."""
        self.register("API Key", APIKeyDetector())
        self.register("Database URL", DatabaseURLDetector())
        self.register("Password", PasswordDetector())
        self.register("PII", PIIDetector())
        self.register("Private Key", PrivateKeyDetector())
        self.register("JWT", JWTDetector())
        self.register("Hardcoded IP", HardcodedIPDetector())
    
    def register(self, name: str, detector: BaseDetector):
        """Register a new detector."""
        self.detectors[name] = detector
    
    def get_detectors(self) -> Dict[str, BaseDetector]:
        """Get all registered detectors."""
        return self.detectors

# Global instance
detector_registry = DetectorRegistry()
```

### 4.2 Individual Detector Implementations

**API Key Detector (`backend/detection/detectors/api_key_detector.py`):**

```python
import re
from backend.detection.base_detector import BaseDetector, DetectionMatch

class APIKeyDetector(BaseDetector):
    def __init__(self):
        super().__init__("API Key")
        self.patterns = {
            "AWS": r"AKIA[0-9A-Z]{16}",
            "GitHub": r"ghp_[a-zA-Z0-9_]{36,255}",
            "Stripe": r"sk_live_[a-zA-Z0-9]{24,}",
            "Google": r"AIza[0-9A-Za-z\-_]{35}",
            "Azure": r"(?i)(defaultendpointsprotocol|accountname|accountkey)=",
            "OpenAI": r"sk-[a-zA-Z0-9]{48}",
        }
    
    def detect(self, file_content: str, file_path: str) -> list[DetectionMatch]:
        matches = []
        
        for line_num, line in enumerate(file_content.split("\n"), 1):
            for service, pattern in self.patterns.items():
                for match in re.finditer(pattern, line):
                    # High confidence for exact patterns like AKIA
                    confidence = 95 if service in ["AWS", "GitHub", "Stripe"] else 85
                    
                    matches.append(DetectionMatch(
                        line_number=line_num,
                        column_start=match.start(),
                        matched_text=match.group(),
                        confidence_score=confidence,
                    ))
        
        return matches
```

**Database URL Detector (`backend/detection/detectors/database_url_detector.py`):**

```python
import re
from backend.detection.base_detector import BaseDetector, DetectionMatch

class DatabaseURLDetector(BaseDetector):
    def __init__(self):
        super().__init__("Database URL")
        self.pattern = re.compile(
            r"(postgresql|mysql|mongodb|oracle|mssql)://[^\s]+",
            re.IGNORECASE
        )
    
    def detect(self, file_content: str, file_path: str) -> list[DetectionMatch]:
        matches = []
        
        for line_num, line in enumerate(file_content.split("\n"), 1):
            for match in self.pattern.finditer(line):
                matches.append(DetectionMatch(
                    line_number=line_num,
                    column_start=match.start(),
                    matched_text=match.group(),
                    confidence_score=90,  # High confidence for protocol match
                ))
        
        return matches
```

**Password Detector (`backend/detection/detectors/password_detector.py`):**

```python
import re
from backend.detection.base_detector import BaseDetector, DetectionMatch

class PasswordDetector(BaseDetector):
    def __init__(self):
        super().__init__("Password")
        self.patterns = {
            "password=": r'password\s*=\s*["\']?([a-zA-Z0-9!@#$%^&*_\-+=]{8,})["\']?',
            "pwd=": r'pwd\s*=\s*["\']?([a-zA-Z0-9!@#$%^&*_\-+=]{8,})["\']?',
            "secret=": r'secret\s*=\s*["\']?([a-zA-Z0-9!@#$%^&*_\-+=]{8,})["\']?',
            "passwd=": r'passwd\s*=\s*["\']?([a-zA-Z0-9!@#$%^&*_\-+=]{8,})["\']?',
            "pass=": r'pass\s*=\s*["\']?([a-zA-Z0-9!@#$%^&*_\-+=]{8,})["\']?',
        }
    
    def detect(self, file_content: str, file_path: str) -> list[DetectionMatch]:
        matches = []
        
        for line_num, line in enumerate(file_content.split("\n"), 1):
            for key_pattern, pattern in self.patterns.items():
                for match in re.finditer(pattern, line, re.IGNORECASE):
                    # Moderate confidence - could be false positive
                    matches.append(DetectionMatch(
                        line_number=line_num,
                        column_start=match.start(),
                        matched_text=match.group(),
                        confidence_score=75,
                    ))
        
        return matches
```

**PII Detector (`backend/detection/detectors/pii_detector.py`):**

```python
import re
from backend.detection.base_detector import BaseDetector, DetectionMatch

class PIIDetector(BaseDetector):
    def __init__(self):
        super().__init__("PII")
        self.patterns = {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "phone": r"(\+\d{1,3}[-.\s]?)?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}",
        }
    
    def detect(self, file_content: str, file_path: str) -> list[DetectionMatch]:
        matches = []
        
        for line_num, line in enumerate(file_content.split("\n"), 1):
            # Email detection
            for match in re.finditer(self.patterns["email"], line):
                matches.append(DetectionMatch(
                    line_number=line_num,
                    column_start=match.start(),
                    matched_text=match.group(),
                    confidence_score=85,
                ))
            
            # Phone detection
            for match in re.finditer(self.patterns["phone"], line):
                matches.append(DetectionMatch(
                    line_number=line_num,
                    column_start=match.start(),
                    matched_text=match.group(),
                    confidence_score=70,
                ))
        
        return matches
```

**Private Key Detector (`backend/detection/detectors/private_key_detector.py`):**

```python
import re
from backend.detection.base_detector import BaseDetector, DetectionMatch

class PrivateKeyDetector(BaseDetector):
    def __init__(self):
        super().__init__("Private Key")
        self.patterns = [
            r"-----BEGIN PRIVATE KEY-----",
            r"-----BEGIN RSA PRIVATE KEY-----",
            r"-----BEGIN DSA PRIVATE KEY-----",
            r"-----BEGIN EC PRIVATE KEY-----",
            r"-----BEGIN OPENSSH PRIVATE KEY-----",
        ]
    
    def detect(self, file_content: str, file_path: str) -> list[DetectionMatch]:
        matches = []
        
        for pattern in self.patterns:
            for line_num, line in enumerate(file_content.split("\n"), 1):
                if pattern in line:
                    matches.append(DetectionMatch(
                        line_number=line_num,
                        column_start=line.find(pattern),
                        matched_text=pattern,
                        confidence_score=98,  # Extremely high confidence
                    ))
        
        return matches
```

**JWT Detector (`backend/detection/detectors/jwt_detector.py`):**

```python
import re
from backend.detection.base_detector import BaseDetector, DetectionMatch

class JWTDetector(BaseDetector):
    def __init__(self):
        super().__init__("JWT")
        self.pattern = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_.-]*")
    
    def detect(self, file_content: str, file_path: str) -> list[DetectionMatch]:
        matches = []
        
        for line_num, line in enumerate(file_content.split("\n"), 1):
            for match in self.pattern.finditer(line):
                matches.append(DetectionMatch(
                    line_number=line_num,
                    column_start=match.start(),
                    matched_text=match.group(),
                    confidence_score=90,
                ))
        
        return matches
```

**Hardcoded IP Detector (`backend/detection/detectors/hardcoded_ip_detector.py`):**

```python
import re
from backend.detection.base_detector import BaseDetector, DetectionMatch

class HardcodedIPDetector(BaseDetector):
    def __init__(self):
        super().__init__("Hardcoded IP")
        # Match patterns like: ip=192.168.1.1, IP=10.0.0.1
        self.pattern = re.compile(
            r"(?i)(ip|ipaddress|host)\s*=\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
            re.IGNORECASE
        )
    
    def detect(self, file_content: str, file_path: str) -> list[DetectionMatch]:
        matches = []
        
        for line_num, line in enumerate(file_content.split("\n"), 1):
            for match in self.pattern.finditer(line):
                matches.append(DetectionMatch(
                    line_number=line_num,
                    column_start=match.start(),
                    matched_text=match.group(),
                    confidence_score=65,  # Moderate confidence
                ))
        
        return matches
```

### 4.3 Scan Execution

**Scanning Service (`backend/services/scan_service.py`):**

```python
from typing import List
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Finding, ScanLog, AuditLog, User
from backend.detection.detector_registry import detector_registry
from backend.risk_engine.risk_calculator import RiskCalculator
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class ScanService:
    def __init__(self, db: Session):
        self.db = db
        self.risk_calculator = RiskCalculator()
    
    async def scan_files(
        self,
        scan_log: ScanLog,
        extracted_files: List[Path],
        user_id: str
    ):
        """
        Scan extracted files for secrets, calculate risks, persist findings.
        """
        detectors = detector_registry.get_detectors()
        total_findings = 0
        
        try:
            for file_path in extracted_files:
                # Skip binary files
                if not self._is_text_file(file_path):
                    logger.warning(f"Skipping binary file: {file_path}")
                    continue
                
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}: {str(e)}")
                    continue
                
                # Run all detectors
                for detector_name, detector in detectors.items():
                    try:
                        matches = detector.detect(file_content, str(file_path))
                        
                        for match in matches:
                            # Calculate risk score
                            risk_score, severity = self.risk_calculator.calculate(
                                finding_type=detector_name,
                                file_path=str(file_path),
                                confidence=match.confidence_score,
                            )
                            
                            # Create Finding record
                            finding = Finding(
                                scan_log_id=scan_log.id,
                                file_path=str(file_path),
                                line_number=match.line_number,
                                category=detector_name,
                                confidence_score=match.confidence_score,
                                masked_preview=detector.mask_preview(match.matched_text),
                                risk_score=risk_score,
                                severity=severity,
                                status="Open",
                                created_at=datetime.now(timezone.utc),
                            )
                            self.db.add(finding)
                            total_findings += 1
                    
                    except Exception as e:
                        logger.error(f"Detector {detector_name} failed: {str(e)}")
                        continue
            
            # Update ScanLog
            scan_log.status = "Completed"
            scan_log.findings_count = total_findings
            self.db.commit()
            
            # Audit log: Scan Completed
            audit_log = AuditLog(
                user_id=user_id,
                action="Scan Completed",
                target_resource="scan_log",
                target_id=scan_log.id,
                created_at=datetime.now(timezone.utc),
                details_json={"scan_log_id": scan_log.id, "findings_count": total_findings},
            )
            self.db.add(audit_log)
            self.db.commit()
        
        except Exception as e:
            logger.error(f"Scan failed: {str(e)}")
            scan_log.status = "Failed"
            self.db.commit()
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely text (not binary)."""
        try:
            with open(file_path, "r", encoding="utf-8"):
                return True
        except UnicodeDecodeError:
            return False
```

---

## 5. Risk Scoring Algorithm (Phase 4)

### 5.1 Risk Calculator Implementation

**Risk Calculator (`backend/risk_engine/risk_calculator.py`):**

```python
from typing import Tuple

class RiskCalculator:
    """Calculate risk scores from sensitivity, exposure, and confidence."""
    
    # Sensitivity table: How sensitive is this type of secret
    SENSITIVITY_TABLE = {
        "Private Key": 100,
        "Database URL": 90,
        "API Key": 85,
        "Password": 80,
        "JWT": 70,
        "Hardcoded IP": 50,
        "PII": 40,
    }
    
    # Exposure table: How exposed is the file based on location
    EXPOSURE_TABLE = {
        ".env": 100,
        ".json": 100,  # Config files
        ".yaml": 100,
        ".yml": 100,
        ".config": 100,
        ".log": 60,
        ".txt": 60,
        ".py": 40,
        ".js": 40,
        ".sql": 40,
        ".ts": 40,
    }
    
    # Severity mapping: Risk Score → Severity
    SEVERITY_MAP = {
        (1, 20): "Low",
        (21, 50): "Medium",
        (51, 90): "High",
        (91, 125): "Critical",
    }
    
    def calculate(
        self,
        finding_type: str,
        file_path: str,
        confidence: int,
    ) -> Tuple[int, str]:
        """
        Calculate risk score using formula:
        Risk_Score = (Sensitivity × Exposure × Confidence) / 100
        
        Args:
            finding_type: Category of finding (e.g., "API Key")
            file_path: Path to the file
            confidence: Confidence score from detector (0-100)
        
        Returns:
            Tuple of (risk_score, severity)
        """
        # Get sensitivity
        sensitivity = self.SENSITIVITY_TABLE.get(finding_type, 50)
        
        # Get exposure from file extension
        exposure = self._get_exposure(file_path)
        
        # Calculate risk score
        risk_score = (sensitivity * exposure * confidence) // 100
        
        # Cap at 125
        risk_score = min(risk_score, 125)
        
        # Map to severity
        severity = self._map_severity(risk_score)
        
        return risk_score, severity
    
    def _get_exposure(self, file_path: str) -> int:
        """Get exposure value based on file extension."""
        for ext, exposure in self.EXPOSURE_TABLE.items():
            if file_path.lower().endswith(ext):
                return exposure
        
        # Default exposure for unknown file types
        return 40
    
    def _map_severity(self, risk_score: int) -> str:
        """Map risk score to severity level."""
        for (min_score, max_score), severity in self.SEVERITY_MAP.items():
            if min_score <= risk_score <= max_score:
                return severity
        return "Low"
```

**Risk Score Examples:**

```
Example 1: Private Key in .env file with 98% confidence
  sensitivity = 100
  exposure = 100
  confidence = 98
  risk_score = (100 × 100 × 98) / 100 = 9800 / 100 = 98
  severity = Critical (91-125)

Example 2: PII (email) in .py file with 85% confidence
  sensitivity = 40
  exposure = 40
  confidence = 85
  risk_score = (40 × 40 × 85) / 100 = 136000 / 100 = 1360 → capped at 125
  severity = Critical (91-125)

Example 3: Hardcoded IP in .log file with 65% confidence
  sensitivity = 50
  exposure = 60
  confidence = 65
  risk_score = (50 × 60 × 65) / 100 = 195000 / 100 = 1950 → capped at 125
  severity = Critical (91-125)

Example 4: PII (phone) in source code with 70% confidence
  sensitivity = 40
  exposure = 40
  confidence = 70
  risk_score = (40 × 40 × 70) / 100 = 112000 / 100 = 112
  severity = Critical (91-125)

Example 5: API Key in .log file with 85% confidence
  sensitivity = 85
  exposure = 60
  confidence = 85
  risk_score = (85 × 60 × 85) / 100 = 433500 / 100 = 4335 → capped at 125
  severity = Critical (91-125)
```

---

## 6. Database Schema (Phase 5, Cross-cutting)

### 6.1 Extended Models

**ScanLog Model:**

```python
# In backend/models.py or new backend/app/models/scan_log.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from datetime import datetime, timezone
from app.models.base import Base

class ScanLog(Base):
    """Record of a completed scan operation."""
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(32), default="In Progress")  # In Progress, Completed, Failed
    file_count = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    temp_dir = Column(String(255), nullable=True)  # Path to temporary extracted files
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Composite index for efficient queries
    __table_args__ = (
        Index("idx_scan_logs_user_created", "user_id", "created_at"),
    )
```

**Finding Model:**

```python
# In backend/models.py or new backend/app/models/finding.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Float
from datetime import datetime, timezone
from app.models.base import Base

class Finding(Base):
    """Detected instance of sensitive information."""
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    scan_log_id = Column(Integer, ForeignKey("scan_logs.id"), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    line_number = Column(Integer, nullable=False)
    category = Column(String(64), nullable=False, index=True)  # API Key, Password, etc.
    confidence_score = Column(Integer, nullable=False)  # 0-100
    masked_preview = Column(String(255), nullable=False)  # Never store full secret
    risk_score = Column(Integer, nullable=False, index=True)  # 1-125
    severity = Column(String(16), nullable=False, index=True)  # Low, Medium, High, Critical
    status = Column(String(32), default="Open", index=True)  # Open, In Review, Resolved, False Positive
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Composite indices
    __table_args__ = (
        Index("idx_findings_scan_log", "scan_log_id"),
        Index("idx_findings_status", "status"),
        Index("idx_findings_risk_score", "risk_score"),
    )
```

**AuditLog Model:**

```python
# In backend/models.py or new backend/app/models/audit_log.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Index
from datetime import datetime, timezone
from app.models.base import Base

class AuditLog(Base):
    """Record of system actions for compliance and investigation."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)  # Upload Started, Scan Completed, etc.
    target_resource = Column(String(64), nullable=False)  # file, scan_log, finding, etc.
    target_id = Column(String(64), nullable=True, index=True)  # ID of the resource being acted upon
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    details_json = Column(JSON, nullable=True)  # Additional context
    
    # Composite index for efficient filtering
    __table_args__ = (
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
        Index("idx_audit_logs_action", "action"),
    )
```

### 6.2 Database Indices

**Index Strategy:**

```sql
-- ScanLog indices
CREATE INDEX idx_scan_logs_user_created ON scan_logs(user_id, created_at DESC);
CREATE INDEX idx_scan_logs_status ON scan_logs(status);

-- Finding indices
CREATE INDEX idx_findings_scan_log ON findings(scan_log_id);
CREATE INDEX idx_findings_status ON findings(status);
CREATE INDEX idx_findings_risk_score ON findings(risk_score DESC);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_category ON findings(category);

-- AuditLog indices
CREATE INDEX idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_target ON audit_logs(target_resource, target_id);
```

---

## 7. API Endpoints

### 7.1 Phase 0: Authentication

**GET /auth/me**

```
Purpose: Verify user role on page reload (Phase 0 requirement)
Authorization: Bearer JWT token
Response:
{
  "id": "user_id",
  "email": "user@example.com",
  "username": "username",
  "role": "Admin|Analyst",
  "is_active": true
}

Status Codes:
  200 OK - User verified
  401 Unauthorized - Token missing or invalid (Frontend: clear AuthContext, redirect to login)
```

### 7.2 Phase 1: Landing Page

**GET /**

```
Purpose: Serve landing page (no auth required)
Response: HTML page with:
  - Headline explaining DataGhost
  - Feature descriptions
  - Sample dashboard screenshot
  - Sign In button → /login
  - Try Demo button → /demo
  - Responsive design
```

### 7.3 Phase 2: File Upload

**POST /upload**

```
Purpose: Upload file(s) for scanning
Authorization: Bearer JWT token
Content-Type: multipart/form-data

Request:
  file: (binary file, .zip/.tar.gz/.env/.json/.sql/.py/.js/.yaml/.yml/.log/.txt)

Response (200):
{
  "scan_log_id": "12345",
  "status": "Scanning"
}

Error Responses:
  400 Bad Request - Unsupported file type, exceeds 10MB, path traversal, etc.
  401 Unauthorized - Token invalid
  403 Forbidden - User not authorized to upload
  500 Internal Server Error - Processing failed
```

**GET /upload/status/{scan_log_id}**

```
Purpose: Check status of ongoing/completed scan
Authorization: Bearer JWT token

Response (200):
{
  "scan_log_id": "12345",
  "status": "In Progress|Completed|Failed",
  "file_count": 5,
  "findings_count": 12,
  "created_at": "2024-01-15T10:30:00Z"
}

Error Responses:
  404 Not Found - Scan doesn't exist
  403 Forbidden - User can't view other user's scan (unless Admin)
  401 Unauthorized - Token invalid
```

### 7.4 Phase 5-6: Findings Management

**GET /findings**

```
Purpose: List findings (with filtering)
Authorization: Bearer JWT token
Query Parameters:
  scan_log_id: (optional) Filter by scan
  status: (optional) Open|In Review|Resolved|False Positive
  severity: (optional) Low|Medium|High|Critical
  category: (optional) API Key|Password|etc.
  from_date: (optional) YYYY-MM-DD
  to_date: (optional) YYYY-MM-DD
  limit: (optional, default 50)
  offset: (optional, default 0)

Response (200):
{
  "total": 150,
  "limit": 50,
  "offset": 0,
  "findings": [
    {
      "id": "finding_1",
      "scan_log_id": "scan_123",
      "file_path": "config/.env",
      "line_number": 42,
      "category": "API Key",
      "confidence_score": 95,
      "masked_preview": "sk_l****************************live",
      "risk_score": 98,
      "severity": "Critical",
      "status": "Open",
      "created_at": "2024-01-15T10:35:00Z",
      "updated_at": "2024-01-15T10:35:00Z"
    },
    ...
  ]
}

Behavior:
  - Analyst: See only findings from their scans
  - Admin: See all findings
```

**PATCH /findings/{finding_id}/status**

```
Purpose: Update finding status
Authorization: Bearer JWT token
Request Body:
{
  "status": "Open|In Review|Resolved|False Positive"
}

Response (200):
{
  "id": "finding_1",
  "status": "In Review",
  "updated_at": "2024-01-15T11:00:00Z"
}

Error Responses:
  403 Forbidden - User doesn't own the finding (unless Admin)
  404 Not Found - Finding doesn't exist
  401 Unauthorized - Token invalid

Side Effect:
  - Create AuditLog record: "Status Changed", old_status → new_status
```

**GET /scans**

```
Purpose: List scan history
Authorization: Bearer JWT token
Query Parameters:
  limit: (optional, default 50)
  offset: (optional, default 0)

Response (200):
{
  "total": 25,
  "scans": [
    {
      "id": "scan_123",
      "user_id": "user_1",
      "status": "Completed",
      "file_count": 5,
      "findings_count": 12,
      "created_at": "2024-01-15T10:30:00Z",
      "findings_by_severity": {
        "Critical": 3,
        "High": 5,
        "Medium": 3,
        "Low": 1
      }
    },
    ...
  ]
}

Behavior:
  - Analyst: See only their scans
  - Admin: See all scans
```

### 7.5 Phase 7: Audit Logging

**GET /audit-logs**

```
Purpose: View audit logs (Admin only)
Authorization: Bearer JWT token
Query Parameters:
  user_id: (optional) Filter by user
  action: (optional) Upload Started|Scan Completed|etc.
  target_resource: (optional) file|scan_log|finding
  from_date: (optional) YYYY-MM-DD
  to_date: (optional) YYYY-MM-DD
  limit: (optional, default 50)
  offset: (optional, default 0)

Response (200):
{
  "total": 500,
  "audit_logs": [
    {
      "id": "audit_1",
      "user_id": "user_1",
      "action": "Scan Completed",
      "target_resource": "scan_log",
      "target_id": "scan_123",
      "created_at": "2024-01-15T10:35:00Z",
      "details": {
        "scan_log_id": "scan_123",
        "findings_count": 12
      }
    },
    ...
  ]
}

Error Responses:
  403 Forbidden - Non-Admin user
  401 Unauthorized - Token invalid
```

### 7.6 Cross-Cutting: Reports

**GET /reports/export-csv**

```
Purpose: Export findings as CSV
Authorization: Bearer JWT token
Query Parameters: Same as GET /findings

Response (200):
Content-Type: text/csv
Attachment: findings_{scan_log_id}_{date}.csv

CSV Columns:
  file_path, line_number, category, risk_score, severity, status, detected_at
```

**GET /reports/export-pdf**

```
Purpose: Export findings as PDF report
Authorization: Bearer JWT token
Query Parameters: Same as GET /findings

Response (200):
Content-Type: application/pdf
Attachment: findings_{scan_log_id}_{date}.pdf

PDF Contents:
  - Scan Summary (date, file count, findings count)
  - Findings Table (all findings with severity-based styling)
  - Generated timestamp
```

---

## 8. Frontend Components & Pages

### 8.1 Landing Page (/landing or /)

**Component: `frontend/pages/Landing.tsx`**

```typescript
export interface LandingProps {}

const Landing: React.FC<LandingProps> = () => {
  return (
    <div className="landing-container">
      {/* Header */}
      <header className="landing-header">
        <h1>DataGhost - Data Loss Prevention</h1>
        <p className="subtitle">Detect and manage sensitive information in your codebase</p>
      </header>

      {/* Features Section */}
      <section className="features">
        <div className="feature-card">
          <h3>🔍 Secret Detection</h3>
          <p>Automatically detect API keys, passwords, private keys, and PII</p>
        </div>
        <div className="feature-card">
          <h3>⚠️ Risk Scoring</h3>
          <p>Prioritize findings by risk level (Low, Medium, High, Critical)</p>
        </div>
        <div className="feature-card">
          <h3>📊 Audit Logs</h3>
          <p>Track all actions for compliance and security investigations</p>
        </div>
      </section>

      {/* Screenshot */}
      <section className="screenshot">
        <img src="/dashboard-screenshot.png" alt="DataGhost Dashboard" />
      </section>

      {/* CTA Section */}
      <section className="cta">
        <Link href="/login" className="btn btn-primary">
          Sign In
        </Link>
        <Link href="/demo" className="btn btn-secondary">
          Try Demo
        </Link>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <p>&copy; 2024 DataGhost. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default Landing;
```

### 8.2 Upload Page (/upload)

**Component: `frontend/pages/Upload.tsx`**

```typescript
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/router";
import FileUploadComponent from "@/components/FileUpload";

const UploadPage: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const [scanLogId, setScanLogId] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);

  if (!isAuthenticated) {
    router.push("/login");
    return null;
  }

  const handleUploadComplete = (id: string) => {
    setScanLogId(id);
    setIsScanning(true);
    // Poll status or redirect to findings
    setTimeout(() => {
      router.push(`/findings?scan=${id}`);
    }, 2000);
  };

  const handleUploadError = (error: string) => {
    alert(`Upload failed: ${error}`);
  };

  return (
    <div className="upload-page">
      <h1>Upload Files for Scanning</h1>
      <FileUploadComponent onComplete={handleUploadComplete} onError={handleUploadError} />
      {isScanning && <p>Scanning in progress...</p>}
    </div>
  );
};

export default UploadPage;
```

### 8.3 Findings Dashboard (/findings)

**Component: `frontend/pages/Findings.tsx`**

```typescript
import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import FindingsTable from "@/components/FindingsTable";
import FilterPanel from "@/components/FilterPanel";

interface Finding {
  id: string;
  file_path: string;
  line_number: number;
  category: string;
  risk_score: number;
  severity: "Low" | "Medium" | "High" | "Critical";
  status: "Open" | "In Review" | "Resolved" | "False Positive";
  masked_preview: string;
  created_at: string;
}

const FindingsPage: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [findings, setFindings] = useState<Finding[]>([]);
  const [filters, setFilters] = useState({
    severity: "",
    status: "Open",
    category: "",
    from_date: "",
    to_date: "",
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) return;

    const fetchFindings = async () => {
      const query = new URLSearchParams(filters).toString();
      const response = await fetch(`/api/v1/findings?${query}`);
      const data = await response.json();
      setFindings(data.findings);
      setLoading(false);
    };

    fetchFindings();
  }, [filters, isAuthenticated]);

  return (
    <div className="findings-page">
      <h1>Findings Dashboard</h1>
      <FilterPanel filters={filters} onFilterChange={setFilters} />
      {loading ? (
        <p>Loading findings...</p>
      ) : (
        <FindingsTable findings={findings} onStatusUpdate={(id, status) => {}} />
      )}
    </div>
  );
};

export default FindingsPage;
```

### 8.4 Audit Logs Page (/admin/audit-logs)

**Component: `frontend/pages/admin/AuditLogs.tsx`**

```typescript
import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/router";

interface AuditLog {
  id: string;
  user_id: string;
  action: string;
  target_resource: string;
  target_id: string;
  created_at: string;
  details: Record<string, any>;
}

const AuditLogsPage: React.FC = () => {
  const { isAuthenticated, role } = useAuth();
  const router = useRouter();
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [filters, setFilters] = useState({
    user_id: "",
    action: "",
    from_date: "",
    to_date: "",
  });

  useEffect(() => {
    if (!isAuthenticated || role !== "Admin") {
      router.push("/access-denied");
      return;
    }

    const fetchAuditLogs = async () => {
      const query = new URLSearchParams(filters).toString();
      const response = await fetch(`/api/v1/audit-logs?${query}`);
      const data = await response.json();
      setAuditLogs(data.audit_logs);
    };

    fetchAuditLogs();
  }, [filters, isAuthenticated, role, router]);

  return (
    <div className="audit-logs-page">
      <h1>Audit Logs</h1>
      {/* Filters and table */}
    </div>
  );
};

export default AuditLogsPage;
```

### 8.5 Navigation & Top Bar

**Component: `frontend/components/TopBar.tsx`**

```typescript
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";

const TopBar: React.FC = () => {
  const { isAuthenticated, user, role, logout } = useAuth();

  return (
    <nav className="top-bar">
      <div className="logo">
        <Link href="/">DataGhost</Link>
      </div>
      <div className="nav-links">
        {isAuthenticated && (
          <>
            <Link href="/findings">Findings</Link>
            <Link href="/scans">Scan History</Link>
            <Link href="/upload">Upload</Link>
            {role === "Admin" && <Link href="/admin/audit-logs">Audit Logs</Link>}
          </>
        )}
      </div>
      <div className="user-info">
        {isAuthenticated && (
          <>
            <span>{user?.email}</span>
            <span className="role-badge">{role}</span>
            <button onClick={logout}>Logout</button>
          </>
        )}
      </div>
    </nav>
  );
};

export default TopBar;
```

---

## 9. Error Handling & Recovery

### 9.1 Upload Error Handling

| Error Scenario | Status | Response | Frontend Action |
|---|---|---|---|
| Unsupported file extension | 400 | `{"detail": "Unsupported file type: .exe"}` | Show error, reject upload |
| File exceeds 10MB | 400 | `{"detail": "File exceeds 10MB limit"}` | Show error, reject upload |
| Path traversal in ZIP | 400 | `{"detail": "Path traversal detected"}` | Show error, reject upload |
| Invalid ZIP format | 400 | `{"detail": "Invalid archive format"}` | Show error, reject upload |
| Server disk full | 500 | `{"detail": "Insufficient disk space"}` | Show error, retry later |
| Authentication token expired | 401 | `{"detail": "Token expired"}` | Clear AuthContext, redirect to login |

### 9.2 Detection Engine Error Handling

**Strategy:**
- Skip unreadable files (log warning, continue scanning)
- Skip binary files (log warning, continue scanning)
- Detector crash: Catch exception, log error, continue with next detector
- Timeout (if any): Set 30-second limit per file, continue if exceeded

```python
try:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
except Exception as e:
    logger.warning(f"Skipping file {file_path}: {e}")
    continue

for detector_name, detector in detectors.items():
    try:
        matches = detector.detect(content, str(file_path))
        # Process matches
    except Exception as e:
        logger.error(f"Detector {detector_name} failed on {file_path}: {e}")
        continue
```

### 9.3 Authorization Error Handling

```
401 Unauthorized (Invalid token):
  Frontend: Clear AuthContext, redirect to /login?reason=unauthorized
  Log attempt in audit logs

403 Forbidden (Insufficient permissions):
  Frontend: Display error message "Access denied"
  Log attempt in audit logs
  Example: Analyst tries to access admin findings
```

### 9.4 Database Error Handling

```python
# Transient error (connection timeout)
from sqlalchemy.exc import OperationalError

try:
    db.commit()
except OperationalError:
    db.rollback()
    # Retry up to 3 times
    for attempt in range(3):
        try:
            db.commit()
            break
        except OperationalError:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)

# Persistent error
except Exception as e:
    db.rollback()
    logger.error(f"Database error: {e}")
    # Log to audit
    audit_log = AuditLog(
        user_id=current_user.id,
        action="Database Error",
        target_resource="system",
        details_json={"error": str(e)}
    )
    db.add(audit_log)
    db.commit()
    raise HTTPException(status_code=500, detail="Database error occurred")
```

---

## 10. Security Controls

### 10.1 File Validation

```python
# Extension whitelist
ALLOWED_EXTENSIONS = {".zip", ".tar.gz", ".env", ".json", ".sql", ".py", ".js", ".yaml", ".yml", ".log", ".txt"}

# Size limit
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Type checking (in addition to extension)
def is_text_file(file_path: Path) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8"):
            return True
    except UnicodeDecodeError:
        return False
```

### 10.2 ZIP/Archive Safety

```python
# Path traversal protection
for member in zip_file.namelist():
    if ".." in member:
        raise ValueError("Path traversal detected")
    
    # Prevent extraction outside target directory
    extract_path = (temp_dir / member).resolve()
    if not str(extract_path).startswith(str(temp_dir)):
        raise ValueError("Unsafe extraction path")

# Depth limit
MAX_EXTRACTION_DEPTH = 3
if len(Path(member).parts) > MAX_EXTRACTION_DEPTH:
    skip_member()

# Symbolic link prevention
if member.issym() or member.islnk():
    skip_member()
```

### 10.3 Secret Masking

```python
def mask_secret(secret: str) -> str:
    """
    Mask sensitive value: show first 4 and last 4 chars, mask middle.
    Never store complete secret in database.
    """
    if len(secret) <= 8:
        return "*" * len(secret)
    
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"

# Example:
# Full: sk_test_SAMPLEKEY123456789012345678
# Masked: sk_t****************************5678
```

### 10.4 RBAC Enforcement

**Every endpoint must check user role:**

```python
from fastapi import HTTPException, Depends

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Extract user from JWT token."""
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency for admin-only endpoints."""
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Usage:
@router.get("/audit-logs")
async def get_audit_logs(current_user: User = Depends(require_admin)):
    # Only admins reach here
    ...
```

### 10.5 Session Management

```python
# JWT token includes expiration
import datetime
from jose import jwt

token_data = {
    "sub": user.id,
    "role": user.role,
    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
}
token = jwt.encode(token_data, settings.secret_key, algorithm="HS256")

# On each request, verify token hasn't expired
def verify_token(token: str):
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    exp = payload.get("exp")
    if datetime.datetime.utcfromtimestamp(exp) < datetime.datetime.utcnow():
        raise HTTPException(status_code=401, detail="Token expired")
```

### 10.6 File Cleanup

```python
from pathlib import Path
import shutil
import asyncio
import datetime

# Cleanup after scan completes
async def scan_files(...):
    try:
        # ... scanning logic ...
        pass
    finally:
        # Always cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")

# Background job: Delete old temp files
async def cleanup_old_files():
    """Delete temp files older than 48 hours."""
    temp_root = Path(TEMP_UPLOAD_DIR)
    now = datetime.datetime.now()
    
    for temp_dir in temp_root.iterdir():
        if temp_dir.is_dir():
            mtime = datetime.datetime.fromtimestamp(temp_dir.stat().st_mtime)
            age = now - mtime
            
            if age > datetime.timedelta(hours=48):
                shutil.rmtree(temp_dir)
                logger.info(f"Auto-cleaned old temp directory: {temp_dir}")
                
                # Audit log
                audit_log = AuditLog(
                    user_id=None,  # System action
                    action="File Cleanup",
                    target_resource="file",
                    details_json={"path": str(temp_dir), "age_hours": age.total_seconds() / 3600}
                )
                db.add(audit_log)
    
    db.commit()

# Schedule every hour
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(cleanup_old_files, "interval", hours=1)
scheduler.start()
```

### 10.7 Audit Logging

```python
# Log all significant actions
class AuditAction:
    UPLOAD_STARTED = "Upload Started"
    SCAN_COMPLETED = "Scan Completed"
    FINDING_VIEWED = "Finding Viewed"
    STATUS_CHANGED = "Status Changed"
    AUDIT_LOG_VIEWED = "Audit Log Viewed"
    FILE_CLEANUP = "File Cleanup"

async def log_action(
    user_id: str,
    action: str,
    target_resource: str,
    target_id: str = None,
    details: dict = None
):
    """Create audit log entry."""
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        target_resource=target_resource,
        target_id=target_id,
        created_at=datetime.now(timezone.utc),
        details_json=details or {}
    )
    db.add(audit_log)
    db.commit()
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

**Detector Tests (`backend/tests/test_detectors.py`):**

```python
import pytest
from backend.detection.detectors import APIKeyDetector, PasswordDetector, PIIDetector

class TestAPIKeyDetector:
    def test_detect_aws_key(self):
        detector = APIKeyDetector()
        content = "export AWS_KEY=AKIAIOSFODNN7EXAMPLE"
        matches = detector.detect(content, "config.env")
        assert len(matches) == 1
        assert matches[0].confidence_score >= 90
    
    def test_detect_github_key(self):
        detector = APIKeyDetector()
        content = "github_token=ghp_1234567890abcdef1234567890abcdef1234"
        matches = detector.detect(content, "secrets.txt")
        assert len(matches) == 1
    
    def test_no_false_positive(self):
        detector = APIKeyDetector()
        content = "# This is a comment about API keys"
        matches = detector.detect(content, "README.md")
        assert len(matches) == 0

class TestPasswordDetector:
    def test_detect_password_assignment(self):
        detector = PasswordDetector()
        content = 'password = "MySecurePassword123!"'
        matches = detector.detect(content, "config.py")
        assert len(matches) == 1

class TestPIIDetector:
    def test_detect_email(self):
        detector = PIIDetector()
        content = "contact: john@example.com for support"
        matches = detector.detect(content, "README.md")
        assert len(matches) == 1
        assert matches[0].confidence_score >= 80
    
    def test_detect_phone(self):
        detector = PIIDetector()
        content = "Call us at +1-555-123-4567"
        matches = detector.detect(content, "contact.txt")
        assert len(matches) == 1
```

**Risk Calculator Tests (`backend/tests/test_risk_calculator.py`):**

```python
import pytest
from backend.risk_engine.risk_calculator import RiskCalculator

class TestRiskCalculator:
    def test_private_key_in_env_file(self):
        calc = RiskCalculator()
        risk_score, severity = calc.calculate(
            finding_type="Private Key",
            file_path=".env",
            confidence=98
        )
        # (100 * 100 * 98) / 100 = 9800 / 100 = 98
        assert risk_score == 98
        assert severity == "Critical"
    
    def test_pii_in_source_code(self):
        calc = RiskCalculator()
        risk_score, severity = calc.calculate(
            finding_type="PII",
            file_path="main.py",
            confidence=85
        )
        # (40 * 40 * 85) / 100 = 1360 / 100 = 13.6 → 13
        assert risk_score == 13
        assert severity == "Low"
    
    def test_risk_score_capped_at_125(self):
        calc = RiskCalculator()
        risk_score, severity = calc.calculate(
            finding_type="API Key",
            file_path=".env",
            confidence=100
        )
        # (85 * 100 * 100) / 100 = 85, not capped
        # But let's test with high values
        assert risk_score <= 125
```

### 11.2 Integration Tests

**Upload Flow (`backend/tests/test_upload_flow.py`):**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from sqlalchemy.orm import Session

client = TestClient(app)

@pytest.fixture
def auth_token(db: Session):
    """Create a test user and return auth token."""
    # Create test user
    # Generate and return JWT token
    ...

def test_upload_scan_find_persist(auth_token: str):
    """End-to-end: Upload → Detect → Persist → Retrieve"""
    
    # Step 1: Upload file
    with open("test_files/secrets.env", "rb") as f:
        response = client.post(
            "/api/v1/upload",
            files={"file": f},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    assert response.status_code == 200
    scan_log_id = response.json()["scan_log_id"]
    
    # Step 2: Wait for scanning to complete
    import time
    time.sleep(2)
    
    # Step 3: Retrieve findings
    response = client.get(
        f"/api/v1/findings?scan_log_id={scan_log_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    findings = response.json()["findings"]
    assert len(findings) > 0
    assert findings[0]["severity"] in ["Low", "Medium", "High", "Critical"]
    assert findings[0]["masked_preview"] != ""  # Should be masked
```

**RBAC Tests (`backend/tests/test_rbac.py`):**

```python
def test_analyst_cannot_view_other_user_findings(analyst1_token, analyst2_token):
    """Analyst can only view their own findings."""
    
    # Analyst 1 uploads file
    response = client.post(
        "/api/v1/upload",
        files={"file": test_file},
        headers={"Authorization": f"Bearer {analyst1_token}"}
    )
    scan_log_id = response.json()["scan_log_id"]
    
    # Wait for scan
    time.sleep(2)
    
    # Analyst 2 tries to view Analyst 1's findings
    response = client.get(
        f"/api/v1/findings?scan_log_id={scan_log_id}",
        headers={"Authorization": f"Bearer {analyst2_token}"}
    )
    
    # Should be forbidden
    assert response.status_code == 403

def test_admin_can_view_all_findings(admin_token, analyst_token):
    """Admin can view findings from any user."""
    
    # Analyst uploads file
    response = client.post(
        "/api/v1/upload",
        files={"file": test_file},
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    scan_log_id = response.json()["scan_log_id"]
    
    # Admin can view
    response = client.get(
        f"/api/v1/findings?scan_log_id={scan_log_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
```

### 11.3 Security Tests

**Path Traversal (`backend/tests/test_security.py`):**

```python
def test_path_traversal_rejection(auth_token):
    """ZIP with .. in path should be rejected."""
    
    # Create malicious ZIP
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("../../../etc/passwd", "sensitive data")
    zip_buffer.seek(0)
    
    response = client.post(
        "/api/v1/upload",
        files={"file": ("malicious.zip", zip_buffer)},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "Path traversal" in response.json()["detail"]

def test_oversized_file_rejection(auth_token):
    """File > 10MB should be rejected."""
    
    # Create 11MB file
    large_file = io.BytesIO(b"x" * (11 * 1024 * 1024))
    
    response = client.post(
        "/api/v1/upload",
        files={"file": ("large.txt", large_file)},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "exceeds 10MB" in response.json()["detail"]

def test_invalid_token_rejection():
    """Invalid token should return 401."""
    
    response = client.get(
        "/api/v1/findings",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401
```

### 11.4 E2E Tests (Frontend + Backend)

```typescript
// frontend/tests/e2e.test.ts
import { test, expect } from "@playwright/test";

test.describe("DLP File Scanning Workflow", () => {
  test("login → upload → view findings → update status", async ({ page }) => {
    // Navigate to login
    await page.goto("http://localhost:3000/login");
    
    // Login
    await page.fill("input[name=email]", "analyst@example.com");
    await page.fill("input[name=password]", "password123");
    await page.click("button:has-text('Login')");
    
    // Wait for redirect to dashboard
    await page.waitForURL("**/upload");
    
    // Upload file
    await page.setInputFiles("input[type=file]", "test_files/secrets.env");
    await page.click("button:has-text('Upload')");
    
    // Wait for findings to load
    await page.waitForURL("**/findings");
    
    // Verify findings displayed
    const findingsTable = await page.locator("table");
    await expect(findingsTable).toContainText("API Key");
    
    // Update status
    await page.locator("select").first().selectOption("In Review");
    await page.click("button:has-text('Save')");
    
    // Verify status updated
    await expect(page.locator("table")).toContainText("In Review");
  });
});
```

---

## 12. Correctness Properties

A property is a formal statement about what the system should do—a characteristic that should hold true across all valid executions. Properties serve as specifications for automated testing, especially property-based testing.

### Property 1: File Masking Invariant

**For any** detected secret in a Finding record, the masked_preview SHALL contain only the first 4 and last 4 characters of the secret, with all middle characters replaced by asterisks.

**Validates: Requirements 3.20, 12.1, 12.3**

### Property 2: Risk Score Formula Accuracy

**For any** Finding with sensitivity S, exposure E, and confidence C, the risk_score SHALL equal (S × E × C) / 100, capped at 125.

**Validates: Requirements 5.1, 5.5**

### Property 3: Severity Mapping Consistency

**For any** risk_score value R, the mapped severity SHALL be:
- Low if 1 ≤ R ≤ 20
- Medium if 21 ≤ R ≤ 50
- High if 51 ≤ R ≤ 90
- Critical if 91 ≤ R ≤ 125

**Validates: Requirements 5.5**

### Property 4: Role Persistence Across Navigation

**For any** authenticated user navigating between pages, the AuthContext role SHALL remain unchanged until the next page reload, at which point GET /auth/me SHALL verify the role matches the backend record.

**Validates: Requirements 1.2, 1.3**

### Property 5: RBAC Enforcement on Findings Access

**For any** Analyst user attempting to access findings from a scan not initiated by them, the Backend SHALL return a 403 Forbidden response.

**Validates: Requirements 6.3, 7.5, 10.5**

### Property 6: Path Traversal Protection

**For any** ZIP archive containing a member with ".." in its path, the extraction SHALL fail and return a 400 Bad Request error.

**Validates: Requirements 3.6**

### Property 7: Session Expiration on Inactivity

**For any** authenticated session that remains inactive for 60 minutes, the next API request SHALL return a 401 Unauthorized response, requiring the user to re-authenticate.

**Validates: Requirements 13.1, 13.3**

### Property 8: Audit Log Completeness

**For any** significant system action (Upload, Scan Completed, Status Changed, File Cleanup), an AuditLog record SHALL be created with user_id, action, target_resource, timestamp, and details.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 11.5**

### Property 9: Detector Pattern Accuracy

**For any** file containing a secret matching a detector's pattern, the detector SHALL identify it with a confidence_score between 40 and 100.

**Validates: Requirements 4.21, 4.22, 4.23, 4.24**

### Property 10: Finding Status Lifecycle

**For any** Finding created in the system, the initial status SHALL be "Open", and status transitions SHALL only occur via authorized PATCH requests that create corresponding AuditLog records.

**Validates: Requirements 7.1, 7.3, 7.5**

---

## 13. Configuration & Deployment

### 13.1 Environment Variables

```env
# Backend (.env)
APP_ENV=production
SECRET_KEY=<generate-strong-key>
DATABASE_URL=postgresql://user:pass@host:5432/dataghost
ACCESS_TOKEN_EXPIRE_MINUTES=60
TEMP_UPLOAD_DIR=/var/tmp/dataghost_uploads
MAX_FILE_SIZE_MB=10
CORS_ORIGINS=https://frontend.example.com

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=https://api.example.com/api/v1
NEXT_PUBLIC_SESSION_TIMEOUT_MINUTES=60
```

### 13.2 Database Migrations

```python
# Using Alembic
# Step 1: Create new migration
# alembic revision --autogenerate -m "Add ScanLog, Finding, AuditLog models"

# Step 2: Review and update migration file
# Step 3: Apply migration
# alembic upgrade head
```

---

## 14. Monitoring & Observability

### 14.1 Key Metrics

- Upload success/failure rate
- Average scan time per file
- Detection accuracy (findings per scan)
- Finding status distribution (Open, Resolved, etc.)
- Audit log volume
- Session timeout rate
- API response times

### 14.2 Logging

```python
import logging

logger = logging.getLogger(__name__)

# Log levels
logger.debug("Detailed diagnostic info")
logger.info("General informational messages")
logger.warning("Warning about potential issues")
logger.error("Error that prevented operation completion")
logger.critical("Critical error requiring immediate attention")
```

---

## 15. Constraints & Assumptions

### Constraints

1. **File Size**: Maximum 10MB per upload
2. **Extraction Depth**: Maximum 3 levels deep for nested archives
3. **Session Timeout**: 1 hour inactivity (hard limit)
4. **Risk Score**: Capped at 125
5. **Concurrent Users**: Minimum 10 simultaneous uploads

### Assumptions

1. **Database**: PostgreSQL in production, SQLite in development
2. **File Storage**: Local filesystem during processing (not cloud storage)
3. **Authentication**: JWT-based with no refresh token rotation initially
4. **Secret Completeness**: Detectors should catch 90%+ of target secrets (in real implementation, this would vary)
5. **User Cooperation**: Users won't intentionally upload malicious archives

---

## 16. Future Enhancements (Out of Scope)

- Machine Learning-based entropy detection
- Custom regex rules builder
- Allowlisting/whitelisting of false positives
- Cloud storage integration (S3, GCS, Azure Blob)
- Real-time file monitoring agents
- Bulk operations on findings
- Scheduled automated scans
- Third-party API integrations
- Advanced reporting (trends, metrics)
- Finding correlation across scans

---

## Appendix A: File Structure Reference

```
backend/
  app/
    models/
      base.py              # DeclarativeBase
      scan_log.py         # ScanLog ORM model
      finding.py          # Finding ORM model
      audit_log.py        # AuditLog ORM model
    api/
      auth_routes.py      # GET /auth/me, login, logout
      upload_routes.py    # POST /upload, GET /upload/status
      findings_routes.py  # GET /findings, PATCH /findings/{id}
      audit_routes.py     # GET /audit-logs (admin only)
      scan_routes.py      # GET /scans
      report_routes.py    # GET /reports/export-csv, export-pdf
    services/
      scan_service.py     # Orchestrate detection, risk calc, persistence
      upload_service.py   # File upload, validation, extraction
    detection/
      base_detector.py    # Abstract BaseDetector class
      detector_registry.py # DetectorRegistry
      detectors/
        api_key_detector.py
        database_url_detector.py
        password_detector.py
        pii_detector.py
        private_key_detector.py
        jwt_detector.py
        hardcoded_ip_detector.py
    risk_engine/
      risk_calculator.py  # Risk scoring algorithm
    core/
      config.py           # Settings
      database.py         # get_db()
      auth.py             # JWT utilities, get_current_user()
    main.py               # FastAPI app initialization

frontend/
  pages/
    index.tsx             # Landing page (/)
    login.tsx             # Login page
    upload.tsx            # Upload page (/upload)
    findings.tsx          # Findings dashboard (/findings)
    scan-history.tsx      # Scan history (/scans)
    admin/
      audit-logs.tsx      # Audit logs (admin only)
  components/
    TopBar.tsx            # Navigation header
    FileUpload.tsx        # Upload component
    FindingsTable.tsx     # Findings display
    FilterPanel.tsx       # Finding filters
  context/
    AuthContext.tsx       # Authentication state management
  hooks/
    useAuth.ts            # Hook to access AuthContext
```

---

## Appendix B: API Response Schema Examples

See Sections 7.1–7.6 for detailed endpoint specifications and response schemas.

---

**End of Design Document**
