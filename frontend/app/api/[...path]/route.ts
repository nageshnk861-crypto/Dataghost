import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import crypto from "crypto";

// Allow Vercel Serverless Functions up to 60 seconds (enough for Render cold start + 2 retries).
export const maxDuration = 60;

// ─── Interfaces ──────────────────────────────────────────────────────────────
interface DeviceRecord {
  id: number;
  device_id: string;
  device_name: string;
  hostname: string;
  platform: string;
  os_name?: string;
  os_type?: string;
  os_version: string;
  status: string;
  last_seen: string;
  ip_address: string;
  agent_version: string;
  risk_score: number;
  policy_status: string;
  sensitive_files_count: number;
  files_scanned: number;
  total_scans: number;
  blocked_transfers_count: number;
  incidents_count: number;
  created_at: string;
}

interface IncidentRecord {
  id: number;
  incident_id: string;
  user: string;
  filename: string;
  file_hash: string;
  classification: string;
  risk_score: number;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
  destination: string;
  action: string;
  action_taken: "BLOCKED" | "ALERTED" | "ALLOWED";
  findings_json?: string;
  findings: Array<{
    rule: string;
    category: string;
    severity: string;
    matched_text: string;
    detail?: string;
  }>;
  device_id: string;
  created_at: string;
  timestamp: string;
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

// ─── In-Memory Storage ────────────────────────────────────────────────────────
const enrollmentSessions = new Map<string, EnrollmentSession>();
const devicesStore: DeviceRecord[] = [];
const incidentsStore: IncidentRecord[] = [];

// Helper to generate a code like DG-A1B2-C3D4
function generateEnrollmentCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const part = () =>
    Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
  return `DG-${part()}-${part()}`;
}

// Mock JWT generator for instant cloud auth
function createToken(payload: object): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = Buffer.from("dataghost-cloud-signature-token").toString("base64url");
  return `${header}.${body}.${signature}`;
}

// Extract username from request
function extractUserFromRequest(req: NextRequest): string {
  const authHeader = req.headers.get("authorization") || "";
  const token = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!token) return "analyst";
  try {
    const parts = token.split(".");
    if (parts.length >= 2) {
      const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8"));
      return payload.sub || payload.username || (payload.email ? payload.email.split("@")[0] : "analyst");
    }
  } catch {
    // fallback
  }
  return "analyst";
}

// ─── Real DLP Scanner Engine ──────────────────────────────────────────────────
interface DlpRule {
  name: string;
  pattern: RegExp;
  category: "PII" | "FINANCIAL" | "CREDENTIALS" | "CORPORATE" | "AI_MODELS";
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  detail: string;
}

const DLP_RULES: DlpRule[] = [
  // User Information (PII)
  {
    name: "EMAIL_ADDRESS",
    pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
    category: "PII",
    severity: "MEDIUM",
    detail: "User Corporate/Personal Email Address Detected",
  },
  {
    name: "PHONE_NUMBER",
    pattern: /\b[6-9]\d{9}\b/g,
    category: "PII",
    severity: "MEDIUM",
    detail: "Contact Phone Number Detected",
  },
  {
    name: "US_SSN",
    pattern: /\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b/g,
    category: "PII",
    severity: "HIGH",
    detail: "US Social Security Number (SSN) Detected",
  },
  {
    name: "AADHAAR_CARD",
    pattern: /\b[2-9]\d{3}[ -]\d{4}[ -]\d{4}\b/g,
    category: "PII",
    severity: "HIGH",
    detail: "Government National ID (Aadhaar) Detected",
  },
  {
    name: "PAN_CARD",
    pattern: /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g,
    category: "PII",
    severity: "HIGH",
    detail: "Government Tax / PAN Card Detected",
  },
  {
    name: "EMPLOYEE_RECORD",
    pattern: /\b(?:employee id|staff id|payroll|salary|ctc|annual package)\b/gi,
    category: "PII",
    severity: "HIGH",
    detail: "Confidential Employee Identity & Payroll Record",
  },

  // Financial (PCI/Banking)
  {
    name: "PCI_CREDIT_CARD",
    pattern: /\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12}|(?:[0-9]{4}[\s\-]){3}[0-9]{4})\b/g,
    category: "FINANCIAL",
    severity: "HIGH",
    detail: "Payment Card Number (PCI-DSS violation)",
  },
  {
    name: "BANK_ACCOUNT",
    pattern: /\b(?:account|acc|bank|ifsc|iban)[\s:=]+([0-9]{9,18})\b/gi,
    category: "FINANCIAL",
    severity: "HIGH",
    detail: "Bank Account Details Detected",
  },

  // Credentials & Keys
  {
    name: "PASSWORD_FIELD",
    pattern: /(?:password|passwd|pwd|secret|credential|auth_pass|db_pass)\s*[:=]\s*["']?([^\s"']{4,})["']?/gi,
    category: "CREDENTIALS",
    severity: "HIGH",
    detail: "Exposed Password / Authentication Secret",
  },
  {
    name: "DATABASE_URL",
    pattern: /(?:postgresql|postgres|mysql(?:\+\w+)?|mariadb|mongodb(?:\+srv)?|redis[s]?|mssql(?:\+\w+)?|sqlserver|oracle|sqlite):\/\/[^\s"'`\[\]{}()<>\\]{4,}/gi,
    category: "CREDENTIALS",
    severity: "CRITICAL",
    detail: "Exposed Database Connection String / Credentials",
  },
  {
    name: "JWT_TOKEN",
    pattern: /\beyJ[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\b/g,
    category: "CREDENTIALS",
    severity: "CRITICAL",
    detail: "Exposed JSON Web Token (JWT)",
  },
  {
    name: "AWS_ACCESS_KEY",
    pattern: /\bAKIA[0-9A-Z]{16}\b/g,
    category: "CREDENTIALS",
    severity: "CRITICAL",
    detail: "Exposed AWS Access Key ID",
  },
  {
    name: "GOOGLE_API_KEY",
    pattern: /\bAIza[0-9A-Za-z_\-]{30,}\b/g,
    category: "CREDENTIALS",
    severity: "CRITICAL",
    detail: "Exposed Google Cloud / Gemini API Key",
  },
  {
    name: "STRIPE_KEY",
    pattern: /\b(?:sk_live_|rk_live_|pk_live_)[A-Za-z0-9]{20,}\b/g,
    category: "CREDENTIALS",
    severity: "CRITICAL",
    detail: "Exposed Stripe Live API Key / Secret",
  },
  {
    name: "GITHUB_TOKEN",
    pattern: /\b(?:gh[pousr]_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{82,255})\b/g,
    category: "CREDENTIALS",
    severity: "CRITICAL",
    detail: "Exposed GitHub Personal Access Token",
  },
  {
    name: "PRIVATE_KEY",
    pattern: /-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----/gi,
    category: "CREDENTIALS",
    severity: "CRITICAL",
    detail: "Exposed Cryptographic Private Key Header",
  },
  {
    name: "IP_ADDRESS",
    pattern: /\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\b/g,
    category: "CORPORATE",
    severity: "MEDIUM",
    detail: "Hardcoded Network IP Address Detected",
  },

  // AI Models Sharing & GenAI Exfiltration
  {
    name: "OPENAI_API_KEY",
    pattern: /\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b/g,
    category: "AI_MODELS",
    severity: "CRITICAL",
    detail: "Exposed OpenAI / ChatGPT API Secret Key",
  },
  {
    name: "ANTHROPIC_API_KEY",
    pattern: /\bsk-ant-[A-Za-z0-9_-]{20,}\b/g,
    category: "AI_MODELS",
    severity: "CRITICAL",
    detail: "Exposed Anthropic Claude API Key",
  },
  {
    name: "HUGGINGFACE_TOKEN",
    pattern: /\bhf_[A-Za-z0-9]{34,}\b/g,
    category: "AI_MODELS",
    severity: "CRITICAL",
    detail: "Exposed HuggingFace AI Model Hub Token",
  },
  {
    name: "AI_MODEL_SHARING",
    pattern: /\b(?:system prompt|you are a helpful ai|chatgpt prompt|openai completions|anthropic claude|share with ai|feeding to gpt|input to llm|prompt for ai model)\b/gi,
    category: "AI_MODELS",
    severity: "HIGH",
    detail: "Corporate Data Exfiltration to Public AI Models / Chatbots",
  },
  {
    name: "AI_TRAINING_DATA_LEAK",
    pattern: /\b(?:ai training dataset|fine-tuning data|llm training corpus|rlhf dataset)\b/gi,
    category: "AI_MODELS",
    severity: "HIGH",
    detail: "Proprietary AI Model Training & Fine-Tuning Dataset Leak",
  },
];

function luhnCheck(numStr: string): boolean {
  const digits = numStr.replace(/\D/g, "").split("").map(Number);
  if (digits.length < 13 || digits.length > 19) return false;
  let sum = 0;
  let shouldDouble = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = digits[i];
    if (shouldDouble) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    shouldDouble = !shouldDouble;
  }
  return sum % 10 === 0;
}

function isPlaceholderPassword(val: string): boolean {
  const stripped = val.replace(/^(?:password|passwd|pwd|secret|credential|auth_pass|db_pass)\s*[:=]\s*["']?/i, "").replace(/["']?$/, "").trim().toLowerCase();
  const placeholders = ["password", "your_password", "changeme", "admin", "secret", "test", "123456", "12345678", "placeholder", "xxx", "********"];
  return placeholders.includes(stripped) || stripped.length < 4;
}

function maskMatch(str: string, rule: string): string {
  if (!str) return "";
  if (rule === "EMAIL_ADDRESS") {
    const parts = str.split("@");
    if (parts.length === 2) {
      return `${parts[0].slice(0, 2)}***@${parts[1]}`;
    }
  }
  if (rule === "JWT_TOKEN") {
    const parts = str.split(".");
    return `${parts[0].slice(0, 8)}...[REDACTED].[REDACTED]`;
  }
  if (rule === "DATABASE_URL") {
    return str.replace(/:\/\/[^:]+:[^@]+@/, "://<REDACTED>@");
  }
  if (rule === "IP_ADDRESS") {
    const parts = str.split(".");
    if (parts.length === 4) return `${parts[0]}.${parts[1]}.***.***`;
  }
  if (rule === "PASSWORD_FIELD") {
    return str.replace(/([:=]\s*["']?)(.*)(["']?)$/, "$1********$3");
  }
  if (rule === "BANK_ACCOUNT") {
    return str.replace(/\d{4,}/g, (d) => `******${d.slice(-4)}`);
  }
  if (rule === "PCI_CREDIT_CARD") {
    const digits = str.replace(/\D/g, "");
    return `************${digits.slice(-4)}`;
  }
  if (rule === "US_SSN") {
    return `***-**-${str.replace(/\D/g, "").slice(-4)}`;
  }
  if (rule === "AADHAAR_CARD") {
    return `****-****-${str.replace(/\D/g, "").slice(-4)}`;
  }
  if (str.length > 8) {
    return `${str.slice(0, 4)}***${str.slice(-4)}`;
  }
  return "***";
}

function analyzeTextDlp(text: string, filename: string, destination: string = "LOCAL") {
  const findings: Array<{
    rule: string;
    category: string;
    severity: string;
    matched_text: string;
    detail: string;
    matches_count?: number;
  }> = [];

  for (const rule of DLP_RULES) {
    const matches = text.match(rule.pattern);
    if (matches && matches.length > 0) {
      let validMatches: string[] = matches;
      if (rule.name === "PCI_CREDIT_CARD") {
        validMatches = matches.filter(luhnCheck);
      } else if (rule.name === "IP_ADDRESS") {
        validMatches = matches.filter((m) => m !== "0.0.0.0" && m !== "255.255.255.255" && !m.startsWith("127."));
      } else if (rule.name === "PASSWORD_FIELD") {
        validMatches = matches.filter((m) => !isPlaceholderPassword(m));
      }

      if (validMatches.length > 0) {
        const unique = Array.from(new Set(validMatches));
        for (const m of unique.slice(0, 5)) {
          findings.push({
            rule: rule.name,
            category: rule.category,
            severity: rule.severity,
            matched_text: maskMatch(m, rule.name),
            detail: rule.detail,
            matches_count: validMatches.filter((x) => x === m).length,
          });
        }
      }
    }
  }

  // Calculate scores
  let findingsScore = 0;
  for (const f of findings) {
    if (f.severity === "CRITICAL") findingsScore += 45;
    else if (f.severity === "HIGH") findingsScore += 25;
    else if (f.severity === "MEDIUM") findingsScore += 12;
    else findingsScore += 5;
  }

  const isAiDest = ["AI_MODEL", "AI_SERVICE", "CHATGPT", "LLM"].includes(destination.toUpperCase());
  const hasAiLeak = findings.some((f) => f.category === "AI_MODELS");
  const destBonus = isAiDest || hasAiLeak ? 20 : destination === "EXTERNAL" ? 15 : destination === "USB" ? 18 : 5;

  let totalScore = findings.length === 0 ? 0 : Math.min(100, Math.max(10, findingsScore + destBonus));

  let classification = "PUBLIC";
  if (totalScore >= 75) classification = "RESTRICTED";
  else if (totalScore >= 45) classification = "CONFIDENTIAL";
  else if (totalScore >= 15) classification = "INTERNAL";

  let severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" = "LOW";
  if (totalScore >= 80 || findings.some((f) => f.severity === "CRITICAL")) {
    severity = "CRITICAL";
  } else if (totalScore >= 60 || findings.some((f) => f.severity === "HIGH")) {
    severity = "HIGH";
  } else if (totalScore >= 30) {
    severity = "MEDIUM";
  }

  let action_taken: "BLOCKED" | "ALERTED" | "ALLOWED" = "ALLOWED";
  if (severity === "CRITICAL" || totalScore >= 70 || hasAiLeak) {
    action_taken = "BLOCKED";
  } else if (severity === "HIGH" || severity === "MEDIUM") {
    action_taken = "ALERTED";
  }

  return {
    filename,
    findings,
    risk_score: totalScore,
    severity,
    classification,
    action_taken,
  };
}

/**
 * Forward the request to the real FastAPI backend with a 60-second timeout.
 * Retries ONCE on a 502/503/504 or network abort before giving up.
 *
 * Returns:
 *   - NextResponse  → either the real backend reply, or a 502 wakeup response
 *                    when the backend is unreachable in production / strict mode.
 *   - null          → local dev with ENABLE_MOCK_FALLBACK=true; caller falls
 *                    through to in-memory mocks.
 */
async function tryProxyToBackend(
  req: NextRequest,
  fullPath: string,
): Promise<NextResponse | null> {
  // Detect Vercel production / preview deployments.
  const isVercel = Boolean(process.env.VERCEL || process.env.NEXT_PUBLIC_VERCEL_ENV);

  // In local dev, set ENABLE_MOCK_FALLBACK=true in .env.local to keep mock behaviour.
  const mockFallbackEnabled = !isVercel && process.env.ENABLE_MOCK_FALLBACK === "true";

  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL ||
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://dataghost-1.onrender.com"
  ).trim().replace(/\/+$/, "");

  const searchParams = req.nextUrl.search;
  const target = `${backendUrl}${fullPath}${searchParams}`;

  // 25s per attempt × 2 attempts = up to ~50s total.
  // Render free-tier cold start is typically 15-40s.
  const timeoutMs = 25_000;

  // ── Wake-ping: fire a cheap GET /api/health to unfreeze the dyno before the real request.
  // We don't await the result — it just kicks the cold-start process early.
  const healthUrl = `${backendUrl}/api/health`;
  const wakeController = new AbortController();
  fetch(healthUrl, { method: "GET", signal: wakeController.signal }).catch(() => {});
  // Give the dyno a short head-start before our first real attempt.
  await new Promise((resolve) => setTimeout(resolve, 300));

  // Body must be read once before the first attempt so it can be re-sent on retry.
  const bodyBuffer =
    ["GET", "HEAD"].includes(req.method) ? undefined : await req.clone().arrayBuffer();

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");

  /** Single fetch attempt — resolves with a Response or throws on timeout/network error. */
  async function attempt(): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(target, {
        method: req.method,
        headers,
        body: bodyBuffer,
        signal: controller.signal,
      });
      clearTimeout(timer);
      return response;
    } catch (err) {
      clearTimeout(timer);
      throw err;
    }
  }

  /** Returns true for gateway-level errors that are worth retrying. */
  function isRetryable(r: Response): boolean {
    return r.status === 502 || r.status === 503 || r.status === 504;
  }

  function makeProxyResponse(r: Response): NextResponse {
    const respHeaders = new Headers(r.headers);
    // Remove headers that conflict when body is decompressed or piped by runtime
    respHeaders.delete("content-encoding");
    respHeaders.delete("content-length");
    respHeaders.delete("transfer-encoding");
    return new NextResponse(r.body, {
      status: r.status,
      statusText: r.statusText,
      headers: respHeaders,
    });
  }

  // ── Attempt 1 ──
  try {
    const r = await attempt();
    if (!isRetryable(r)) {
      wakeController.abort(); // cancel wake-ping if we got a real response
      return makeProxyResponse(r);
    }
  } catch {
    // Network error / timeout — fall through to retry
  }

  // ── Attempt 2 (after 2s backoff) ──
  await new Promise((resolve) => setTimeout(resolve, 2000));
  try {
    const r = await attempt();
    if (!isRetryable(r)) {
      wakeController.abort();
      return makeProxyResponse(r);
    }
  } catch {
    // Both attempts failed
  }

  wakeController.abort();
  // If the backend fails or is cold-starting, allow routes with built-in handlers
  // (such as /api/scan, /api/scan/file, /api/scan/text, /api/dashboard/*, etc.)
  // to fall through to the built-in DLP engine instead of failing with 502.
  const hasLocalEngine =
    fullPath.startsWith("/api/scan") ||
    fullPath.startsWith("/api/v1/upload") ||
    fullPath.startsWith("/api/upload") ||
    fullPath.startsWith("/api/dashboard") ||
    fullPath.startsWith("/api/incidents") ||
    fullPath.startsWith("/api/findings") ||
    fullPath.startsWith("/api/devices") ||
    fullPath.startsWith("/api/events") ||
    fullPath.startsWith("/api/policies") ||
    fullPath.startsWith("/api/analytics");

  if (hasLocalEngine || mockFallbackEnabled) {
    return null;
  }

  if (isVercel) {
    return backend502(fullPath);
  }
  return null;
}

/** Emit a 502 JSON response prompting the caller to retry. */
function backend502(path: string): NextResponse {
  return NextResponse.json(
    {
      error: "Backend is waking up, please retry in a moment",
      message:
        "The DataGhost backend is starting up (Render free-tier cold start). " +
        "This usually takes 15–40 seconds. Please wait a moment and click Retry.",
      path,
    },
    { status: 502 },
  );
}

// ─── GET Handlers ─────────────────────────────────────────────────────────────
export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const pathStr = "/" + pathSegments.join("/");
  const fullApiPath = `/api${pathStr}`;

  // Forward to real backend; returns null only in local dev with ENABLE_MOCK_FALLBACK=true.
  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes !== null) return proxyRes;

  const origin = request.nextUrl.origin;
  const currentUser = extractUserFromRequest(request);

  // ── Health ──
  if (pathStr === "/health" || pathStr === "/v1/health") {
    return NextResponse.json({ status: "healthy", timestamp: new Date().toISOString(), platform: "cloud" });
  }

  // ── Authentication Profile ──
  if (pathStr === "/auth/me" || pathStr === "/users/me") {
    return NextResponse.json({
      id: 1,
      username: currentUser,
      email: `${currentUser}@dataghost.local`,
      role: currentUser.toLowerCase().includes("admin") ? "admin" : "analyst",
      is_active: true,
      created_at: new Date().toISOString(),
    });
  }

  // ── Dashboard Stats ──
  if (pathStr === "/dashboard/stats") {
    const totalFilesScanned = devicesStore.reduce((acc, d) => acc + (d.files_scanned || d.total_scans || 0), 0);
    const activeCount = devicesStore.filter((d) => d.status === "ACTIVE").length;
    // sensitive_files: scans with any findings (matches real backend: findings_count > 0 OR risk >= 30)
    const sensitiveFiles = incidentsStore.length || devicesStore.reduce((acc, d) => acc + (d.sensitive_files_count || 0), 0);
    // security events: BLOCKED + ALERTED (matches real backend)
    const blockedTransfers = incidentsStore.filter((i) => i.action_taken === "BLOCKED" || i.action_taken === "ALERTED").length;
    const criticalIncidents = incidentsStore.filter((i) => i.severity === "CRITICAL").length;

    const recentThreats = incidentsStore.slice(0, 5).map((i) => ({
      incident_id: i.incident_id,
      filename: i.filename,
      risk_score: i.risk_score,
      severity: i.severity,
      user: i.user,
      timestamp: i.timestamp,
      action_taken: i.action_taken,
    }));

    return NextResponse.json({
      protected_devices: activeCount,
      active_devices: activeCount,
      files_scanned: totalFilesScanned,
      total_scans: totalFilesScanned,
      sensitive_files: sensitiveFiles,
      blocked_transfers: blockedTransfers,
      critical_incidents: criticalIncidents,
      recent_threats: recentThreats,
    });
  }

  if (pathStr === "/dashboard/activity") {
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const now = new Date();
    const activity = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(now);
      d.setDate(d.getDate() - (6 - i));
      const dateName = days[d.getDay()];
      const dayIncidents = incidentsStore.filter((inc) => {
        const incDate = new Date(inc.timestamp);
        return incDate.toDateString() === d.toDateString();
      });
      return {
        date: dateName,
        scans: 10 + dayIncidents.length * 4,
        sensitive: dayIncidents.length,
        blocked: dayIncidents.filter((inc) => inc.action_taken === "BLOCKED").length,
      };
    });
    return NextResponse.json(activity);
  }

  // ── Incidents (/api/incidents) ──
  if (pathStr === "/incidents") {
    const search = (request.nextUrl.searchParams.get("search") || "").toLowerCase();
    const severityFilter = request.nextUrl.searchParams.get("severity");
    const statusFilter = request.nextUrl.searchParams.get("status");
    const page = parseInt(request.nextUrl.searchParams.get("page") || "1", 10);
    const perPage = parseInt(request.nextUrl.searchParams.get("per_page") || "100", 10);

    let filtered = [...incidentsStore];
    if (severityFilter && severityFilter !== "ALL") {
      filtered = filtered.filter((i) => i.severity === severityFilter);
    }
    if (statusFilter && statusFilter !== "ALL") {
      filtered = filtered.filter((i) => i.status === statusFilter);
    }
    if (search) {
      filtered = filtered.filter(
        (i) =>
          i.filename.toLowerCase().includes(search) ||
          i.user.toLowerCase().includes(search) ||
          i.incident_id.toLowerCase().includes(search)
      );
    }

    const start = (page - 1) * perPage;
    const pagedItems = filtered.slice(start, start + perPage);

    return NextResponse.json({
      items: pagedItems,
      total: filtered.length,
      page,
      per_page: perPage,
      total_pages: Math.max(1, Math.ceil(filtered.length / perPage)),
    });
  }

  // ── Enrollment Status (/devices/enrollment/status/:code) ──
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

    return NextResponse.json({
      enrollment_code: code,
      platform: "Windows",
      status: "PENDING",
      is_expired: false,
      expires_in_seconds: 540,
    });
  }

  // ── Devices List & Details ──
  if (pathSegments[0] === "devices" && pathSegments[1] !== "enrollment") {
    if (pathSegments.length === 1) {
      return NextResponse.json(devicesStore);
    }
    const devId = pathSegments[1];
    if (pathSegments[2] === "scan-summary") {
      const dev = devicesStore.find((d) => d.device_id === devId || String(d.id) === devId);
      if (!dev) {
        return NextResponse.json({ message: `Device '${devId}' not found.` }, { status: 404 });
      }
      const devIncidents = incidentsStore.filter((i) => i.device_id === dev.device_id);
      if ((dev.files_scanned || 0) === 0 && devIncidents.length === 0) {
        return NextResponse.json({
          status: "no_data",
          has_scan_data: false,
          message: "No scan data yet",
          device: dev,
          risk_score: null,
          risk_level: null,
          block_level: null,
          sensitive_files: 0,
          blocked_transfers: 0,
          critical_incidents: 0,
          threats_detected: 0,
          user_information_count: 0,
          ai_model_sharing_count: 0,
          scanned_files_count: 0,
          total_bytes_scanned: 0,
          scan_results: [],
          is_simulated: false,
        });
      }
      return NextResponse.json({
        status: "success",
        has_scan_data: true,
        device: dev,
        risk_score: dev.risk_score,
        risk_level: dev.risk_score >= 80 ? "CRITICAL" : dev.risk_score >= 60 ? "HIGH" : dev.risk_score >= 30 ? "MEDIUM" : "LOW",
        block_level: dev.blocked_transfers_count > 0 ? "BLOCKED" : devIncidents.length > 0 ? "ALERTED" : "ALLOWED",
        sensitive_files: dev.sensitive_files_count || 0,
        blocked_transfers: dev.blocked_transfers_count || 0,
        critical_incidents: devIncidents.filter((i) => i.severity === "CRITICAL").length,
        threats_detected: devIncidents.length,
        user_information_count: devIncidents.length,
        ai_model_sharing_count: 0,
        scanned_files_count: dev.files_scanned || 0,
        total_bytes_scanned: 0,
        scan_results: [],
        is_simulated: false,
      });
    }
    const dev = devicesStore.find((d) => d.device_id === devId || String(d.id) === devId);
    if (dev) {
      const devIncidents = incidentsStore.filter((i) => i.device_id === dev.device_id);
      return NextResponse.json({
        ...dev,
        recent_incidents: devIncidents.slice(0, 10),
      });
    }
    return NextResponse.json(
      { message: `Device '${devId}' not found.` },
      { status: 404 }
    );
  }

  // ── DLP Rules ──
  if (pathStr === "/dlp-rules") {
    return NextResponse.json(
      DLP_RULES.map((r) => ({
        name: r.name.toLowerCase(),
        display_name: r.name.replace(/_/g, " "),
        category: r.category,
        severity: r.severity,
        action: r.severity === "CRITICAL" ? "BLOCK" : "ALERT",
        description: r.detail,
        enabled: true,
      }))
    );
  }

  // ── Users ──
  if (pathStr === "/users") {
    return NextResponse.json([
      { id: 1, username: currentUser, email: `${currentUser}@dataghost.local`, role: "analyst", is_active: true, created_at: new Date().toISOString() },
      { id: 2, username: "admin", email: "admin@dataghost.local", role: "admin", is_active: true, created_at: new Date().toISOString() },
    ]);
  }

  return NextResponse.json({ message: "Not found", path: fullApiPath }, { status: 404 });
}

// ─── POST Handlers ────────────────────────────────────────────────────────────
export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const pathStr = "/" + pathSegments.join("/");
  const fullApiPath = `/api${pathStr}`;

  // Forward to real backend; returns null only in local dev with ENABLE_MOCK_FALLBACK=true.
  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes !== null) return proxyRes;

  let body: any = {};
  let uploadedFile: { name: string; size: number; text: string; buffer: Buffer } | null = null;
  let uploadedFiles: Array<{ name: string; size: number; text: string; buffer: Buffer }> = [];

  const contentType = request.headers.get("content-type") || "";
  if (contentType.includes("multipart/form-data") || contentType.includes("application/x-www-form-urlencoded")) {
    try {
      const formData = await request.formData();
      for (const [key, val] of formData.entries()) {
        if (typeof val === "string") {
          body[key] = val;
        }
      }
      const fileEntry = formData.get("file");
      if (fileEntry && typeof fileEntry === "object" && "arrayBuffer" in fileEntry) {
        const f = fileEntry as File;
        const ab = await f.arrayBuffer();
        const buf = Buffer.from(ab);
        uploadedFile = {
          name: f.name || "uploaded_file.txt",
          size: f.size || buf.byteLength,
          text: buf.toString("utf-8"),
          buffer: buf,
        };
      }
      const allFiles = formData.getAll("files");
      for (const fe of allFiles) {
        if (fe && typeof fe === "object" && "arrayBuffer" in fe) {
          const f = fe as File;
          const ab = await f.arrayBuffer();
          const buf = Buffer.from(ab);
          uploadedFiles.push({
            name: f.name || "uploaded_file.txt",
            size: f.size || buf.byteLength,
            text: buf.toString("utf-8"),
            buffer: buf,
          });
        }
      }
    } catch (e) {
      console.warn("Could not parse multipart form data:", e);
    }
  } else {
    try {
      body = await request.json();
    } catch {
      body = {};
    }
  }

  const origin = request.nextUrl.origin;
  const currentUser = extractUserFromRequest(request);

  // ── Authentication / Login ──
  if (pathStr === "/auth/login") {
    const username = body.username || "user";
    const role = username.toLowerCase().includes("admin") ? "admin" : "analyst";
    return NextResponse.json({
      access_token: createToken({ sub: username, role }),
      token_type: "bearer",
      username,
      role,
    });
  }

  // ── Firebase Registration / Sync ──
  if (pathStr === "/auth/register/firebase") {
    const authHeader = request.headers.get("authorization") || "";
    const token = authHeader.replace(/^Bearer\s+/i, "");
    let username = "user";
    let role = "analyst";
    if (token) {
      try {
        const parts = token.split(".");
        if (parts.length >= 2) {
          const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8"));
          if (payload.email) username = payload.email.split("@")[0];
          if (payload.name) username = payload.name;
        }
      } catch {
        // default
      }
    }
    return NextResponse.json({
      access_token: createToken({ sub: username, role }),
      token_type: "bearer",
      username,
      role,
    });
  }

  // ── Standard Enrollment QR (/api/devices/enrollment/create) ──
  if (pathStr === "/devices/enrollment/create" || pathStr === "/devices/enrollment/create-easy" || pathStr === "/devices/enrollment/create-android-enterprise") {
    const platform = body.platform || "Windows";
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
    const qrPayload = {
      version: "1.0",
      server_url: origin,
      token,
      code,
      platform,
      expires_at: new Date(expiresAt).toISOString(),
    };

    return NextResponse.json({
      enrollment_code: code,
      raw_token: token,
      platform,
      qr_data: pathStr.includes("create-easy") ? qrUrl : JSON.stringify(qrPayload),
      server_url: origin,
      expires_at: new Date(expiresAt).toISOString(),
      expires_in_seconds: 600,
      status: "PENDING",
    });
  }

  // ── Device Registration (/api/devices/enrollment/register or /api/devices/register) ──
  if (pathStr === "/devices/enrollment/register" || pathStr === "/devices/register") {
    const code = body.enrollment_code || body.code || "";
    const platform = body.platform || "Windows";
    const deviceName = body.device_name || body.hostname || `${platform}-Workstation-${Math.floor(1000 + Math.random() * 9000)}`;
    const newDeviceId = `dg-${platform.toLowerCase().slice(0, 3)}-${Date.now().toString(36)}`;
    const authToken = `dg_auth_${Math.random().toString(36).substring(2)}`;

    if (code && enrollmentSessions.has(code)) {
      const session = enrollmentSessions.get(code)!;
      session.status = "USED";
      session.deviceName = deviceName;
      session.deviceId = newDeviceId;
    }

    const newRecord: DeviceRecord = {
      id: devicesStore.length + 1,
      device_id: newDeviceId,
      device_name: deviceName,
      hostname: body.hostname || deviceName,
      platform,
      os_name: body.os_name || `${platform} Enterprise`,
      os_type: platform,
      os_version: body.os_version || "11 x64",
      status: "ACTIVE",
      last_seen: new Date().toISOString(),
      ip_address: "192.168.1." + Math.floor(50 + Math.random() * 150),
      agent_version: "2.4.0",
      risk_score: 0,
      policy_status: "Enforced",
      sensitive_files_count: 0,
      files_scanned: 0,
      total_scans: 0,
      blocked_transfers_count: 0,
      incidents_count: 0,
      created_at: new Date().toISOString(),
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

  // ── Real Device DLP Scan Trigger (/devices/:id/scan) ──
  if (pathSegments[0] === "devices" && pathSegments[2] === "scan") {
    const devId = pathSegments[1];
    const dev = devicesStore.find((d) => d.device_id === devId || String(d.id) === devId);

    if (!dev) {
      // Do NOT auto-create ghost devices. Return 404 so the UI shows an error,
      // never a synthetic "allowed" result for an unknown device.
      return NextResponse.json(
        { message: `Device '${devId}' not found.` },
        { status: 404 }
      );
    }

    // Check for explicit DEMO flag — server env var ONLY; never trust client-supplied body.demo
    const isDemo =
      process.env.DEMO_MODE === "1" ||
      process.env.DEMO_MODE === "true";

    // Real files collection
    const filesToScan: Array<{ filename: string; content: string; destination: string }> = [];

    // Case 1: Custom files or text sent by client
    if (body.files && Array.isArray(body.files) && body.files.length > 0) {
      for (const f of body.files) {
        filesToScan.push({
          filename: f.filename || "custom_uploaded_file.txt",
          content: f.content || "",
          destination: f.destination || "EXTERNAL",
        });
      }
    } else if (body.custom_content) {
      filesToScan.push({
        filename: body.filename || "user_submitted_data.txt",
        content: body.custom_content,
        destination: body.destination || "EXTERNAL",
      });
    } else if (isDemo) {
      // Case 2: Explicit DEMO mode only: load simulated test documents
      filesToScan.push(
        {
          filename: "customer_pii_identity_records.csv",
          content: `Employee,User_Email,Phone,Gov_ID,Payment_Card\nJohn Doe,john.doe@company.com,9876543210,123-45-6789,4532-8921-3412-8910\nJane Smith,jane.smith@corporate.net,9123456789,ABCDE1234F,5421-1234-5678-9012`,
          destination: "LOCAL",
        },
        {
          filename: "ai_chatgpt_prompt_exfiltration.txt",
          content: `System Prompt for AI Model:\nYou are a helpful AI assistant. Here is our internal proprietary database schema and customer list to share with AI: feeding to GPT:\nsk-proj-91823749281729384719283749182739481729384719\nCustomer API key and password = SuperSecretDBPassword2026!`,
          destination: "AI_MODEL",
        },
        {
          filename: "claude_anthropic_model_keys.env",
          content: `ANTHROPIC_API_KEY=sk-ant-api03-abcdef123456789012345678901234567890\nHUGGINGFACE_TOKEN=hf_ABCDEF1234567890123456789012345678\nAI fine-tuning data and LLM training corpus access authorized.`,
          destination: "AI_MODEL",
        },
        {
          filename: "clean_system_architecture.md",
          content: `# Architecture Overview\nDataGhost is an agent-based DLP system. It enforces security policies locally on the endpoint without transmitting plaintext files to third parties.\nAll telemetry is processed securely.`,
          destination: "LOCAL",
        },
        {
          filename: "clean_project_config.json",
          content: `{\n  "version": "2.4.0",\n  "telemetry": true,\n  "audit_logging": "enabled"\n}`,
          destination: "LOCAL",
        }
      );
    }

    // In production without demo, if no files to scan: return empty state without simulated score
    if (filesToScan.length === 0) {
      return NextResponse.json({
        status: "no_data",
        has_scan_data: false,
        message: "No scan data yet",
        device: {
          device_id: dev.device_id,
          device_name: dev.device_name,
          platform: dev.platform,
          status: dev.status,
          files_scanned: dev.files_scanned || 0,
          incidents_count: dev.incidents_count || 0,
          last_seen: dev.last_seen,
          os_name: dev.os_name || `${dev.platform} OS`,
          os_version: dev.os_version,
          hostname: dev.hostname,
          ip_address: dev.ip_address,
          risk_score: null,
        },
        risk_score: null,
        risk_level: null,
        block_level: null,
        sensitive_files: 0,
        blocked_transfers: 0,
        critical_incidents: 0,
        threats_detected: 0,
        high_risk_count: 0,
        user_information_count: 0,
        ai_model_sharing_count: 0,
        scanned_files_count: 0,
        total_bytes_scanned: 0,
        scan_results: [],
        is_simulated: false,
      });
    }

    const scanResults: any[] = [];
    let sensitiveCount = 0;
    let blockedCount = 0;
    let criticalCount = 0;
    let userInformationCount = 0;
    let aiModelSharingCount = 0;

    for (const item of filesToScan) {
      const res = analyzeTextDlp(item.content, item.filename, item.destination);
      const fileHash = crypto.createHash("sha256").update(item.content).digest("hex");
      const fileSize = Buffer.byteLength(item.content, "utf-8");

      let incidentId: string | null = null;
      if (res.risk_score >= 30) {
        sensitiveCount++;
        if (res.action_taken === "BLOCKED") blockedCount++;
        if (res.severity === "CRITICAL") criticalCount++;

        incidentId = `DG-${new Date().getFullYear()}-${String(incidentsStore.length + 1).padStart(4, "0")}`;
        const newIncident: IncidentRecord = {
          id: incidentsStore.length + 1,
          incident_id: incidentId,
          user: currentUser,
          filename: item.filename,
          file_hash: fileHash,
          classification: res.classification,
          risk_score: res.risk_score,
          severity: res.severity,
          status: "OPEN",
          destination: item.destination.toUpperCase(),
          action: "UPLOAD",
          action_taken: res.action_taken,
          findings: res.findings,
          findings_json: JSON.stringify(res.findings),
          device_id: dev.device_id,
          created_at: new Date().toISOString(),
          timestamp: new Date().toISOString(),
        };
        incidentsStore.unshift(newIncident);
      }

      for (const f of res.findings) {
        if (f.category === "AI_MODELS") aiModelSharingCount++;
        else userInformationCount++;
      }

      scanResults.push({
        filename: item.filename,
        classification: res.classification,
        risk_score: res.risk_score,
        severity: res.severity,
        action_taken: res.action_taken,
        file_hash: fileHash,
        file_size: fileSize,
        incident_id: incidentId,
        destination: item.destination,
        findings: res.findings,
      });
    }

    const maxRisk = Math.max(...scanResults.map((r) => r.risk_score), 0);
    const overallRiskLevel =
      criticalCount > 0 ? "CRITICAL" : maxRisk >= 60 ? "HIGH" : maxRisk >= 30 ? "MEDIUM" : "LOW";
    const overallBlockLevel = blockedCount > 0 ? "BLOCKED" : sensitiveCount > 0 ? "ALERTED" : "ALLOWED";

    // Update device state
    dev.files_scanned = (dev.files_scanned || 0) + filesToScan.length;
    dev.total_scans = (dev.total_scans || 0) + 1;
    dev.sensitive_files_count = (dev.sensitive_files_count || 0) + sensitiveCount;
    dev.blocked_transfers_count = (dev.blocked_transfers_count || 0) + blockedCount;
    dev.incidents_count = (dev.incidents_count || 0) + sensitiveCount;
    dev.risk_score = Math.max(dev.risk_score || 0, maxRisk);
    dev.last_seen = new Date().toISOString();

    return NextResponse.json({
      status: "success",
      has_scan_data: true,
      message: `Real-time scan completed successfully for device '${dev.device_name}'.`,
      source: isDemo ? "demo_simulation" : "live_filesystem",
      is_simulated: isDemo,
      device: {
        device_id: dev.device_id,
        device_name: dev.device_name,
        platform: dev.platform,
        status: dev.status,
        files_scanned: dev.files_scanned,
        incidents_count: dev.incidents_count,
        last_seen: dev.last_seen,
        os_name: dev.os_name || `${dev.platform} OS`,
        os_version: dev.os_version,
        hostname: dev.hostname,
        ip_address: dev.ip_address,
        risk_score: dev.risk_score,
      },
      scanned_files_count: filesToScan.length,
      risk_level: overallRiskLevel,
      risk_score: maxRisk,
      block_level: overallBlockLevel,
      sensitive_files: sensitiveCount,
      blocked_transfers: blockedCount,
      critical_incidents: criticalCount,
      threats_detected: sensitiveCount,
      high_risk_count: scanResults.filter((r) => r.risk_score >= 70).length,
      user_information_count: userInformationCount,
      ai_model_sharing_count: aiModelSharingCount,
      total_bytes_scanned: scanResults.reduce((acc, r) => acc + r.file_size, 0),
      scan_results: scanResults,
    });
  }

  // ── Text & File DLP Scanner (/api/scan/text, /api/scan/file, /api/scan) ──
  if (pathStr === "/scan/text" || pathStr === "/scan" || pathStr === "/scan/file") {
    const text = body.text || body.content || uploadedFile?.text || "";
    const filename = body.filename || uploadedFile?.name || "scan_artifact.dat";
    const dest = body.destination || "EXTERNAL";
    const effectiveSize = uploadedFile?.size || Buffer.byteLength(text, "utf-8");
    const res = analyzeTextDlp(text, filename, dest);

    const scanId = `scan-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    const fileHash = crypto.createHash("sha256").update(text).digest("hex");
    const bytesInspected = effectiveSize;

    let incidentId: string | null = null;
    if (res.risk_score >= 30) {
      incidentId = `DG-${new Date().getFullYear()}-${String(incidentsStore.length + 1).padStart(4, "0")}`;
      incidentsStore.unshift({
        id: incidentsStore.length + 1,
        incident_id: incidentId,
        user: currentUser,
        filename,
        file_hash: fileHash,
        classification: res.classification,
        risk_score: res.risk_score,
        severity: res.severity,
        status: "OPEN",
        destination: dest.toUpperCase(),
        action: body.action || "UPLOAD",
        action_taken: res.action_taken,
        findings: res.findings,
        findings_json: JSON.stringify(res.findings),
        device_id: body.device_id || "WEB-CONSOLE",
        created_at: new Date().toISOString(),
        timestamp: new Date().toISOString(),
      });
    }

    // Shape matches ScanResponse so the Scanner UI can display proper status/findings
    return NextResponse.json({
      scan_id: scanId,
      filename,
      file_hash: fileHash,
      file_size: bytesInspected,
      bytes_inspected: bytesInspected,
      scan_status: "COMPLETED",
      is_simulated: false,
      score: res.risk_score,
      risk_score: res.risk_score,
      // decision_score: confidence-weighted normalised 0.0–1.0 (matches real backend)
      decision_score: parseFloat((res.risk_score / 100).toFixed(4)),
      severity: res.severity,
      classification: res.classification,
      recommended_action: res.action_taken === "BLOCKED" ? "BLOCK" : res.action_taken === "ALERTED" ? "ALERT" : "ALLOW",
      action_taken: res.action_taken,
      total_findings: res.findings.length,
      findings: res.findings.map((f) => ({
        rule: f.rule,
        rule_name: f.rule,
        category: f.category,
        severity: f.severity,
        matched_text: f.matched_text,
        sample_match: f.matched_text,
        matches_count: f.matches_count ?? 1,
        detail: f.detail,
      })),
      incident_id: incidentId,
      timestamp: new Date().toISOString(),
    });
  }

  // ── Multi-File Upload Scanner (/api/v1/upload, /api/upload) ──
  if (pathStr === "/v1/upload" || pathStr === "/upload") {
    const filesList = uploadedFiles.length > 0 ? uploadedFiles : (uploadedFile ? [uploadedFile] : []);
    const dest = body.destination || "EXTERNAL";
    const results = filesList.map((fileItem) => {
      const text = fileItem.text || "";
      const filename = fileItem.name || "uploaded_file.txt";
      const res = analyzeTextDlp(text, filename, dest);
      const scanId = `scan-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
      const fileHash = crypto.createHash("sha256").update(text).digest("hex");
      const bytesInspected = fileItem.size || Buffer.byteLength(text, "utf-8");

      let incidentId: string | null = null;
      if (res.risk_score >= 30) {
        incidentId = `DG-${new Date().getFullYear()}-${String(incidentsStore.length + 1).padStart(4, "0")}`;
        incidentsStore.unshift({
          id: incidentsStore.length + 1,
          incident_id: incidentId,
          user: currentUser,
          filename,
          file_hash: fileHash,
          classification: res.classification,
          risk_score: res.risk_score,
          severity: res.severity,
          status: "OPEN",
          destination: dest.toUpperCase(),
          action: body.action || "UPLOAD",
          action_taken: res.action_taken,
          findings: res.findings,
          findings_json: JSON.stringify(res.findings),
          device_id: body.device_id || "WEB-CONSOLE",
          created_at: new Date().toISOString(),
          timestamp: new Date().toISOString(),
        });
      }

      return {
        scan_id: scanId,
        filename,
        file_hash: fileHash,
        file_size: bytesInspected,
        bytes_inspected: bytesInspected,
        scan_status: "COMPLETED",
        is_simulated: false,
        score: res.risk_score,
        risk_score: res.risk_score,
        decision_score: parseFloat((res.risk_score / 100).toFixed(4)),
        severity: res.severity,
        classification: res.classification,
        recommended_action: res.action_taken === "BLOCKED" ? "BLOCK" : res.action_taken === "ALERTED" ? "ALERT" : "ALLOW",
        action_taken: res.action_taken,
        total_findings: res.findings.length,
        findings: res.findings.map((f) => ({
          rule: f.rule,
          rule_name: f.rule,
          category: f.category,
          severity: f.severity,
          matched_text: f.matched_text,
          sample_match: f.matched_text,
          matches_count: f.matches_count ?? 1,
          detail: f.detail,
        })),
        incident_id: incidentId,
        timestamp: new Date().toISOString(),
      };
    });

    return NextResponse.json(results);
  }

  return NextResponse.json({ success: true, timestamp: new Date().toISOString() });
}

// ─── PATCH Handlers ───────────────────────────────────────────────────────────
export async function PATCH(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const fullApiPath = `/api/${pathSegments.join("/")}`;

  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes !== null) return proxyRes;

  let body: any = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  // Update Device
  if (pathSegments[0] === "devices" && pathSegments.length === 2) {
    const devId = pathSegments[1];
    const dev = devicesStore.find((d) => d.device_id === devId || String(d.id) === devId);
    if (dev) {
      if (body.status) dev.status = body.status;
      if (body.device_name) dev.device_name = body.device_name;
      return NextResponse.json(dev);
    }
  }

  // Update Incident Status (/api/incidents/:id)
  if (pathSegments[0] === "incidents" && pathSegments.length === 2) {
    const incId = pathSegments[1];
    const inc = incidentsStore.find((i) => i.incident_id === incId || String(i.id) === incId);
    if (inc) {
      if (body.status) inc.status = body.status;
      return NextResponse.json(inc);
    }
  }

  return NextResponse.json({ success: true });
}

// ─── DELETE Handlers ──────────────────────────────────────────────────────────
export async function DELETE(request: NextRequest, { params }: { params: { path: string[] } }) {
  const pathSegments = params.path || [];
  const fullApiPath = `/api/${pathSegments.join("/")}`;

  const proxyRes = await tryProxyToBackend(request, fullApiPath);
  if (proxyRes !== null) return proxyRes;

  if (pathSegments[0] === "devices" && pathSegments.length === 2) {
    const devId = pathSegments[1];
    const idx = devicesStore.findIndex((d) => d.device_id === devId || String(d.id) === devId);
    if (idx !== -1) {
      devicesStore.splice(idx, 1);
    }
    return NextResponse.json({ success: true, message: "Device removed successfully" });
  }

  if (pathSegments[0] === "incidents" && pathSegments.length === 2) {
    const incId = pathSegments[1];
    const idx = incidentsStore.findIndex((i) => i.incident_id === incId || String(i.id) === incId);
    if (idx !== -1) {
      incidentsStore.splice(idx, 1);
    }
    return NextResponse.json({ success: true, message: "Incident removed successfully" });
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
