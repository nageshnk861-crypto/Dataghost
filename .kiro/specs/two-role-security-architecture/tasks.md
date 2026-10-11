# Phase 3: Implementation Tasks

Two-Role Security Architecture Bugfix - Sequential Implementation Plan

## Overview

This implementation plan follows the security architecture bugfix in strict dependency order:
1. Fix admin role hardcoding (unblocks device access, scan persistence, dashboard)
2. Implement device ownership filtering (validates access before operations)
3. Persist real scan results (enables dashboard aggregation)
4. Stop using mock endpoints (ensures data integrity)
5. Aggregate real dashboard data (final verification)

Each task is atomic and testable. Verification steps confirm both the fix works and existing behavior is preserved.

---

## PHASE 3.1: Fix Admin Role Hardcoding

### 3.1.1 Update Backend: GET /auth/me Endpoint

- [x] 3.1.1 Implement GET /auth/me endpoint in backend
  - Add new endpoint to `backend/api/auth_routes.py`
  - **Endpoint**: GET /auth/me
  - **Authentication**: Requires Bearer token (JWT)
  - **Response**: JSON with user_id, username, role (from User record in database)
  - Return 401 if token invalid or expired
  - Return 200 with user data if authenticated
  - **Specification Reference**: _Issue 1 - Expected Behavior (2.1, 2.3)_
  - **Verification Step**: Test GET /auth/me returns correct role for both admin and analyst users
  - _Requirements: 2.1, 2.3_

### 3.1.2 Update Frontend: Fetch Role from Backend on Login

- [x] 3.1.2 Replace hardcoded role with backend fetch in frontend/lib/auth.ts
  - Remove hardcoded role: "admin" assignment
  - After successful login, call GET /auth/me endpoint
  - Store fetched role in localStorage (from backend response)
  - Add error handling for failed role fetch
  - Fall back to clearing role if GET /auth/me fails
  - **Specification Reference**: _Issue 1 - Expected Behavior (2.1)_
  - **Verification Step**: Login as analyst, verify localStorage contains role="analyst"
  - _Requirements: 2.1_

### 3.1.3 Update Frontend: Fetch Role on Page Reload

- [x] 3.1.3 Verify stored role against backend on page reload in frontend/lib/auth.ts
  - On app initialization, read role from localStorage
  - If role exists, call GET /auth/me to verify current role
  - Update localStorage if role changed (e.g., admin changed to analyst in backend)
  - Clear session if roles do not match (potential security issue)
  - Add error handling for failed verification
  - **Specification Reference**: _Issue 1 - Expected Behavior (2.2)_
  - **Verification Step**: After login, reload page and verify role is correct
  - _Requirements: 2.2_

### 3.1.4 Update Frontend: Remove Hardcoded Role from Login Page

- [x] 3.1.4 Remove mock role assignment from frontend/app/login/page.tsx
  - Remove any hardcoded role: "admin" in login flow
  - Ensure login route calls the updated auth.ts functions
  - Remove mock success handlers that set role
  - Verify login page redirects to /dashboard after successful auth
  - **Specification Reference**: _Issue 1 - Expected Behavior (2.1, 2.3)_
  - **Verification Step**: Login flow sets role from backend, not hardcoded
  - _Requirements: 2.1, 2.3_

### 3.1.5 Verification: Admin and Analyst Roles Load Correctly

- [x] 3.1.5 Test role loading for both user types
  - Test Scenario A: Admin login
    - Log in as admin user (user_id=1, role="admin" in User table)
    - Verify GET /auth/me returns role="admin"
    - Verify localStorage contains role="admin"
    - Reload page and verify role persists
  - Test Scenario B: Analyst login
    - Log in as analyst user (user_id=2, role="analyst" in User table)
    - Verify GET /auth/me returns role="analyst"
    - Verify localStorage contains role="analyst"
    - Reload page and verify role persists
  - **Specification Reference**: _Issue 1 - Expected Behavior (2.1, 2.2)_
  - **Preservation Reference**: _Issue 1 - Unchanged Behavior (3.1, 3.2, 3.3)_
  - Verify logout clears role from localStorage
  - Verify incorrect credentials still fail
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

### 3.1.6 Checkpoint: Authentication Complete

- [x] 3.1.6 Verify all authentication tests pass before proceeding
  - Run all authentication tests: `pytest backend/tests/auth_tests.py -v`
  - Verify frontend role loading works in UI
  - Confirm both admin and analyst roles load correctly
  - Proceed to Phase 3.2 (Device Access Control) once passing
  - _Requirements: 2.1, 2.2, 2.3_

---

## PHASE 3.2: Implement Device Access Control

**DEPENDENCY**: Requires Phase 3.1 completed (admin/analyst roles must load correctly)

### 3.2.1 Update Database Schema: Add FK Constraint

- [x] 3.2.1 Add Foreign Key constraint and NOT NULL to devices.user_id
  - Execute migration or direct ALTER TABLE (in alembic migration):
    - ALTER TABLE devices MODIFY user_id INT NOT NULL
    - ALTER TABLE devices ADD CONSTRAINT fk_device_user FOREIGN KEY (user_id) REFERENCES users(id)
    - CREATE INDEX idx_device_user_id ON devices(user_id)
  - Verify migration succeeds
  - Verify existing devices have valid user_id values (backfill if needed)
  - **Specification Reference**: _Issue 2 - Expected Behavior (2.4, 2.5, 2.6)_
  - _Requirements: 2.4, 2.5, 2.6_

### 3.2.2 Update Backend: Filter Devices by User in GET /devices

- [x] 3.2.2 Implement role-based device filtering in backend/api/device_routes.py
  - Get authenticated user_id and role from request context
  - If role == "analyst": return only devices where device.user_id == authenticated_user_id
  - If role == "admin": return all devices (existing behavior)
  - Return empty list if analyst has no devices
  - Return 401 if user not authenticated
  - **Specification Reference**: _Issue 2 - Expected Behavior (2.4, 2.5)_
  - **Verification Step**: analyst1 GET /devices returns only analyst1's devices
  - _Requirements: 2.4, 2.5_

### 3.2.3 Update Backend: Verify Ownership in Device Detail Endpoint

- [x] 3.2.3 Add ownership check to device detail endpoints in backend/api/device_routes.py
  - GET /devices/{id}: Check (role == "admin" OR device.user_id == authenticated_user_id)
  - POST /devices/{id}/scan: Check (role == "admin" OR device.user_id == authenticated_user_id)
  - PUT /devices/{id}: Check (role == "admin" OR device.user_id == authenticated_user_id)
  - Return 403 Forbidden if ownership check fails
  - Return 401 if user not authenticated
  - **Specification Reference**: _Issue 2 - Expected Behavior (2.6, 2.7)_
  - **Verification Step**: analyst1 GET /devices/analyst2-device returns 403
  - _Requirements: 2.6, 2.7_

### 3.2.4 Update Frontend: Request User's Own Devices

- [x] 3.2.4 Update frontend device list to call GET /devices correctly
  - Frontend/app component calls GET /devices
  - Display returned devices in UI
  - Handle 403 error (should not occur for GET /devices, but handle gracefully)
  - **Specification Reference**: _Issue 2 - Expected Behavior (2.4, 2.5)_
  - _Requirements: 2.4, 2.5_

### 3.2.5 Verification: Device Access Control Enforced

- [x] 3.2.5 Test device filtering for both user types
  - Test Setup: Create two analyst users (analyst1, analyst2) with different devices
    - analyst1 owns device1 and device2
    - analyst2 owns device3
  - Test Scenario A: Analyst1 views devices
    - analyst1 GET /devices returns [device1, device2]
    - analyst1 GET /devices/device1 returns 200 (own device)
    - analyst1 GET /devices/device3 returns 403 (other analyst's device)
  - Test Scenario B: Admin views devices
    - admin GET /devices returns [device1, device2, device3]
    - admin GET /devices/device3 returns 200 (admin can access any device)
  - **Specification Reference**: _Issue 2 - Expected Behavior (2.4, 2.5, 2.6, 2.7)_
  - **Preservation Reference**: _Issue 2 - Unchanged Behavior (3.4, 3.5)_
  - Verify admin can still perform device management operations
  - _Requirements: 2.4, 2.5, 2.6, 2.7, 3.4, 3.5_

### 3.2.6 Checkpoint: Device Access Control Complete

- [x] 3.2.6 Verify all device access tests pass before proceeding
  - Run device access tests: `pytest backend/tests/device_tests.py -v`
  - Verify database FK constraint in place
  - Confirm analyst/admin access control working
  - Proceed to Phase 3.3 (Scan Persistence) once passing
  - _Requirements: 2.4, 2.5, 2.6, 2.7_

---

## PHASE 3.3: Persist Real Scan Results

**DEPENDENCY**: Requires Phase 3.2 completed (device ownership must be verified)

### 3.3.1 Update Backend: Create ScanLog on Scan Completion

- [ ] 3.3.1 Implement ScanLog persistence in backend/api/device_routes.py
  - POST /devices/{id}/scan endpoint now creates ScanLog record
  - Extract from scan results: files_scanned (actual count, not hardcoded)
  - Extract findings_count and risk_score from scan analysis
  - Set timestamp to current time
  - Set device_id and user_id (from device ownership)
  - Return 201 Created with ScanLog ID in response
  - **Specification Reference**: _Issue 3 - Expected Behavior (2.9, 2.11)_
  - **Verification Step**: After scan, ScanLog record exists with correct file count
  - _Requirements: 2.9, 2.11_

### 3.3.2 Update Backend: Create Incident Records

- [ ] 3.3.2 Implement Incident creation for high-risk findings in backend/api/device_routes.py
  - After ScanLog created, check findings for risk_score >= 30
  - For each finding >= 30: create Incident record
  - Set incident_type, finding_description, risk_score, timestamp
  - Link to ScanLog and Device
  - Do NOT create incidents for findings < 30 (preserve clean data)
  - **Specification Reference**: _Issue 3 - Expected Behavior (2.10)_
  - **Verification Step**: After scan with high-risk findings, Incident records created
  - _Requirements: 2.10_

### 3.3.3 Update Backend: Enforce Device Ownership on Scan

- [ ] 3.3.3 Add ownership verification to POST /devices/{id}/scan
  - Check (role == "admin" OR device.user_id == authenticated_user_id)
  - Return 403 if ownership check fails
  - Return 401 if user not authenticated
  - **Specification Reference**: _Issue 3 - Expected Behavior (2.12)_
  - **Verification Step**: analyst1 POST /devices/analyst2-device/scan returns 403
  - _Requirements: 2.12_

### 3.3.4 Update Frontend: Remove Mock Scan Handlers

- [ ] 3.3.4 Remove mock scan handlers from frontend/app/api/[...path]/route.ts
  - Remove hardcoded "0 FILES SCANNED" response
  - Remove mock success response handlers for /devices/{id}/scan
  - Proxy scan requests directly to backend
  - **Specification Reference**: _Issue 3 - Expected Behavior (2.8)_
  - **Preservation Reference**: _Issue 3 - Unchanged Behavior (3.6)_
  - _Requirements: 2.8, 3.6_

### 3.3.5 Update Frontend: Increase Timeout and Handle Errors

- [ ] 3.3.5 Update frontend route timeout and error handling
  - Increase timeout from 8 seconds to 15-30 seconds for scan operations
  - If backend unavailable: return 502 with message "Backend unavailable"
  - Do NOT serve mock data (only for development/enrollment)
  - Handle ScanLog creation delay (scan may take 15+ seconds)
  - **Specification Reference**: _Issue 4 - Expected Behavior (2.13, 2.14)_
  - _Requirements: 2.13, 2.14_

### 3.3.6 Verification: Scans Persist Real Data

- [ ] 3.3.6 Test scan persistence for real file counts
  - Test Scenario A: Analyst scans device with 10 files
    - analyst1 scans device1 with 10 files
    - ScanLog created with files_scanned=10 (not hardcoded 45)
    - Response returns files_scanned=10
  - Test Scenario B: Multiple scans aggregate correctly
    - analyst1 scans device1 (10 files)
    - analyst1 scans device1 again (15 files)
    - Both ScanLog records created
    - Total scanned: 25 files across two records
  - Test Scenario C: Incident creation
    - Scan finds 3 findings with risk_scores [25, 35, 80]
    - Only 2 Incident records created (35 and 80 >= 30)
    - Finding with 25 not in Incident table
  - **Specification Reference**: _Issue 3 - Expected Behavior (2.8, 2.9, 2.10, 2.11)_
  - **Preservation Reference**: _Issue 3 - Unchanged Behavior (3.6, 3.7)_
  - Verify analyst owns device check enforced (2.12)
  - Verify error handling returns proper messages (not mocked success)
  - _Requirements: 2.8, 2.9, 2.10, 2.11, 2.12, 3.6, 3.7_

### 3.3.7 Checkpoint: Scan Persistence Complete

- [ ] 3.3.7 Verify all scan persistence tests pass before proceeding
  - Run scan tests: `pytest backend/tests/scan_tests.py -v`
  - Verify ScanLog records created with correct file counts
  - Verify Incident records created for high-risk findings
  - Verify ownership check enforced
  - Proceed to Phase 3.4 (Mock Precedence) once passing
  - _Requirements: 2.8, 2.9, 2.10, 2.11, 2.12_

---

## PHASE 3.4: Remove Mock Precedence Over Backend

**DEPENDENCY**: Requires Phase 3.3 completed (real scan data must exist)

### 3.4.1 Update Frontend: Remove Mock Auth Handlers

- [ ] 3.4.1 Remove mock login handlers from frontend/app/api/[...path]/route.ts
  - Remove mock /auth/login handler that returns hardcoded role
  - Remove mock /auth/me handler (if exists)
  - Proxy auth requests directly to backend
  - If backend unavailable: return 502 error
  - **Specification Reference**: _Issue 4 - Expected Behavior (2.15)_
  - _Requirements: 2.15_

### 3.4.2 Update Frontend: Remove Mock Device Handlers

- [ ] 3.4.2 Remove mock device list handlers from frontend/app/api/[...path]/route.ts
  - Remove mock /devices handler that returns fake device list
  - Remove mock /devices/{id} handler
  - Proxy device requests directly to backend
  - If backend unavailable: return 502 error
  - **Specification Reference**: _Issue 4 - Expected Behavior (2.15)_
  - _Requirements: 2.15_

### 3.4.3 Update Frontend: Remove Mock Dashboard Handlers

- [ ] 3.4.3 Remove mock dashboard handlers from frontend/app/api/[...path]/route.ts
  - Remove mock /dashboard handler that returns hardcoded stats (1845 files, etc.)
  - Proxy dashboard requests directly to backend
  - If backend unavailable: return 502 error
  - **Specification Reference**: _Issue 4 - Expected Behavior (2.15)_
  - _Requirements: 2.15_

### 3.4.4 Allow Mock Responses Only for Enrollment

- [ ] 3.4.4 Keep mock enrollment handlers but restrict scope
  - Keep mock /enrollment-in-progress handler (temporary, short-lived)
  - Keep mock /enrollment-status handler (temporary, short-lived)
  - Remove mock handlers for production endpoints: auth, devices, scan, dashboard
  - Add environment flag to disable mock in production
  - **Specification Reference**: _Issue 4 - Expected Behavior (2.16)_
  - **Preservation Reference**: _Issue 4 - Unchanged Behavior (3.8)_
  - _Requirements: 2.16, 3.8_

### 3.4.5 Verification: No Mock Data in Production Endpoints

- [ ] 3.4.5 Test that backend unavailable returns 502 (not mock data)
  - Test Scenario A: Backend unavailable on login
    - Stop backend service
    - Attempt login
    - Verify response is 502 "Backend unavailable" (not mock success)
  - Test Scenario B: Backend unavailable on device fetch
    - Stop backend service
    - Attempt GET /devices
    - Verify response is 502 (not mock device list)
  - Test Scenario C: Backend unavailable on scan
    - Stop backend service
    - Attempt POST /devices/{id}/scan
    - Verify response is 502 (not mock success)
  - Test Scenario D: Backend unavailable on dashboard
    - Stop backend service
    - Attempt GET /dashboard
    - Verify response is 502 (not hardcoded stats)
  - **Specification Reference**: _Issue 4 - Expected Behavior (2.13, 2.15)_
  - **Preservation Reference**: _Issue 4 - Unchanged Behavior (3.8)_
  - Verify enrollment mocks still work for development
  - _Requirements: 2.13, 2.15, 3.8_

### 3.4.6 Checkpoint: Mock Precedence Removed

- [ ] 3.4.6 Verify backend is trusted for production endpoints
  - Verify all production endpoint mocks removed
  - Verify 502 errors returned when backend unavailable
  - Verify enrollment mocks still available for development
  - Proceed to Phase 3.5 (Dashboard Aggregation) once passing
  - _Requirements: 2.13, 2.15_

---

## PHASE 3.5: Aggregate Real Dashboard Data

**DEPENDENCY**: Requires Phase 3.3 completed (ScanLog and Incident records must exist)

### 3.5.1 Update Backend: Aggregate ScanLog Data

- [ ] 3.5.1 Implement dashboard aggregation in backend/api/dashboard_routes.py
  - GET /dashboard endpoint aggregates from ScanLog and Incident tables
  - Calculate files_scanned: SUM(ScanLog.files_count) for applicable records
  - Calculate findings_count: COUNT(Incident records) where risk_score >= 30
  - Calculate critical_incidents: COUNT(Incident records) where risk_score >= 75
  - **Specification Reference**: _Issue 5 - Expected Behavior (2.17, 2.18, 2.19, 2.20)_
  - **Verification Step**: Dashboard shows aggregated data from database, not hardcoded
  - _Requirements: 2.17, 2.18, 2.19, 2.20_

### 3.5.2 Update Backend: Apply Role-Based Filtering

- [ ] 3.5.2 Implement role-based dashboard filtering in backend/api/dashboard_routes.py
  - If role == "analyst": filter to devices where device.user_id == authenticated_user_id
  - If role == "admin": include all organization devices
  - Apply filter to both ScanLog and Incident queries
  - Aggregate only filtered records
  - **Specification Reference**: _Issue 5 - Expected Behavior (2.21, 2.22)_
  - **Verification Step**: analyst1 sees only analyst1's scan data on dashboard
  - _Requirements: 2.21, 2.22_

### 3.5.3 Update Frontend: Display Real Dashboard Stats

- [ ] 3.5.3 Update frontend dashboard to display aggregated stats
  - Remove hardcoded values (1845 files, 42 sensitive, 2 critical)
  - Display values returned from GET /dashboard endpoint
  - Update stats layout to show real aggregated data
  - **Specification Reference**: _Issue 5 - Expected Behavior (2.17)_
  - **Preservation Reference**: _Issue 5 - Unchanged Behavior (3.9, 3.10)_
  - _Requirements: 2.17, 3.9, 3.10_

### 3.5.4 Verification: Dashboard Aggregates Real Data

- [ ] 3.5.4 Test dashboard aggregation with real scan data
  - Test Scenario A: Admin dashboard aggregates all scans
    - Admin views dashboard after:
      - analyst1 scans device1 (10 files, 3 incidents)
      - analyst2 scans device3 (15 files, 1 incident)
    - Dashboard shows: files_scanned=25, findings_count=4, critical_incidents based on risk_scores
    - Not hardcoded 1845 files
  - Test Scenario B: Analyst dashboard shows only own scans
    - analyst1 views dashboard
    - Dashboard shows: files_scanned=10 (only analyst1's scan)
    - Does NOT include analyst2's 15 files
  - Test Scenario C: Dashboard reflects real risk filtering
    - After scans with mixed risk scores
    - findings_count includes incidents with risk_score >= 30
    - critical_incidents includes only incidents with risk_score >= 75
  - **Specification Reference**: _Issue 5 - Expected Behavior (2.17, 2.18, 2.19, 2.20, 2.21, 2.22)_
  - **Preservation Reference**: _Issue 5 - Unchanged Behavior (3.9, 3.10)_
  - Verify response format unchanged from original (same JSON structure)
  - _Requirements: 2.17, 2.18, 2.19, 2.20, 2.21, 2.22, 3.9, 3.10_

### 3.5.5 Checkpoint: Dashboard Complete

- [ ] 3.5.5 Verify all dashboard tests pass
  - Run dashboard tests: `pytest backend/tests/dashboard_tests.py -v`
  - Verify aggregation returns correct totals
  - Verify role-based filtering working
  - Verify hardcoded data removed
  - Proceed to Phase 3.6 (Full Integration) once passing
  - _Requirements: 2.17, 2.18, 2.19, 2.20, 2.21, 2.22_

---

## PHASE 3.6: Full Integration Checkpoint

### 3.6.1 Full End-to-End Workflow Test

- [ ] 3.6.1 Test complete security architecture workflow
  - **Setup**: Two analyst users (analyst1, analyst2), one admin, with devices and scans
  - **Workflow**:
    1. analyst1 logs in (gets role="analyst" from backend)
    2. analyst1 views /devices (sees only own devices)
    3. analyst1 clicks scan on device1
    4. Scan creates real ScanLog (10 files_scanned, not hardcoded)
    5. High-risk findings create Incident records
    6. analyst1 views dashboard (sees own aggregated data: 10 files)
    7. admin logs in (gets role="admin")
    8. admin views /devices (sees all organization devices)
    9. admin views dashboard (sees all organization data: 25+ files from all users)
  - **Verification Points**:
    - Role loading: ✓ analyst1 gets analyst, admin gets admin
    - Device filtering: ✓ analyst1 sees 2 devices, admin sees 3+ devices
    - Scan persistence: ✓ ScanLog created with real 10 files
    - Incident creation: ✓ High-risk findings in Incident table
    - Dashboard aggregation: ✓ analyst1 sees 10 files, admin sees 25+ files
    - No mock data: ✓ All data from database, no hardcoded values
  - **Specification Reference**: _Issues 1-5 - All Expected Behaviors_
  - **Preservation Reference**: _Issues 1-5 - All Unchanged Behaviors_
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14, 2.15, 2.16, 2.17, 2.18, 2.19, 2.20, 2.21, 2.22, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

### 3.6.2 All Tests Pass

- [ ] 3.6.2 Run full test suite and verify all tests pass
  - Backend tests: `pytest backend/tests/ -v`
  - Frontend tests: `npm test` (if configured)
  - Integration tests (if available)
  - Verify no regressions in existing functionality
  - All 10 acceptance criteria requirements satisfied

### 3.6.3 Security Validation Complete

- [ ] 3.6.3 Confirm security fixes in place
  - Admin role no longer hardcoded ✓
  - Device access properly filtered by user_id ✓
  - Scan results persist to ScanLog and Incident tables ✓
  - Mock endpoints removed for production flows ✓
  - Dashboard aggregates real data, not hardcoded ✓
  - Ready for deployment

---

## Test Execution Commands

```bash
# Run all backend tests
pytest backend/tests/ -v

# Run specific test modules
pytest backend/tests/auth_tests.py -v
pytest backend/tests/device_tests.py -v
pytest backend/tests/scan_tests.py -v
pytest backend/tests/dashboard_tests.py -v

# Run with coverage
pytest backend/tests/ --cov=backend/api --cov=backend/app

# Frontend tests (if configured)
npm test -- --run
```

## Deployment Checklist

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Database migrations applied (FK constraint on devices.user_id)
- [ ] Role verification endpoint (GET /auth/me) deployed
- [ ] Device ownership filtering enforced
- [ ] ScanLog and Incident persistence working
- [ ] Mock endpoints removed for production flows
- [ ] Dashboard aggregation using real data
- [ ] No hardcoded values in responses
- [ ] Backend unavailable returns 502 (not mocked data)
