# DataGhost API Reference

Complete endpoint documentation with request/response examples.

**Base URL:** `http://localhost:8000` (dev) or `https://api.dataghost.com` (production)

All endpoints require JWT authentication (except `/api/auth/login`).

---

## Table of Contents

1. [Authentication](#authentication)
2. [File Scanner](#file-scanner)
3. [Incidents](#incidents)
4. [Dashboard](#dashboard)
5. [Analytics](#analytics)
6. [Devices](#devices)
7. [Device Enrollment](#device-enrollment)
8. [Error Responses](#error-responses)

---

## Authentication

### POST /api/auth/login

Login with username and password. Returns a JWT access token.

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "dataghost123"
  }'
```

**Request Body:**
```json
{
  "username": "string (required, 3-128 chars)",
  "password": "string (required, 8-128 chars)"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTcwNTMyODAwMCwiaWF0IjoxNzA1MjQxNjAwfQ.abcdefg...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Invalid credentials",
  "status": 401,
  "timestamp": "2024-01-15T10:30:45Z"
}
```

---

### GET /api/auth/me

Get the current authenticated user's profile.

**Request:**
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <access_token>"
```

**Response (200 OK):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@dataghost.local",
  "role": "admin",
  "is_active": true,
  "created_at": "2024-01-15T10:00:00Z"
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated",
  "status": 401
}
```

---

### POST /api/auth/logout

Logout the current user (clears session).

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

**Response (200 OK):**
```json
{
  "message": "Logged out successfully",
  "timestamp": "2024-01-15T10:30:45Z"
}
```

---

## File Scanner

### POST /api/scanner/scan

Upload and scan a file. The backend will:
1. Extract text (PDF, DOCX, TXT)
2. Run 16 DLP rules (regex patterns)
3. Run ML classification (PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED)
4. Compute risk score (0-100)
5. Determine action (ALLOW/ALERT/RESTRICT/BLOCK)
6. Create incident record

**Request:**
```bash
curl -X POST http://localhost:8000/api/scanner/scan \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@customer_data.txt" \
  -F "source=web"
```

**Request Body (multipart/form-data):**
- `file` (required): Binary file (PDF, DOCX, TXT, DOC)
- `source` (optional): "web", "agent", "api" (default: "web")

**Response (200 OK):**
```json
{
  "incident_id": "DG-2024-0042",
  "file_id": 123,
  "filename": "customer_data.txt",
  "file_hash": "abc123def456...",
  "size_bytes": 2048,
  "risk_score": 94,
  "risk_level": "CRITICAL",
  "classification": "CONFIDENTIAL",
  "status": "new",
  "action_taken": "BLOCK",
  "findings_count": 5,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "File size exceeds 50MB limit",
  "status": 400
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated",
  "status": 401
}
```

---

### GET /api/scanner/history

Get file scan history with pagination.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/scanner/history?limit=20&offset=0&days=7" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**
- `limit` (optional): Results per page (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `days` (optional): Show scans from last N days (default: 30)

**Response (200 OK):**
```json
{
  "total": 156,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "file_id": 123,
      "filename": "customer_data.txt",
      "file_hash": "abc123def456...",
      "size_bytes": 2048,
      "uploaded_at": "2024-01-15T10:30:00Z",
      "uploaded_by": "admin",
      "incident_count": 1,
      "latest_risk": "CRITICAL"
    },
    {
      "file_id": 122,
      "filename": "quarterly_report.pdf",
      "file_hash": "xyz789abc123...",
      "size_bytes": 1024000,
      "uploaded_at": "2024-01-14T14:20:00Z",
      "uploaded_by": "analyst",
      "incident_count": 0,
      "latest_risk": null
    }
  ]
}
```

---

## Incidents

### GET /api/incidents/

List incidents with advanced filtering and pagination.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/incidents/?status=new&risk_level=CRITICAL&days=7&limit=50&offset=0" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**
- `status` (optional): `new`, `reviewing`, `resolved`, `archived`
- `risk_level` (optional): `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
- `days` (optional): Show incidents from last N days (default: 7)
- `device_id` (optional): Filter by device
- `limit` (optional): Results per page (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response (200 OK):**
```json
{
  "total": 156,
  "filtered": 12,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": 1,
      "incident_id": "DG-2024-0042",
      "file_id": 123,
      "filename": "customer_data.txt",
      "user_id": 1,
      "username": "admin",
      "device_id": "DEVICE-001",
      "status": "new",
      "risk_score": 94,
      "risk_level": "CRITICAL",
      "classification": "CONFIDENTIAL",
      "action_taken": "BLOCK",
      "findings_count": 5,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### GET /api/incidents/{id}

Get detailed incident information including all findings.

**Request:**
```bash
curl -X GET http://localhost:8000/api/incidents/1 \
  -H "Authorization: Bearer <access_token>"
```

**Response (200 OK):**
```json
{
  "id": 1,
  "incident_id": "DG-2024-0042",
  "file_id": 123,
  "filename": "customer_data.txt",
  "size_bytes": 2048,
  "user_id": 1,
  "username": "admin",
  "device_id": "DEVICE-001",
  "status": "new",
  "risk_score": 94,
  "risk_level": "CRITICAL",
  "classification": "CONFIDENTIAL",
  "action_taken": "BLOCK",
  "findings": [
    {
      "type": "email",
      "match": "john.doe@example.com",
      "line": 5,
      "confidence": 0.99,
      "severity": "MEDIUM"
    },
    {
      "type": "credit_card",
      "match": "4532-1234-5678-****",
      "line": 12,
      "confidence": 0.95,
      "severity": "CRITICAL"
    },
    {
      "type": "aadhaar",
      "match": "2345 6789 0123",
      "line": 8,
      "confidence": 0.92,
      "severity": "HIGH"
    },
    {
      "type": "pan_card",
      "match": "ABCDE1234F",
      "line": 10,
      "confidence": 0.98,
      "severity": "HIGH"
    },
    {
      "type": "api_key",
      "match": "apikey=sk_live_4eC39HqLy....",
      "line": 3,
      "confidence": 0.87,
      "severity": "CRITICAL"
    }
  ],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Incident not found",
  "status": 404
}
```

---

### PATCH /api/incidents/{id}

Update incident status or add notes.

**Request:**
```bash
curl -X PATCH http://localhost:8000/api/incidents/1 \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved",
    "notes": "False positive - test data"
  }'
```

**Request Body:**
```json
{
  "status": "string (new, reviewing, resolved, archived)",
  "notes": "string (optional, max 1000 chars)"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "incident_id": "DG-2024-0042",
  "status": "resolved",
  "notes": "False positive - test data",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

---

### DELETE /api/incidents/{id}

Delete (hard-delete) an incident.

**Request:**
```bash
curl -X DELETE http://localhost:8000/api/incidents/1 \
  -H "Authorization: Bearer <access_token>"
```

**Response (204 No Content):**
```
(empty response body)
```

---

## Dashboard

### GET /api/dashboard/stats

Get dashboard summary statistics.

**Request:**
```bash
curl -X GET http://localhost:8000/api/dashboard/stats \
  -H "Authorization: Bearer <access_token>"
```

**Response (200 OK):**
```json
{
  "total_incidents": 156,
  "critical_risk": 12,
  "high_risk": 23,
  "medium_risk": 45,
  "low_risk": 76,
  "avg_risk_score": 62,
  "new_today": 8,
  "resolved_today": 3,
  "status_breakdown": {
    "new": 45,
    "reviewing": 67,
    "resolved": 38,
    "archived": 6
  },
  "classification_breakdown": {
    "public": 76,
    "internal": 45,
    "confidential": 23,
    "restricted": 12
  },
  "action_breakdown": {
    "allow": 76,
    "alert": 45,
    "restrict": 23,
    "block": 12
  },
  "top_risk_types": [
    { "type": "credit_card", "count": 34, "avg_confidence": 0.94 },
    { "type": "email", "count": 28, "avg_confidence": 0.99 },
    { "type": "aadhaar", "count": 22, "avg_confidence": 0.91 }
  ]
}
```

---

### GET /api/dashboard/recent

Get 5-10 most recent HIGH/CRITICAL incidents.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/dashboard/recent?limit=10" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**
- `limit` (optional): Number of recent incidents to return (default: 5, max: 20)

**Response (200 OK):**
```json
{
  "incidents": [
    {
      "id": 1,
      "incident_id": "DG-2024-0042",
      "filename": "customer_data.txt",
      "risk_score": 94,
      "risk_level": "CRITICAL",
      "status": "new",
      "created_at": "2024-01-15T10:30:00Z",
      "username": "admin",
      "device_id": "DEVICE-001"
    }
  ]
}
```

---

## Analytics

### GET /api/analytics/trends

Get time-series incident trend data for the specified period.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/analytics/trends?days=7" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**
- `days` (optional): Number of days to return (default: 7, max: 90)

**Response (200 OK):**
```json
{
  "period_days": 7,
  "data": [
    {
      "date": "2024-01-09",
      "total_incidents": 12,
      "critical": 2,
      "high": 3,
      "medium": 5,
      "low": 2
    },
    {
      "date": "2024-01-10",
      "total_incidents": 18,
      "critical": 4,
      "high": 8,
      "medium": 5,
      "low": 1
    },
    {
      "date": "2024-01-11",
      "total_incidents": 14,
      "critical": 1,
      "high": 5,
      "medium": 6,
      "low": 2
    }
  ]
}
```

---

### GET /api/analytics/risk-distribution

Get risk level distribution across all incidents.

**Request:**
```bash
curl -X GET http://localhost:8000/api/analytics/risk-distribution \
  -H "Authorization: Bearer <access_token>"
```

**Response (200 OK):**
```json
{
  "critical": 12,
  "high": 23,
  "medium": 45,
  "low": 76,
  "total": 156
}
```

---

### GET /api/analytics/top-findings

Get the top detected data types by frequency.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/analytics/top-findings?limit=10" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**
- `limit` (optional): Number of top types to return (default: 10)

**Response (200 OK):**
```json
{
  "findings": [
    {
      "type": "credit_card",
      "count": 45,
      "avg_confidence": 0.94,
      "severity": "CRITICAL"
    },
    {
      "type": "email",
      "count": 38,
      "avg_confidence": 0.99,
      "severity": "MEDIUM"
    },
    {
      "type": "aadhaar",
      "count": 28,
      "avg_confidence": 0.91,
      "severity": "HIGH"
    },
    {
      "type": "pan_card",
      "count": 22,
      "avg_confidence": 0.98,
      "severity": "HIGH"
    },
    {
      "type": "api_key",
      "count": 18,
      "avg_confidence": 0.87,
      "severity": "CRITICAL"
    }
  ]
}
```

---

## Devices

### GET /api/devices/

List all monitored endpoint devices.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/devices/?limit=50&offset=0" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**
- `limit` (optional): Results per page (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response (200 OK):**
```json
{
  "total": 5,
  "devices": [
    {
      "id": 1,
      "device_id": "DEVICE-001",
      "hostname": "workstation-01",
      "os": "Windows 10",
      "agent_version": "1.0.0",
      "agent_status": "active",
      "last_seen": "2024-01-15T11:20:00Z",
      "incident_count": 12
    },
    {
      "id": 2,
      "device_id": "DEVICE-002",
      "hostname": "macbook-pro",
      "os": "macOS 13.0",
      "agent_version": "1.0.0",
      "agent_status": "active",
      "last_seen": "2024-01-15T11:18:00Z",
      "incident_count": 5
    },
    {
      "id": 3,
      "device_id": "DEVICE-003",
      "hostname": "ubuntu-server",
      "os": "Ubuntu 22.04",
      "agent_version": "1.0.0",
      "agent_status": "inactive",
      "last_seen": "2024-01-14T08:30:00Z",
      "incident_count": 0
    }
  ]
}
```

---

### GET /api/devices/{device_id}/incidents

Get all incidents from a specific device.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/devices/DEVICE-001/incidents?limit=50" \
  -H "Authorization: Bearer <access_token>"
```

**Response (200 OK):**
```json
{
  "device_id": "DEVICE-001",
  "hostname": "workstation-01",
  "total_incidents": 12,
  "items": [
    {
      "id": 1,
      "incident_id": "DG-2024-0042",
      "filename": "customer_data.txt",
      "risk_score": 94,
      "status": "new",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## Device Enrollment

### Android Enterprise DPC (Recommended Primary Flow)

Automatic device enrollment using official Android Enterprise Device Policy Controller (DPC) provisioning. **No security bypasses, no silent permission grants—uses only official Android provisioning.**

**Enrollment Flow:**
1. Admin generates enrollment QR via backend
2. Device reset to factory settings
3. Setup wizard: tap screen 6× quickly
4. "Set up with QR code" → scan QR
5. Android system validates DPC manifest
6. DPC downloads automatically from signed APK checksum
7. DPC extracts enrollment token, registers with backend
8. Backend returns ACTIVE device status
9. WorkManager schedules heartbeat every 15 minutes

**Prerequisites:**
- Android device with "Tap to Set Up" enabled (most devices)
- Android Enterprise account with Google Workspace / Azure AD
- Device must reach backend endpoint to download DPC APK

---

### POST /api/devices/enrollment/create-android-enterprise

Generate a DataGhost Android Enterprise enrollment QR code (Automatic Enrollment).

**Request:**
```bash
curl -X POST http://localhost:8000/api/devices/enrollment/create-android-enterprise \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "Android",
    "organization_id": "acme-corp"
  }'
```

**Request Body:**
```json
{
  "platform": "string (required: 'Android')",
  "organization_id": "string (optional: for multi-tenant support)"
}
```

**Response (200 OK):**
```json
{
  "enrollment_code": "DG-AB12-CD34",
  "raw_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "platform": "Android",
  "server_url": "https://api.dataghost.com",
  "qr_data": {
    "version": "1.0",
    "server_url": "https://api.dataghost.com",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "code": "DG-AB12-CD34",
    "platform": "Android",
    "expires_at": "2024-01-15T00:15:00Z",
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": "com.dataghost.agent/com.dataghost.agent.enrollment.DataGhostDeviceAdminReceiver",
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": "https://api.dataghost.com/dataghost-agent.apk",
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM": "oEK0v2z9Hsw3DZ8FzCP1m8XQAx4kymZ-uFSGS9Py7LY",
    "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": false,
    "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
      "com.dataghost.SERVER_URL": "https://api.dataghost.com",
      "com.dataghost.ENROLLMENT_TOKEN": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "com.dataghost.ENROLLMENT_CODE": "DG-AB12-CD34",
      "com.dataghost.EXPIRES_AT": "2024-01-15T00:15:00Z"
    }
  },
  "qr_code_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "expires_at": "2024-01-15T00:15:00Z",
  "expires_in_seconds": 900,
  "status": "PENDING"
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Invalid platform. Must be 'Android'.",
  "status": 400
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated",
  "status": 401
}
```

---

### POST /api/devices/enrollment/register

Register a device after successful DPC provisioning. Called by the DataGhostDeviceAdminReceiver after QR scan and APK installation.

**Authentication:** Uses enrollment token (bearer token in Authorization header)

**Request:**
```bash
curl -X POST http://localhost:8000/api/devices/enrollment/register \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "enrollment_code": "DG-AB12-CD34",
    "device_model": "Pixel 8",
    "android_version": "14",
    "imei": "358240051111110"
  }'
```

**Request Body:**
```json
{
  "enrollment_code": "string (required: must match QR)",
  "device_model": "string (optional: device model from Build.MODEL)",
  "android_version": "string (optional: Android API level)",
  "imei": "string (optional: device identifier)"
}
```

**Response (200 OK):**
```json
{
  "device_id": "DG-DEVICE-001",
  "status": "ACTIVE",
  "enrollment_code": "DG-AB12-CD34",
  "auth_token": "device_auth_token_here",
  "enrolled_at": "2024-01-15T00:00:00Z",
  "server_url": "https://api.dataghost.com",
  "heartbeat_interval_seconds": 900,
  "message": "Device registered successfully. Heartbeat scheduled."
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Enrollment token expired",
  "status": 400
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Invalid enrollment token",
  "status": 401
}
```

**Response (409 Conflict):**
```json
{
  "detail": "Enrollment token already used",
  "status": 409
}
```

---

### GET /api/devices/enrollment/status/{enrollment_code}

Poll enrollment status from the device. Used by the frontend to show real-time enrollment progress.

**Request:**
```bash
curl -X GET http://localhost:8000/api/devices/enrollment/status/DG-AB12-CD34 \
  -H "Authorization: Bearer <access_token>"
```

**Response (200 OK) - PENDING:**
```json
{
  "enrollment_code": "DG-AB12-CD34",
  "status": "PENDING",
  "message": "Waiting for device to scan QR code"
}
```

**Response (200 OK) - USED (Device Registered):**
```json
{
  "enrollment_code": "DG-AB12-CD34",
  "status": "USED",
  "device_name": "Pixel 8",
  "device_id": "DG-DEVICE-001",
  "registered_at": "2024-01-15T00:00:45Z",
  "message": "Device successfully enrolled"
}
```

**Response (200 OK) - EXPIRED:**
```json
{
  "enrollment_code": "DG-AB12-CD34",
  "status": "EXPIRED",
  "message": "Enrollment link expired. Generate a new QR code."
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Enrollment code not found",
  "status": 404
}
```

---

### GET /dataghost-agent.apk

Download the DataGhost DPC Agent APK. This endpoint is called by the Android system during DPC provisioning to validate the signature checksum and download the APK.

**Request:**
```bash
curl -X GET http://localhost:8000/dataghost-agent.apk \
  -H "Accept: application/vnd.android.package-archive"
```

**Response (200 OK):**
```
(Binary APK file)
```

**Response Headers:**
```
Content-Type: application/vnd.android.package-archive
Content-Length: 6721743
```

**Response (404 Not Found):**
```json
{
  "detail": "APK not found. Ensure backend/.env has SERVER_PUBLIC_URL configured.",
  "status": 404
}
```

---

### Easy Enrollment (Agent-Based, Fallback)

For BYOD scenarios or when automatic DPC provisioning is not available.

**Enrollment Flow:**
1. User downloads DataGhost Agent app from Play Store
2. Opens app → "Enroll Device"
3. Enters enrollment code (DG-XXXX-XXXX) or scans QR
4. Agent validates with backend
5. Creates Work Profile (if supported)
6. Registers and shows dashboard

---

### POST /api/devices/enrollment/create-easy

Generate an enrollment link for manual agent installation (Easy Enrollment).

**Request:**
```bash
curl -X POST http://localhost:8000/api/devices/enrollment/create-easy \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "Android",
    "profile_type": "WorkProfile"
  }'
```

**Request Body:**
```json
{
  "platform": "string (required: 'Android')",
  "profile_type": "string (optional: 'WorkProfile' or 'FullyManaged', default: 'WorkProfile')"
}
```

**Response (200 OK):**
```json
{
  "enrollment_code": "DG-XY78-ZW90",
  "raw_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "platform": "Android",
  "profile_type": "WorkProfile",
  "server_url": "https://api.dataghost.com",
  "instructions": {
    "step_1": "Download DataGhost Agent from Google Play Store",
    "step_2": "Open the app and tap 'Enroll Device'",
    "step_3": "Enter code: DG-XY78-ZW90",
    "step_4": "Follow on-screen prompts to create Work Profile",
    "step_5": "Device appears in dashboard within 30 seconds"
  },
  "expires_at": "2024-01-15T00:15:00Z",
  "expires_in_seconds": 900,
  "status": "PENDING"
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong",
  "status": 400,
  "timestamp": "2024-01-15T10:30:45Z"
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created |
| 204 | No Content | Deletion successful |
| 400 | Bad Request | Invalid input (missing field, wrong type) |
| 401 | Unauthorized | Missing or invalid JWT token |
| 403 | Forbidden | User lacks permission (RBAC) |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists |
| 422 | Unprocessable Entity | Validation error |
| 500 | Server Error | Unexpected backend error |

### Common Error Examples

**Missing Authentication:**
```json
{
  "detail": "Not authenticated",
  "status": 401
}
```

**Invalid Credentials:**
```json
{
  "detail": "Invalid credentials",
  "status": 401
}
```

**Permission Denied:**
```json
{
  "detail": "Insufficient permissions",
  "status": 403
}
```

**Invalid File Upload:**
```json
{
  "detail": "File type not allowed. Allowed: PDF, DOCX, TXT, DOC",
  "status": 400
}
```

**Validation Error:**
```json
{
  "detail": "Validation error",
  "errors": [
    {
      "field": "username",
      "message": "Username must be between 3 and 128 characters"
    }
  ],
  "status": 422
}
```

---

## Rate Limiting

Currently not implemented. Future versions will include:
- 1000 requests/hour per user
- 100 file uploads/hour per user
- Burst allowance: 20 requests/minute

---

## Pagination

List endpoints support pagination:

```bash
GET /api/incidents/?limit=50&offset=0
```

All list responses include:
```json
{
  "total": 156,
  "limit": 50,
  "offset": 0,
  "items": [...]
}
```

### Pagination Example

**Page 1:**
```bash
/api/incidents/?limit=50&offset=0  # Results 0-49
```

**Page 2:**
```bash
/api/incidents/?limit=50&offset=50  # Results 50-99
```

---

## Authentication Header

All endpoints (except `/api/auth/login`) require the JWT token in the `Authorization` header:

```bash
Authorization: Bearer <access_token>
```

**Example:**
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  http://localhost:8000/api/incidents/
```

Missing or invalid token returns `401 Unauthorized`.

---

## Response Timestamps

All timestamps are in ISO 8601 format (UTC):
```
2024-01-15T10:30:45Z
```

---

## OpenAPI / Swagger

Interactive API documentation available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

These are auto-generated from the FastAPI server and include request/response schemas and try-it-out functionality.

