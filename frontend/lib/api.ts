"use client";

/**
 * DataGhost – centralised typed API client.
 * All functions delegate to apiFetch from lib/auth (which adds Bearer token
 * and handles 401 → redirect to /login).
 */
import { apiFetch } from "@/lib/auth";

// ─── TypeScript interfaces ───────────────────────────────────────────────────

export interface ThreatItem {
  incident_id: string;
  filename: string;
  risk_score: number;
  severity: string;
  user: string;
  timestamp: string;
  action_taken: string;
  // Legacy backend fields
  label?: string;
  score?: number;
}

export interface DashboardStats {
  protected_devices: number;
  files_scanned: number;
  sensitive_files: number;
  blocked_transfers: number;
  critical_incidents: number;
  recent_threats: ThreatItem[];
}

export interface ActivityDataPoint {
  date: string;
  scans: number;
  sensitive: number;
  blocked: number;
}

export interface RiskSegment {
  name: string;
  value: number;
  color: string;
}

export interface IncidentRow {
  incident_id: string;
  timestamp: string;
  user: string;
  filename: string;
  classification: string;
  risk_score: number;
  severity: string;
  action_taken: string;
  destination?: string;
  device_id?: string;
  findings_json?: string;
  status?: string;
}

export interface IncidentParams {
  page?: number;
  per_page?: number;
  severity?: string;
  status?: string;
  classification?: string;
}

export interface IncidentListResponse {
  items: IncidentRow[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface Device {
  id?: number;
  device_id?: string;
  device_name: string;
  platform?: string;
  os_name?: string;
  os_version?: string;
  architecture?: string;
  hostname?: string;
  ip_address: string;
  os_type: string;
  status: string;
  last_seen: string;
  enrolled_at?: string;
  registered_at?: string;
  organization_id?: string;
  user_id?: string;
  device_metadata?: string;
  files_scanned: number;
  agent_version: string;
  incidents_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface EnrollmentCreateResponse {
  enrollment_code: string;
  raw_token: string;
  platform: string;
  qr_data: string;
  server_url: string;
  expires_at: string;
  expires_in_seconds: number;
  status: string;
}

export interface EnrollmentStatusResponse {
  enrollment_code: string;
  platform: string;
  status: string;
  device_id?: string;
  device_name?: string;
  used_at?: string;
  expires_at: string;
  is_expired: boolean;
}

export interface DeviceDetail extends Device {
  last_scan?: string | null;
  last_incident?: string | null;
  policy_status?: string;
  recent_incidents?: IncidentRow[];
}

export interface ProvisioningRecord {
  id: string;
  platform: string;
  status: string;
  device_count?: number;
  created_at: string;
  expires_at: string;
  last_used_at?: string | null;
  enrollment_code?: string;
  qr_data?: string;
}

export interface EnrollmentPolicy {
  id: string;
  name: string;
  platform: string;
  organization_id?: string;
  compliance_level: string;
  dlp_rules?: Array<{ id: string; name: string }>;
  require_attestation: boolean;
  created_at: string;
  status?: string;
}


export interface ScanFinding {
  rule_name?: string;
  rule?: string;
  category: string;
  severity: string;
  matches_count?: number;
  sample_match?: string;
  matched_text?: string;
}

export interface ScanResultData {
  filename: string;
  file_size?: number;
  file_hash?: string;
  classification: string;
  decision_score: number;
  risk_score: number;
  severity: string;
  action_taken: string;
  findings: ScanFinding[];
  incident_id?: string | null;
  breakdown?: Record<string, unknown>;
}

export interface ScanTextPayload {
  text: string;
  filename?: string;
  destination?: string;
  action?: string;
  device_id?: string;
  user?: string;
}

// ─── Helper for handling API responses ─────────────────────────────────────────

async function handleResponse<T>(res: Response, endpoint: string): Promise<T> {
  if (res.ok) {
    return res.json();
  }
  let detail = "";
  try {
    const data = await res.json();
    detail = data.detail || data.message || "";
  } catch {
    // Ignore JSON parsing failure
  }
  const isDev = process.env.NODE_ENV !== "production";
  const devInfo = isDev ? ` [Endpoint: ${endpoint} | HTTP ${res.status}]` : "";

  if (res.status === 401) {
    throw new Error(detail || `Authentication required or session expired. Please log in again.${devInfo}`);
  }
  if (res.status === 403) {
    throw new Error(detail || `Access forbidden. You do not have permission for this resource.${devInfo}`);
  }
  if (res.status === 404) {
    throw new Error(detail || `API endpoint not found: ${endpoint}.${devInfo}`);
  }
  if (res.status >= 500) {
    throw new Error(detail || `Backend server error (HTTP ${res.status}). Please check backend logs.${devInfo}`);
  }

  const baseMsg = detail || `Request failed with status ${res.status}`;
  throw new Error(`${baseMsg}${devInfo}`);
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const res = await apiFetch("/api/dashboard/stats");
  return handleResponse<DashboardStats>(res, "/api/dashboard/stats");
}

export async function fetchDashboardActivity(): Promise<ActivityDataPoint[]> {
  const res = await apiFetch("/api/dashboard/activity");
  return handleResponse<ActivityDataPoint[]>(res, "/api/dashboard/activity");
}

// ─── Incidents ───────────────────────────────────────────────────────────────

export async function fetchIncidents(params: IncidentParams = {}): Promise<IncidentListResponse> {
  const q = new URLSearchParams();
  if (params.page != null) q.set("page", String(params.page));
  if (params.per_page != null) q.set("per_page", String(params.per_page));
  if (params.severity && params.severity !== "ALL") q.set("severity", params.severity);
  if (params.status && params.status !== "ALL") q.set("status", params.status);
  if (params.classification && params.classification !== "ALL") q.set("classification", params.classification);
  const qs = q.toString();
  const endpoint = `/api/incidents${qs ? "?" + qs : ""}`;
  const res = await apiFetch(endpoint);
  return handleResponse<IncidentListResponse>(res, endpoint);
}

export async function patchIncidentStatus(
  incidentId: string,
  status: string
): Promise<IncidentRow> {
  const endpoint = `/api/incidents/${incidentId}`;
  const res = await apiFetch(endpoint, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  return handleResponse<IncidentRow>(res, endpoint);
}

// ─── Devices ─────────────────────────────────────────────────────────────────

export async function fetchDevices(): Promise<Device[]> {
  const res = await apiFetch("/api/devices");
  return handleResponse<Device[]>(res, "/api/devices");
}

export async function createEnrollmentToken(platform: string): Promise<EnrollmentCreateResponse> {
  const endpoint = "/api/devices/enrollment/create";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify({ platform }),
  });
  return handleResponse<EnrollmentCreateResponse>(res, endpoint);
}

export async function createEasyEnrollmentToken(platform: string): Promise<EnrollmentCreateResponse> {
  const endpoint = "/api/devices/enrollment/create-easy";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify({ platform }),
  });
  return handleResponse<EnrollmentCreateResponse>(res, endpoint);
}


export async function createAndroidEnterpriseEnrollmentToken(): Promise<EnrollmentCreateResponse> {
  const endpoint = "/api/devices/enrollment/create-android-enterprise";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify({ platform: "Android" }),
  });
  return handleResponse<EnrollmentCreateResponse>(res, endpoint);
}


export async function fetchEnrollmentStatus(codeOrToken: string): Promise<EnrollmentStatusResponse> {
  const endpoint = `/api/devices/enrollment/status/${encodeURIComponent(codeOrToken)}`;
  const res = await apiFetch(endpoint);
  return handleResponse<EnrollmentStatusResponse>(res, endpoint);
}

export async function registerEnrollmentDevice(payload: {
  enrollment_code?: string;
  token?: string;
  device_name: string;
  platform?: string;
  os_name?: string;
  os_version?: string;
  hostname?: string;
}): Promise<any> {
  const endpoint = "/api/devices/enrollment/register";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return handleResponse<any>(res, endpoint);
}

export async function fetchDeviceDetail(deviceId: string): Promise<DeviceDetail> {
  const endpoint = `/api/devices/${encodeURIComponent(deviceId)}`;
  const res = await apiFetch(endpoint);
  return handleResponse<DeviceDetail>(res, endpoint);
}

export async function updateDevice(
  deviceId: string,
  updates: { device_name?: string; status?: string }
): Promise<Device> {
  const endpoint = `/api/devices/${encodeURIComponent(deviceId)}`;
  const res = await apiFetch(endpoint, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
  return handleResponse<Device>(res, endpoint);
}

export async function deleteDevice(deviceId: string): Promise<{ status: string; message: string }> {
  const endpoint = `/api/devices/${encodeURIComponent(deviceId)}`;
  const res = await apiFetch(endpoint, {
    method: "DELETE",
  });
  return handleResponse<{ status: string; message: string }>(res, endpoint);
}

export async function triggerDeviceScan(
  deviceId: string,
  payload?: {
    file_path?: string;
    custom_content?: string;
    filename?: string;
    destination?: string;
    action?: string;
  }
): Promise<any> {
  const endpoint = `/api/devices/${encodeURIComponent(deviceId)}/scan`;
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: payload ? JSON.stringify(payload) : undefined,
  });
  return handleResponse<any>(res, endpoint);
}


// ─── Scanner ─────────────────────────────────────────────────────────────────

export async function scanFile(file: File, opts: {
  destination?: string;
  action?: string;
  device_id?: string;
  user?: string;
} = {}): Promise<ScanResultData> {
  const form = new FormData();
  form.append("file", file);
  form.append("destination", opts.destination ?? "EXTERNAL");
  form.append("action", opts.action ?? "UPLOAD");
  form.append("device_id", opts.device_id ?? "WEB-CONSOLE");
  form.append("user", opts.user ?? "web_analyst");

  // apiFetch detects FormData body and omits Content-Type so the browser
  // sets the correct multipart boundary automatically.
  const endpoint = "/api/scan/file";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: form,
  });

  return handleResponse<ScanResultData>(res, endpoint);
}

export async function scanText(payload: ScanTextPayload): Promise<ScanResultData> {
  const endpoint = "/api/scan/text";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify({
      text: payload.text,
      filename: payload.filename ?? "demo.txt",
      destination: payload.destination ?? "EXTERNAL",
      action: payload.action ?? "UPLOAD",
      device_id: payload.device_id ?? "WEB-CONSOLE",
      user: payload.user ?? "web_analyst",
    }),
  });
  return handleResponse<ScanResultData>(res, endpoint);
}

// ─── Admin: Device Provisioning ──────────────────────────────────────────────

export async function fetchProvisioningRecords(
  limit: number = 50,
  offset: number = 0,
  platform?: string,
  status?: string
): Promise<ProvisioningRecord[]> {
  const q = new URLSearchParams();
  q.set("limit", String(limit));
  q.set("offset", String(offset));
  if (platform) q.set("platform", platform);
  if (status) q.set("status", status);
  const qs = q.toString();
  const endpoint = `/api/v1/device-provisioning?${qs}`;
  const res = await apiFetch(endpoint);
  return handleResponse<ProvisioningRecord[]>(res, endpoint);
}

export async function createProvisioningRecord(
  platform: string,
  organizationId: string,
  deviceCount: number = 1,
  expirationDays: number = 7
): Promise<EnrollmentCreateResponse> {
  const endpoint = "/api/v1/device-provisioning/create";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify({
      platform,
      organization_id: organizationId,
      device_count: deviceCount,
      expiration_days: expirationDays,
    }),
  });
  return handleResponse<EnrollmentCreateResponse>(res, endpoint);
}

export async function revokeProvisioningRecord(recordId: string): Promise<{ status: string }> {
  const endpoint = `/api/v1/device-provisioning/${encodeURIComponent(recordId)}/revoke`;
  const res = await apiFetch(endpoint, {
    method: "POST",
  });
  return handleResponse<{ status: string }>(res, endpoint);
}

// ─── Admin: Device Management ────────────────────────────────────────────────

export async function resetDeviceEnrollment(deviceId: string): Promise<Device> {
  const endpoint = `/api/v1/devices/${encodeURIComponent(deviceId)}/reset-enrollment`;
  const res = await apiFetch(endpoint, {
    method: "POST",
  });
  return handleResponse<Device>(res, endpoint);
}

export async function disableDevice(deviceId: string): Promise<Device> {
  const endpoint = `/api/v1/devices/${encodeURIComponent(deviceId)}`;
  const res = await apiFetch(endpoint, {
    method: "PATCH",
    body: JSON.stringify({ status: "DISABLED" }),
  });
  return handleResponse<Device>(res, endpoint);
}

// ─── Admin: Enrollment Policies ──────────────────────────────────────────────

export async function fetchEnrollmentPolicies(
  limit: number = 50,
  offset: number = 0,
  platform?: string,
  org?: string
): Promise<EnrollmentPolicy[]> {
  const q = new URLSearchParams();
  q.set("limit", String(limit));
  q.set("offset", String(offset));
  if (platform) q.set("platform", platform);
  if (org) q.set("organization", org);
  const qs = q.toString();
  const endpoint = `/api/v1/enrollment-policies?${qs}`;
  const res = await apiFetch(endpoint);
  return handleResponse<EnrollmentPolicy[]>(res, endpoint);
}

export async function createEnrollmentPolicy(
  name: string,
  platform: string,
  organizationId: string,
  ruleIds: string[],
  complianceLevel: string = "MEDIUM",
  requireAttestation: boolean = false
): Promise<EnrollmentPolicy> {
  const endpoint = "/api/v1/enrollment-policies/create";
  const res = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify({
      name,
      platform,
      organization_id: organizationId,
      dlp_rule_ids: ruleIds,
      compliance_level: complianceLevel,
      require_attestation: requireAttestation,
    }),
  });
  return handleResponse<EnrollmentPolicy>(res, endpoint);
}

// ─── Health Check ─────────────────────────────────────────────────────────────

export interface HealthCheckResult {
  status: string;
  version?: string;
}

export async function checkHealth(): Promise<HealthCheckResult> {
  const endpoint = "/health";
  const res = await apiFetch(endpoint);
  return handleResponse<HealthCheckResult>(res, endpoint);
}

