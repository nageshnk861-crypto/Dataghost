# Bugfix Requirements: Two-Role Security Architecture

## Introduction

This bugfix addresses critical security vulnerabilities in the authentication, device access control, and data persistence layers. The current implementation trusts frontend-supplied data, lacks per-user device ownership validation, returns mock data instead of real scan results, and uses mock endpoints that override backend operations. These issues compromise the security model where users should only access their own data based on their verified role (admin or analyst).

The five critical issues form a dependency chain:
1. Fix admin role hardcoding (unblocks all other fixes)
2. Implement device ownership filtering
3. Persist real scan results to database
4. Stop using mock endpoints for production operations
5. Aggregate real data in dashboard

## Bug Analysis

### ISSUE 1: Admin Role Hardcoding

#### Current Behavior (Defect)

1.1 WHEN a user logs in through the frontend THEN the system sets role: "admin" in localStorage regardless of their actual role

1.2 WHEN a logged-in user reloads the page THEN the system displays role: "admin" from localStorage despite the backend User record containing a different role

1.3 WHEN the frontend API route processes login requests THEN the mock handler returns role: "admin" for all users without verifying against backend

#### Expected Behavior (Correct)

2.1 WHEN a user logs in through the frontend THEN the system fetches the user's role from the backend User record and stores it in localStorage

2.2 WHEN a logged-in user reloads the page THEN the system verifies the stored role against the current backend User record before using it

2.3 WHEN the frontend receives authentication data THEN the system SHALL verify role values only from backend-signed responses, never trusting frontend role assignment

#### Unchanged Behavior (Regression Prevention)

3.1 WHEN a valid user logs in with correct credentials THEN the system SHALL CONTINUE TO authenticate successfully and establish a session

3.2 WHEN a user logs out THEN the system SHALL CONTINUE TO clear all session data including role from localStorage

3.3 WHEN a user provides incorrect credentials THEN the system SHALL CONTINUE TO reject the login attempt

---

### ISSUE 2: Device Access Control Gap

#### Current Behavior (Defect)

1.4 WHEN an analyst user requests GET /devices THEN the system returns all devices in their organization regardless of ownership

1.5 WHEN accessing a device detail endpoint THEN the system returns device data without verifying the requesting user owns the device

1.6 WHEN viewing devices via frontend THEN the system displays all organization devices in the UI regardless of the current user's role

#### Expected Behavior (Correct)

2.4 WHEN an analyst user requests GET /devices THEN the system SHALL return only devices where device.user_id equals the authenticated user's ID

2.5 WHEN an admin user requests GET /devices THEN the system SHALL return all devices in their organization

2.6 WHEN accessing a device detail endpoint THEN the system SHALL verify (role == "admin" OR device.user_id == authenticated_user_id) before returning device data

2.7 WHEN a user attempts to access another user's device via direct URL manipulation THEN the system SHALL return 403 Forbidden

#### Unchanged Behavior (Regression Prevention)

3.4 WHEN an admin user views devices THEN the system SHALL CONTINUE TO return all organization devices with full details

3.5 WHEN performing device management operations (enroll, configure) THEN the system SHALL CONTINUE TO require valid device IDs and proper authentication

---

### ISSUE 3: Fake Scan Success

#### Current Behavior (Defect)

1.7 WHEN a user clicks "Scan Device" in the UI THEN the system returns a mock success response with hardcoded "0 FILES SCANNED" without executing actual backend scan logic

1.8 WHEN a scan completes THEN no ScanLog record is created in the database despite the frontend displaying success

1.9 WHEN a scan completes THEN no Incident record is created even if findings exceed risk threshold of 30

1.10 WHEN accessing scan results THEN the system displays mock data fields (files_scanned, findings_count, risk_score) that do not correspond to database records

#### Expected Behavior (Correct)

2.8 WHEN a user clicks "Scan Device" THEN the system SHALL proxy to backend POST /devices/{id}/scan and return actual results, or return 502/503 error if backend unavailable

2.9 WHEN a scan completes successfully THEN the system SHALL create a ScanLog record with actual scanned file counts and findings

2.10 WHEN a scan completes successfully THEN the system SHALL create Incident records for findings with risk_score >= 30

2.11 WHEN returning scan results THEN the system SHALL include only database-persisted fields: files_scanned, findings_count, risk_score, timestamp

2.12 WHEN an analyst user initiates a scan THEN the system SHALL verify device.user_id == authenticated_user_id before allowing the scan

#### Unchanged Behavior (Regression Prevention)

3.6 WHEN a valid device exists and is ready for scanning THEN the system SHALL CONTINUE TO support scan initiation with proper authentication

3.7 WHEN a scan encounters an error during execution THEN the system SHALL CONTINUE TO return appropriate error messages without creating spurious records

---

### ISSUE 4: Mock Precedence Over Backend

#### Current Behavior (Defect)

1.11 WHEN a user performs an operation (auth, devices, scan, dashboard) AND the backend times out THEN the system serves mock responses instead of backend data

1.12 WHEN backend processing takes longer than 8 seconds THEN the system falls back to mock handlers instead of waiting for valid responses

1.13 WHEN mock handlers execute THEN users see demo/hardcoded data even though real backend is running or would have provided correct data

#### Expected Behavior (Correct)

2.13 WHEN a user performs an operation AND backend is unavailable THEN the system SHALL return a 502/503 error with message "Backend unavailable" instead of mock data

2.14 WHEN a user initiates a scan or other long-running operation THEN the system SHALL wait up to 15-30 seconds for backend response before timing out

2.15 WHEN operating in production THEN the system SHALL NOT serve mock responses for auth, devices, scan, or dashboard endpoints

2.16 WHEN operating in production THEN the system SHALL ONLY use mock responses for enrollment-in-progress and enrollment-status polling (short-lived operations)

#### Unchanged Behavior (Regression Prevention)

3.8 WHEN a backend service is temporarily unavailable during development THEN the system SHALL CONTINUE TO allow developers to use mock data when explicitly configured

---

### ISSUE 5: Dashboard Shows False Data

#### Current Behavior (Defect)

1.14 WHEN accessing the dashboard THEN the system returns hardcoded mock statistics (1845 files scanned, 42 sensitive files, 2 critical incidents) regardless of actual scan data

1.15 WHEN an analyst views the dashboard THEN the system displays all organization incidents instead of only incidents from their own devices

1.16 WHEN dashboard aggregation runs THEN no computation occurs against ScanLog and Incident database tables

#### Expected Behavior (Correct)

2.17 WHEN accessing the dashboard THEN the system SHALL aggregate real statistics from ScanLog and Incident database tables

2.18 WHEN calculating files_scanned THEN the system SHALL sum ScanLog.files_count for all applicable records (admin: org-wide, analyst: own devices only)

2.19 WHEN calculating sensitive_files count THEN the system SHALL count Incident records where risk_score >= 50 for all applicable records

2.20 WHEN calculating critical_incidents count THEN the system SHALL count Incident records where risk_score >= 75 for all applicable records

2.21 WHEN an analyst accesses the dashboard THEN the system SHALL filter statistics to show only incidents and scans from devices where device.user_id == authenticated_user_id

2.22 WHEN an admin accesses the dashboard THEN the system SHALL filter statistics to show all incidents and scans across the organization

#### Unchanged Behavior (Regression Prevention)

3.9 WHEN dashboard data is fetched THEN the system SHALL CONTINUE TO authenticate requests and verify user permissions

3.10 WHEN dashboard calculations complete THEN the system SHALL CONTINUE TO return statistics in the same JSON format as before
