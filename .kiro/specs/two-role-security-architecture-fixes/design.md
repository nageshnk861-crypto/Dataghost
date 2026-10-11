# Two-Role Security Architecture Fixes – Bugfix Design

## Overview

This bugfix addresses five critical security vulnerabilities in the DataGhost platform that fundamentally undermine the two-role (admin/analyst) access control model:

1. **Admin role hardcoding** – Frontend login always assigns `role: "admin"` to all users
2. **Device access control gap** – No ownership verification; analysts can see all devices
3. **Fake scan success** – Mock scan handler returns hardcoded success instead of real data
4. **Mock precedence** – Mock responses take priority over backend errors in production
5. **Dashboard false data** – Hardcoded stats instead of real database aggregation

These issues collectively allow:
- Any analyst to masquerade as admin
- Any user to see all organization devices, not just their own
- False incident records with fabricated scan results
- Dashboards showing misleading statistics

**Impact Severity:** CRITICAL – Multiple role-bypass vectors combine to completely break the RBAC authorization model.

**Fix Strategy:** 
1. Move role authority to backend (single source of truth)
2. Enforce device ownership in database and API layer
3. Replace mock scan responses with real database records
4. Disable mock fallbacks for production endpoints
5. Aggregate real data from database for analytics

---

## Glossary

- **Bug_Condition (C)**: A scenario where:
  - Login succeeds without backend role verification (Issue #1), OR
  - Device/scan API succeeds without ownership validation (Issues #2, #3), OR
  - Dashboard returns hardcoded values instead of database queries (Issue #5)

- **Property (P)**: The desired security behavior:
  - Role is fetched from backend User.role database field
  - All device queries are filtered by user ownership + role
  - All scan operations create real database records
  - All responses contain real data from persistent storage

- **Preservation**: Existing behavior that must remain unchanged:
  - Mouse/web UI login still works
  - Button display and UI flows unchanged
  - Device enrollment process (with added user_id field)
  - Dashboard UI displays same information, sourced from real data

- **Frontend Mock Handler**: The fallback route handler in `frontend/app/api/[...path]/route.ts` that returns hardcoded mock responses
- **Database of Record**: The single authoritative source of truth for all data (User.role, Device.user_id, ScanLog, Incident)
- **Access Control Token**: JWT from backend containing user identity; role is read from database, never from token
- **Ownership Check**: Verification that current_user.id matches the resource's user_id field (or user is admin)

---

## Bug Details

### Bug Condition

The bug manifests across five distinct but related security failures:

**Issue #1 – Admin Role Hardcoding**
The frontend login flow assigns `role: "admin"` directly in the token/session without backend verification. Any user logging in appears as admin to the frontend application logic.

**Issue #2 – Device Access Control Gap**
The backend device endpoints (GET /devices, GET /devices/{id}, POST /devices/{id}/scan) do NOT filter results by user ownership. An analyst registered on Device-A can query all devices in the organization, including those belonging to other analysts.

**Issue #3 – Fake Scan Success**
The frontend mock scan handler (frontend/app/api/[...path]/route.ts:559) returns hardcoded `{ status: "COMPLETED", scanned_files: 45, findings_count: 0 }` instead of calling the real backend. No ScanLog or Incident records are created in the database.

**Issue #4 – Mock Precedence**
The frontend proxy handler (tryProxyToBackend) has an 8-second timeout and falls through to mock responses on timeout/unavailability, treating mock data as acceptable fallback for production APIs.

**Issue #5 – Dashboard False Data**
The backend GET /dashboard/stats endpoint returns hardcoded statistics:
```python
{
  files_scanned: 1845,      # hardcoded
  sensitive_files: 42,      # hardcoded
  critical_incidents: 2     # hardcoded
}
```
instead of aggregating from ScanLog and Incident tables.

**Formal Specification:**
```
FUNCTION isBugCondition(request, user, operation)
  INPUT: 
    request = HTTP request to /auth/login, /devices, /devices/{id}, /devices/{id}/scan, /dashboard/stats
    user = authenticated user from JWT
    operation = "login" | "list_devices" | "get_device" | "trigger_scan" | "get_dashboard"
  OUTPUT: boolean (true if bug condition holds)
  
  // Issue #1: Role hardcoding
  IF operation == "login"
    RETURN localStorage.dg_user.role == "admin" for ALL users
  
  // Issue #2: No ownership check
  IF operation == "list_devices" OR operation == "get_device"
    RETURN endpoint does NOT filter Device.user_id == user.id when user.role == "analyst"
  
  // Issue #3: Fake scan success
  IF operation == "trigger_scan"
    RETURN response contains hardcoded mock data (45 files, 0 findings)
           AND no ScanLog record is persisted
  
  // Issue #4: Mock precedence
  IF backend timeout OR backend unavailable
    RETURN tryProxyToBackend falls through to mock handler
           (200 with fake data) instead of returning 502 error
  
  // Issue #5: False dashboard data
  IF operation == "get_dashboard"
    RETURN stats contain hardcoded values, not SUM(ScanLog.files_scanned)
END FUNCTION
```

### Examples

**Example 1 – Admin Role Spoofing**
1. User registers as "analyst-john"
2. Logs in with correct credentials
3. Frontend receives `{ access_token: "...", user: { username: "analyst-john", role: "admin" } }`
4. **Expected:** `role: "analyst"` (from backend User.role field)
5. **Actual:** `role: "admin"` (hardcoded in login page)
6. **Impact:** analyst-john sees admin controls, can change incident statuses, modify dashboard filters

**Example 2 – Device Visibility Bypass**
1. Analyst-A logs in, gets list of their 3 devices: [Device-1, Device-2, Device-3]
2. Analyst-A makes GET /devices request
3. **Expected:** Response contains only Device-1, Device-2, Device-3
4. **Actual:** Response contains ALL 50 devices in organization (including Analyst-B's devices)
5. **Impact:** Analyst-A can now GET /devices/device-50/scan and trigger scans on devices they don't own

**Example 3 – Fake Scan Record Creation**
1. Analyst uploads file via POST /devices/123/scan
2. Frontend receives: `{ status: "COMPLETED", scanned_files: 45, findings_count: 0 }`
3. **Expected:** ScanLog record created with device_id=123, files_scanned from real scan
4. **Actual:** No ScanLog record created; mock response contains hardcoded 45 files
5. **Impact:** Dashboard shows false cumulative scan numbers; audit logs show no scan activity

**Example 4 – Stale Mock Data After Timeout**
1. Backend scan endpoint takes 12 seconds to complete
2. Frontend timeout is 8 seconds
3. Frontend abort() triggered, falls back to mock handler
4. **Expected:** 504 Gateway Timeout (user sees "backend unavailable")
5. **Actual:** 200 OK with hardcoded mock data { status: "COMPLETED", ... }
6. **Impact:** User believes scan completed successfully when it may have failed silently

**Example 5 – Dashboard Aggregation Missing**
1. Analyst performs 2 scans: 10 files (scan 1) + 15 files (scan 2)
2. Analyst views dashboard
3. **Expected:** `files_scanned: 25` (computed from SELECT SUM(files_scanned) FROM scan_logs)
4. **Actual:** `files_scanned: 1845` (hardcoded mock value)
5. **Impact:** SOC analyst makes decisions based on false statistics

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
1. Frontend login UI flow (form submission) continues to work
2. Button display, text, and error messages remain identical
3. Device enrollment process persists device records
4. Dashboard UI layout and charts unchanged
5. Incident listing and filtering unchanged
6. Agent heartbeat and status updates continue to work

**Scope:**
All inputs that do NOT involve the bug condition should be completely unaffected by this fix. This includes:
- Valid backend responses (already below timeout, no errors)
- Firebase authentication path (separate from JWT login)
- Incident status updates (PATCH /incidents/{id})
- User profile editing (non-role fields)
- Report generation and export

---

## Hypothesized Root Cause

Based on code analysis and the bug descriptions:

1. **Admin Role Hardcoding Root Cause:**
   - Lines in `frontend/app/login/page.tsx`: `role: "admin"` assigned without backend lookup
   - The code should call GET /auth/me AFTER login to fetch verified role from User.role
   - Currently: saves role directly, then attempts async sync (but doesn't wait)

2. **Device Access Control Root Cause:**
   - Device.user_id field exists but is never SET during enrollment (device_routes.py:register_with_enrollment)
   - Device query endpoints (GET /devices, GET /devices/{id}) do NOT include WHERE clause filters
   - No role-based logic: if analyst, filter by user_id; if admin, return all

3. **Fake Scan Success Root Cause:**
   - Frontend mock handler has hardcoded response object
   - Backend scan endpoint may already create ScanLog records, but frontend never reaches it
   - Mock takes precedence in fallback chain: timeout → mock success (not error)

4. **Mock Precedence Root Cause:**
   - tryProxyToBackend has 8-second timeout (too short for long scans)
   - On abort/timeout, function returns null (undefined), falling back to mock handler
   - Mock handler returns 200 for ALL endpoints (auth, devices, scan, dashboard)

5. **Dashboard False Data Root Cause:**
   - backend/api/dashboard_routes.py returns hardcoded dict instead of querying database
   - No SUM/COUNT/GROUP BY logic against ScanLog or Incident tables
   - No role-based filtering (all analysts see org-wide stats)

---

## Correctness Properties

Property 1: Role Authority from Backend

_For any_ login request where a user provides valid credentials, the fixed login flow SHALL:
1. Accept the credentials via backend /auth/login endpoint
2. Receive JWT access_token in response
3. Call GET /auth/me with the JWT
4. Extract role from the User.role database field in the response
5. Store ONLY the JWT in localStorage (not the role directly)
6. On page reload, re-verify role by calling GET /auth/me again

This ensures role is read-only from the database and cannot be spoofed at the frontend.

**Validates: Requirements 2.1, 2.2 (Admin role hardcoding fix)**

Property 2: Device Ownership Enforcement

_For any_ GET /devices or GET /devices/{id} request from a non-admin user, the fixed backend SHALL:
1. Query Device records filtering by Device.user_id == current_user.id
2. If user is admin, return all devices in the organization
3. If user is analyst trying to GET a device with different user_id, return 403 Forbidden

This ensures analysts cannot access devices they don't own.

**Validates: Requirements 2.3, 2.4 (Device access control)**

Property 3: Real Scan Records Created

_For any_ POST /devices/{id}/scan request that succeeds, the fixed code SHALL:
1. Create a ScanLog record with device_id, user_id, and files_scanned from real scan
2. Create Incident records for any findings (risk_score >= 30)
3. Return response with actual persisted values from database
4. NOT return hardcoded mock scan numbers (45 files, 0 findings)

This ensures scans are auditable and counted accurately.

**Validates: Requirements 2.5, 2.6 (Fake scan success fix)**

Property 4: Backend Error on Unavailability

_For any_ request where backend is unavailable or times out (after 20 seconds), the fixed frontend SHALL:
1. Return 502 Bad Gateway error (not mock success data)
2. Include error message: "Backend service unavailable. Please try again."
3. Allow user to retry the request

This ensures users are not deceived by false mock data.

**Validates: Requirements 2.7, 2.8 (Mock precedence fix)**

Property 5: Real Dashboard Aggregation

_For any_ GET /dashboard/stats request, the fixed backend SHALL:
1. Query ScanLog table and SUM(files_scanned) for user's devices (if analyst) or all org devices (if admin)
2. Query Incident table and COUNT WHERE risk_score >= 50 (sensitive files)
3. Query Incident table and COUNT WHERE risk_score >= 75 (critical incidents)
4. Return response with actual aggregated values, not hardcoded 1845

This ensures dashboard statistics reflect real scan activity.

**Validates: Requirements 2.9, 2.10 (Dashboard false data fix)**

Property 6: Preservation – Non-Buggy Inputs Unchanged

_For any_ input that does NOT trigger the bug condition (valid backend response, no timeout, authenticated user accessing their own resources), the fixed system SHALL:
1. Produce the same result as the original system
2. Maintain identical UI behavior, buttons, error messages
3. Preserve device enrollment, incident updates, and user management flows

This ensures we don't break existing functionality while fixing the security issues.

**Validates: Requirements 3.1, 3.2, 3.3 (Preservation requirements)**

---

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

#### File 1: `frontend/lib/auth.ts` – Fetch role from backend after login

**Current State:**
- `saveUser({ username, role })` saves role directly from login response
- No subsequent GET /auth/me call to verify role

**Changes:**
1. Add function `fetchUserProfileFromBackend()` that calls GET /auth/me
2. Modify login flow to call this function after receiving JWT
3. Extract role from User.role field (not from login response directly)

```typescript
export async function fetchUserProfileFromBackend(jwt: string): Promise<{username, role, email} | null> {
  // Make GET /auth/me with Bearer JWT
  // Parse response, extract User.role from database
  // Return {username, role, email}
}
```

#### File 2: `frontend/app/login/page.tsx` – Call backend role verification

**Current State:**
- Line 34: `role: "admin"` hardcoded for all users
- Line 60: Async sync attempt but doesn't wait for result

**Changes:**
1. After `/api/auth/login` succeeds, wait for GET /auth/me call
2. Extract role from response
3. Only store JWT in localStorage (not role directly)

```typescript
// After login succeeds:
const jwt = data.access_token;
const profile = await fetchUserProfileFromBackend(jwt);
saveJwt(jwt);
saveUser({ username: profile.username, role: profile.role });
```

#### File 3: `frontend/lib/AuthContext.tsx` – Re-verify role on page load

**Current State:**
- AuthProvider loads user from localStorage.dg_user
- Trusts saved role without backend verification

**Changes:**
1. On initial load, call GET /auth/me with stored JWT
2. Re-verify role from backend
3. Update state if role has changed

#### File 4: `backend/api/device_routes.py` – Add ownership validation

**Current State:**
- GET /devices does NOT filter by user_id
- GET /devices/{id} does NOT check ownership

**Changes:**
1. GET /devices: Add WHERE clause:
   ```python
   if current_user.role == "analyst":
       query = query.filter(Device.user_id == current_user.id)
   ```

2. GET /devices/{id}: Add ownership check:
   ```python
   if device.user_id != current_user.id and current_user.role != "admin":
       raise HTTPException(status_code=403, detail="Access denied")
   ```

3. POST /devices/enrollment/register: Set device owner:
   ```python
   device = Device(..., user_id=current_user.id)  # Ensure field is set
   ```

#### File 5: `backend/models.py` – Database schema changes

**Current State:**
- Device.user_id field exists but is nullable and never set
- No foreign key constraint

**Changes:**
1. Add database migration (or SQL directly):
   ```sql
   ALTER TABLE devices ADD CONSTRAINT fk_device_user 
     FOREIGN KEY (user_id) REFERENCES users(id);
   CREATE INDEX idx_device_user_id ON devices(user_id);
   ALTER TABLE devices MODIFY user_id INT NOT NULL;
   ```

#### File 6: `frontend/app/api/[...path]/route.ts` – Disable mock fallbacks

**Current State:**
- Line 99: 8-second timeout (too short)
- Line 100: Falls through to mock handler on timeout
- Mock handlers return hardcoded success for all endpoints

**Changes:**
1. Increase timeout to 20 seconds:
   ```typescript
   const timer = setTimeout(() => controller.abort(), 20000);
   ```

2. Remove mock success responses for production endpoints:
   - DELETE mock login handler (keep backend only)
   - DELETE mock device list handler
   - DELETE mock scan handler
   - DELETE mock dashboard handler

3. For auth, devices, scan, dashboard: Return 502 error if backend unavailable
   ```typescript
   return NextResponse.json(
     { detail: "Backend service unavailable. Please try again." },
     { status: 502 }
   );
   ```

4. KEEP mock enrollment-status for polling (short-lived, not persisted)

#### File 7: `backend/api/device_routes.py` – Scan endpoint ownership check

**Current State:**
- POST /devices/{id}/scan does NOT verify device ownership
- Response returns fields but may contain stale mock data if frontend intercepted

**Changes:**
1. Add ownership validation:
   ```python
   if device.user_id != current_user.id and current_user.role != "admin":
       raise HTTPException(status_code=403, detail="Access denied")
   ```

2. Ensure response includes real database fields from ScanLog:
   ```python
   return {
       status: "success",
       files_scanned: scan_log.files_scanned,  # Real count
       incidents_count: len(incidents),        # Real count
       ...
   }
   ```

#### File 8: `backend/api/dashboard_routes.py` – Real aggregation queries

**Current State:**
- Line X: Returns hardcoded `{ files_scanned: 1845, ... }`
- No database queries

**Changes:**
1. Get user's devices:
   ```python
   if current_user.role == "analyst":
       devices = db.query(Device).filter(Device.user_id == current_user.id)
   else:
       devices = db.query(Device).filter(Device.organization_id == current_user.organization_id)
   ```

2. Aggregate scan data:
   ```python
   files_scanned = db.query(func.sum(ScanLog.files_scanned))
                     .join(Device)
                     .filter(Device.id.in_([d.id for d in devices]))
                     .scalar() or 0
   ```

3. Aggregate incident data:
   ```python
   sensitive_files = db.query(Incident).filter(
       Incident.risk_score >= 50,
       Incident.device_id.in_([d.device_id for d in devices])
   ).count()
   ```

4. Return real aggregated values:
   ```python
   return {
       files_scanned: files_scanned,        # Real count
       sensitive_files: sensitive_files,    # Real count
       critical_incidents: critical_count,  # Real count
       ...
   }
   ```

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan:** 
- Write tests that simulate each bug condition
- Run on UNFIXED code to observe failures
- Document actual failure modes

**Test Cases**:

1. **Bug #1 – Admin Role Hardcoding Test**
   - Create analyst user account
   - Log in with analyst credentials
   - Check localStorage.dg_user.role
   - **Expected (unfixed):** "admin" (BUG)
   - **Expected (fixed):** "analyst"

2. **Bug #2 – Device Access Control Test**
   - Create Analyst-1 and Analyst-2 with separate devices
   - Log in as Analyst-1
   - Make GET /devices request
   - **Expected (unfixed):** Returns all org devices including Analyst-2's (BUG)
   - **Expected (fixed):** Returns only Analyst-1's devices

3. **Bug #3 – Fake Scan Success Test**
   - Trigger POST /devices/{id}/scan via frontend
   - Check if ScanLog record created in database
   - **Expected (unfixed):** No record created, mock response returned (BUG)
   - **Expected (fixed):** ScanLog record with real file count

4. **Bug #4 – Mock Precedence Test**
   - Kill backend server
   - Make GET /dashboard/stats request
   - **Expected (unfixed):** 200 OK with hardcoded mock stats (BUG)
   - **Expected (fixed):** 502 Bad Gateway error

5. **Bug #5 – Dashboard Aggregation Test**
   - Perform 2 scans: 10 files + 15 files
   - Check GET /dashboard/stats response
   - **Expected (unfixed):** files_scanned = 1845 (hardcoded, BUG)
   - **Expected (fixed):** files_scanned = 25 (aggregated)

**Expected Counterexamples on Unfixed Code:**
- Analysts see "admin" in UI controls
- Device queries return all org devices (no WHERE clause)
- Scan responses contain mock data (45 files hardcoded)
- Backend unavailability returns 200 with mock data
- Dashboard shows same stats regardless of actual scans

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL user IN [admin, analyst_1, analyst_2]:
  FOR ALL operation IN [login, get_devices, trigger_scan, get_dashboard]:
    IF isBugCondition(operation, user):
      result := fixed_operation(user)
      ASSERT expectedBehavior(result, user, operation)
END FOR
```

**Test Implementation:**
1. Test login flow with various user roles → verify role from backend
2. Test device listing → verify filtering by user_id
3. Test scan triggering → verify ScanLog creation
4. Test dashboard → verify real aggregation
5. Test backend errors → verify 502 returned

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (valid backend responses, authenticated users accessing their own resources), the fixed system produces the same result as the original.

**Pseudocode:**
```
FOR ALL request WHERE NOT isBugCondition(request):
  ASSERT fixed_code(request) == original_code(request)
END FOR
```

**Testing Approach:** Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases (e.g., empty device list, single incident, zero scans)
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan:** Observe behavior on UNFIXED code first for valid backend responses, then write tests to verify this continues after fix.

**Test Cases**:

1. **Preservation – Valid Backend Response**
   - Backend responds within timeout (no bug condition)
   - Response is proxied as-is to frontend
   - **Verify:** Fixed code returns identical response

2. **Preservation – Admin Sees All Devices**
   - Admin user logs in
   - Makes GET /devices request
   - **Verify:** Returns all org devices (same as before)

3. **Preservation – Device Enrollment**
   - User enrolls new device via POST /devices/enrollment/register
   - **Verify:** Device is created with user_id set (new field, non-breaking)

4. **Preservation – Incident Status Update**
   - PATCH /incidents/{id} with new status
   - **Verify:** Works identically before and after fix

5. **Preservation – UI Elements Unchanged**
   - Login page button text, labels, error messages
   - Dashboard chart layout, colors
   - Device list column order
   - **Verify:** No visual changes after fix

6. **Preservation – Firebase Auth Path**
   - Google sign-in flow continues to work
   - Firebase token verification unchanged
   - **Verify:** Firebase users still authenticate successfully

### Unit Tests

- Test `fetchUserProfileFromBackend()` with mock responses
- Test device ownership validation in query builder
- Test scan response aggregation
- Test dashboard query generation and aggregation
- Test timeout handling and error responses
- Test role-based query filters

### Property-Based Tests

- Generate random user roles (admin, analyst) and verify correct query filters are applied
- Generate random device ownership scenarios and verify access control
- Generate random scan counts and verify dashboard aggregation
- Generate random backend response times and verify timeout/error handling
- Generate random incident risk scores and verify critical/sensitive classification

### Integration Tests

- End-to-end: Register user → Login → View devices → Trigger scan → Check dashboard
- Multi-role: Admin sees all data, analyst sees own data only
- Context switching: Admin switch to analyst view, verify filtering applies
- Scan to incident: Trigger scan → Check ScanLog created → Verify dashboard updated
- Backend failures: Verify 502 returned when backend unavailable

---

## Implementation Dependencies

1. **Database schema** must be updated FIRST (add constraints, indexes, set user_id on existing devices)
2. **Backend device routes** must add ownership validation BEFORE frontend changes
3. **Backend dashboard** must use real queries BEFORE frontend updates
4. **Frontend auth** must call GET /auth/me AFTER backend is ready
5. **Frontend mock handlers** must be disabled LAST (after backend is verified working)

---

## Verification Checklist

After implementing all fixes, verify:

- [ ] Analyst user logs in, role is "analyst" (not "admin")
- [ ] Analyst GET /devices returns only their devices
- [ ] Analyst GET /devices/{other-analyst-device} returns 403 Forbidden
- [ ] Scan triggers create ScanLog record with real file count
- [ ] Dashboard shows aggregated scan counts, not hardcoded 1845
- [ ] Backend unavailability returns 502 (not mock data)
- [ ] Admin still sees all org devices
- [ ] Device enrollment sets user_id correctly
- [ ] Login redirect delay reduced (no waiting for async profile sync)
- [ ] All existing tests pass (preservation validation)

