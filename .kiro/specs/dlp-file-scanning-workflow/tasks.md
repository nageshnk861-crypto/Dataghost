# Implementation Plan: DataGhost DLP File Scanning Workflow

## Overview

This document provides an actionable implementation plan for the DataGhost DLP File Scanning Workflow, organized into 13 phases with discrete, testable tasks. The plan converts requirements and design specifications into concrete coding steps, building incrementally from authentication through end-to-end integration testing.

The workflow includes:
- Phase 0: Quick fix for role consistency (AuthContext persistence and re-verification)
- Phases 1-7: Core implementation (landing page, upload, detection, risk scoring, persistence, status management, audit logging)
- Phases 8-9: Enhancement features (scan history, reports, session management)
- Phases 10-11: Cross-cutting concerns (file cleanup, masking, end-to-end testing)
- Phase 12: Deployment and documentation

Each task specifies files to create/modify, acceptance criteria, estimated effort, and risk level.

---

## Phase 0: Quick Fix - Role Inconsistency (1-2 days)

- [x] 0.1 Fix AuthContext role persistence across navigation
- **Files to create/modify:**
  - `frontend/context/AuthContext.tsx` (modify existing context in `frontend/lib/AuthContext.tsx`)
  - `frontend/hooks/useAuth.ts` (create hook wrapper)
- **Acceptance Criteria:**
  - AuthContext stores `user` object with `id`, `email`, `username`, and `role` fields
  - Role persists in memory across page navigation without re-fetching
  - User role accessible via `useAuth()` hook throughout app
  - AuthContext initializes with `null` user on first load
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 1.1, 1.2_

- [x] 0.2 Implement role re-verification on page reload via GET /auth/me
- **Files to create/modify:**
  - `frontend/context/AuthContext.tsx` (add useEffect hook in `frontend/lib/AuthContext.tsx`)
  - `backend/api/auth_routes.py` (verify GET /auth/me exists and returns role)
- **Acceptance Criteria:**
  - On page reload, AuthContext calls GET /auth/me before rendering content
  - GET /auth/me returns user object with role
  - `loading` state is true during verification, false after completion
  - AuthContext waits for verification before resolving `isLoading` to false
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 1.3, 1.4_

- [x] 0.3 Handle 401 and role mismatch on page reload
- **Files to create/modify:**
  - `frontend/context/AuthContext.tsx` (add error handling in `frontend/lib/AuthContext.tsx`)
  - `frontend/pages/_app.tsx` (add route guards via `frontend/lib/useAuthGuard.ts` and `frontend/app/(app)/layout.tsx`)
- **Acceptance Criteria:**
  - If GET /auth/me returns 401, AuthContext clears and redirects to /login
  - If returned role differs from stored role, AuthContext clears and redirects to /login
  - User is prompted with notification if role changes unexpectedly
  - Redirect preserves return URL as query param (optional)
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 1.5, 1.6_

- [x] 0.4 Test role consistency across dashboard navigation
- **Files to create/modify:**
  - `frontend/__tests__/auth.test.ts` (create test suite)
  - `backend/tests/test_auth_routes.py` (create/enhance tests)
- **Acceptance Criteria:**
  - Test: Navigate between /findings, /scans, /upload without role changes
  - Test: Reload page and verify role re-fetched correctly
  - Test: Logout works and clears AuthContext
  - Test: 401 response redirects to /login
  - All tests pass with >90% coverage of AuthContext logic
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 1.1, 1.5, 1.6_

---

## Phase 1: Landing Page (1-2 days)

### 1.1 Create public landing page component (no auth required)
- **Files to create/modify:**
  - `frontend/pages/index.tsx` (or replace/rename `pages/_app.tsx` logic)
  - `frontend/pages/landing.tsx` (create landing page)
  - `frontend/styles/landing.module.css` (create styles)
- **Acceptance Criteria:**
  - Landing page renders without authentication
  - Page structure: header, features section, screenshot, CTA buttons, footer
  - No API calls made for unauthenticated users
  - Page markup is semantic and accessible
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 2.1_

### 1.2 Add headline, feature descriptions, and sample screenshot
- **Files to create/modify:**
  - `frontend/pages/landing.tsx` (add content)
  - `frontend/public/assets/dashboard-screenshot.png` (add image)
- **Acceptance Criteria:**
  - Headline clearly explains DataGhost DLP purpose
  - 3+ feature cards describe: secret detection, risk scoring, audit logging
  - Sample dashboard screenshot displayed prominently
  - All text is accurate and proofread
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 2.2, 2.3, 2.4_

### 1.3 Add Sign In and Demo buttons
- **Files to create/modify:**
  - `frontend/pages/landing.tsx` (add buttons and links)
  - `frontend/pages/demo.tsx` (create demo page, placeholder)
- **Acceptance Criteria:**
  - "Sign In" button navigates to /login
  - "Try Demo" button navigates to /demo
  - Buttons are prominent and keyboard-accessible
  - Button hover states provide visual feedback
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 2.5, 2.6_

### 1.4 Make landing page responsive (mobile, tablet, desktop)
- **Files to create/modify:**
  - `frontend/styles/landing.module.css` (add responsive styles)
  - `frontend/pages/landing.tsx` (verify semantic HTML)
- **Acceptance Criteria:**
  - Page renders correctly on 320px (mobile), 768px (tablet), 1920px (desktop)
  - Images scale appropriately
  - Text remains readable on all screen sizes
  - Touch targets are at least 44px on mobile
  - No horizontal scrolling on mobile
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 2.7_

### 1.5 Update root route to show landing page instead of redirect
- **Files to create/modify:**
  - `frontend/pages/_app.tsx` or `frontend/middleware.ts` (add routing logic)
  - `frontend/pages/index.tsx` (update or create)
- **Acceptance Criteria:**
  - Unauthenticated user accessing `/` sees landing page
  - Authenticated user accessing `/` redirects to dashboard
  - No role-based redirect for unauthenticated users
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 2.1, 2.8_

### 1.6 Test landing page renders for unauthenticated users
- **Files to create/modify:**
  - `frontend/__tests__/landing.test.ts` (create test suite)
- **Acceptance Criteria:**
  - Test: Landing page loads without errors
  - Test: All buttons and links are clickable
  - Test: Page is responsive on multiple screen sizes
  - Test: Unauthenticated users see landing, authenticated users don't
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 2.1, 2.7, 2.8_

---

## Phase 2: File Upload & Validation (2-3 days)

### [x] 2.1 Create FileUpload component with validation UI
- **Files to create/modify:**
  - `frontend/components/FileUpload.tsx` (create component)
  - `frontend/styles/fileupload.module.css` (create styles)
- **Acceptance Criteria:**
  - Component displays file input with drag-and-drop support
  - Accepted file types clearly displayed to user
  - Progress indicator shows during upload
  - Error messages displayed inline
  - Component is keyboard-accessible
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Low
- _Requirements: 3.1, 3.2_

### [x] 2.2 Implement POST /api/v1/upload endpoint in backend
- **Files to create/modify:**
  - `backend/api/upload_routes.py` (create routes)
  - `backend/models.py` (add ScanLog model if not present)
- **Acceptance Criteria:**
  - Endpoint accepts multipart/form-data with file
  - Endpoint requires authentication (JWT token)
  - Returns 201 with `scan_log_id` on success
  - Returns 400 with error detail on validation failure
  - Returns 401 if token invalid
  - ScanLog record created in database
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Medium
- _Requirements: 3.1_

### [x] 2.3 Add file validation (extension, size, format)
- **Files to create/modify:**
  - `backend/api/upload_routes.py` (add validation logic)
  - `backend/validators.py` (create or enhance)
- **Acceptance Criteria:**
  - File extension validation: only .zip, .tar.gz, .env, .json, .sql, .py, .js, .yaml, .yml, .log, .txt allowed
  - File size validation: reject files >10MB
  - File format validation: verify ZIP/TAR.GZ have correct magic bytes
  - Return 400 with specific error message for each failure case
  - Test with valid and invalid files
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 3.2, 3.3_

### [x] 2.4 Implement ZIP/TAR.GZ extraction with path-traversal protection
- **Files to create/modify:**
  - `backend/services/file_service.py` (create or enhance)
  - `backend/api/upload_routes.py` (use file service)
- **Acceptance Criteria:**
  - ZIP files extracted to temporary directory
  - TAR.GZ files extracted to temporary directory
  - Path traversal attacks blocked: reject archives with ".." in paths
  - Symbolic links skipped with warning
  - Extraction depth limited to 3 levels
  - Extracted files stored in memory (not on disk) during scan
  - Return 400 if extraction fails or is unsafe
- **Estimated Effort:** 3-4 hours
- **Risk Level:** High
- _Requirements: 3.5, 3.6_

### 2.5 Create ScanLog database record
- **Files to create/modify:**
  - `backend/models.py` (add ScanLog model)
  - `backend/api/upload_routes.py` (create ScanLog on upload)
- **Acceptance Criteria:**
  - ScanLog table created with fields: id, user_id, status, file_count, findings_count, temp_dir, created_at
  - ScanLog record created after file validation
  - ScanLog status initially set to "In Progress"
  - Foreign key to User table enforced
  - Indices created for efficient queries
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 3.1_

### 2.6 Create audit log for "Upload Started" action
- **Files to create/modify:**
  - `backend/models.py` (add AuditLog model if not present)
  - `backend/services/audit_service.py` (create service)
  - `backend/api/upload_routes.py` (call audit service)
- **Acceptance Criteria:**
  - AuditLog record created with: user_id, action="Upload Started", target_resource="file", details with file_name and file_size
  - AuditLog created immediately after ScanLog creation
  - Timestamp is accurate (UTC)
  - AuditLog persisted to database
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 7.1_

### 2.7 Implement /api/v1/upload/status endpoint
- **Files to create/modify:**
  - `backend/api/upload_routes.py` (add status endpoint)
- **Acceptance Criteria:**
  - Endpoint accepts scan_log_id as path parameter
  - Endpoint requires authentication (JWT token)
  - Returns 200 with ScanLog details: status, file_count, findings_count
  - Returns 404 if scan_log_id doesn't exist
  - Returns 403 if user is Analyst and doesn't own the scan
  - Admin users can access any scan
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 3.7, 10_

### 2.8 Test upload with valid files
- **Files to create/modify:**
  - `frontend/__tests__/fileupload.test.ts` (create test suite)
  - `backend/tests/test_upload_routes.py` (create test suite)
  - `backend/tests/fixtures/sample_files/` (create test files)
- **Acceptance Criteria:**
  - Test: Upload single .env file succeeds
  - Test: Upload .zip archive succeeds
  - Test: Upload .tar.gz archive succeeds
  - Test: Upload returns scan_log_id
  - Test: ScanLog record created in database
  - Test: AuditLog record created
  - Frontend test: FileUpload component handles success response
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 3.1_

### 2.9 Test upload with oversized/invalid files
- **Files to create/modify:**
  - `backend/tests/test_upload_routes.py` (add tests)
  - `frontend/__tests__/fileupload.test.ts` (add tests)
- **Acceptance Criteria:**
  - Test: Upload >10MB file returns 400
  - Test: Upload unsupported file type returns 400
  - Test: Upload corrupted ZIP returns 400
  - Test: Frontend displays error message for each failure case
  - Frontend error messages are user-friendly
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 3.3, 3.4_

### 2.10 Test ZIP path-traversal protection
- **Files to create/modify:**
  - `backend/tests/test_upload_routes.py` (add tests)
  - `backend/tests/fixtures/malicious.zip` (create test ZIP with traversal)
- **Acceptance Criteria:**
  - Test: Upload ZIP with "../" in paths returns 400
  - Test: Upload ZIP with "../../" in paths returns 400
  - Test: Upload TAR.GZ with "../" in paths returns 400
  - Test: Error message clearly indicates path traversal detected
  - No files extracted outside target directory
- **Estimated Effort:** 2-3 hours
- **Risk Level:** High
- _Requirements: 3.6_


---

## Phase 3: Secret Detection (3-4 days)

### [x] 3.1 Create BaseDetector abstract class and registry
- **Files to create/modify:**
  - `backend/detection/base_detector.py` (create base class)
  - `backend/detection/detector_registry.py` (create registry)
  - `backend/detection/__init__.py` (create package)
- **Acceptance Criteria:**
  - BaseDetector abstract class with `detect()` method
  - DetectionMatch dataclass with fields: line_number, column_start, matched_text, confidence_score
  - Detector registry stores detectors by name
  - Registry has `register()` and `get_detectors()` methods
  - Registry is singleton or module-level instance
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 4_

### [x] 3.2 Implement APIKeyDetector (AWS, GitHub, Stripe, Google, Azure, OpenAI)
- **Files to create/modify:**
  - `backend/detection/detectors/api_key_detector.py` (create)
  - `backend/detection/detector_registry.py` (register detector)
- **Acceptance Criteria:**
  - Detector matches AWS AKIA pattern
  - Detector matches GitHub ghp_ pattern
  - Detector matches Stripe sk_live_ pattern
  - Detector matches Google AIza pattern
  - Detector matches Azure connection string patterns
  - Detector matches OpenAI sk- pattern
  - Confidence scores assigned: 95 for exact patterns, 85 for fuzzy
  - Test with sample API keys for each service
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 4.1, 4.2, 4.3_

### [x] 3.3 Implement DatabaseURLDetector (PostgreSQL, MySQL, MongoDB, Oracle, MSSQL)
- **Files to create/modify:**
  - `backend/detection/detectors/database_url_detector.py` (create)
  - `backend/detection/detector_registry.py` (register detector)
- **Acceptance Criteria:**
  - Detector matches postgresql:// pattern
  - Detector matches mysql:// pattern
  - Detector matches mongodb:// pattern
  - Detector matches oracle:// pattern
  - Detector matches mssql:// pattern
  - Confidence score: 90
  - Test with sample database URLs
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 4.4, 4.5, 4.6_

### [x] 3.4 Implement PasswordDetector (password=, pwd=, secret=, passwd=, pass=)
- **Files to create/modify:**
  - `backend/detection/detectors/password_detector.py` (create)
  - `backend/detection/detector_registry.py` (register detector)
- **Acceptance Criteria:**
  - Detector matches password= pattern (case-insensitive)
  - Detector matches pwd= pattern
  - Detector matches secret= pattern
  - Detector matches passwd= pattern
  - Detector matches pass= pattern
  - Extracts value after `=` (8+ chars)
  - Confidence score: 75 (moderate, could be false positive)
  - Test with sample password lines
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 4.7, 4.8, 4.9_

### [x] 3.5 Implement PIIDetector (email, phone numbers)
- **Files to create/modify:**
  - `backend/detection/detectors/pii_detector.py` (create)
  - `backend/detection/detector_registry.py` (register detector)
- **Acceptance Criteria:**
  - Detector matches email pattern: [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
  - Detector matches phone pattern: (\+\d{1,3}[-.\s]?)?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}
  - Email confidence: 85
  - Phone confidence: 70
  - Test with sample emails and phone numbers
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 4.10, 4.11, 4.12, 4.13_

### [x] 3.6 Implement PrivateKeyDetector (PEM, RSA, DSA, EC keys)
- **Files to create/modify:**
  - `backend/detection/detectors/private_key_detector.py` (create)
  - `backend/detection/detector_registry.py` (register detector)
- **Acceptance Criteria:**
  - Detector matches BEGIN PRIVATE KEY pattern
  - Detector matches BEGIN RSA PRIVATE KEY pattern
  - Detector matches BEGIN DSA PRIVATE KEY pattern
  - Detector matches BEGIN EC PRIVATE KEY pattern
  - Confidence score: 98 (extremely high confidence)
  - Test with sample private keys
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 4.14, 4.15, 4.16_

### [x] 3.7 Implement JWTDetector (eyJ pattern)
- **Files to create/modify:**
  - `backend/detection/detectors/jwt_detector.py` (create)
  - `backend/detection/detector_registry.py` (register detector)
- **Acceptance Criteria:**
  - Detector matches JWT pattern: eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.
  - Confidence score: 90
  - Test with sample JWT tokens
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 4.17, 4.19_

### [x] 3.8 Implement HardcodedIPDetector (ip=, host= patterns)
- **Files to create/modify:**
  - `backend/detection/detectors/hardcoded_ip_detector.py` (create)
  - `backend/detection/detector_registry.py` (register detector)
- **Acceptance Criteria:**
  - Detector matches ip= pattern (case-insensitive)
  - Detector matches IP= pattern
  - Detector matches ipaddress= pattern
  - Detector matches host= pattern
  - Validates IPv4 format: \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}
  - Confidence score: 65 (moderate confidence)
  - Test with sample hardcoded IPs
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 4.18, 4.19_

### [x] 3.9 Create scan execution service that runs all detectors
- **Files to create/modify:**
  - `backend/services/scan_service.py` (create)
  - `backend/api/upload_routes.py` (call scan service after upload)
- **Acceptance Criteria:**
  - ScanService iterates through all registered detectors
  - For each file, runs all detectors in parallel (or sequential if simpler)
  - Collects all matches from all detectors
  - Handles detector failures gracefully (log, continue)
  - Skips binary files
  - Skips unreadable files
  - Returns list of Finding objects
  - Timeout per file: 30 seconds
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Medium
- _Requirements: 4_

### [x] 3.10 Test each detector with sample inputs
- **Files to create/modify:**
  - `backend/tests/test_detectors.py` (create test suite)
  - `backend/tests/fixtures/sample_secrets/` (create test files with secrets)
- **Acceptance Criteria:**
  - Test APIKeyDetector with AWS, GitHub, Stripe, Google keys
  - Test DatabaseURLDetector with PostgreSQL, MySQL, MongoDB URLs
  - Test PasswordDetector with password=, pwd=, secret= patterns
  - Test PIIDetector with emails and phone numbers
  - Test PrivateKeyDetector with RSA, DSA, EC keys
  - Test JWTDetector with valid JWT tokens
  - Test HardcodedIPDetector with ip= and host= patterns
  - Each detector has >80% test coverage
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Low
- _Requirements: 4.1-4.19_

### [x] 3.11 Test multiple detections in same file
- **Files to create/modify:**
  - `backend/tests/test_detectors.py` (add integration test)
  - `backend/tests/fixtures/sample_secrets/multi_secret_file.txt` (create test file)
- **Acceptance Criteria:**
  - Test file contains 3+ different secret types
  - All detectors find their respective secrets
  - Each secret gets separate Finding record
  - Finding count = expected number of secrets
  - No false negatives or missing detections
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 4.20_

---

## Phase 4: Risk Scoring (2-3 days)

### 4.1 Create RiskCalculator class with sensitivity table
- **Files to create/modify:**
  - `backend/risk_engine/risk_calculator.py` (create)
  - `backend/risk_engine/__init__.py` (create package)
- **Acceptance Criteria:**
  - RiskCalculator class created with SENSITIVITY_TABLE
  - Sensitivity values: Private Key=100, Database URL=90, API Key=85, Password=80, JWT=70, Hardcoded IP=50, PII=40
  - `get_sensitivity()` method returns correct value for finding type
  - Default sensitivity for unknown types: 50
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 5.1, 5.2_

### 4.2 Create exposure table based on file location
- **Files to create/modify:**
  - `backend/risk_engine/risk_calculator.py` (add EXPOSURE_TABLE)
- **Acceptance Criteria:**
  - EXPOSURE_TABLE defined with exposure values by file extension
  - Config files (.env, .json, .yaml, .yml, .config): 100
  - Log files (.log, .txt): 60
  - Source code (.py, .js, .sql, .ts): 40
  - Default exposure for unknown types: 40
  - `get_exposure()` method returns correct value for file path
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 5.1, 5.3_

### 4.3 Implement risk score formula: (Sensitivity × Exposure × Confidence) / 100
- **Files to create/modify:**
  - `backend/risk_engine/risk_calculator.py` (add calculate method)
- **Acceptance Criteria:**
  - `calculate()` method accepts: finding_type, file_path, confidence
  - Formula: (sensitivity × exposure × confidence) / 100
  - Result capped at 125 (max risk score)
  - Result is integer (round if necessary)
  - Returns tuple: (risk_score, severity)
  - Test with multiple examples to verify correctness
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 5.1_

### 4.4 Implement severity mapper (Low/Medium/High/Critical)
- **Files to create/modify:**
  - `backend/risk_engine/risk_calculator.py` (add SEVERITY_MAP and _map_severity method)
- **Acceptance Criteria:**
  - SEVERITY_MAP defined:
    - 1-20: Low
    - 21-50: Medium
    - 51-90: High
    - 91-125: Critical
  - `_map_severity()` method returns correct severity for risk score
  - Test boundary cases: 1, 20, 21, 50, 51, 90, 91, 125
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 5.5_

### 4.5 Integrate risk scoring into scan service
- **Files to create/modify:**
  - `backend/services/scan_service.py` (call risk calculator for each finding)
  - `backend/models.py` (add risk_score and severity fields to Finding model)
- **Acceptance Criteria:**
  - ScanService creates Finding with risk_score and severity
  - RiskCalculator called for each match
  - Finding.risk_score stored in database
  - Finding.severity stored in database
  - Risk scoring happens immediately after detection
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 5_

### 4.6 Test risk calculation with sample findings
- **Files to create/modify:**
  - `backend/tests/test_risk_calculator.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Private Key in .env with 98% confidence → risk=98, severity=Critical
  - Test: PII in .py with 85% confidence → risk=score calculated, severity determined
  - Test: Hardcoded IP in .log with 65% confidence → risk=score calculated
  - Test: Risk score capped at 125 when formula exceeds
  - Test: All boundary cases in severity mapping
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 5_

### 4.7 Verify severity mapping boundaries (1-20, 21-50, 51-90, 91-125)
- **Files to create/modify:**
  - `backend/tests/test_risk_calculator.py` (add boundary tests)
- **Acceptance Criteria:**
  - Test: Risk=1 → Low
  - Test: Risk=20 → Low
  - Test: Risk=21 → Medium
  - Test: Risk=50 → Medium
  - Test: Risk=51 → High
  - Test: Risk=90 → High
  - Test: Risk=91 → Critical
  - Test: Risk=125 → Critical
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 5.5_

---

## Phase 5: Finding Persistence & Dashboard (3-4 days)

### 5.1 Create Finding database model with proper fields
- **Files to create/modify:**
  - `backend/models.py` (add Finding model)
- **Acceptance Criteria:**
  - Finding model with fields: id, scan_log_id, file_path, line_number, category, confidence_score, masked_preview, risk_score, severity, status, created_at, updated_at
  - Foreign key to ScanLog
  - Indices on: scan_log_id, status, risk_score, severity, category
  - status default: "Open"
  - Table created in database
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 6.1_

### 5.2 Create AuditLog model
- **Files to create/modify:**
  - `backend/models.py` (add AuditLog model)
- **Acceptance Criteria:**
  - AuditLog model with fields: id, user_id, action, target_resource, target_id, created_at, details_json
  - Foreign key to User
  - Indices on: user_id, created_at, action
  - Table created in database
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 7_

### 5.3 Implement POST /api/v1/findings endpoint (create during scan)
- **Files to create/modify:**
  - `backend/api/findings_routes.py` (create)
  - `backend/services/scan_service.py` (call findings endpoint or create directly)
- **Acceptance Criteria:**
  - Endpoint creates Finding records in database after detection
  - Endpoint requires authentication
  - Returns 201 with Finding ID on success
  - Returns 400 if Finding data invalid
  - Findings persisted with all required fields
  - Multiple findings created for multiple detections
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 6.1_

### 5.4 Implement GET /api/v1/findings endpoint with role-based filtering
- **Files to create/modify:**
  - `backend/api/findings_routes.py` (add list endpoint)
- **Acceptance Criteria:**
  - Endpoint requires authentication
  - Analyst users see only findings from scans they initiated
  - Admin users see all findings
  - Supports filtering by: severity, status, category, date_range
  - Supports pagination: limit, offset
  - Returns 200 with findings list
  - RBAC enforced: 403 if user doesn't have permission
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Medium
- _Requirements: 6.3, 6.4, 10_

### 5.5 Create findings dashboard component (table, sorting, filtering)
- **Files to create/modify:**
  - `frontend/pages/findings.tsx` (create findings page)
  - `frontend/components/FindingsTable.tsx` (create table component)
  - `frontend/components/FilterPanel.tsx` (create filter component)
  - `frontend/styles/findings.module.css` (create styles)
- **Acceptance Criteria:**
  - Dashboard displays findings in sortable table
  - Columns: category, file_path, line_number, masked_preview, risk_score, severity, status
  - Sort by risk_score descending by default
  - Filter by: severity, status, category, date_range
  - Pagination: show 50 findings per page
  - Table is responsive and accessible
- **Estimated Effort:** 4-5 hours
- **Risk Level:** Medium
- _Requirements: 6.5, 6.6, 6.7_

### 5.6 Implement Admin sees all findings, Analyst sees own findings
- **Files to create/modify:**
  - `backend/api/findings_routes.py` (add RBAC logic)
  - `frontend/pages/findings.tsx` (adjust display based on role)
- **Acceptance Criteria:**
  - Backend enforces RBAC on GET /findings
  - Admin role can see all findings
  - Analyst role sees only own findings
  - Returns 403 if Analyst tries to access other user's findings
  - Frontend adjusts UI based on user role
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 6.3, 6.4, 10_

### 5.7 Add scan history section
- **Files to create/modify:**
  - `frontend/components/ScanHistory.tsx` (create component)
  - `backend/api/scan_routes.py` (create or enhance)
- **Acceptance Criteria:**
  - Component displays list of previous scans
  - Shows: scan_date, file_count, total_findings_count, findings_by_severity
  - Analyst sees only own scans
  - Admin sees all scans
  - Click on scan loads its findings
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 6.8, 6.9_

### 5.8 Test RBAC: Analyst cannot access other user's findings
- **Files to create/modify:**
  - `backend/tests/test_findings_routes.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Analyst A uploads file → scan_log_id_a
  - Test: Analyst B tries GET /findings with Analyst A's scan
  - Test: Backend returns 403 Forbidden
  - Test: AuditLog records unauthorized access attempt
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Medium
- _Requirements: 10_

### 5.9 Test Admin can access all findings
- **Files to create/modify:**
  - `backend/tests/test_findings_routes.py` (add tests)
- **Acceptance Criteria:**
  - Test: Admin user GET /findings returns all findings
  - Test: Admin can access findings from any user's scan
  - Test: No 403 errors for Admin users
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 10_

---

## Phase 6: Finding Status Management (2-3 days)

### 6.1 Add status field to Finding model (Open, In Review, Resolved, False Positive)
- **Files to create/modify:**
  - `backend/models.py` (add status field to Finding)
- **Acceptance Criteria:**
  - Status field added: Enum or String with values: Open, In Review, Resolved, False Positive
  - Default value: "Open"
  - Migration created if using Alembic
  - Index created on status field
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 7.1, 7.2_

### 6.2 Implement PATCH /api/v1/findings/{id}/status endpoint
- **Files to create/modify:**
  - `backend/api/findings_routes.py` (add PATCH endpoint)
- **Acceptance Criteria:**
  - Endpoint accepts status in request body
  - Validates status is one of: Open, In Review, Resolved, False Positive
  - Returns 200 with updated Finding
  - Returns 400 if status invalid
  - Returns 404 if Finding not found
  - Returns 401 if user not authenticated
- **Estimated Effort:** 2 hours
- **Risk Level:** Medium
- _Requirements: 7.3_

### 6.3 Add status change validation (only owner or admin)
- **Files to create/modify:**
  - `backend/api/findings_routes.py` (add permission check)
- **Acceptance Criteria:**
  - Analyst can only update findings from own scans
  - Admin can update any finding
  - Returns 403 if user doesn't have permission
  - Permission check happens before update
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Medium
- _Requirements: 7.4, 7.5_

### 6.4 Create audit log for status changes
- **Files to create/modify:**
  - `backend/services/audit_service.py` (create/enhance)
  - `backend/api/findings_routes.py` (call audit service on status update)
- **Acceptance Criteria:**
  - AuditLog record created on status change
  - Details include: finding_id, old_status, new_status
  - Timestamp accurate (UTC)
  - AuditLog persisted to database
  - Admin can view these audit logs
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 7.6_

### 6.5 Add status dropdown to findings dashboard
- **Files to create/modify:**
  - `frontend/components/FindingsTable.tsx` (add dropdown to table)
  - `frontend/styles/findings.module.css` (style dropdown)
- **Acceptance Criteria:**
  - Each finding row has status dropdown
  - Options: Open, In Review, Resolved, False Positive
  - Dropdown is editable (not disabled)
  - Clicking option sends PATCH request
  - On success, UI updates immediately
  - On error, displays error message
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 7.7_

### 6.6 Test status update permissions (Analyst own, Admin any)
- **Files to create/modify:**
  - `backend/tests/test_findings_routes.py` (add tests)
- **Acceptance Criteria:**
  - Test: Analyst can update status of own findings
  - Test: Analyst cannot update status of other's findings (403)
  - Test: Admin can update any finding
  - Test: Non-authenticated user cannot update (401)
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Medium
- _Requirements: 10_

### 6.7 Test audit log records status changes
- **Files to create/modify:**
  - `backend/tests/test_audit_service.py` (create/enhance test suite)
- **Acceptance Criteria:**
  - Test: Status change creates AuditLog
  - Test: AuditLog contains correct old_status and new_status
  - Test: Multiple status changes create separate AuditLog records
  - Test: Admin can retrieve audit logs for findings
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 7_

---

## Phase 7: Audit Logging (2-3 days)

### 7.1 Implement AuditLog creation for all important actions
- **Files to create/modify:**
  - `backend/services/audit_service.py` (create comprehensive audit logging)
  - `backend/api/upload_routes.py` (call audit service)
  - `backend/api/findings_routes.py` (call audit service)
- **Acceptance Criteria:**
  - "Upload Started" logged when file upload begins
  - "Scan Completed" logged when scan finishes
  - "Finding Viewed" logged when user views finding
  - "Status Changed" logged with old and new status
  - All audit logs include: user_id, action, target_resource, timestamp, details_json
  - Audit service handles errors gracefully (doesn't crash if logging fails)
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 7.1, 7.2, 7.3, 7.4_

### 7.2 Create /api/v1/audit-logs endpoint (admin only)
- **Files to create/modify:**
  - `backend/api/audit_routes.py` (create)
- **Acceptance Criteria:**
  - Endpoint requires authentication
  - Endpoint requires admin role (returns 403 for non-admin)
  - Supports filtering by: user_id, action, date_range, target_resource
  - Supports pagination: limit, offset
  - Returns 200 with audit logs
  - Returns 403 if user is not admin
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 7.2_

### 7.3 Implement audit log filtering (user_id, action, date_range)
- **Files to create/modify:**
  - `backend/api/audit_routes.py` (add filtering logic)
  - `backend/services/audit_service.py` (add query methods)
- **Acceptance Criteria:**
  - Filter by user_id: returns only audit logs for that user
  - Filter by action: returns only specified action type
  - Filter by date_range: from_date and to_date parameters
  - Filter by target_resource: file, scan_log, finding, etc.
  - Multiple filters work together (AND logic)
  - Invalid filters return 400 with error message
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 7.3_

### 7.4 Create admin-only audit log viewer component
- **Files to create/modify:**
  - `frontend/pages/admin/audit-logs.tsx` (create page)
  - `frontend/components/AuditLogsTable.tsx` (create table component)
  - `frontend/components/AuditFilterPanel.tsx` (create filter component)
  - `frontend/styles/audit.module.css` (create styles)
- **Acceptance Criteria:**
  - Page only accessible to Admin users
  - Non-admin users see 403 error
  - Table displays audit logs with: user_id, action, target_resource, timestamp
  - Supports filtering and pagination
  - Details expandable to show details_json
  - Responsive and accessible design
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Medium
- _Requirements: 7.4, 7.5_

### 7.5 Test audit logs record correct details
- **Files to create/modify:**
  - `backend/tests/test_audit_routes.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Upload creates "Upload Started" audit log
  - Test: Scan creates "Scan Completed" audit log with findings_count
  - Test: Status update creates "Status Changed" audit log
  - Test: All fields populated correctly
  - Test: Timestamps accurate
  - Test: Details JSON properly formatted
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 7.1-7.4_

### 7.6 Test non-admin access to audit logs returns 403
- **Files to create/modify:**
  - `backend/tests/test_audit_routes.py` (add test)
- **Acceptance Criteria:**
  - Test: Analyst user GET /audit-logs returns 403
  - Test: Unauthenticated user GET /audit-logs returns 401
  - Test: Admin user GET /audit-logs returns 200 with audit logs
  - Test: Attempted access logged in audit logs
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 7.6, 7.7, 7.8_

---

## Phase 8: Scan History & Reports (2-3 days)

### 8.1 Create /api/v1/scans endpoint (list scans with role filtering)
- **Files to create/modify:**
  - `backend/api/scan_routes.py` (create or enhance)
- **Acceptance Criteria:**
  - Endpoint requires authentication
  - Analyst sees only own scans
  - Admin sees all scans
  - Supports pagination: limit, offset
  - Returns: scan_date, file_count, findings_count, findings_by_severity
  - Returns 200 on success
  - Returns 403 if user doesn't have permission
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 8.1, 8.2_

### 8.2 Create scan history component
- **Files to create/modify:**
  - `frontend/pages/scans.tsx` (create page)
  - `frontend/components/ScanHistoryTable.tsx` (create table component)
  - `frontend/styles/scans.module.css` (create styles)
- **Acceptance Criteria:**
  - Page displays user's scan history
  - Table shows: scan_date, file_count, findings_count, findings_by_severity breakdown
  - Click on scan loads its findings in dashboard
  - Responsive and accessible design
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: 8.2, 8.3, 8.4_

### 8.3 Implement CSV export functionality
- **Files to create/modify:**
  - `backend/api/export_routes.py` (create)
  - `frontend/components/ExportButton.tsx` (create button component)
- **Acceptance Criteria:**
  - Backend endpoint: GET /api/v1/export/csv
  - Endpoint exports current findings list as CSV
  - CSV columns: file_path, line_number, category, risk_score, severity, status, detected_at
  - Analyst exports only own findings
  - Admin exports filtered findings
  - Frontend download triggered client-side
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 8.5, 8.6_

### 8.4 Implement PDF report generation
- **Files to create/modify:**
  - `backend/api/export_routes.py` (add PDF endpoint)
  - `backend/services/pdf_service.py` (create PDF generation)
- **Acceptance Criteria:**
  - Backend endpoint: GET /api/v1/export/pdf
  - PDF includes: scan_summary, findings_table, timestamp
  - PDF is readable with proper formatting
  - Analyst generates reports for own findings
  - Admin generates for any findings
  - Frontend download triggered client-side
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Medium
- _Requirements: 8.6_

### 8.5 Add export buttons to findings dashboard
- **Files to create/modify:**
  - `frontend/pages/findings.tsx` (add export buttons)
  - `frontend/components/ExportButton.tsx` (enhance)
- **Acceptance Criteria:**
  - "Export as CSV" button visible on dashboard
  - "Export as PDF" button visible on dashboard
  - Buttons trigger download with correct filename
  - Buttons include loading state
  - Error handling if export fails
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 8.5_

### 8.6 Test CSV export contains correct fields
- **Files to create/modify:**
  - `backend/tests/test_export_routes.py` (create test suite)
- **Acceptance Criteria:**
  - Test: CSV export returns 200 OK
  - Test: CSV contains all required columns
  - Test: CSV data matches findings in database
  - Test: CSV filename includes scan ID and date
  - Test: CSV is properly formatted (valid CSV syntax)
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 8.5, 8.6_

### 8.7 Test PDF report formatting
- **Files to create/modify:**
  - `backend/tests/test_export_routes.py` (add tests)
- **Acceptance Criteria:**
  - Test: PDF export returns 200 OK
  - Test: PDF contains scan summary section
  - Test: PDF contains findings table
  - Test: PDF contains timestamp
  - Test: PDF is readable and properly formatted
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 8.6_

---

## Phase 9: Cross-Cutting - Session Management (1-2 days)

### 9.1 Implement 1-hour inactivity timeout in backend
- **Files to create/modify:**
  - `backend/core/config.py` (add SESSION_TIMEOUT_MINUTES = 60)
  - `backend/api/auth_routes.py` (update login to set token expiry)
- **Acceptance Criteria:**
  - JWT token expires after 60 minutes
  - Token expiry time included in token payload
  - Backend verifies expiry on each request
  - Returns 401 if token expired
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 13.1, 13.2_

### 9.2 Implement inactivity timeout logic in frontend
- **Files to create/modify:**
  - `frontend/context/AuthContext.tsx` (add session timeout logic)
  - `frontend/hooks/useSessionTimeout.ts` (create custom hook)
- **Acceptance Criteria:**
  - Session timeout timer initialized at 60 minutes
  - Timer resets on user activity: mousedown, keydown, scroll, touchstart
  - After 60 minutes of inactivity, user is logged out
  - On logout, AuthContext clears and redirects to /login
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 13.1, 13.3, 13.4_

### 9.3 Show inactivity warning 5 minutes before expiration
- **Files to create/modify:**
  - `frontend/context/AuthContext.tsx` (add warning timer)
  - `frontend/components/InactivityWarning.tsx` (create warning modal)
  - `frontend/styles/inactivity-warning.module.css` (create styles)
- **Acceptance Criteria:**
  - Warning modal appears 5 minutes before session expiration
  - Warning displays countdown timer
  - User can extend session by clicking "Stay Logged In"
  - If no action taken, session expires and user logs out
  - Modal is dismissible (optional)
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 13.6_

### 9.4 Auto-logout on timeout
- **Files to create/modify:**
  - `frontend/context/AuthContext.tsx` (add auto-logout on timeout)
- **Acceptance Criteria:**
  - After timeout, AuthContext.logout() is called automatically
  - User redirected to /login page
  - AuthContext cleared
  - Notification displayed: "Your session has expired"
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 13.4, 13.5_

### 9.5 Test inactivity timeout behavior
- **Files to create/modify:**
  - `frontend/__tests__/session-timeout.test.ts` (create test suite)
  - `backend/tests/test_auth_timeout.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Session expires after 60 minutes
  - Test: Activity resets timeout timer
  - Test: Warning appears 5 minutes before expiry
  - Test: Auto-logout on timeout
  - Test: Token validation returns 401 for expired token
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 13_

### 9.6 Test warning displays correctly
- **Files to create/modify:**
  - `frontend/__tests__/inactivity-warning.test.ts` (create test)
- **Acceptance Criteria:**
  - Test: Warning modal appears 5 minutes before timeout
  - Test: Countdown timer is accurate
  - Test: "Stay Logged In" button extends session
  - Test: Modal disappears on action
  - Test: User interface properly styled
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 13.6_

---

## Phase 10: Cross-Cutting - File Cleanup & Secret Masking (1-2 days)

### 10.1 Implement secret masking in Finding model (first/last 4 chars)
- **Files to create/modify:**
  - `backend/services/scan_service.py` (call masking function)
  - `backend/detection/base_detector.py` (add mask_preview method if not present)
- **Acceptance Criteria:**
  - Finding.masked_preview stores only first 4 and last 4 chars visible
  - Middle portion masked with asterisks (*)
  - Secrets shorter than 8 chars: all masked
  - Masking happens before Finding is persisted
  - Complete secret never stored in database
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 12.1, 12.2, 12.3_

### 10.2 Implement automatic file deletion after processing
- **Files to create/modify:**
  - `backend/services/scan_service.py` (add file cleanup)
  - `backend/services/file_service.py` (add delete method)
- **Acceptance Criteria:**
  - After scan completes, all extracted files deleted from temp directory
  - Temp directory removed
  - Deletion happens synchronously after scan
  - Errors in deletion logged but don't crash scan
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Medium
- _Requirements: 11.1, 11.2_

### 10.3 Implement background job to clean up old temp files (48h)
- **Files to create/modify:**
  - `backend/services/background_jobs.py` (create)
  - `backend/main.py` or app startup (schedule background job)
- **Acceptance Criteria:**
  - Background job runs daily or on interval
  - Finds temp files older than 48 hours
  - Deletes old temp files and directories
  - Logs cleanup operations
  - Handles errors gracefully
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 11.3, 11.4_

### 10.4 Log file deletion to audit trail
- **Files to create/modify:**
  - `backend/services/file_service.py` (add audit logging)
  - `backend/services/audit_service.py` (create audit log entry)
- **Acceptance Criteria:**
  - Each file deletion creates AuditLog record
  - AuditLog includes: file_path, deletion_reason, timestamp
  - Audit logs for background job cleanup
  - Admin can view file deletion history
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 11.5_

### 10.5 Test masked preview format
- **Files to create/modify:**
  - `backend/tests/test_masking.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Secret "abcdefghijklmnop" → "abcd****ijklmnop"
  - Test: Secret "abc" → "***"
  - Test: Secret "12345678" → "1234****"
  - Test: Masked format consistent across all findings
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: 12.1_

### 10.6 Test file cleanup after successful scan
- **Files to create/modify:**
  - `backend/tests/test_file_cleanup.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Upload and scan → temp files deleted
  - Test: Temp directory removed after scan
  - Test: Files not on disk after scan completes
  - Test: Multiple scans each clean up their own files
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Medium
- _Requirements: 11.1, 11.2_

### 10.7 Test file cleanup after scan failure
- **Files to create/modify:**
  - `backend/tests/test_file_cleanup.py` (add tests)
- **Acceptance Criteria:**
  - Test: If scan fails, temp files are still cleaned up
  - Test: Temp directory removed even on error
  - Test: Error handling doesn't interfere with cleanup
- **Estimated Effort:** 1 hour
- **Risk Level:** Medium
- _Requirements: 11.1, 11.2_

---

## Phase 11: Integration & End-to-End Testing (2-3 days)

### 11.1 Write end-to-end test: Login → Upload → Scan → View → Resolve
- **Files to create/modify:**
  - `backend/tests/test_e2e.py` (create E2E test suite)
  - `frontend/__tests__/e2e.test.ts` (create E2E test suite)
- **Acceptance Criteria:**
  - Test: User logs in with valid credentials
  - Test: User navigates to upload page
  - Test: User uploads test file
  - Test: Scan completes and findings displayed
  - Test: User clicks on finding
  - Test: User updates finding status to "Resolved"
  - Test: All assertions pass
- **Estimated Effort:** 3-4 hours
- **Risk Level:** Medium
- _Requirements: All_

### 11.2 Test role consistency across all pages during workflow
- **Files to create/modify:**
  - `frontend/__tests__/role-consistency.test.ts` (create test suite)
- **Acceptance Criteria:**
  - Test: Analyst role persists from /login to /findings
  - Test: Role doesn't change on page reload
  - Test: Admin role shows admin UI elements
  - Test: Analyst role hides admin UI elements
  - Test: Role mismatch triggers logout
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: 1, 10_

### 11.3 Test RBAC for all protected endpoints
- **Files to create/modify:**
  - `backend/tests/test_rbac.py` (create comprehensive RBAC test suite)
- **Acceptance Criteria:**
  - Test: Analyst cannot access admin endpoints (returns 403)
  - Test: Unauthenticated users cannot access protected endpoints (returns 401)
  - Test: Admin can access all endpoints
  - Test: Analyst can only access own data
  - Test: All protected endpoints properly validate permissions
- **Estimated Effort:** 2-3 hours
- **Risk Level:** High
- _Requirements: 10_

### 11.4 Performance test: Scan 10MB file within 30 seconds
- **Files to create/modify:**
  - `backend/tests/test_performance.py` (create performance test)
  - `backend/tests/fixtures/large_test_file.zip` (create 10MB test file)
- **Acceptance Criteria:**
  - Test: Upload and scan 10MB file completes within 30 seconds
  - Test: All detectors run successfully on large file
  - Test: Memory usage stays within reasonable limits
  - Test: No timeout errors
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: Non-functional requirement_

### 11.5 Test error handling (invalid file, timeout, etc.)
- **Files to create/modify:**
  - `backend/tests/test_error_handling.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Invalid file upload returns 400 with descriptive error
  - Test: Timeout on large file returns appropriate error
  - Test: Corrupted ZIP returns 400
  - Test: Permission denied returns 403
  - Test: Server errors return 500 with error message
  - Test: Frontend displays all error messages appropriately
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Medium
- _Requirements: Error Handling section_

### 11.6 Test audit trail completeness
- **Files to create/modify:**
  - `backend/tests/test_audit_completeness.py` (create test suite)
- **Acceptance Criteria:**
  - Test: Upload creates audit log
  - Test: Scan completion creates audit log
  - Test: Status change creates audit log
  - Test: Failed operations create error audit logs
  - Test: Admin can retrieve complete audit trail
  - Test: No audit log entries missing
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: 7_

---

## Phase 12: Deployment & Documentation (1-2 days)

### 12.1 Update README with project overview
- **Files to create/modify:**
  - `README.md` (create/update)
- **Acceptance Criteria:**
  - README includes project description
  - Installation instructions clear
  - Quick start guide provided
  - Key features listed
  - Troubleshooting section included
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: Documentation_

### 12.2 Document API endpoints and response formats
- **Files to create/modify:**
  - `API.md` (create/update)
- **Acceptance Criteria:**
  - All endpoints documented with request/response examples
  - Status codes explained
  - Error responses documented
  - Authentication requirements clear
  - RBAC matrix included
- **Estimated Effort:** 2-3 hours
- **Risk Level:** Low
- _Requirements: Documentation_

### 12.3 Document detection rules and risk scoring
- **Files to create/modify:**
  - `DETECTION_RULES.md` (create)
  - `RISK_SCORING.md` (create)
- **Acceptance Criteria:**
  - Each detector documented with example patterns
  - Confidence score explanations
  - Risk scoring formula explained
  - Sensitivity and exposure tables documented
  - Example calculations provided
- **Estimated Effort:** 1-2 hours
- **Risk Level:** Low
- _Requirements: Documentation_

### 12.4 Create deployment checklist
- **Files to create/modify:**
  - `DEPLOYMENT_CHECKLIST.md` (create)
- **Acceptance Criteria:**
  - Pre-deployment checks listed
  - Database migration steps documented
  - Environment variables listed
  - Health check procedures included
  - Rollback procedures documented
- **Estimated Effort:** 1 hour
- **Risk Level:** Low
- _Requirements: Documentation_

### 12.5 Deploy to Vercel (frontend) and Render (backend)
- **Files to create/modify:**
  - `.vercelrc` or `vercel.json` (frontend config)
  - `render.yaml` (backend deployment config)
- **Acceptance Criteria:**
  - Frontend deployed to Vercel with correct environment variables
  - Backend deployed to Render with database connection
  - Environment variables secured (not hardcoded)
  - Both services connected and communicating
  - Deployment logs reviewed for errors
- **Estimated Effort:** 2-3 hours
- **Risk Level:** High
- _Requirements: Deployment_

### 12.6 Verify production deployment
- **Files to create/modify:**
  - `PROD_VERIFICATION.md` (create verification checklist)
- **Acceptance Criteria:**
  - Frontend loads without errors
  - Login works with production credentials
  - Upload functionality works end-to-end
  - Findings display correctly
  - Audit logs accessible to admin
  - No console errors in browser
  - API endpoints respond correctly
  - Database queries execute successfully
- **Estimated Effort:** 2 hours
- **Risk Level:** High
- _Requirements: Deployment_

---

## Summary

**Total Estimated Effort:** 85-110 days (depending on parallelization and team size)

**Critical Path:**
1. Phase 0: Role consistency (1-2 days)
2. Phase 1: Landing page (1-2 days)
3. Phase 2: File upload (2-3 days)
4. Phase 3: Detection (3-4 days)
5. Phase 4: Risk scoring (2-3 days)
6. Phase 5: Persistence (3-4 days)
7. Phases 6-7: Status & Audit (4-6 days)
8. Phases 8-11: Enhancements & Testing (6-8 days)
9. Phase 12: Deployment (1-2 days)

**Risk Mitigation:**
- High-risk items (path traversal, RBAC, file cleanup) have dedicated testing
- Integration testing catches cross-phase issues early
- Checkpoint tasks after each phase validate functionality
- Security concerns reviewed at each phase

---

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["0.1", "1.1", "2.1"]
    },
    {
      "id": 1,
      "tasks": ["0.2", "1.2", "2.2", "2.5"]
    },
    {
      "id": 2,
      "tasks": ["0.3", "1.3", "1.4", "2.3", "2.6"]
    },
    {
      "id": 3,
      "tasks": ["0.4", "1.5", "1.6", "2.4", "2.7", "3.1"]
    },
    {
      "id": 4,
      "tasks": ["2.8", "2.9", "2.10", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8"]
    },
    {
      "id": 5,
      "tasks": ["3.9", "3.10", "3.11", "4.1", "4.2", "4.3", "4.4"]
    },
    {
      "id": 6,
      "tasks": ["4.5", "4.6", "4.7", "5.1", "5.2", "5.3"]
    },
    {
      "id": 7,
      "tasks": ["5.4", "5.5", "5.6", "5.7", "6.1", "6.2"]
    },
    {
      "id": 8,
      "tasks": ["5.8", "5.9", "6.3", "6.4", "6.5", "7.1"]
    },
    {
      "id": 9,
      "tasks": ["6.6", "6.7", "7.2", "7.3", "7.4"]
    },
    {
      "id": 10,
      "tasks": ["7.5", "7.6", "8.1", "8.2", "8.3", "9.1", "9.2"]
    },
    {
      "id": 11,
      "tasks": ["8.4", "8.5", "8.6", "8.7", "9.3", "9.4"]
    },
    {
      "id": 12,
      "tasks": ["9.5", "9.6", "10.1", "10.2", "10.3"]
    },
    {
      "id": 13,
      "tasks": ["10.4", "10.5", "10.6", "10.7", "11.1", "11.2"]
    },
    {
      "id": 14,
      "tasks": ["11.3", "11.4", "11.5", "11.6", "12.1", "12.2"]
    },
    {
      "id": 15,
      "tasks": ["12.3", "12.4", "12.5", "12.6"]
    }
  ]
}
```

