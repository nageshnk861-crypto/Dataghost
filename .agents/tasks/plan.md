# DataGhost Frontend Integration Plan

## Codebase Findings

### File Layout (all routes and components)

**App Router structure:**
```
frontend/app/
  layout.tsx                    — root layout (no sidebar, no auth guard)
  page.tsx                      — SOC Dashboard (OLD, uses raw fetch, no auth guard, mocks)
  login/page.tsx                — Login page (functional, uses lib/auth)
  incidents/page.tsx            — Incidents (OLD path, 20 hardcoded mocks, no auth guard)
  devices/page.tsx              — Devices (OLD path, 24 generated mocks, no auth guard)
  scanner/page.tsx              — Scanner (OLD path, mock fallback, no auth guard, demo mock)
  (app)/layout.tsx              — Auth-guarded shell (checks dg_token, wraps with Sidebar + main)
  (app)/dashboard/page.tsx      — NEW dashboard (uses apiFetch, real API, auth via layout)
  (app)/analytics/page.tsx      — Analytics (EXISTS — has hardcoded TOP_USERS, SEV_DATA, DEST_DATA mocks)
  (app)/events/page.tsx         — Events timeline (uses apiFetch, real data)
  (app)/users/page.tsx          — User management (hardcoded sampleUsers — out of scope)
  (app)/files/page.tsx          — (not read, out of scope)
  (app)/policies/page.tsx       — (not read, out of scope)
  (app)/settings/page.tsx       — (not read, out of scope)

frontend/components/
  Sidebar.tsx                   — links to /, /scanner, /incidents, /devices
  TopBar.tsx                    — sticky header used by (app)/* pages
  StatCard.tsx                  — stat card with icon, value, color, subtitle
  ClassificationBadge.tsx       — PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED badge
  IncidentTable.tsx             — table with 10 internal mocks, accepts incidents? and limit? props
  ThreatFeed.tsx                — threat list with 5 internal mocks, accepts threats? prop
  ScanResult.tsx                — scan result display (no mocks, driven by props)
  RiskGauge.tsx                 — circular risk gauge (driven by props)
  charts/ScanActivityChart.tsx  — line chart with 7-day internal mocks
  charts/RiskDistributionChart.tsx — donut chart with 4 internal mocks

frontend/lib/
  auth.ts                       — getToken, setToken, clearToken, getUser, apiFetch, useAuth
```

### TypeScript path aliases
`tsconfig.json` defines `"paths": { "@/*": ["./*"] }`, so `@/lib/api`, `@/components/X`, `@/lib/auth` all resolve from the frontend root.

### CSS utility classes (globals.css)
- `.dg-input` — text input styling
- `.dg-select` — select element styling
- `.dg-card` — card container (bg-card + border + border-radius + padding)
- `.ghost-card` — card with `#0f1729` bg and `#1a2744` border (used inline throughout)
- `.stat-card` — gradient stat card with hover lift
- `.btn-primary` — cyan gradient button
- `.btn-ghost` — transparent bordered button
- `.data-table` — th/td table styling
- `.spinner` — animated loading spinner
- `.animate-fade-up` — entry animation
- `.drop-zone` / `.drop-zone.dragging` — file drag-drop zone
- `.badge-critical/.high/.medium/.low` — severity badge presets
- `.badge-restricted/.confidential/.internal/.public` — classification badges
- `.badge-blocked/.alerted/.allowed` — action badges
- `.glow-cyan/.glow-red/.glow-green` — text glow effects
- `.glass` / `.glass-hover` — glassmorphism card
- `.grid-pattern` — background grid lines
- `.nav-link` / `.nav-link.active` — sidebar link

### Tailwind custom tokens (tailwind.config.ts)
```
bg-dg-bg      = #0a0f1e
bg-dg-card    = #0f1729
border-dg-border = #1a2744
text-dg-cyan  = #00d4ff
text-dg-danger = #ff3b3b
text-dg-warning = #ff9f0a
text-dg-success = #34d058
```

### Backend API endpoints confirmed
```
POST   /api/auth/login              — { username, password } → { access_token }
GET    /api/auth/me                 — → { username, role }
GET    /api/dashboard/stats         — requires Bearer → DashboardStats
GET    /api/dashboard/activity      — requires Bearer → ActivityDataPoint[]
GET    /api/incidents               — optional Bearer, query: page, page_size, severity, status, classification, destination, date_from, date_to
PATCH  /api/incidents/{id}          — optional Bearer, body: { status: "OPEN"|"ACKNOWLEDGED"|"RESOLVED" }
GET    /api/devices                 — no auth required
POST   /api/scan/file               — multipart: file, destination, action, device_id, user
POST   /api/scan/text               — JSON: { text, filename, ... }
```

### Mock data locations to remove
1. `app/page.tsx` — `MOCK_STATS`, `MOCK_ACTIVITY`, `MOCK_RISK_DIST` (top-level consts) + uses raw `fetch` instead of `apiFetch`
2. `app/incidents/page.tsx` — `MOCK_INCIDENTS` array of 20 rows (top-level const)
3. `app/devices/page.tsx` — `makeMockDevices()` function + `MOCK_DEVICES` const
4. `app/scanner/page.tsx` — `MOCK_SCAN_RESULT` const, demo fallback in `runScan()`, `runDemoScan()` uses mock timeout
5. `components/IncidentTable.tsx` — `MOCK_INCIDENTS` array of 10 rows (used as fallback when `incidents` prop is empty)
6. `components/ThreatFeed.tsx` — `MOCK_THREATS` array of 5 rows (used as fallback when `threats` prop is empty/absent)
7. `components/charts/ScanActivityChart.tsx` — `MOCK_DATA` array (used when `data` prop absent)
8. `components/charts/RiskDistributionChart.tsx` — `MOCK_DATA` array (used when `data` prop absent)
9. `app/(app)/analytics/page.tsx` — `DEST_DATA`, `SEV_DATA`, `TOP_USERS` top-level consts; classification breakdown computed from mock percentages

### Key architectural observation
The project has **two dashboard systems** that exist in parallel:
- `app/page.tsx` — OLD: raw fetch, mock fallback, no auth guard
- `app/(app)/dashboard/page.tsx` — NEW: uses `apiFetch`, real auth, layout guards
- `app/(app)/layout.tsx` — auth-guarded shell used by all `(app)/*` pages

The `(app)/*` routes are already wired correctly. The old root routes (`/`, `/incidents`, `/devices`, `/scanner`) still exist outside `(app)/` and use no auth guard. The plan migrates the old pages and ensures consistent use of the `(app)/` shell.

---

## Implementation Plan

- [ ] 1. Create `frontend/.env.local` with `NEXT_PUBLIC_API_URL`

      All pages currently inline `const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`. The `.env.local` file does not exist (confirmed). Creating it gives `NEXT_PUBLIC_API_URL` a real value and removes the inline fallback need.

      Files: `frontend/.env.local`

      Content:
      ```
      NEXT_PUBLIC_API_URL=http://localhost:8000
      ```

      Verify: `cat frontend/.env.local` — file exists with the correct line. No build step needed; Next.js reads `.env.local` automatically on `next dev`.

---

- [ ] 2. Create `frontend/lib/api.ts` — centralised typed API client

      Design decision: create a single typed wrapper around the existing `apiFetch` from `lib/auth.ts` rather than using axios (axios is in package.json but not used anywhere — avoid introducing it). Export typed async functions for every backend endpoint the UI calls. Use the `@/` alias (tsconfig maps `@/*` → `./`).

      **All API functions to include:**

      ```ts
      // Auth
      login(username, password) → { access_token }
      fetchMe(token) → { username, role }

      // Dashboard
      fetchDashboardStats() → DashboardStats
      fetchDashboardActivity() → ActivityDataPoint[]

      // Incidents
      fetchIncidents(params: IncidentParams) → IncidentListResponse
      patchIncidentStatus(incidentId, status) → IncidentResponse

      // Devices
      fetchDevices() → Device[]

      // Scan
      scanFile(formData: FormData) → ScanResponse
      scanText(payload: ScanTextPayload) → ScanResponse
      ```

      **TypeScript interfaces to define in `lib/api.ts`:**

      ```ts
      // Re-export from or align with existing IncidentRow in IncidentTable.tsx
      export interface IncidentRow { ... }          // matches IncidentTable.tsx IncidentRow exactly
      export interface IncidentListResponse { items: IncidentRow[]; total: number; page: number; per_page: number; pages: number; }
      export interface IncidentParams { page?: number; per_page?: number; severity?: string; status?: string; classification?: string; }
      export interface DashboardStats { protected_devices: number; files_scanned: number; sensitive_files: number; blocked_transfers: number; critical_incidents: number; recent_threats: ThreatItem[]; }
      export interface ActivityDataPoint { date: string; scans: number; sensitive: number; blocked: number; }
      export interface ThreatItem { incident_id: string; filename: string; risk_score: number; severity: string; user: string; timestamp: string; action_taken: string; }
      export interface Device { id?: number; device_id?: string; device_name: string; ip_address: string; os_type: string; status: string; last_seen: string; files_scanned: number; agent_version: string; incidents_count?: number; }
      export interface ScanResponse { filename: string; file_hash?: string; classification: string; confidence: number; risk_score: number; severity: string; action_taken: string; findings: ScanFinding[]; incident_id?: string | null; breakdown?: Record<string, number>; }
      export interface ScanFinding { rule_name: string; category: string; severity: string; matches_count: number; sample_match?: string; }
      export interface ScanTextPayload { text: string; filename?: string; destination?: string; action?: string; device_id?: string; user?: string; }
      export interface RiskSegment { name: string; value: number; color: string; }
      ```

      Import convention: all other files import from `@/lib/api` (e.g. `import { fetchIncidents, IncidentRow } from "@/lib/api"`).

      Files: `frontend/lib/api.ts`

      Verify: `cd frontend && npx tsc --noEmit` — zero TypeScript errors.

---

- [ ] 3. Create `frontend/lib/useAuthGuard.ts` — auth guard hook

      The `(app)/layout.tsx` already contains the auth check logic. Extract it into a reusable hook so the old pages at `/`, `/incidents`, `/devices`, `/scanner` can also use it.

      ```ts
      // frontend/lib/useAuthGuard.ts
      "use client";
      import { useEffect, useState } from "react";
      import { useRouter } from "next/navigation";
      import { getToken } from "@/lib/auth";

      export function useAuthGuard(): boolean {
        const router = useRouter();
        const [checked, setChecked] = useState(false);
        useEffect(() => {
          if (!getToken()) {
            router.replace("/login");
          } else {
            setChecked(true);
          }
        }, [router]);
        return checked;
      }
      ```

      Returns `true` once the token check passes so pages can gate rendering. Returns `false` during the redirect check so pages can render a spinner.

      Files: `frontend/lib/useAuthGuard.ts`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 4. Update `frontend/components/IncidentTable.tsx` — remove internal mocks, add `loading` and `onStatusChange` props

      Current state: has a 10-row `MOCK_INCIDENTS` array used as fallback when `incidents` prop is empty or absent. Also has no `loading` prop and no status-change callback.

      Changes:
      - Remove the `MOCK_INCIDENTS` const entirely.
      - Add `loading?: boolean` prop. When `loading` is true, render 5 skeleton rows (use the same `animate-pulse` technique already used in `ScanResult.tsx`).
      - Add `onStatusChange?: (incidentId: string, newStatus: string) => void` prop. Add a "Status" column after "Action" with a `<select className="dg-select">` populated with `["OPEN","ACKNOWLEDGED","RESOLVED"]`. On change call `onStatusChange(row.incident_id, newValue)`.
      - When `incidents` prop is an empty array and `loading` is false, render a "No incidents found" empty-state row.
      - Keep the `limit` prop, expandable row detail, `SeverityBadge`, `ActionBadge`, `ClassificationBadge` exactly as-is.

      Import: use `IncidentRow` from `@/lib/api` — remove the local `IncidentRow` interface and re-export it from there so callers can import it from either place (keep `export type { IncidentRow }` in this file for backward compatibility).

      Skeleton row structure (5 rows × 7 columns):
      ```tsx
      <tr>
        <td colSpan={8}><div className="h-4 w-full animate-pulse rounded" style={{background:"rgba(26,39,68,0.8)"}} /></td>
      </tr>
      ```

      Files: `frontend/components/IncidentTable.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors. Check that existing pages that pass `incidents={paginated}` (incidents page) and `limit={5}` with no incidents (dashboard) still compile.

---

- [ ] 5. Rewrite `frontend/app/page.tsx` — SOC Dashboard (root route)

      Current state: uses raw `fetch`, falls back silently to `MOCK_STATS`, `MOCK_ACTIVITY`, `MOCK_RISK_DIST`. No auth guard. `RiskDistributionChart` receives hardcoded `MOCK_RISK_DIST` directly.

      The `(app)/dashboard/page.tsx` is the better, newer version that already works. The root `app/page.tsx` is the OLD version served at `/`. Since `Sidebar.tsx` links to `/` (not `/dashboard`), the user lands on the old unauthenticated page. Fix by redirecting `/` to `/dashboard`.

      Changes to `app/page.tsx`:
      - Replace the entire component with a simple redirect:
        ```tsx
        import { redirect } from "next/navigation";
        export default function RootPage() {
          redirect("/dashboard");
        }
        ```
      - This is a Server Component (no `"use client"` needed).
      - Remove all mock consts, all useState/useEffect, all imports of StatCard/ThreatFeed/IncidentTable/charts/Sidebar.

      Changes to `app/(app)/dashboard/page.tsx` (the real dashboard):
      - Remove `MOCK_*` fallback: if API fails, show a non-blocking error banner (red `dg-card`-styled div) and display zeros/empty state rather than fake data.
      - Add 30-second auto-refresh (already present as `setInterval(load, 30_000)` — keep it).
      - Add skeleton loaders: during initial `loading === true`, render 5 skeleton `stat-card` divs and a skeleton chart area instead of the spinner.
      - Compute `RiskDistributionChart` data from real incidents severity counts: derive from `stats.critical_incidents` and a separate `fetchIncidents` call for severity breakdown (fetch one page, group by severity). Use the `RiskSegment` type from `@/lib/api`.
      - Remove hardcoded `classData` percentages — compute from a real incidents call OR keep the proportional estimate only as a loading placeholder and swap to real data once fetched.
      - Import: `import { fetchDashboardStats, fetchDashboardActivity, fetchIncidents } from "@/lib/api"`. Keep `apiFetch` usage via the new typed wrappers.
      - Error banner: `const [error, setError] = useState<string | null>(null)` — on any fetch failure, set error message. Render above the stat cards: `{error && <div className="dg-card" style={{borderColor:"#ff3b3b",color:"#ff3b3b"}}>{error}</div>}`

      Files: `frontend/app/page.tsx`, `frontend/app/(app)/dashboard/page.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 6. Update `frontend/components/ThreatFeed.tsx` — remove internal mock fallback

      Current state: has `MOCK_THREATS` array used when `threats` prop is absent/empty.

      Changes:
      - Remove `MOCK_THREATS` const.
      - When `threats` prop is absent or empty array, render a clean empty state: a centered message "No recent threats detected" with a green checkmark icon instead of fake data.

      Files: `frontend/components/ThreatFeed.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 7. Remove internal mocks from chart components

      **`components/charts/ScanActivityChart.tsx`:**
      - Remove `MOCK_DATA` const.
      - When `data` prop is empty or absent, render a `<div>` with "No activity data" centered in the chart area (same height as the chart, `style={{height:220}}`).

      **`components/charts/RiskDistributionChart.tsx`:**
      - Remove `MOCK_DATA` const.
      - When `data` prop is empty or absent, render a "No risk data" empty-state inside the chart container.

      Files:
      - `frontend/components/charts/ScanActivityChart.tsx`
      - `frontend/components/charts/RiskDistributionChart.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 8. Rewrite `frontend/app/incidents/page.tsx` — remove 20 hardcoded mocks, backend pagination, auth guard, PATCH status

      Current state: `MOCK_INCIDENTS` array of 20 rows initialized directly into state. Fetches from backend once on mount, replaces only if `data.items.length > 0`. No auth guard. No status update. Client-side pagination on mock data.

      Changes:
      - Add `useAuthGuard()` at top — render spinner if `!checked`.
      - Remove `MOCK_INCIDENTS` const entirely.
      - Replace state with: `const [incidents, setIncidents] = useState<IncidentRow[]>([])`, `const [loading, setLoading] = useState(true)`, `const [error, setError] = useState<string | null>(null)`, `const [total, setTotal] = useState(0)`, `const [page, setPage] = useState(1)`.
      - Fetch uses `fetchIncidents` from `@/lib/api` with `{ page, per_page: PAGE_SIZE, severity: severity !== "ALL" ? severity : undefined }`. On error set `error` state.
      - Pagination is now backend-driven: `totalPages = Math.ceil(total / PAGE_SIZE)`. Next/Previous buttons trigger a new `fetchIncidents` call by updating `page`.
      - Severity filter triggers `setPage(1)` then re-fetch (use a `useEffect` that depends on `[page, severity]`).
      - Search filter remains client-side over the current page's data (no change to UX, just operates over the fetched `incidents` slice rather than all 20 mocks).
      - Pass `loading` prop and `onStatusChange` callback to `<IncidentTable>`. The `onStatusChange` callback calls `patchIncidentStatus(incidentId, newStatus)` from `@/lib/api`, then re-fetches the current page.
      - Error banner: same pattern as dashboard — `{error && <div className="px-4 py-3 rounded-lg text-sm" style={{background:"rgba(255,59,59,0.06)",border:"1px solid rgba(255,59,59,0.2)",color:"#ff3b3b"}}>⚠ {error}</div>}`.
      - Stats row (Total, Critical, Blocked, Filtered) now computed from the real `incidents` array + `total` from API.
      - Import: `import { fetchIncidents, patchIncidentStatus, IncidentRow } from "@/lib/api"` and `import { useAuthGuard } from "@/lib/useAuthGuard"`.

      Files: `frontend/app/incidents/page.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 9. Rewrite `frontend/app/devices/page.tsx` — remove mock generation, add auth guard, skeleton cards, error state, refresh

      Current state: `makeMockDevices()` generates 24 mocks; fetches real data once but only replaces if `data.length > 0`. No auth guard. `window.location.reload()` for refresh.

      Changes:
      - Add `useAuthGuard()` — render spinner if `!checked`.
      - Remove `makeMockDevices()` function and `MOCK_DEVICES` const.
      - Initialize: `const [devices, setDevices] = useState<Device[]>([])`, `const [loading, setLoading] = useState(true)`, `const [error, setError] = useState<string | null>(null)`.
      - Use `fetchDevices()` from `@/lib/api`. On error set `error` state (don't silently ignore).
      - Fetch sends the `Authorization: Bearer <token>` header via `apiFetch` (wrap `fetchDevices` around `apiFetch("/api/devices")`).
      - Replace the `setLoading(true)` spinner with skeleton cards: 6 skeleton `ghost-card` divs (same grid layout) that pulse while `loading` is true.
      - Refresh button: instead of `window.location.reload()`, call the fetch function again: `<button className="btn-ghost text-xs" onClick={loadDevices}>↻ Refresh</button>`.
      - Error banner: same pattern as above.
      - When `devices` is empty and not loading, render "No devices registered" empty state.
      - Import: `import { fetchDevices, Device } from "@/lib/api"` and `import { useAuthGuard } from "@/lib/useAuthGuard"`.

      Files: `frontend/app/devices/page.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 10. Update `frontend/app/scanner/page.tsx` — auth guard, auth token on POST, remove demo fallback mock, real demo button

      Current state: no auth guard. `runScan()` catches any error and falls back to `MOCK_SCAN_RESULT`. `runDemoScan()` uses `setTimeout` to show `MOCK_SCAN_RESULT` without calling the API at all.

      Changes:
      - Add `useAuthGuard()` — render spinner if `!checked`.
      - Remove `MOCK_SCAN_RESULT` const.
      - In `runScan()`: replace raw `fetch` with `scanFile(formData)` from `@/lib/api` (which calls `apiFetch` and includes the Bearer token). On error, set `error` state with the message — do NOT fall back to mock data.
      - In `runDemoScan()`: replace `setTimeout` mock with a real `POST /api/scan/text` call using `scanText` from `@/lib/api`. Use this fixed payload:
        ```json
        {
          "text": "Customer PAN: ABCDE1234F, Aadhaar: 1234 5678 9012, Email: test@example.com, Phone: 9876543210",
          "filename": "demo_customer_data.txt",
          "destination": "EXTERNAL",
          "action": "UPLOAD",
          "device_id": "WEB-CONSOLE",
          "user": "web_analyst"
        }
        ```
        On error, set `error` state — do not fall back to a hardcoded result.
      - Remove `isDemoResult` state (was used to show "Demo mode — mock result shown (backend not connected)" banner — remove that banner).
      - Keep `ScanningProgress` component, drop zone, drag-and-drop, and error UI exactly as-is.
      - Import: `import { scanFile, scanText } from "@/lib/api"` and `import { useAuthGuard } from "@/lib/useAuthGuard"`.

      Files: `frontend/app/scanner/page.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 11. Update `frontend/app/(app)/analytics/page.tsx` — replace hardcoded mocks with real data from incidents API

      Current state: `TOP_USERS`, `SEV_DATA`, `DEST_DATA` are hardcoded consts. `classData` is computed from `stats.sensitive_files` using fixed percentage splits. Only `stats` and `activity` are fetched from real API.

      Changes:
      - Fetch incidents via `fetchIncidents({ per_page: 100 })` on mount alongside the existing stats/activity calls.
      - Derive `SEV_DATA` from real incidents: count incidents by severity → `[{name:"Critical", value: critCount, color:"#ef4444"}, ...]`.
      - Derive `DEST_DATA` from real incidents: count incidents by `destination` field → build the four-item array dynamically.
      - Derive `TOP_USERS` from real incidents: group by `user`, sum incident count, sort descending, take top 5. Compute average `risk` per user from incident `risk_score` values.
      - Derive `classData` from real incidents: count by `classification`, not from fixed percentages. Use same `COLORS` array and `CLASS_LABELS` order.
      - Keep KPI row (Detection Rate 99.2%, False Positives 0.8%, Avg Risk Score, MTTR) — compute `Avg Risk Score` from real incidents average. Keep others as static (they are demo metrics; marking them as static is acceptable).
      - Add `const [incidentsLoading, setIncidentsLoading] = useState(true)` — merge with existing `loading` state so the page shows spinner until all three fetches complete.
      - Remove the `DEST_DATA`, `SEV_DATA`, `TOP_USERS` const blocks.
      - Import: `import { fetchIncidents, IncidentRow, fetchDashboardStats, fetchDashboardActivity } from "@/lib/api"`. Auth is already handled by `(app)/layout.tsx`.

      Files: `frontend/app/(app)/analytics/page.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 12. Update `frontend/components/Sidebar.tsx` — add Analytics link, fix active-state logic for (app)/* routes

      Current state: 4 nav items link to `/`, `/scanner`, `/incidents`, `/devices`. None link to `/dashboard` or `/analytics`. The Dashboard nav item uses `href="/"` which no longer renders a dashboard (it now redirects to `/dashboard`).

      Changes:
      - Change Dashboard `href` from `"/"` to `"/dashboard"`.
      - Add Analytics nav item: `{ href: "/analytics", label: "Analytics", icon: <BarChart2 SVG> }`.
      - Add Events nav item: `{ href: "/events", label: "Events", icon: <Activity SVG> }` (the `(app)/events/page.tsx` already exists).
      - Fix active-state check: for `/dashboard` use `pathname === "/dashboard" || pathname.startsWith("/dashboard")`. For the root `/` check, it is now unused.
      - Keep `/scanner`, `/incidents`, `/devices` hrefs as-is (they still exist and work outside the `(app)/` shell).

      Files: `frontend/components/Sidebar.tsx`

      Verify: `cd frontend && npx tsc --noEmit` — no errors.

---

- [ ] 13. Final type-check and build verification

      Run the full Next.js type-check and build to confirm all 12 changes compile together without errors.

      Files: (none created — verification only)

      Verify:
      ```
      cd frontend
      npx tsc --noEmit
      ```
      Expected: 0 errors, 0 warnings on TypeScript strict mode (`"strict": true` in tsconfig.json).

      Then optionally:
      ```
      cd frontend
      npm run build
      ```
      Expected: Build completes successfully (output: `.next/`). Any pre-existing lint warnings are acceptable; new errors introduced by this plan's changes must be zero.

---

## Implementation Notes for the Coder

### Import convention
All new imports must use the `@/` alias:
```ts
import { fetchIncidents, IncidentRow } from "@/lib/api";
import { useAuthGuard } from "@/lib/useAuthGuard";
import { apiFetch, getToken } from "@/lib/auth";
```
Never use relative imports like `../../lib/api` in new code.

### Auth pattern
- Pages inside `app/(app)/` — auth is handled by `app/(app)/layout.tsx`. Do NOT add `useAuthGuard()` to these pages; they are already protected.
- Pages outside `(app)/` (root `/`, `/incidents`, `/devices`, `/scanner`) — add `useAuthGuard()` from `@/lib/useAuthGuard`.
- All API calls that require auth should go through `apiFetch` (called by the typed functions in `lib/api.ts`), which adds `Authorization: Bearer <token>` and handles 401 → redirect.

### Error state pattern
Use this consistent pattern for error banners:
```tsx
{error && (
  <div
    className="px-4 py-3 rounded-lg text-sm mb-4"
    style={{
      background: "rgba(255,59,59,0.06)",
      border: "1px solid rgba(255,59,59,0.2)",
      color: "#ff3b3b",
    }}
  >
    ⚠ {error}
  </div>
)}
```

### Skeleton loader pattern
Use `animate-pulse` with `rgba(26,39,68,0.8)` background (matches the existing `SkeletonBlock` in `ScanResult.tsx`):
```tsx
<div
  className="h-4 rounded animate-pulse"
  style={{ background: "rgba(26,39,68,0.8)" }}
/>
```

### API base URL
All typed functions in `lib/api.ts` should call `apiFetch(path)` which already reads `process.env.NEXT_PUBLIC_API_URL`. Do NOT re-read `process.env.NEXT_PUBLIC_API_URL` inside `lib/api.ts` — delegate to `apiFetch`.

### Incident status update
`PATCH /api/incidents/{id}` accepts `{ "status": "OPEN" | "ACKNOWLEDGED" | "RESOLVED" }`. The frontend IncidentTable dropdown must use exactly these three values.

### Scanner demo button
`POST /api/scan/text` endpoint accepts JSON body (not FormData). Use `apiFetch("/api/scan/text", { method: "POST", body: JSON.stringify(payload) })`. Content-Type header is set by `apiFetch` automatically.

### Risk distribution on dashboard
The `(app)/dashboard/page.tsx` currently computes `classData` from `stats.sensitive_files * [0.18, 0.35, 0.32, 0.15]`. Replace with a real incidents fetch grouped by severity for the `RiskDistributionChart`: call `fetchIncidents({ per_page: 100 })` once, count by severity, map to `RiskSegment[]` with these colors: `{LOW:"#34d058", MEDIUM:"#ff9f0a", HIGH:"#ff6b35", CRITICAL:"#ff3b3b"}`.
