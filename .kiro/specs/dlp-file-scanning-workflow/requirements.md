# Requirements Document: DataGhost DLP File Scanning Workflow

## Introduction

DataGhost is a Data Loss Prevention (DLP) system that helps developers and security teams detect and manage sensitive information (secrets, PII, private keys) in their codebases and configuration files. This requirements document defines the core functionality for the file scanning workflow, including user authentication, file upload, multi-detector secret detection, risk scoring, finding persistence, status management, and audit logging.

The system is designed in seven phases, with a quick fix for role inconsistency preceding the main implementation phases. The workflow spans from user authentication through secret detection, risk calculation, finding management, and comprehensive audit tracking.

---

## Glossary

- **System**: The DataGhost DLP application backend and frontend
- **User**: Any authenticated individual interacting with DataGhost
- **Analyst**: A user role with ability to view and manage findings from scans they initiated
- **Admin**: A user role with ability to view and manage all findings system-wide and manage audit logs
- **Unauthenticated User**: A visitor who has not logged in
- **Session**: An authenticated user's continuous activity period; expires after 1 hour of inactivity
- **Finding**: A detected instance of sensitive information (secrets, PII, private keys) in a scanned file
- **Scan**: A complete analysis operation on one or more uploaded files
- **ScanLog**: A database record documenting a completed scan operation
- **Secret**: Sensitive information including API keys, database URLs, passwords, private keys, JWT tokens, and hardcoded credentials
- **Risk Score**: A numeric value (1-125) indicating the overall risk of a detected finding, calculated from Sensitivity × Exposure × Confidence
- **Severity**: A categorical classification (Low, Medium, High, Critical) mapped from Risk Score
- **Confidence**: A measure (0-100%) of how certain the detection is based on pattern matching precision
- **Sensitivity**: A measure (0-100%) of how sensitive a finding type is (e.g., private keys = highest)
- **Exposure**: A measure (0-100%) of how exposed a file is based on its location (config files most exposed)
- **PII**: Personally Identifiable Information including email addresses and phone numbers
- **RBAC**: Role-Based Access Control; system enforces permissions based on user role
- **AuthContext**: Client-side state management object holding user authentication data and role
- **Audit Log**: A record of system actions including user ID, action type, target resource, and timestamp
- **ZIP Archive**: A compressed file format (.zip or .tar.gz) potentially containing multiple files
- **Masked Finding**: A Finding record that stores sensitive information in obfuscated form (never the complete secret)
- **Status**: The lifecycle state of a Finding: Open, In Review, Resolved, or False Positive
- **False Positive**: A Finding incorrectly flagged as sensitive when it is not actually sensitive

---

## Requirements

### Requirement 1: Role Inconsistency Fix (Phase 0)

**User Story:** As a user, I want my role to persist across page navigation and be re-verified on reload, so that I see consistent permissions and am prompted to re-login if there's a mismatch.

#### Acceptance Criteria

1. THE AuthContext SHALL store the current user role (Analyst or Admin) in client-side state
2. WHEN a user navigates between pages, THE AuthContext SHALL retain the user role without fetching the role again
3. WHEN a user reloads the browser or returns after browser closure, THE Frontend SHALL call GET /auth/me to verify the stored role
4. IF the role returned from GET /auth/me differs from the stored role in AuthContext, THEN THE System SHALL clear the AuthContext and redirect to the login page
5. IF GET /auth/me returns a 401 status, THEN THE Frontend SHALL clear the AuthContext and redirect to the login page
6. WHEN the user clicks the logout button, THE AuthContext SHALL be cleared and the user SHALL be redirected to the login page

---

### Requirement 2: Landing Page (Phase 1)

**User Story:** As an unauthenticated user, I want to see a compelling landing page explaining DataGhost's purpose before signing in, so that I understand the product value.

#### Acceptance Criteria

1. WHEN an unauthenticated user accesses the application root URL, THE System SHALL display the landing page instead of redirecting to login
2. THE Landing_Page SHALL include a headline explaining what DataGhost does
3. THE Landing_Page SHALL include a description of key features: secret detection, risk scoring, audit logging
4. THE Landing_Page SHALL display a sample dashboard screenshot showing the findings interface
5. THE Landing_Page SHALL include a "Sign In" button that navigates to /login
6. THE Landing_Page SHALL include a "Try Demo" button that navigates to a demo scan page
7. THE Landing_Page SHALL be responsive and render correctly on mobile, tablet, and desktop devices
8. WHEN an authenticated user accesses the root URL, THE System SHALL redirect to the dashboard instead of displaying the landing page

---

### Requirement 3: File Upload & Validation (Phase 2)

**User Story:** As a user, I want to upload files for scanning, with validation ensuring only supported formats are accepted and files don't exceed size limits.

#### Acceptance Criteria

1. WHEN a user navigates to the upload page, THE Upload_Component SHALL display a file input accepting either a single file or a ZIP archive
2. THE Upload_Component SHALL accept files with these extensions: .zip, .tar.gz, .env, .json, .sql, .py, .js, .yaml, .yml, .log, .txt
3. IF a user selects a file with an unsupported extension, THE Frontend SHALL display an error message and reject the upload
4. IF the selected file exceeds 10MB, THE Frontend SHALL display an error message and reject the upload
5. WHEN a user uploads a ZIP or TAR.GZ file, THE Backend SHALL extract all files from the archive
6. IF the ZIP archive contains any path with ".." (parent directory escape), THE Backend SHALL reject the upload and return an error response
7. WHEN the Backend processes the uploaded file(s), THE System SHALL display a progress indicator on the Frontend
8. IF any file extraction fails, THE Backend SHALL return an error response and THE Frontend SHALL display an error message
9. THE System SHALL delete all uploaded files after processing the scan (files retained in memory during scan only)

---

### Requirement 4: Secret Detection Engine (Phase 3)

**User Story:** As a user, I want the system to detect multiple types of secrets in my uploaded files, so that I can identify what sensitive information is exposed.

#### Acceptance Criteria

**Detector 1: API Keys**

1. WHEN THE Detector scans a file, THE API_Key_Detector SHALL identify API keys from: AWS, GitHub, Stripe, Google Cloud, Azure, OpenAI, and other common services
2. THE API_Key_Detector SHALL match patterns like: AKIA (AWS), ghp_ (GitHub), sk_live_ (Stripe), AIza (Google)
3. WHEN an API key is detected, THE Finding SHALL include: file_path, line_number, detection_category="API Key", confidence_score, masked_preview

**Detector 2: Database URLs**

4. WHEN THE Detector scans a file, THE Database_URL_Detector SHALL identify database connection strings
5. THE Database_URL_Detector SHALL match patterns: postgresql://, mysql://, mongodb://, oracle://, mssql://
6. WHEN a database URL is detected, THE Finding SHALL include: file_path, line_number, detection_category="Database URL", confidence_score, masked_preview

**Detector 3: Passwords**

7. WHEN THE Detector scans a file, THE Password_Detector SHALL identify hardcoded passwords
8. THE Password_Detector SHALL match patterns: password=, pwd=, secret=, passwd=, pass=
9. WHEN a password is detected, THE Finding SHALL include: file_path, line_number, detection_category="Password", confidence_score, masked_preview

**Detector 4: PII**

10. WHEN THE Detector scans a file, THE PII_Detector SHALL identify Personally Identifiable Information
11. THE PII_Detector SHALL detect email addresses matching pattern: [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
12. THE PII_Detector SHALL detect phone numbers matching pattern: (\+\d{1,3}[-.\s]?)?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}
13. WHEN PII is detected, THE Finding SHALL include: file_path, line_number, detection_category="PII", confidence_score, masked_preview

**Detector 5: Private Keys**

14. WHEN THE Detector scans a file, THE Private_Key_Detector SHALL identify private encryption keys
15. THE Private_Key_Detector SHALL match patterns: BEGIN PRIVATE KEY, BEGIN RSA PRIVATE KEY, BEGIN DSA PRIVATE KEY, BEGIN EC PRIVATE KEY
16. WHEN a private key is detected, THE Finding SHALL include: file_path, line_number, detection_category="Private Key", confidence_score, masked_preview

**Additional Detectors**

17. WHEN THE Detector scans a file, THE JWT_Detector SHALL identify JWT tokens matching pattern: eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.
18. WHEN THE Detector scans a file, THE Hardcoded_IP_Detector SHALL identify hardcoded IPv4 addresses in patterns like ip=, IP=, ipaddress=
19. WHEN a JWT or hardcoded IP is detected, THE Finding SHALL include: file_path, line_number, detection_category, confidence_score, masked_preview

**General Finding Requirements**

20. THE Finding record SHALL never store the complete secret value; only a masked preview (first 4 and last 4 characters visible, middle masked with *)
21. WHEN a Finding is created, THE confidence_score SHALL be set based on regex match precision (0-100)
22. THE confidence_score for exact pattern matches SHALL be 90-100
23. THE confidence_score for fuzzy pattern matches SHALL be 60-89
24. THE confidence_score for weak pattern matches SHALL be 40-59

---

### Requirement 5: Risk Scoring (Phase 4)

**User Story:** As an analyst, I want each finding to have a risk score that guides prioritization, so that I focus on the most critical secrets first.

#### Acceptance Criteria

1. WHEN a Finding is created, THE Risk_Calculator SHALL compute Risk_Score using formula: Risk_Score = (Sensitivity × Exposure × Confidence) / 100
2. THE Sensitivity value SHALL be assigned based on finding type:
   - Private Keys: 100
   - Database URLs: 90
   - API Keys: 85
   - Passwords: 80
   - JWT Tokens: 70
   - Hardcoded IPs: 50
   - PII: 40
3. THE Exposure value SHALL be assigned based on file location:
   - Configuration files (.env, .json config, .yaml): 100
   - Log files (.log, .txt): 60
   - Source code (.py, .js, .sql): 40
4. THE Confidence value is derived from the detector regex match precision (0-100), already assigned during detection
5. THE Severity level SHALL be mapped from Risk_Score as follows:
   - Risk_Score 1-20: Severity = "Low"
   - Risk_Score 21-50: Severity = "Medium"
   - Risk_Score 51-90: Severity = "High"
   - Risk_Score 91-125: Severity = "Critical"
6. WHEN Risk_Score is calculated, THE Finding record SHALL include: risk_score, severity, sensitivity, exposure, confidence

---

### Requirement 6: Finding Persistence & Dashboard (Phase 5)

**User Story:** As a user, I want my scan findings persisted and visible on a dashboard, so that I can review and track detected secrets over time.

#### Acceptance Criteria

1. WHEN a scan completes, THE Backend SHALL create a ScanLog record with: user_id, scan_date, file_count, total_findings_count, scan_status="Completed"
2. WHEN a Finding is detected, THE Backend SHALL create a Finding record with: scan_log_id, file_path, line_number, category, confidence_score, masked_preview, risk_score, severity, created_at
3. WHEN an Analyst accesses the dashboard, THE Dashboard SHALL display all Findings from scans initiated by that Analyst
4. WHEN an Admin accesses the dashboard, THE Dashboard SHALL display all Findings from all users in the system
5. THE Dashboard SHALL display each Finding with columns: category, file_path, line_number, masked_preview, risk_score, severity, status, last_modified_at
6. THE Dashboard SHALL sort Findings by risk_score in descending order by default
7. THE Dashboard SHALL allow filtering by: severity, status, category, date_range
8. THE Dashboard SHALL include a "Scan History" section showing previous scans with: scan_date, file_count, total_findings_count, findings_count_by_severity
9. THE Dashboard SHALL allow users to select a scan from history to view its associated Findings

---

### Requirement 7: Finding Status Management (Phase 6)

**User Story:** As an analyst, I want to manage finding status to track remediation progress, so that I can update the system as secrets are addressed.

#### Acceptance Criteria

1. WHEN a Finding is created, THE initial status SHALL be "Open"
2. THE System SHALL support the following status values: "Open", "In Review", "Resolved", "False Positive"
3. WHEN an Analyst updates a Finding's status, THE change SHALL only be permitted if the Analyst created the scan that generated the Finding
4. WHEN an Admin updates a Finding's status, THE change SHALL be permitted on any Finding regardless of ownership
5. WHEN a Finding's status is updated, THE Backend SHALL create an audit record with: finding_id, user_id, old_status, new_status, changed_at
6. IF a non-owning Analyst attempts to update a Finding status, THE Backend SHALL return a 403 Forbidden response
7. THE Dashboard SHALL display a status dropdown/selector for each Finding, enabling inline status updates

---

### Requirement 8: Audit Logging (Phase 7)

**User Story:** As a security administrator, I want comprehensive audit logs of all system actions, so that I can track user activity and investigate security incidents.

#### Acceptance Criteria

1. WHEN a user uploads a file, THE Backend SHALL create an AuditLog record with: user_id, action="Upload Started", target_resource="file", timestamp, details (file_name, file_size)
2. WHEN a scan completes, THE Backend SHALL create an AuditLog record with: user_id, action="Scan Completed", target_resource="scan_log", timestamp, details (scan_log_id, findings_count)
3. WHEN a user views a Finding, THE Backend SHALL create an AuditLog record with: user_id, action="Finding Viewed", target_resource="finding", timestamp, details (finding_id)
4. WHEN a user updates a Finding's status, THE Backend SHALL create an AuditLog record with: user_id, action="Status Changed", target_resource="finding", timestamp, details (finding_id, old_status, new_status)
5. WHEN an Admin accesses the audit log viewer, THE Audit_Log_Viewer SHALL display all AuditLog records with: user_id, action, target_resource, timestamp
6. THE Audit_Log_Viewer SHALL support filtering by: user_id, action, date_range, target_resource
7. THE Audit_Log_Viewer SHALL be accessible only to Admin users; other users receive a 403 Forbidden response
8. WHEN a non-Admin user attempts to access the audit log viewer, THE Backend SHALL return a 403 Forbidden response and log this attempt

---

### Requirement 9: Scan History & Reports

**User Story:** As a user, I want to view my previous scans and export findings, so that I can maintain records and share results with team members.

#### Acceptance Criteria

1. WHEN an Analyst accesses the Scan History page, THE System SHALL display all ScanLog records initiated by that Analyst
2. WHEN an Admin accesses the Scan History page, THE System SHALL display all ScanLog records from all users
3. WHEN viewing Scan History, THE System SHALL display: scan_date, file_count, total_findings_count, findings_by_severity_breakdown, scan_status
4. WHEN an Analyst clicks on a scan in history, THE System SHALL load and display all Findings associated with that scan
5. WHEN a user clicks "Export as CSV", THE System SHALL generate a CSV file containing all displayed Findings with columns: file_path, line_number, category, risk_score, severity, status, detected_at
6. WHEN a user clicks "Export as PDF", THE System SHALL generate a PDF report containing: scan_summary, findings_table, timestamp
7. WHEN an Analyst exports findings, THE export SHALL include only findings from scans they initiated
8. WHEN an Admin exports findings, THE export SHALL include findings from all scans or filtered scans based on applied filters

---

### Requirement 10: Cross-Cutting - Authentication & Authorization (RBAC)

**User Story:** As a system administrator, I want to enforce role-based access control across all features, so that users only access data and operations appropriate to their role.

#### Acceptance Criteria

1. WHEN a user makes any API request, THE Backend SHALL verify the user's authentication token (JWT)
2. IF the authentication token is missing or invalid, THE Backend SHALL return a 401 Unauthorized response
3. WHEN THE Backend receives a 401 response, THE Frontend SHALL redirect the user to the login page and clear the AuthContext
4. THE Backend SHALL enforce RBAC on all endpoints requiring authentication
5. THE Backend SHALL verify that an Analyst can only view/manage findings from scans they created
6. THE Backend SHALL verify that an Admin can view/manage all findings and access all admin features
7. WHEN a user with insufficient permissions attempts to access a protected endpoint, THE Backend SHALL return a 403 Forbidden response
8. THE User_Role is stored in the JWT token and extracted by THE Backend on each request
9. THE Frontend SHALL use the User_Role from AuthContext to conditionally render admin-only UI elements (e.g., Audit Log Viewer, System-Wide Dashboard)

---

### Requirement 11: Cross-Cutting - File Lifecycle

**User Story:** As a user, I want uploaded files to be securely deleted after processing, so that sensitive file contents are not retained on disk.

#### Acceptance Criteria

1. WHEN a file is uploaded and extracted, THE Backend SHALL process the file and store all findings in the database
2. AFTER scan processing completes, THE Backend SHALL delete all extracted files from the filesystem
3. THE Backend SHALL not retain any uploaded file content on disk after processing
4. IF uploaded files remain on disk beyond 48 hours (e.g., due to processing failures), THE Background_Job_Scheduler SHALL automatically delete them
5. THE Backend SHALL log all file deletion operations to the AuditLog

---

### Requirement 12: Cross-Cutting - Finding Masking

**User Story:** As a security professional, I want secret values masked in the database, so that database administrators cannot view complete secrets.

#### Acceptance Criteria

1. WHEN a Finding is created, THE masked_preview SHALL contain only the first 4 and last 4 characters of the detected secret, with the middle portion masked with asterisks
2. WHEN THE Complete secret value is never stored in the Finding record or any log
3. WHEN a Finding's masked_preview is displayed to a user, THE user SHALL see only the masked format
4. IF an Analyst or Admin needs to verify a secret, THE System SHALL provide a way to view the full secret only by comparing against the original uploaded file content (temporarily loaded into memory)

---

### Requirement 13: Cross-Cutting - Session Management

**User Story:** As a security administrator, I want sessions to expire after inactivity, so that inactive sessions don't pose a security risk.

#### Acceptance Criteria

1. WHEN a user logs in, THE Backend SHALL create a session with a 1-hour inactivity timeout
2. WHEN a user makes any authenticated request, THE inactivity timeout SHALL be reset
3. WHEN the inactivity timeout expires, THE session SHALL become invalid
4. WHEN a user attempts to make a request with an expired session, THE Backend SHALL return a 401 Unauthorized response
5. WHEN THE Frontend receives a 401 response, THE Frontend SHALL clear the AuthContext and redirect to the login page
6. THE Frontend SHALL optionally display an inactivity warning 5 minutes before session expiration

---

## Edge Cases and Error Handling

### Upload Validation Edge Cases

- User uploads a file with double extension (.sql.gz): THE System SHALL validate based on the final extension (.gz)
- User uploads a ZIP containing another ZIP: THE System SHALL extract recursively up to 3 levels deep
- User uploads a ZIP with a symbolic link: THE System SHALL skip symbolic links and log a warning
- User uploads a file with special characters in filename: THE System SHALL sanitize the filename and process the file

### Detection Engine Edge Cases

- A line contains multiple secrets: THE Backend SHALL create separate Finding records for each detected secret
- A secret spans multiple lines (e.g., multi-line private key): THE Backend SHALL capture the starting line number and include a note that the finding spans multiple lines
- A file contains false positive patterns (e.g., "password_field" in code comments): THE System SHALL assign low confidence scores; users can mark as "False Positive"
- Empty or binary files are uploaded: THE Backend SHALL skip processing and log a warning

### Risk Scoring Edge Cases

- Risk_Score calculation results in a value > 125: THE System SHALL cap the score at 125 and assign Severity="Critical"
- Risk_Score calculation results in a decimal: THE System SHALL round to the nearest integer

### Authorization Edge Cases

- A deleted user's scan findings still exist: THE Dashboard SHALL continue to display findings (user_id is retained as historical data)
- An Analyst is promoted to Admin role: THE Frontend SHALL reflect the new role after the next page reload or AuthContext refresh
- Multiple rapid status updates on the same Finding: THE Backend SHALL process updates sequentially and maintain an ordered audit trail

---

## Non-Functional Requirements

1. THE System SHALL provide findings within 30 seconds for files up to 10MB
2. THE Frontend SHALL be responsive on devices with screen widths from 320px (mobile) to 1920px (desktop)
3. THE Backend SHALL support concurrent uploads from at least 10 simultaneous users
4. THE System SHALL store audit logs indefinitely for compliance purposes
5. THE System SHALL encrypt sensitive data at rest (database passwords, masked secrets)
6. THE System SHALL use HTTPS for all network communications
7. THE Frontend AND Backend SHALL follow WCAG 2.1 Level AA accessibility standards

---

## Out of Scope (Future Phases)

The following features are explicitly out of scope for this release:

- Machine Learning-based detection models
- Entropy-based secret detectors
- Real-time file monitoring on user systems
- Cloud storage integration (AWS S3, Google Cloud Storage, Azure Blob)
- Custom detection rule builder
- Allowlisting/whitelisting of false positives
- Integration with external DLP systems
- Bulk operations on findings
- Scheduled automated scans
- API for third-party integrations

