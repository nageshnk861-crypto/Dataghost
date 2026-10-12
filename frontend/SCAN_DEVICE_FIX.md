# ROOT CAUSE IDENTIFIED

## Problem
POST /api/devices/{id}/scan returns mock response instead of real scan data.

Mock Response (Line 556-562, frontend/app/api/[...path]/route.ts):
```
{
  status: "COMPLETED",
  scanned_files: 45,
  findings_count: 0,
  risk_level: "LOW",
  timestamp: new Date().toISOString(),
}
```

Expected Response (backend/api/device_routes.py:1060):
```
{
  status: "success",
  device: { device_id, device_name, files_scanned, incidents_count, ... },
  scanned_files_count: N,
  threats_detected: X,
  scan_results: [ ... ]
}
```

## Why Frontend Shows 0 FILES SCANNED
1. Mock scan endpoint doesn't increment device.files_scanned
2. Device list returns stale data with files_scanned: 0
3. UI displays 0 because device data never updated in mock store

## Fix Strategy
1. Improve proxy timeout (2s ? 8s)
2. Update mock scan to match backend response structure
3. Increment mock device counters during scan
4. Test with backend when deployed
