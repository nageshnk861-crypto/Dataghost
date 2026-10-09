# DataGhost Device Enrollment Redesign - Implementation Plan

**Task ID:** task-enrollment-redesign  
**Status:** Pending Implementation  
**Features:** 6 independent, sequential FEATs  

---

## Overview

This plan implements zero-touch automatic device enrollment for DataGhost across Windows, Android, macOS, and iOS platforms. It also fixes critical Android NullPointerException crashes and adds admin dashboard pages for device provisioning and management.

The task decomposes into 6 separable features:
- **FEAT-001:** Backend ORM models for device provisioning and identity
- **FEAT-002:** Backend secure enrollment API endpoints (bootstrap, attest, complete, config, policy)
- **FEAT-003:** Android NPE crash fixes
- **FEAT-004:** Android managed app configuration support for zero-touch MDM
- **FEAT-005:** Frontend admin device management pages (provisioning, devices, policies)
- **FEAT-006:** Backend comprehensive tests and integration verification

---

## FEAT-001: Backend ORM Models for Device Provisioning

**Effort:** Medium | **Files:** backend/models.py, backend/database.py

### What to Do
Add three new SQLAlchemy ORM models and one Enum to backend/models.py to support secure device provisioning:

1. **EnrollmentState Enum** — Python Enum with 17 states (NEW, DISCOVERING_CONFIGURATION, CONFIGURATION_FOUND, AUTHENTICATING_DEVICE, ATTESTING_DEVICE, REGISTERING_DEVICE, ENROLLED, CONFIGURING_AGENT, POLICY_DOWNLOADED, ACTIVE, plus 6 failure states). String values for database compatibility.

2. **DeviceProvisioning Model** — Admin-created bulk device provisioning records:
   - id (PK), organizationId, enrollmentPolicyId, platform, status
   - provisioningMethod (AUTOMATIC_ENROLLMENT | QR_ENROLLMENT | MANUAL_CODE)
   - bootstrapTokenHash (SHA-256 hashed, never plaintext)
   - devicePublicKey, certificate, deviceCount
   - createdAt, expiresAt, lastUsedAt, revokedAt
   - Indexes on bootstrapTokenHash and organizationId

3. **DeviceIdentity Model** — Unique cryptographic identity per enrolled device:
   - id (PK), deviceId (unique, format: DG-DEVICE-XXXXXXXX)
   - platform, publicKey (PEM-encoded, server-side only), attestationData (JSON)
   - enrollmentCode (unique, format: DG-XXXX-XXXX), createdAt
   - Indexes on deviceId and enrollmentCode

4. **Device Model Updates** — Add optional columns to existing Device model:
   - publicKeyFingerprint (String 64, SHA-256 hash)
   - attestationStatus (String 32, default 'PENDING')
   - identityProvidedBy (String 32)
   - cryptoAlgorithm (String 32, default 'RSA-2048')

### Database Migration
Update backend/database.py init_db() function to safely add new tables and columns:
- Create DeviceProvisioning and DeviceIdentity tables
- Add new columns to Device table using ALTER TABLE ADD COLUMN
- Check IF EXISTS to prevent errors on re-runs
- Test non-destructive migration on existing database

### Verification
```bash
cd backend
python -m pytest tests/ -v -k model
python -c 'from database import init_db; from models import EnrollmentState, DeviceProvisioning, DeviceIdentity; init_db(); print("Models OK")'
sqlite3 dataghost.db '.schema device_provisioning'
sqlite3 dataghost.db '.schema device_identity'
```

---

## FEAT-002: Backend Enrollment API Endpoints

**Effort:** High | **Files:** backend/api/enrollment_routes.py, backend/api/router.py

### What to Do
Create new file c:\\Users\\ARUN\\Desktop\\dataghost\\backend\\api\\enrollment_routes.py with 6 endpoints under prefix `/device-enrollment` (will be mounted at `/api/v1/device-enrollment` in main.py):

#### 1. POST /bootstrap
- **Auth:** Bearer token (raw bootstrap token, single-use)
- **Body:** { platform, deviceModel, osVersion, deviceSerialNumber }
- **Returns:** { serverUrl, organizationId, enrollmentPolicy, deviceIdentityPublicKey }
- **Security:** Token consumed immediately, second call returns 401 (replay prevention)
- **Action:** Mark token as CONSUMED_BOOTSTRAP

#### 2. POST /attest
- **Auth:** Bearer deviceToken (issued during bootstrap)
- **Body:** { platform, attestationData, devicePublicKey }
- **Returns:** { attestationValid: bool, deviceToken (refreshed) }
- **Action:** Validate platform-provided attestation (Android SafetyNet stub, iOS DeviceCheck stub, Windows TPM stub)

#### 3. POST /complete
- **Auth:** Bearer deviceToken
- **Body:** { deviceId, platform, publicKey, enrollmentCode }
- **Returns:** { deviceId: DG-DEVICE-XXXXXXXX, status: ACTIVE, heartbeatIntervalSeconds: 30 }
- **Action:** Create Device record, assign permanent ID, update EnrollmentState to ACTIVE, store public key fingerprint

#### 4. GET /configuration
- **Auth:** Bearer deviceToken
- **Returns:** { organizationId, policyId, dlpRules, serverUrl, heartbeatInterval }
- **Action:** Return device configuration, allows device to discover its settings after enrollment

#### 5. GET /policy
- **Auth:** Bearer deviceToken
- **Returns:** { policyId, rules: [], configurations }
- **Action:** Return full DLP policy rules for device to execute locally

#### 6. Helper Functions
- `_validate_attestation(platform, attestation_data, public_key)` — Platform-specific validation (stubs for now)
- `_consume_token(token, db)` — Mark token as used, return enrollment record or raise 401
- `_generate_device_id(platform, db)` — Generate unique DG-{platform}-{hex} identifier

### Requirements
- All endpoints require Bearer token authentication
- Bootstrap token is single-use, expires after first call
- No plaintext secrets in logs or responses
- Comprehensive logging of all enrollment steps
- Mount router in backend/api/router.py with include_router()

### Verification
```bash
cd backend
pytest tests/test_enrollment.py -v
# Test bootstrap with valid token
curl -H 'Authorization: Bearer <token>' http://localhost:8000/api/v1/device-enrollment/bootstrap -X POST
# Verify token consumed: second call returns 401
# Verify /complete creates Device in DB
# Check Swagger: http://localhost:8000/docs
```

---

## FEAT-003: Android NPE Crash Fixes

**Effort:** Medium | **Files:** 4 Kotlin files in mobile/android/app/src/main/java/com/dataghost/agent/

### What to Do
Fix 4 critical NullPointerException crashes by applying Kotlin null-safety patterns:

#### 1. EnrollmentActivity.kt
- Validate all UI element references exist after layout creation
- Replace direct access with safe operators: `serverUrlInput?.text?.toString() ?: ''`
- Fix startHeartbeatAfterEnrollment() cast:
  ```kotlin
  val app = applicationContext as? DataGhostApp
  app?.startHeartbeatAfterEnrollment() ?: Unit
  ```

#### 2. AdminPolicyComplianceActivity.kt
- Wrap applicationContext cast in explicit null check:
  ```kotlin
  val app = context.applicationContext as? DataGhostApp
  if (app != null) app.startHeartbeatAfterEnrollment()
  else Log.w(TAG, "App instance not available")
  ```
- Check manager result and response fields before accessing

#### 3. DataGhostDeviceAdminReceiver.kt (line 168)
- Replace safe cast chain with explicit check:
  ```kotlin
  val app = context.applicationContext as? DataGhostApp
  if (app != null) app.startHeartbeatAfterEnrollment()
  else Log.e(TAG, "Failed to initialize heartbeat")
  ```

#### 4. EnrollmentManager.kt
- Validate API response fields in registerDevice():
  ```kotlin
  response.deviceId?.let { id -> /* use id */ } 
    ?: run { Log.e(...); throw NullPointerException(...) }
  ```
- Check deviceId, authToken, serverUrl, heartbeatIntervalSeconds all non-null

### Verification
```bash
cd mobile/android
./gradlew assembleDebug
./gradlew testDebugUnitTest -v
# Manual test on emulator: enrollment flow should not crash
adb logcat | grep -i 'nullpointer'  # Should show 0 results
```

---

## FEAT-004: Android Managed Configuration Support

**Effort:** High | **Files:** 5 Kotlin files in mobile/android/app/src/main/java/com/dataghost/agent/

### What to Do
Add managed app configuration (RestrictionsManager) support for zero-touch MDM enrollment:

#### 1. Create ManagedConfigHelper.kt
```kotlin
fun readManagedConfig(context: Context): ManagedConfigData? {
  // Read RestrictionsManager with keys:
  // - com.dataghost.organization_id
  // - com.dataghost.server_url
  // - com.dataghost.bootstrap_token
  // - com.dataghost.enrollment_code
  // Validate all fields non-null, serverUrl starts with https://
  // Return ManagedConfigData or null if missing/invalid
}
```

#### 2. Create ManagedConfigData.kt
```kotlin
data class ManagedConfigData(
  val organizationId: String,
  val serverUrl: String,
  val bootstrapToken: String,
  val enrollmentCode: String
) {
  init {
    require(organizationId.isNotEmpty()) { "organizationId required" }
    require(serverUrl.startsWith("https://")) { "serverUrl must be HTTPS" }
    require(bootstrapToken.isNotEmpty()) { "bootstrapToken required" }
  }
}
```

#### 3. Update EnrollmentActivity.kt
- On onCreate, read managed config: `ManagedConfigHelper.readManagedConfig(this)`
- If config valid and present:
  - Auto-populate serverUrlInput and codeInput
  - Show toast: "Enrollment configured by administrator"
  - Optionally auto-start enrollment (with user confirmation)
- If config missing/invalid, show manual enrollment UI as before

#### 4. Update EnrollmentManager.kt
- Add `bootstrapToken` parameter to bootstrap() method
- If bootstrapToken provided (from managed config), use it directly
- If not provided, use token from enrollment code lookup (existing flow)
- Log whether bootstrap token came from managed config or manual entry

#### 5. Update DataGhostApp.kt
- On first app start (check SharedPreferences FIRST_RUN flag):
  - Call ManagedConfigHelper.readManagedConfig()
  - If config valid, pre-initialize enrollment parameters
  - Store in SharedPreferences
  - Set skipManualEnrollmentUI = true

### AndroidManifest.xml
- Ensure MANAGE_APP_CONFIGURATIONS permission is declared

### Verification
```bash
cd mobile/android
./gradlew assembleDebug
./gradlew testDebugUnitTest -v
# Manual test: verify app detects managed config (if set) and auto-populates fields
# Fallback test: app shows manual UI if no managed config
adb logcat | grep -i 'managed'
```

---

## FEAT-005: Frontend Admin Device Management Pages

**Effort:** High | **Files:** frontend/app/(app)/admin/*, frontend/lib/api.ts, frontend/components/Admin*.tsx

### What to Do
Create three new admin dashboard pages for device provisioning and management:

#### 1. Create frontend/app/(app)/admin/layout.tsx
- Shared layout with TopBar, Sidebar, breadcrumbs
- Navigation to /admin/provisioning, /admin/devices, /admin/enrollment-policies
- Display current user role (admin-only)

#### 2. Create frontend/app/(app)/admin/provisioning/page.tsx
- Table: ID, Platform, Status, Device Count, Created At, Expires At, Last Used, Actions
- Filters: platform dropdown (Windows|Linux|macOS|Android|iOS), status dropdown (ACTIVE|REVOKED|EXPIRED)
- "Create New" button → modal to select platform, organization, device count, expiration days
- On create: POST /api/v1/device-provisioning/create, receive enrollmentCode and qr_data
- Display QR code (use qrcode.react library)
- Copy enrollment code to clipboard button
- "Revoke" button for each active record
- Expiration countdown timer
- Pagination (limit=50)

#### 3. Create frontend/app/(app)/admin/devices/page.tsx
- Table: Device ID, Name, Platform, Status, Last Seen, Enrolled At, Organization, Files Scanned, Incidents, Actions
- Color-code status: ACTIVE=green, OFFLINE=gray, DISABLED=red
- Filters: platform, status, organization
- Search by device name/id (client-side)
- Click row → device detail drawer with specs, IP, OS version, agent version, heartbeat interval, last 10 incidents
- "Reset Enrollment" button → clear device auth tokens, force re-enrollment
- "Disable Device" button → status=DISABLED, cannot authenticate
- "View Incidents" button → navigate to /incidents?device_id=...
- "Download Manifest" button → export JSON/CSV
- Pagination, refresh

#### 4. Create frontend/app/(app)/admin/enrollment-policies/page.tsx
- Table: Policy ID, Name, Platform, Organization, DLP Rules Count, Created At, Status, Actions
- "Create New" button → modal: name, platform, organization, multi-select DLP rules, compliance level, require attestation checkbox
- Click row → policy detail drawer with full rule list, compliance settings, assigned devices count
- "Edit" button (if not assigned to devices)
- "Delete" button (if no devices assigned)
- "Duplicate" button (copy policy with new name)
- Pagination, refresh

#### 5. Extend frontend/lib/api.ts
Add TypeScript types and functions:
```typescript
fetchProvisioningRecords(limit, offset, platform?, status?)
createProvisioningRecord(platform, organizationId, deviceCount, expirationDays)
revokeProvisioningRecord(recordId)
resetDeviceEnrollment(deviceId)
disableDevice(deviceId)
fetchEnrollmentPolicies(limit, offset, platform?, org?)
createEnrollmentPolicy(name, platform, org, ruleIds, complianceLevel, requireAttestation)
```

#### 6. Create shared admin components
- `components/AdminHeader.tsx` — current admin user, organization context
- `components/AdminNav.tsx` — sidebar with navigation
- `components/DeviceDetailDrawer.tsx` — device specs in slide-out panel
- `components/ProvisioningModal.tsx` — form to create provisioning
- `components/PolicyModal.tsx` — form to create/edit policy

#### 7. RBAC Enforcement
- Check `current_user.role === 'admin'` on all /admin pages
- If not admin, show 403 Forbidden page
- Use existing AuthError pattern from codebase

#### 8. Error Handling & Loading
- Show loading spinner while fetching
- Show error toast if API fails
- "Retry" button on error
- Auto-refresh data every 30 seconds (configurable)

### Verification
```bash
cd frontend
npm run build
npm run test  # if tests written
# Manual test: login as admin, navigate to /admin/provisioning
# Create new record, verify QR displays
# Navigate to /admin/devices, verify list loads
# Click device → detail drawer opens
# Login as non-admin → /admin/* returns 403
```

---

## FEAT-006: Backend Tests and Integration Verification

**Effort:** High | **Files:** backend/tests/test_enrollment*.py

### What to Do
Add comprehensive unit and integration tests covering all enrollment scenarios:

#### 1. backend/tests/test_enrollment_provisioning.py
- Test provisioning creation with valid platform/org
- Verify token hashing (SHA-256, not plaintext)
- Test expiration countdown
- Test revocation sets status=REVOKED
- Test RBAC: non-admin cannot create (403)
- Use existing test fixtures (admin_user, db)

#### 2. backend/tests/test_enrollment_flow.py
- Test full bootstrap → attest → complete flow
- Test single-use token: second call with same token returns 401
- Test token consumption prevents re-use in different endpoints
- Test /complete creates Device with DG-DEVICE-XXXX ID
- Verify Device.publicKeyFingerprint computed correctly
- Test idempotency: duplicate /complete calls return same device ID
- Test /configuration returns org/policy data
- Test /policy returns DLP rules

#### 3. backend/tests/test_enrollment_attestation.py
- Test invalid attestation rejected
- Test missing attestation allows fallback (attestationStatus=SKIPPED)
- Test attestation validation stubs (Android, iOS, Windows)

#### 4. backend/tests/test_enrollment_errors.py
- Test expired token (401)
- Test revoked token (401)
- Test invalid platform (400)
- Test missing required fields (422)
- Test malformed PEM public key rejected
- Test race condition: concurrent enrollment with same token (one succeeds, other gets 409)

#### 5. backend/tests/test_device_migrations.py
- Test database.init_db() creates new tables without error
- Fresh database: DeviceProvisioning, DeviceIdentity created
- Existing database with Device table: migration adds columns without dropping data
- Existing Device records still readable post-migration
- Migration idempotent: call init_db() twice, no errors

#### 6. backend/tests/test_device_identity.py
- Test DeviceIdentity created with unique deviceId (DG-DEVICE-XXXX)
- Test enrollmentCode unique per device
- Test publicKey stored in PEM format
- Test attestationData stored as JSON
- Test indexes on deviceId, enrollmentCode

#### 7. backend/tests/test_enrollment_integration.py (end-to-end)
- Setup: POST /create provisioning, receive token
- Step 1: POST /bootstrap → token consumed, config returned
- Step 2: POST /attest → attestationValid=true
- Step 3: POST /complete → Device created with status=ACTIVE
- Verify device in GET /devices list
- Verify heartbeat works: POST /devices/{device_id}/heartbeat
- Verify policy download: GET /policy returns rules

#### 8. backend/tests/test_device_routes_regression.py
- Existing POST /devices/enrollment/register still works
- Existing GET /devices works
- Existing POST /devices/heartbeat works
- Existing device creation not broken
- Use existing device fixtures, verify still queryable

### Goals
- **Coverage:** Minimum 80% for new enrollment code
- **All tests pass:** `pytest backend/tests/test_enrollment*.py -v`
- **No regressions:** `pytest tests/test_device_routes.py -v` still pass
- **Migrations verified:** non-destructive on existing database

### Verification
```bash
cd backend
python -m pytest tests/ -v
python -m pytest tests/ --cov=backend --cov-report=html
# Verify coverage >= 80%
open htmlcov/index.html
# Verify no regressions
pytest tests/test_device_routes.py -v
```

---

## Implementation Order & Dependencies

1. **FEAT-001 (Backend Models)** — Foundation; must complete first
2. **FEAT-002 (Backend API)** — Depends on FEAT-001; implements endpoints
3. **FEAT-003 (Android NPE Fixes)** — Independent; fixes current crashes
4. **FEAT-004 (Android Managed Config)** — Depends on FEAT-003; uses fixed code
5. **FEAT-005 (Frontend Admin Pages)** — Depends on FEAT-002; calls new endpoints
6. **FEAT-006 (Backend Tests)** — Depends on all; comprehensive verification

**Execution:** Sequential. Each FEAT builds on previous. No parallel work.

---

## Testing & Verification Strategy

### Per-FEAT Verification
- Each FEAT includes specific verification commands (unit tests, builds, manual tests)
- All tests must pass before moving to next FEAT
- Database migrations verified on fresh and existing databases

### Cross-FEAT Integration Verification
- Run backend tests, frontend build, Android build
- Verify all APIs mounted correctly (check Swagger docs)
- Verify database schema created correctly
- Start backend, verify no startup errors
- Manual end-to-end enrollment test

### Regression Prevention
- Run existing device route tests
- Verify existing Device records still queryable
- Verify backward compatibility of existing enrollment endpoints

---

## Security Considerations

✅ **Implemented:**
- Bootstrap tokens hashed (SHA-256), never stored plaintext
- Single-use tokens (consumed on first call, replay prevention)
- Short-lived tokens (10-minute expiry, configurable)
- Device identity unique and cryptographic (DG-DEVICE-XXXX format)
- Public key storage (never private keys)
- Attestation validation (platform-specific)
- RBAC on admin endpoints (admin-only access)
- Comprehensive logging (no plaintext secrets)

⚠️ **Assumptions:**
- Platform attestation validation implemented (stubs for now, real implementations later)
- Android managed config relies on MDM system security
- Device public keys assumed valid (PEM format validation added)
- No end-to-end encryption between device and backend (use TLS)

---

## Files to Read Before Implementing

1. **Documentation:**
   - c:\\Users\\ARUN\\Desktop\\dataghost\\ARCHITECTURE.md
   - c:\\Users\\ARUN\\Desktop\\dataghost\\API.md
   - c:\\Users\\ARUN\\Desktop\\dataghost\\README.md

2. **Backend patterns:**
   - backend/models.py (SQLAlchemy patterns)
   - backend/auth.py (JWT patterns)
   - backend/api/device_routes.py (existing endpoints)
   - backend/database.py (SQLite migration patterns)

3. **Frontend patterns:**
   - frontend/lib/api.ts (API client patterns)
   - frontend/app/(app)/devices/page.tsx (existing device page)
   - frontend/app/(app)/dashboard/page.tsx (existing dashboard)
   - frontend/components/ (UI component patterns)

4. **Android patterns:**
   - mobile/android/app/src/main/java/com/dataghost/agent/ui/EnrollmentActivity.kt
   - mobile/android/app/src/main/java/com/dataghost/agent/DataGhostApp.kt
   - mobile/android/app/src/main/java/com/dataghost/agent/enrollment/EnrollmentManager.kt

---

## Success Criteria

✅ All 6 FEATs implemented and verified  
✅ Android NPE crashes fixed  
✅ Zero-touch enrollment works end-to-end (device → QR → bootstrap → attest → complete → active)  
✅ Admin can create provisioning records with QR codes  
✅ Admin can view enrolled devices and manage enrollment  
✅ Device receives unique DG-DEVICE-XXXX identifier  
✅ Bootstrap tokens single-use and hashed  
✅ No plaintext secrets in code or logs  
✅ All unit tests pass (>80% coverage)  
✅ No regressions in existing functionality  
✅ Database migrations non-destructive  

---

**Status:** Ready for implementation via workflow FEATs.  
**Artifacts:** FEAT JSON files under c:\\Users\\ARUN\\Desktop\\dataghost\\.agents\\tasks\\task-enrollment-redesign\\features\\

