# DataGhost iOS Agent

An Enterprise-ready Data Loss Prevention (DLP) agent integration architecture for iOS endpoints.

## Apple Security & MDM Guidelines
1. **Privacy & Security Sandbox Compliant**: Complies strictly with Apple App Store Guidelines and iOS Application Sandboxing. Does NOT bypass iOS system security or request private system/root access.
2. **Apple MDM Integration**: Supports Mobile Device Management (MDM) deployment via Apple Business Manager / Managed App Configuration (`com.apple.configuration.managed`).
3. **QR & Managed Enrollment**: Supports enrollment via QR code scan or automated payload delivery via Managed App Config.
4. **Unique Device Identifier**: Receives a permanent, non-sequential device ID (`dg-ios-xxxx`) upon backend registration.
5. **Background Heartbeat**: Utilizes `BGTaskScheduler` (Background App Refresh) to transmit periodic heartbeat telemetry.

---

## Directory Structure
- `DataGhostAgent/`:
  - `DataGhostEnrollmentManager.swift`: Handles QR parsing & registration API calls.
  - `DataGhostHeartbeatManager.swift`: Schedules iOS background heartbeats.
  - `DataGhostDLPManager.swift`: Handles user-selected document scanning & security policy enforcement.
  - `DataGhostMDMProfile.mobileconfig`: Sample Mobile Device Management XML configuration payload.
