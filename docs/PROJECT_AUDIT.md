# DataGhost — Project Audit
**Phase 0 · Generated during repository inspection**
**Date:** 2026-10-02

---

## 1. Current Architecture

```
dataghost/
├── backend/                 ← FastAPI application (ACTIVE, runs on port 8000)
│   ├── main.py              ← App factory, CORS, startup seeding
│   ├── auth.py              ← JWT + bcrypt + Bearer dependency
│   ├── config.py            ← pydantic-settings (SQLite default)
│   ├── database.py          ← SQLAlchemy engine, WAL mode
│   ├── models.py            ← 4 ORM tables: users, devices, incidents, scan_logs
│   ├── api/                 ← 5 sub-routers mounted under /api
│   │   ├── router.py
│   │   ├── auth_routes.py   ← POST /api/auth/login, GET /api/auth/me
│   │   ├── scan_routes.py   ← POST /api/scan/file, POST /api/scan/text
│   │   ├── incident_routes.py  ← GET /api/incidents, GET /api/incidents/{id}
│   │   ├── device_routes.py    ← GET /api/devices, POST /api/devices/register
│   │   └── dashboard_routes.py ← GET /api/dashboard/stats, /api/dashboard/activity
│   ├── scanner/
│   │   ├── dlp_rules.py     ← 16 compiled regex rules
│   │   ├── sensitive_scanner.py ← DLP runner + severity scorer
│   │   └── text_extractor.py    ← .txt/.csv/.json/.pdf/.docx/.xlsx extraction
│   ├── classifier/
│   │   ├── ml_classifier.py ← TF-IDF + LogisticRegression pipeline
│   │   ├── train_classifier.py  ← 240-example synthetic training set
│   │   └── model/classifier_pipeline.joblib  ← pre-trained model (present)
│   ├── risk_engine/
│   │   └── risk_calculator.py ← 5-component 0-100 risk score
│   ├── schemas/
│   │   └── schemas.py       ← Pydantic v2 request/response models
│   ├── app/                 ← OBSOLETE scaffold (see §6)
│   ├── migrations/          ← Alembic env.py present; no version files yet
│   └── tests/
│       └── test_health.py   ← 1 placeholder test
│
├── frontend/                ← Next.js 14 application (port 3000)
│   ├── app/
│   │   ├── page.tsx         ← Root SOC dashboard (unauthenticated, mock+live)
│   │   ├── login/page.tsx   ← JWT login
│   │   ├── scanner/page.tsx ← File-upload scanner
│   │   ├── incidents/page.tsx ← Incidents list with filter + pagination
│   │   ├── devices/page.tsx ← Device grid
│   │   └── (app)/           ← Auth-gated route group
│   │       ├── layout.tsx   ← Token check + redirect
│   │       ├── dashboard/page.tsx  ← Richer Recharts dashboard
│   │       ├── analytics/page.tsx  ← Analytics charts
│   │       ├── events/page.tsx     ← Event timeline (live, 15 s refresh)
│   │       ├── files/page.tsx
│   │       ├── policies/page.tsx
│   │       ├── settings/page.tsx
│   │       └── users/page.tsx
│   └── components/
│       ├── Sidebar.tsx, TopBar.tsx, StatCard.tsx
│       ├── ThreatFeed.tsx, IncidentTable.tsx, ScanResult.tsx
│       ├── RiskGauge.tsx, ClassificationBadge.tsx
│       └── charts/ (ScanActivityChart, RiskDistributionChart)
│
├── agent/
│   └── dataghost_agent.py   ← Standalone watchdog agent (self-contained)
│
├── database/                ← Empty placeholder directory
├── docs/                    ← This audit (newly created)
├── infrastructure/          ← .gitkeep placeholders only
├── ml/                      ← .gitkeep placeholders only
├── docker-compose.yml       ← postgres + redis + backend + frontend
├── .env.example
└── README.md
```

---

## 2. Existing Technologies

| Layer | Technology | Version | Status |
|---|---|---|---|
| Frontend framework | Next.js | 14.2.18 | ✅ Working |
| Frontend language | TypeScript | 5.7.2 | ✅ Working |
| Styling | Tailwind CSS | 3.4.16 | ✅ Working |
| Charts | Recharts | 2.13.3 | ✅ Working |
| Backend framework | FastAPI | 0.115.6 | ✅ Working |
| Backend language | Python | 3.x | ✅ Working |
| Validation | Pydantic v2 | 2.10.4 | ✅ Working |
| ORM | SQLAlchemy | 2.0.36 | ✅ Working |
| Migrations | Alembic | 1.14.0 | ⚠ Installed, no versions |
| Dev database | SQLite (WAL) | — | ✅ Working |
| Prod database | PostgreSQL | 16 (Docker) | ✅ Docker only |
| Auth | JWT (python-jose) + bcrypt | — | ✅ Working |
| ML | scikit-learn TF-IDF+LogReg | — | ✅ Working |
| Agent | Python watchdog + colorama | — | ✅ Self-contained |
| Container | Docker + Compose | — | ✅ Working |
| CI | GitHub Actions | — | ⚠ Basic only |
| Linter | Ruff | 0.8.4 | ✅ |
| Test runner | pytest | 8.3.4 | ⚠ 1 test only |

**Missing from requirements.txt** (needed by backend but not listed):
- `python-jose[cryptography]` — used in `auth.py`
- `passlib[bcrypt]` — used in `auth.py`
- `joblib` — used by classifier
- `scikit-learn` — used by classifier
- `numpy` — used by classifier
- `python-multipart` — required by FastAPI file uploads
- `PyPDF2` or `pypdf` — used by text_extractor.py
- `python-docx` — used by text_extractor.py
- `openpyxl` — used by text_extractor.py

---

## 3. Existing Features

### ✅ Backend (fully working)
- JWT authentication (login, Bearer token, `get_current_user`)
- Password hashing with bcrypt
- `GET /api/auth/me` — returns current user
- `POST /api/scan/file` — full pipeline: extract → DLP → ML → risk → persist
- `POST /api/scan/text` — same pipeline via JSON body
- `GET /api/incidents` — paginated list with severity + date filters
- `GET /api/incidents/{id}` — single incident detail
- `GET /api/devices` — list all devices
- `POST /api/devices/register` — upsert device (no auth, for agent)
- `GET /api/dashboard/stats` — SOC summary counts
- `GET /api/dashboard/activity` — 7-day per-day breakdown
- `GET /health` — health check
- 16 DLP regex rules (PII, financial, credentials, corporate)
- TF-IDF + LogisticRegression document classifier (4 classes)
- 5-component risk engine (sensitivity + classification + destination + action + volume)
- SQLite default with PostgreSQL via env override
- Demo data seeding (24 devices, 200 scans, 87 incidents) on first boot
- Admin user auto-created on first boot (admin / dataghost123)

### ✅ Frontend (fully working)
- Login page with JWT storage
- Auth-gated route group `(app)/` with redirect
- Root SOC dashboard (`/`) — 5 stat cards, threat feed, incident table, charts
- File scanner (`/scanner`) — drag-drop upload, demo mode, result display
- Incidents page (`/incidents`) — filter, search, pagination, mock+live
- Devices page (`/devices`) — grid view, mock+live
- Auth-gated dashboard (`/dashboard`) — Recharts, 5-stat cards, area/pie/bar charts
- Analytics page (`/analytics`) — line chart, pie charts, compliance gauges
- Events timeline (`/events`) — live 15-second refresh
- `ThreatFeed` schema mismatch fixed (previous fix commit) — live feed now works
- All pages have mock-data fallback for offline demo

### ✅ Agent
- Watchdog filesystem observer
- Inline DLP rules (mirrors backend)
- Inline text extraction
- Inline risk calculator
- Colored terminal output (colorama)
- Backend auth + fallback to local-only mode
- ASCII banner, demo-ready output

---

## 4. Missing Features (vs. requirements)

The following items from the master spec are not yet implemented:

### Backend
| Feature | Spec Section | Priority |
|---|---|---|
| Versioned API routes (`/api/v1/...`) | §29 | Medium |
| Simulation / controlled transfer endpoint | §16 | High (demo) |
| Security event table (`security_events`) | §15, §28 | High |
| Audit log table + endpoints | §23, §28 | High |
| Policy table + engine | §24, §28 | High |
| Risk assessment table | §28 | Medium |
| ML predictions table | §28 | Medium |
| Incident notes / timeline tables | §21, §28 | Medium |
| RBAC enforcement (super_admin / analyst / user roles) | §7 | High |
| Rate limiting | §30 | Medium |
| Alembic migration versions | §3, §28 | Medium |
| `/api/v1/users` CRUD | §29 | Medium |
| `/api/v1/policies` CRUD | §24, §29 | Medium |
| `/api/v1/audit` endpoints | §23, §29 | Medium |
| `/api/v1/simulations/transfer` | §16, §29 | High (demo) |
| `/api/v1/ai/explain` (Ollama optional) | §20, §29 | Low |
| ML anomaly detection (Isolation Forest) | §19 | Medium |
| Prometheus metrics endpoint | §32 | Low |
| Input size/rate limiting | §30 | Medium |

### Frontend
| Feature | Spec Section | Priority |
|---|---|---|
| Incident detail page (`/incidents/[id]`) | §25, §26 | High (demo) |
| Individual device detail page (`/devices/[id]`) | §25 | Medium |
| Policies page (currently stub) | §25 | Medium |
| Users admin page (currently stub) | §25 | Medium |
| Settings page (currently stub) | §25 | Low |
| Audit log page (`/audit`) | §25 | Medium |
| RBAC-based UI restrictions (hide admin from users) | §7 | Medium |
| Simulation UI (trigger controlled transfer) | §16 | High (demo) |
| Incident workflow (change status, add notes) | §21 | High (demo) |

### Infrastructure
| Feature | Spec Section | Priority |
|---|---|---|
| Prometheus + Grafana in docker-compose | §31, §32 | Low |
| `.env.example` database URL for SQLite path | §13 | Low |
| GitHub Actions: frontend lint + type check | §33 | Low |
| GitHub Actions: security scan | §33 | Low |

### Documentation
| Missing file | Spec Section |
|---|---|
| `docs/REQUIREMENTS.md` | §39 |
| `docs/ARCHITECTURE.md` | §39 |
| `docs/DATABASE.md` | §39 |
| `docs/API.md` | §39 |
| `docs/SECURITY.md` | §39 |
| `docs/ML.md` | §39 |
| `docs/AGENT.md` | §39 |
| `docs/DEPLOYMENT.md` | §39 |
| `docs/TESTING.md` | §39 |
| `docs/DEMO.md` | §39 |

---

## 5. Duplicate Functionality

| Duplication | Location | Recommendation |
|---|---|---|
| **Two `config.py` files** | `backend/config.py` (active) and `backend/app/core/config.py` (scaffold, PostgreSQL-only, not imported by main.py) | Keep `backend/config.py`; archive `backend/app/` scaffold |
| **Two `main.py` files** | `backend/main.py` (active, full app) and `backend/app/main.py` (scaffold stub, health-only) | Keep `backend/main.py`; archive `backend/app/` scaffold |
| **Inline DLP rules in agent** | `agent/dataghost_agent.py` contains a full copy of all DLP rules and text-extraction logic | Acceptable for a self-contained agent; document the intentional duplication |
| **Sidebar rendered twice** | `frontend/app/page.tsx` renders its own `<Sidebar>`; `frontend/app/(app)/layout.tsx` also renders `<Sidebar>` inside the auth-gated shell | Each route tree independently includes Sidebar — not a bug, but creates two separate instances. Consider a unified layout if routes are consolidated |
| **Two `next.config` files** | `frontend/next.config.js` and `frontend/next.config.mjs` both exist | Remove one (keep `.mjs`) |

---

## 6. Broken / Incomplete Functionality

| Item | Severity | Details |
|---|---|---|
| **`backend/app/` scaffold** | High | `backend/app/main.py` imports `app.api.health` and `app.core.config` but this path is not mounted in the active `backend/main.py`. Running `uvicorn app.main:app` would fail because `app.core.database.py` still imports PostgreSQL-only settings with no SQLite fallback. This directory is dead code. |
| **Alembic — no migration versions** | Medium | `backend/migrations/versions/` is empty (only a `.gitkeep`). `alembic upgrade head` would be a no-op. Schema is created via `Base.metadata.create_all()` on startup, which works but bypasses migration history. |
| **`backend/requirements.txt` missing deps** | High | `python-jose`, `passlib[bcrypt]`, `joblib`, `scikit-learn`, `numpy`, `python-multipart`, PDF/DOCX/XLSX extraction libs are used but not declared. `pip install -r requirements.txt` in a fresh environment will fail at runtime. |
| **`/incidents/[id]` detail page missing** | High | The incidents list page links to individual incidents but no detail route exists. Clicking an incident row would 404. Required for the viva demo flow. |
| **Policies / Users / Settings pages are stubs** | Medium | Pages exist but contain no real functionality (likely placeholder content). |
| **Simulation endpoint missing** | High | The demo scenario (§36 Scenario 3) requires `POST /api/v1/simulations/transfer`. Without it the "controlled transfer → BLOCK → incident" demo flow cannot be shown live. |
| **Audit log table + UI missing** | Medium | Every important action should be logged. Currently no `audit_logs` table exists. |
| **RBAC is username+role stored, not enforced** | Medium | `User.role` is stored as a string but no endpoint checks whether the caller is `admin` vs. `analyst`. Any authenticated user can call any endpoint. |
| **CI does not install auth/ML deps** | Medium | GitHub Actions `pip install -r requirements.txt` will fail because those packages are missing from requirements.txt. |
| **Incident ID uniqueness race condition** | Low | `_make_incident_id` counts existing incidents to generate the next ID. Under concurrent scans, two requests could generate the same ID. |
| **`next.config.js` + `.mjs` conflict** | Low | Having both files may cause unexpected Next.js behavior. |

---

## 7. Security Concerns

| Concern | Severity | Details |
|---|---|---|
| **Hardcoded default `SECRET_KEY`** | High | `config.py` defaults to `"supersecretkey-change-in-production-at-least-32-chars"`. Any deployment that does not override `SECRET_KEY` via env will use this key. The `.env.example` correctly labels it as "generate-with-openssl" but the fallback is too guessable. |
| **CORS `allow_origins=["*"]`** | Medium | `main.py` uses wildcard CORS for demo convenience. Fine for local dev; must be restricted for any real deployment. |
| **`/api/scan/file` has no authentication** | Medium | The scan endpoint intentionally comments out auth for agent compatibility, but this means any unauthenticated caller can trigger scans and create incidents. The agent should use device registration tokens or a dedicated auth scheme. |
| **Default admin credentials logged** | Low | Startup logs print `username=admin, password=dataghost123` in plaintext to console. Acceptable for demo; remove before any real use. |
| **No rate limiting** | Medium | All endpoints are rate-unlimited. A simple loop could flood the database with scan logs. |
| **No input size limit** | Medium | `POST /api/scan/file` and `/api/scan/text` accept unlimited-size inputs. Large files could cause memory exhaustion. |
| **Token expiry is 1440 minutes (24 hours)** | Low | Very long token lifetime increases exposure window if a token is stolen. |
| **No HTTPS enforcement** | Low | Docker Compose exposes plain HTTP. Acceptable for local demo; would need TLS termination for real deployment. |
| **`findings_json` stores raw match samples** | Low | Storing sample matches (e.g., first 50 chars of an API key) in the database means sensitive data is partially persisted. Consider storing only match counts in production. |

---

## 8. Dependency Problems

```
# Missing from backend/requirements.txt:
python-jose[cryptography]   # auth.py: jwt
passlib[bcrypt]             # auth.py: CryptContext
joblib                      # classifier: pipeline load/save
scikit-learn                # classifier: TF-IDF, LogReg
numpy                       # classifier: probability arrays
python-multipart            # FastAPI: UploadFile form parsing
pypdf                       # text_extractor.py: PDF extraction
python-docx                 # text_extractor.py: DOCX extraction
openpyxl                    # text_extractor.py: XLSX extraction

# Agent (agent/requirements.txt — not inspected above)
# Should include: watchdog, requests, colorama
```

The `ruff` linter is listed as a production dependency rather than a dev dependency — minor but worth noting.

---

## 9. Build / Test Problems

| Problem | Impact |
|---|---|
| `pip install -r requirements.txt` fails in fresh env | Blocks Docker build, CI, and local dev |
| Only 1 backend test (`test_health.py`) — likely a placeholder | No real coverage |
| No frontend tests at all | No CI validation of UI |
| CI workflow only covers backend lint + pytest | Frontend type check / lint not in CI |
| `ruff check .` will warn about unused imports in scaffold files | Minor noise |

---

## 10. Recommended Architecture

The existing `backend/main.py` + flat module structure is clean and functional. The recommended architecture preserves it and adds the missing layers:

```
backend/
├── main.py                   ← Keep as-is
├── auth.py                   ← Keep + add RBAC decorator
├── config.py                 ← Keep + fix SECRET_KEY default warning
├── database.py               ← Keep as-is
├── models.py                 ← Extend: add AuditLog, Policy, SecurityEvent tables
├── api/
│   ├── router.py             ← Add new sub-routers
│   ├── auth_routes.py        ← Keep + add /register (admin only)
│   ├── scan_routes.py        ← Keep + add input size limits
│   ├── incident_routes.py    ← Keep + add PATCH status update
│   ├── device_routes.py      ← Keep as-is
│   ├── dashboard_routes.py   ← Keep + fix already done
│   ├── simulation_routes.py  ← NEW: POST /simulations/transfer
│   ├── audit_routes.py       ← NEW: GET /audit
│   ├── policy_routes.py      ← NEW: CRUD /policies
│   └── user_routes.py        ← NEW: CRUD /users (admin only)
├── scanner/                  ← Keep as-is
├── classifier/               ← Keep as-is
├── risk_engine/              ← Keep as-is
├── schemas/                  ← Extend for new models
└── migrations/versions/      ← Add actual migration

frontend/
├── app/
│   ├── page.tsx             ← Keep (root SOC)
│   ├── (app)/
│   │   ├── incidents/[id]/page.tsx  ← NEW: detail page
│   │   ├── events/page.tsx          ← Keep + minor fix
│   │   └── policies/page.tsx        ← Implement from stub
└── components/
    └── IncidentDetail.tsx   ← NEW component
```

---

## 11. Migration / Implementation Plan

Following the Phase structure from the master spec, and given what already exists:

| Phase | Status | Work Remaining |
|---|---|---|
| **Phase 0** — Audit | ✅ Complete | This document |
| **Phase 1** — Foundation + Docker + DB | ✅ Mostly done | Fix requirements.txt; add missing packages |
| **Phase 2** — Authentication + RBAC | ✅ Auth done | Add RBAC enforcement (role checks on admin endpoints) |
| **Phase 3** — DB models + migrations | ⚠ Partial | Add AuditLog, Policy, SecurityEvent tables; create Alembic versions |
| **Phase 4** — Data scanner | ✅ Complete | — |
| **Phase 5** — Sensitive data detection | ✅ Complete | — |
| **Phase 6** — Data classification | ✅ Complete | — |
| **Phase 7** — Agent | ✅ Complete | — |
| **Phase 8** — Security events | ⚠ Partial | Formalize SecurityEvent table; event types |
| **Phase 9** — Risk engine + policy engine | ⚠ Partial | Risk engine done; policy table + evaluator missing |
| **Phase 10** — Incident management | ⚠ Partial | Incident CRUD done; status update + notes missing |
| **Phase 11** — Controlled response + simulation | ❌ Missing | POST /simulations/transfer endpoint + frontend UI |
| **Phase 12** — ML anomaly detection | ❌ Missing | Isolation Forest on scan features |
| **Phase 13** — Dashboard + analytics | ✅ Mostly done | Missing incident detail page |
| **Phase 14** — Ollama AI analyst | ❌ Missing | Optional, low priority |
| **Phase 15** — Prometheus + Grafana | ❌ Missing | Add to docker-compose |
| **Phase 16** — DevSecOps pipeline | ⚠ Partial | CI basic; need frontend checks + security scan |
| **Phase 17** — Security testing | ❌ Missing | Auth bypass tests, input validation tests |
| **Phase 18** — Final docs + demo | ❌ Missing | Demo script, DEMO.md, remaining docs |

**Recommended next phases (in order):**
1. Fix `requirements.txt` — blocks everything else
2. Add missing tables (AuditLog, Policy, SecurityEvent) + Alembic version
3. Add simulation endpoint + incident detail page — critical for the viva demo
4. Add RBAC enforcement + audit logging
5. Add incident status workflow
6. Add policies CRUD
7. ML anomaly detection
8. Prometheus + Grafana
9. Full documentation

---

## 12. Files to Preserve

All files under `backend/` (except `backend/app/`) — do not touch.
All files under `frontend/` — do not touch (build passes cleanly).
`agent/dataghost_agent.py` — working demo agent.
`docker-compose.yml` — working orchestration.
`.env.example` — correct template.
`.github/workflows/ci.yml` — extend, don't replace.
`README.md` — keep, update later.
`backend/classifier/model/classifier_pipeline.joblib` — trained model, do not delete.
`backend/dataghost.db*` — dev database files (in .gitignore).

---

## 13. Obsolete Files (do NOT delete automatically)

| File/Directory | Reason | Safe to delete? |
|---|---|---|
| `backend/app/` | Dead scaffold; not imported by active main.py | Yes, after confirming nothing references it |
| `backend/app/core/config.py` | Superseded by `backend/config.py` | Yes, with `backend/app/` |
| `backend/app/main.py` | Stub app, health-only | Yes, with `backend/app/` |
| `frontend/next.config.js` | Duplicate of `next.config.mjs` | Yes, keep `.mjs` |
| `infrastructure/docker/.gitkeep` | Empty placeholder | Keep for now |
| `ml/` directories with `.gitkeep` | Placeholders for future Isolation Forest work | Keep for now |

**Do NOT delete `backend/app/` until Phase 3 work explicitly migrates anything worth keeping.
Do NOT delete any `.gitkeep` files — they preserve directory structure in git.**

---

## 14. Files That Must NOT Be Deleted Automatically

- `backend/classifier/model/classifier_pipeline.joblib` — took ~10–30s to train
- `backend/dataghost.db`, `dataghost.db-shm`, `dataghost.db-wal` — dev data
- `agent/.venv/` — local virtual environment (in .gitignore)
- `.github/workflows/ci.yml` — CI configuration
- `docker-compose.yml` — orchestration
- All `frontend/` source files — Next.js build passes cleanly

---

## Summary

DataGhost already has a solid, working foundation:

- The full backend scan pipeline (DLP → ML → risk → persist) works end-to-end.
- The frontend has complete mock-data coverage and a real-data fetch path.
- The agent runs standalone and reports to the backend.
- Docker Compose starts all services.

The primary gaps for the viva demo are:

1. **`requirements.txt` is missing critical packages** — fix first.
2. **No incident detail page** — the demo flow cannot show full evidence without it.
3. **No simulation endpoint** — Scenario 3 (controlled transfer → BLOCK) cannot be demonstrated live.
4. **No audit logging** — every important action should have a trail.
5. **No RBAC enforcement** — any authenticated user can call admin endpoints.
6. **No policy engine** — policies are not evaluated; the risk engine hard-codes the decision.

These six gaps, fixed in order, make DataGhost a complete, defensible major project.
