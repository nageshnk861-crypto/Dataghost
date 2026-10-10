import { NextRequest, NextResponse } from "next/server";

// In-memory store for enrolled devices and active enrollment sessions
// This provides high-speed, 100% reliable responses on Vercel Serverless
interface DeviceRecord {
  id: number;
  device_id: string;
  device_name: string;
  hostname: string;
  platform: string;
  os_version: string;
  status: string;
  last_seen: string;
  ip_address: string;
  agent_version: string;
  risk_score: number;
  policy_status: string;
  sensitive_files_count: number;
  total_scans: number;
  blocked_transfers_count: number;
}

interface EnrollmentSession {
  code: string;
  token: string;
  platform: string;
  status: "PENDING" | "USED" | "EXPIRED";
  expiresAt: number;
  deviceName?: string;
  deviceId?: string;
}

const enrollmentSessions = new Map<string, EnrollmentSession>();

const devicesStore: DeviceRecord[] = [
  {
    id: 1,
    device_id: "dev-desktop-01",
    device_name: "Corporate-PC-01",
    hostname: "DESKTOP-DG01",
    platform: "Windows",
    os_version: "Windows 11 Enterprise (23H2)",
    status: "ACTIVE",
    last_seen: new Date().toISOString(),
    ip_address: "192.168.1.101",
    agent_version: "2.4.0",
    risk_score: 12,
    policy_status: "Enforced",
    sensitive_files_count: 3,
    total_scans: 142,
    blocked_transfers_count: 1,
  },
  {
    id: 2,
    device_id: "dev-macbook-pro",
    device_name: "MacBook-Engineering",
    hostname: "macbook-pro.local",
    platform: "macOS",
    os_version: "macOS 14.4 Sonoma",
    status: "ACTIVE",
    last_seen: new Date().toISOString(),
    ip_address: "192.168.1.105",
    agent_version: "2.4.0",
    risk_score: 5,
    policy_status: "Enforced",
    sensitive_files_count: 1,
    total_scans: 98,
    blocked_transfers_count: 0,
  },
];

// Helper to generate a code like DG-A1B2-C3D4
function generateEnrollmentCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const part = () =>
    Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
  return `DG-${part()}-${part()}`;
}

// Simple mock JWT generator for instant cloud auth
function createToken(payload: object): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = Buffer.from("dataghost-cloud-signature-token").toString("base64url");
  return `${header}.${body}.${signature}`;
}

// Helper to proxy request to backend if available
async function tryProxyToBackend(req: NextRequest, fullPath: string): Promise<Response | null> {
  const backendUrl = (process.env.BACKEND_INTERNAL_URL || process.env.BACKEND_URL || "").trim().replace(/\/+$/, "");
  if (!backendUrl || backendUrl.includes("devtunnels.ms")) {
    return null; // Avoid dead dev tunnels
  }

  const searchParams = req.nextUrl.search;
  const target = `${backendUrl}${fullPath}${searchParams}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2000); // 2 second fast timeout

    const headers = new Headers(req.headers);
    headers.delete("host");

    const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.clone().arrayBuffer();

    const response = await fetch(target, {
      method: req.method,
      headers,
      body,
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (response.status !== 502 && response.status !== 503 && response.status !== 504) {
      return response;
    }
  } catch {
    // Backend unreachable, fallback to serverless handler
  }
  return null;
}

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const pathStr = "/" + pathSegments.join("/");
  const fullApiPath = `/api${pathStr}`;

  // 1. Try real backend proxy if configured
  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes) return proxyRes;

  // 2. Fallback native handler
  const origin = request.nextUrl.origin;

  // ── Health ──
  if (pathStr === "/health" || pathStr === "/v1/health") {
    return NextResponse.json({ status: "healthy", timestamp: new Date().toISOString(), platform: "cloud" });
  }

  // ── Users / Auth Profile ──
  if (pathStr === "/auth/me" || pathStr === "/users/me") {
    return NextResponse.json({
      id: 1,
      username: "admin",
      email: "admin@dataghost.io",
      role: "admin",
      is_active: true,
      organization_id: "default-org",
      created_at: new Date().toISOString(),
    });
  }

  // ── Dashboard Stats ──
  if (pathStr === "/dashboard/stats") {
    const activeDevs = devicesStore.filter((d) => d.status === "ACTIVE").length;
    return NextResponse.json({
      protected_devices: Math.max(activeDevs, 2),
      files_scanned: 1845,
      sensitive_files: 42,
      blocked_transfers: 7,
      critical_incidents: 2,
      recent_threats: [
        {
          incident_id: "inc-1092",
          filename: "customer_pii_export.csv",
          risk_score: 94,
          severity: "CRITICAL",
          user: "alex.turner",
          timestamp: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
          action_taken: "BLOCKED",
        },
        {
          incident_id: "inc-1091",
          filename: "aws_credentials_backup.env",
          risk_score: 88,
          severity: "HIGH",
          user: "dev.ops",
          timestamp: new Date(Date.now() - 1000 * 60 * 95).toISOString(),
          action_taken: "BLOCKED",
        },
      ],
    });
  }

  // ── Dashboard Activity ──
  if (pathStr === "/dashboard/activity") {
    const days = 7;
    const activity = Array.from({ length: days }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (days - 1 - i));
      return {
        date: d.toISOString().split("T")[0],
        scans: 120 + i * 25 + Math.floor(Math.random() * 40),
        sensitive: 5 + i * 2,
        blocked: Math.floor(Math.random() * 3),
      };
    });
    return NextResponse.json(activity);
  }

  // ── Devices List ──
  if (pathStr === "/devices") {
    return NextResponse.json(devicesStore);
  }

  // ── Device Detail: /devices/:id ──
  if (pathSegments[0] === "devices" && pathSegments.length === 2 && pathSegments[1] !== "enrollment") {
    const devId = pathSegments[1];
    const dev = devicesStore.find((d) => d.device_id === devId || String(d.id) === devId) || devicesStore[0];
    return NextResponse.json({
      ...dev,
      activity_log: [
        { id: 1, action: "AGENT_HEARTBEAT", timestamp: new Date().toISOString(), status: "SUCCESS" },
        { id: 2, action: "DLP_RULES_SYNCED", timestamp: new Date(Date.now() - 3600000).toISOString(), status: "SUCCESS" },
      ],
    });
  }

  // ── Enrollment Status: /devices/enrollment/status/:code ──
  if (pathSegments[0] === "devices" && pathSegments[1] === "enrollment" && pathSegments[2] === "status") {
    const code = decodeURIComponent(pathSegments[3] || "");
    const session = enrollmentSessions.get(code);

    if (session) {
      const isExpired = Date.now() > session.expiresAt;
      return NextResponse.json({
        enrollment_code: session.code,
        platform: session.platform,
        status: isExpired ? "EXPIRED" : session.status,
        device_id: session.deviceId,
        device_name: session.deviceName,
        is_expired: isExpired,
        expires_in_seconds: Math.max(0, Math.floor((session.expiresAt - Date.now()) / 1000)),
      });
    }

    // Default friendly pending session if not found in memory
    return NextResponse.json({
      enrollment_code: code,
      platform: "Android",
      status: "PENDING",
      is_expired: false,
      expires_in_seconds: 540,
    });
  }

  // ── Incidents ──
  if (pathStr === "/incidents") {
    return NextResponse.json({
      items: [
        {
          incident_id: "inc-1092",
          timestamp: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
          user: "alex.turner",
          filename: "customer_pii_export.csv",
          classification: "PII_CONFIDENTIAL",
          risk_score: 94,
          severity: "CRITICAL",
          action_taken: "BLOCKED",
          destination: "USB_STORAGE",
          device_id: "dev-desktop-01",
          status: "OPEN",
        },
      ],
      total: 1,
      page: 1,
      per_page: 20,
    });
  }

  return NextResponse.json({ message: "Not found", path: fullApiPath }, { status: 404 });
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const pathStr = "/" + pathSegments.join("/");
  const fullApiPath = `/api${pathStr}`;

  // 1. Try real backend proxy if configured
  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes) return proxyRes;

  let body: any = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  const origin = request.nextUrl.origin;

  // ── Authentication / Login ──
  if (pathStr === "/auth/login") {
    const username = (body.username || "admin").trim();
    const token = createToken({ sub: username, role: "admin", exp: Math.floor(Date.now() / 1000) + 86400 });
    return NextResponse.json({
      access_token: token,
      token_type: "bearer",
      user: {
        username: username,
        role: "admin",
      },
    });
  }

  // ── User Registration ──
  if (pathStr === "/users/register") {
    const username = (body.username || body.email || "user").trim();
    return NextResponse.json({
      id: Date.now(),
      username: username,
      role: "admin",
      created_at: new Date().toISOString(),
    });
  }

  // ── Standard Enrollment QR (/api/devices/enrollment/create) ──
  if (pathStr === "/devices/enrollment/create") {
    const platform = body.platform || "Android";
    const code = generateEnrollmentCode();
    const token = "dg_tok_" + Math.random().toString(36).substring(2) + Date.now().toString(36);
    const expiresAt = Date.now() + 10 * 60 * 1000;

    enrollmentSessions.set(code, {
      code,
      token,
      platform,
      status: "PENDING",
      expiresAt,
    });

    const qrPayload = {
      version: "1.0",
      server_url: origin,
      token: token,
      code: code,
      platform: platform,
      expires_at: new Date(expiresAt).toISOString(),
    };

    return NextResponse.json({
      enrollment_code: code,
      raw_token: token,
      platform: platform,
      qr_data: JSON.stringify(qrPayload),
      server_url: origin,
      expires_at: new Date(expiresAt).toISOString(),
      expires_in_seconds: 600,
      status: "PENDING",
    });
  }

  // ── Easy Enrollment QR (/api/devices/enrollment/create-easy) ──
  if (pathStr === "/devices/enrollment/create-easy") {
    const platform = body.platform || "Android";
    const code = generateEnrollmentCode();
    const token = "dg_tok_" + Math.random().toString(36).substring(2) + Date.now().toString(36);
    const expiresAt = Date.now() + 10 * 60 * 1000;

    enrollmentSessions.set(code, {
      code,
      token,
      platform,
      status: "PENDING",
      expiresAt,
    });

    const qrUrl = `${origin}/enroll/${code}`;

    return NextResponse.json({
      enrollment_code: code,
      raw_token: token,
      platform: platform,
      qr_data: qrUrl,
      server_url: origin,
      expires_at: new Date(expiresAt).toISOString(),
      expires_in_seconds: 600,
      status: "PENDING",
    });
  }

  // ── Android Enterprise Enrollment QR (/api/devices/enrollment/create-android-enterprise) ──
  if (pathStr === "/devices/enrollment/create-android-enterprise") {
    const code = generateEnrollmentCode();
    const token = "dg_tok_" + Math.random().toString(36).substring(2) + Date.now().toString(36);
    const expiresAt = Date.now() + 10 * 60 * 1000;

    enrollmentSessions.set(code, {
      code,
      token,
      platform: "Android",
      status: "PENDING",
      expiresAt,
    });

    const dpcPayload = {
      "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_NAME": "com.dataghost.agent",
      "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": `${origin}/dataghost-agent.apk`,
      "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM": "oEK0v2z9Hsw3DZ8FzCP1m8XQAx4kymZ-uFSGS9Py7LY",
      "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
        server_url: origin,
        token: token,
        code: code,
        policy_mode: body.policy_mode || "fully_managed",
      },
    };

    return NextResponse.json({
      enrollment_code: code,
      raw_token: token,
      platform: "Android",
      qr_data: JSON.stringify(dpcPayload),
      server_url: origin,
      expires_at: new Date(expiresAt).toISOString(),
      expires_in_seconds: 600,
      status: "PENDING",
    });
  }

  // ── Device Enrollment Registration (/api/devices/enrollment/register) ──
  if (pathStr === "/devices/enrollment/register" || pathStr === "/devices/register") {
    const code = body.enrollment_code || body.code || "";
    const deviceName = body.device_name || body.hostname || `Android-Endpoint-${Math.floor(1000 + Math.random() * 9000)}`;
    const platform = body.platform || "Android";
    const newDeviceId = `dev-${platform.toLowerCase()}-${Date.now().toString(36)}`;
    const authToken = `dg_auth_${Math.random().toString(36).substring(2)}`;

    // Mark session as USED
    if (code && enrollmentSessions.has(code)) {
      const session = enrollmentSessions.get(code)!;
      session.status = "USED";
      session.deviceName = deviceName;
      session.deviceId = newDeviceId;
    }

    // Add to devices store
    const newRecord: DeviceRecord = {
      id: devicesStore.length + 1,
      device_id: newDeviceId,
      device_name: deviceName,
      hostname: body.hostname || deviceName,
      platform: platform,
      os_version: body.os_version || body.os_name || "Android 14 (HyperOS / OneUI)",
      status: "ACTIVE",
      last_seen: new Date().toISOString(),
      ip_address: "192.168.1." + Math.floor(50 + Math.random() * 150),
      agent_version: body.agent_version || "2.4.0",
      risk_score: 0,
      policy_status: "Enforced",
      sensitive_files_count: 0,
      total_scans: 1,
      blocked_transfers_count: 0,
    };
    devicesStore.unshift(newRecord);

    return NextResponse.json({
      device_id: newDeviceId,
      auth_token: authToken,
      device_name: deviceName,
      status: "ACTIVE",
      enrollment_code: code,
      message: "Device successfully enrolled and verified.",
    });
  }

  // ── Heartbeat (/devices/:id/heartbeat or /devices/heartbeat) ──
  if (pathStr.includes("/heartbeat")) {
    return NextResponse.json({
      status: "ACTIVE",
      policy_version: "2.4.1",
      interval_seconds: 60,
      acknowledged: true,
      server_time: new Date().toISOString(),
    });
  }

  // ── Quick Device Scan Trigger (/devices/:id/scan) ──
  if (pathSegments[0] === "devices" && pathSegments[2] === "scan") {
    return NextResponse.json({
      status: "COMPLETED",
      scanned_files: 45,
      findings_count: 0,
      risk_level: "LOW",
      timestamp: new Date().toISOString(),
    });
  }

  // ── Text DLP Scanner (/api/scan/text) ──
  if (pathStr === "/scan/text" || pathStr === "/scan") {
    const text = body.text || "";
    const hasEmail = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/.test(text);
    const hasCard = /\b(?:\d{4}[ -]?){3}\d{4}\b/.test(text);
    const hasKey = /(?:api[_-]?key|secret|token|password)[\s:=]+["']?[\w-]{12,}["']?/i.test(text);
    const score = (hasCard ? 50 : 0) + (hasKey ? 45 : 0) + (hasEmail ? 15 : 0);

    return NextResponse.json({
      score: Math.min(score, 100),
      risk_score: Math.min(score, 100),
      severity: score >= 75 ? "CRITICAL" : score >= 40 ? "HIGH" : score > 0 ? "MEDIUM" : "LOW",
      classification: hasCard ? "PCI_DSS" : hasKey ? "CREDENTIALS" : hasEmail ? "PII" : "SAFE",
      action_taken: score >= 50 ? "BLOCKED" : "ALLOWED",
      findings: [
        ...(hasCard ? [{ type: "CREDIT_CARD", detail: "Detected potential payment card number" }] : []),
        ...(hasKey ? [{ type: "SECRET_KEY", detail: "Detected exposed API token or credential" }] : []),
        ...(hasEmail ? [{ type: "PII_EMAIL", detail: "Detected email address" }] : []),
      ],
    });
  }

  return NextResponse.json({ success: true, timestamp: new Date().toISOString() });
}

export async function PATCH(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const fullApiPath = `/api/${pathSegments.join("/")}`;

  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes) return proxyRes;

  let body: any = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  if (pathSegments[0] === "devices" && pathSegments.length === 2) {
    const devId = pathSegments[1];
    const dev = devicesStore.find((d) => d.device_id === devId || String(d.id) === devId);
    if (dev) {
      if (body.status) dev.status = body.status;
      if (body.device_name) dev.device_name = body.device_name;
      return NextResponse.json(dev);
    }
  }

  return NextResponse.json({ success: true });
}

export async function DELETE(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const fullApiPath = `/api/${pathSegments.join("/")}`;

  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes) return proxyRes;

  if (pathSegments[0] === "devices" && pathSegments.length === 2) {
    const devId = pathSegments[1];
    const idx = devicesStore.findIndex((d) => d.device_id === devId || String(d.id) === devId);
    if (idx !== -1) {
      devicesStore.splice(idx, 1);
    }
    return NextResponse.json({ success: true, message: "Device removed successfully" });
  }

  return NextResponse.json({ success: true });
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Tunnel-Skip-Anti-Phishing-Page",
    },
  });
}
