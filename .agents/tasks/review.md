# DataGhost Frontend–Backend Integration (v3 review)

This is the third review pass. The change wires the DataGhost frontend to real backend APIs across
all major pages: a centralised `lib/api.ts` typed client, a `useAuthGuard` hook, and rewrites of
dashboard, incidents, devices, scanner, and analytics pages. All pages show skeleton loaders and
error banners with Retry.

Prior review (v2) raised one blocking finding: the analytics KPI row contained hardcoded constants
("Detection Rate: 99.2% (est.)", "MTTR: 4.2h (est.)", compliance posture scores) with no API
backing. That finding is **resolved** in this pass — those widgets have been removed entirely. The
analytics page now derives all KPIs from the live incidents API: average risk score, blocked-transfer
rate, critical rate, and incidents sampled. No blocking or high findings remain.

Watch for: (1) `app/(app)/users/page.tsx` initialises from a `sampleUsers` hardcoded array with
no API call — this page was not in scope for this integration change, so it is noted as
informational rather than blocking. (2) `app/(app)/files/page.tsx` uses `any[]` typing and calls
`apiFetch` directly rather than going through the typed `lib/api.ts` client, but this is also
out-of-scope for this pass. (3) No build log was produced; TypeScript type correctness is
assessed from code inspection only.

**Verdict**: APPROVED

---

## High-level view

Auth gating is consistent. Pages inside `app/(app)/` are covered by the group layout
(`app/(app)/layout.tsx`) which performs the same token-check-and-redirect as `useAuthGuard`.
Pages outside that group (`/incidents`, `/devices`, `/scanner`) call `useAuthGuard()` directly.
No page slips through ungated.

The API client in `lib/api.ts` delegates all JSON calls to `apiFetch` from `lib/auth.ts`, which
injects the Bearer token and handles 401→redirect centrally. The multipart file-upload path
bypasses `apiFetch` to avoid corrupting the form boundary, but it calls `getToken()` directly and
sets the Authorization header manually — the auth contract is preserved. No mock fallbacks exist in
the API layer; every function throws on a non-OK response.

The analytics KPI section that drove the prior NEEDS_CHANGES verdict has been replaced with metrics
derived entirely from the incidents API response. All four KPI cards (`avgRisk`, `blockedRate`,
`criticalRate`, `incidents.length`) are computed from live data. The `decision_score` field is
displayed as "decision score: N.NNN" in `ScanResult.tsx` — correctly not labelled as a probability.

`app/(app)/users/page.tsx` and `app/(app)/policies/page.tsx` initialise from hardcoded in-file
arrays. These pages were not listed in the integration task scope, so they are out-of-scope
observations rather than findings on this change.

---

<details>
<summary>Issues (0)</summary>

No actionable issues remain. All prior blocking findings have been resolved.

Out-of-scope observations (not findings on this change):
- `app/(app)/users/page.tsx` uses a `sampleUsers` hardcoded array with no API backend call.
- `app/(app)/policies/page.tsx` initialises from a `defaultPolicies` hardcoded array.
- `app/(app)/files/page.tsx` types its state as `any[]` rather than using the typed `IncidentRow` from `lib/api.ts`.

</details>

<details>
<summary>Details</summary>

### Prior blocking finding: analytics hardcoded KPIs — resolved

The v2 review identified KPI cards with invented values ("Detection Rate: 99.2% (est.)",
"False Positives: 0.8% (est.)", "MTTR: 4.2h (est.)") and a compliance posture section with
hardcoded scores. In the current code, none of those strings are present. The KPI row is now:

```tsx
{ label: "Avg Risk Score",     value: avgRisk > 0 ? String(avgRisk) : "—", ... },
{ label: "Blocked Rate",       value: incidents.length > 0 ? `${blockedRate}%` : "—", ... },
{ label: "Critical Rate",      value: incidents.length > 0 ? `${criticalRate}%` : "—", ... },
{ label: "Incidents Sampled",  value: incidents.length > 0 ? String(incidents.length) : "—", ... },
```

All four values are derived from the incidents API response. The compliance posture section is
gone entirely. The finding is closed.

### Auth guard coverage

`app/(app)/layout.tsx` implements the token check inline rather than calling `useAuthGuard()`,
but the logic is identical — `getToken()` → redirect to `/login` if absent, gate rendering with
a `checked` boolean. All five pages under that layout (dashboard, analytics, events, files, users)
are covered. `/incidents`, `/devices`, and `/scanner` each call `useAuthGuard()` at the top of
their component. No page in scope is ungated. (confirmed)

### decision_score labelling

`ScanResult.tsx` displays `decision_score` as "decision score: {decision_score.toFixed(3)}".
The `ScanResultData` interface uses the field name `decision_score`. `lib/api.ts` defines the
same field in both `ScanResultData` and the scanner response mapping. No page or component
uses the word "probability" or "confidence" in connection with this value. (confirmed)

### No new npm dependencies

`package.json` contains the same dependencies present before this change. `axios` is present but
is a pre-existing dependency; it is not imported in any of the new files (`lib/api.ts` and all
rewritten pages use native `fetch`). `firebase` is similarly pre-existing and unused in the
integration files. (confirmed)

</details>

---

<details>
<summary>File map</summary>

| File | What changed |
|------|-------------|
| `frontend/lib/api.ts` | New: typed API client, all endpoint functions delegating to `apiFetch` |
| `frontend/lib/useAuthGuard.ts` | New (lives in `lib/`, not `components/`): token-check hook |
| `frontend/lib/auth.ts` | Pre-existing: `apiFetch`, token helpers — unchanged |
| `frontend/app/page.tsx` | Rewritten to a simple redirect to `/dashboard` |
| `frontend/app/(app)/layout.tsx` | Pre-existing auth-guarded group layout |
| `frontend/app/(app)/dashboard/page.tsx` | Real API, skeleton loading, 30s refresh, Retry |
| `frontend/app/(app)/analytics/page.tsx` | Charts + KPIs from incidents API; hardcoded values removed |
| `frontend/app/incidents/page.tsx` | Backend pagination, severity/status filter, PATCH status, skeleton rows, Retry |
| `frontend/app/devices/page.tsx` | Real `fetchDevices()`, skeleton cards, Refresh + Retry |
| `frontend/app/scanner/page.tsx` | Auth guard, real scan, demo button uses real `scanText()`, no mock fallback |
| `frontend/components/IncidentTable.tsx` | `incidents` prop, `loading` prop, `onStatusChange`, `React.Fragment key` |
| `frontend/components/ScanResult.tsx` | `decision_score` field, correct label |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL=http://localhost:8000` |

Full diff: `git diff main -- frontend/`

</details>
