# 👻 DataGhost

## AI-Powered Data Loss Prevention & Leakage Detection System

> DataGhost monitors endpoints, detects sensitive data using regex DLP rules and ML
> classification, scores risk, and provides a real-time Security Operations Center dashboard.

---

## Architecture

```text
                     ┌──────────────────┐
                     │ DataGhost Agent  │
                     └────────┬─────────┘
                              │
                    Encrypted Communication
                              │
                              ▼
                     ┌──────────────────┐
                     │   API Gateway    │
                     │   (FastAPI)      │
                     └────────┬─────────┘
                              │
             ┌────────────────┼────────────────┐
             ↓                ↓                ↓
       Data Scanner       ML Classifier    Identity
       (DLP Rules)        (TF-IDF+SVM)    (JWT Auth)
             │                │                │
             └────────────────┼────────────────┘
                              ↓
                       Risk Engine
                     (0-100 Score)
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
               Alert Engine       Response Engine
                    │              (ALLOW/ALERT/BLOCK)
                    └─────────┬─────────┘
                              ↓
                     Incident Database
                     (PostgreSQL)
                              ↓
                       Security Dashboard
                       (Next.js SOC UI)
```

```text
Endpoints
   │
   ├── Laptop 1
   ├── Laptop 2
   ├── Laptop 3
   └── Server
        │
        ↓
   DataGhost Agent
        │
        ↓
   Secure API
        │
        ↓
      Cloud
        │
 ┌──────┴───────┐
 ↓              ↓
Database       Risk Engine
 │              │
 └──────┬───────┘
        ↓
 Security Dashboard
```

---

## Features

- 🔍 **16 DLP Detection Rules** — PII, credentials, financial data, corporate markers
- 🤖 **ML Document Classifier** — 4-class (PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED) using TF-IDF + LinearSVC
- ⚡ **Real-time Risk Scoring** — 0–100 composite score with automatic ALLOW / ALERT / BLOCK
- 👻 **DataGhost Agent** — Lightweight file-system monitor for any endpoint
- 📊 **SOC Dashboard** — Live threat feed, scan activity charts, incident management
- 🐳 **Docker Ready** — One-command deployment with Postgres and Redis

---

## Tech Stack

| Layer          | Technology                                          |
|----------------|-----------------------------------------------------|
| Frontend       | Next.js 14, TypeScript, Tailwind CSS, Recharts      |
| Backend        | Python, FastAPI, SQLAlchemy, PostgreSQL / SQLite    |
| ML / AI        | scikit-learn (TF-IDF + LinearSVC)                   |
| Security       | JWT auth, bcrypt, 16-rule DLP regex engine          |
| Agent          | Python watchdog, colorama                           |
| Infrastructure | Docker, Redis, PostgreSQL                           |

---

## Quick Start (Docker)

```bash
git clone <repo-url>
cd dataghost

# Copy environment file and edit passwords / secret key
cp .env.example .env

# Start all services (Postgres, Redis, backend, frontend)
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000) — the SOC dashboard.  
API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Manual Setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Copy and configure environment (SQLite is the default — no Postgres needed)
cp .env.example .env

# Train the ML classifier (~60 synthetic samples, expects ≥ 80% accuracy)
python classifier/train_classifier.py

# Start the API server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Agent

```bash
cd agent
pip install -r requirements.txt

# Optional: set backend credentials ()
export DATAGHOST_USER=admin
export DATAGHOST_PASS=dataghost123

# Edit config.json to set watch_dirs if needed
python dataghost_agent.py
```

---

## Demo Scenario

1. Start the backend and frontend (see above).
2. Open [http://localhost:3000](http://localhost:3000) — the SOC dashboard shows stats and a live threat feed.
3. Go to the **Scanner** page and upload a file or paste text.
4. Create a test file with PII:

   ```text
   # customer_data.txt
   Name: Rahul Sharma
   Email: rahul@example.com
   Phone: 9876543210
   PAN: ABCDE1234F
   Aadhaar: 2345 6789 0123
   ```

5. Run the agent:

   ```bash
   cd agent && python dataghost_agent.py
   ```

6. Drop `customer_data.txt` into `~/Documents` — the agent detects it instantly:

   ```text
   ╔══════════════════════════════════════╗
   ║  🚨 DATA EXFILTRATION DETECTED  🚨  ║
   ╠══════════════════════════════════════╣
   ║  File: customer_data.txt             ║
   ║  Risk: 94 /100 CRITICAL              ║
   ║  Action: BLOCKED                     ║
   ╚══════════════════════════════════════╝
   ```

7. Refresh the dashboard — the incident appears in the threat feed and incidents table.

---

## Detection Examples

| Data Type      | Example                             | Severity  |
|----------------|-------------------------------------|-----------|
| Email          | `user@company.com`                  | MEDIUM    |
| Indian Phone   | `9876543210`                        | MEDIUM    |
| Aadhaar        | `2345 6789 0123`                    | HIGH      |
| PAN Card       | `ABCDE1234F`                        | HIGH      |
| Credit Card    | `4111111111111111`                  | HIGH      |
| Password field | `password=SuperSecret99`            | HIGH      |
| API Key        | `apikey=abc123...xyz789`            | CRITICAL  |
| Private Key    | `-----BEGIN RSA PRIVATE KEY-----`   | CRITICAL  |
| JWT Token      | `eyJhbGci...`                       | CRITICAL  |
| AWS Key        | `AKIAIOSFODNN7EXAMPLE`              | CRITICAL  |

---

## SOC Dashboard

```text
╔══════════════════════════════════════╗
║          DATAGHOST SOC               ║
╠══════════════════════════════════════╣
║ Protected Devices             24     ║
║ Files Scanned              18,492    ║
║ Sensitive Files             1,203    ║
║ Blocked Transfers              37    ║
║ Critical Incidents              4    ║
╠══════════════════════════════════════╣
║ THREATS                              ║
║ 🔴 Customer Data Upload     92       ║
║ 🔴 API Key Exposure         88       ║
║ 🟡 PII Document             64       ║
╚══════════════════════════════════════╝
```

---

## Risk Score Formula

```text
Risk Score (0-100) =
  Data Sensitivity   (0-40)   ← from DLP findings
+ Classification     (0-20)   ← PUBLIC=0 / INTERNAL=8 / CONFIDENTIAL=15 / RESTRICTED=20
+ Destination        (0-20)   ← LOCAL=0 / INTERNAL=5 / CLOUD=15 / USB=18 / EXTERNAL=20
+ Action             (0-10)   ← READ=2 / COPY=7 / SHARE=8 / EMAIL=9 / UPLOAD=10
+ Volume             (0-10)   ← file size proxy (max 10 pts)
```

Severity thresholds: `< 30` LOW · `< 60` MEDIUM · `< 80` HIGH · `≥ 80` CRITICAL

---

## Incident ID Format

`DG-YYYY-XXXX` — e.g. `DG-2024-0042`

---

## Default Credentials

| Username | Password       |
|----------|----------------|
| `admin`  | `dataghost123` |

> Change these in `.env` before any production deployment.

---

## Switching from SQLite to PostgreSQL

The backend uses SQLite by default for zero-config local dev.  
To switch to Postgres, set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/dataghost
```

Docker Compose does this automatically — the `backend` service overrides `DATABASE_URL`
to point at the `db` container.

---

## ML Classifier Notes

The bundled training set is intentionally small (~60 synthetic samples).
`train_classifier.py` prints accuracy on its test split — expect 85–95% on the synthetic data.
For production, replace `classifier/training_data.json` with real labelled documents.

---

## Project Structure

```text
dataghost/
├── agent/                  # Endpoint agent (Python + watchdog)
│   ├── dataghost_agent.py
│   ├── config.json
│   └── requirements.txt
├── backend/                # FastAPI service
│   ├── api/                # Route handlers
│   ├── classifier/         # ML training + inference
│   ├── risk_engine/        # Risk scoring
│   ├── scanner/            # DLP rules + text extractor
│   ├── schemas/            # Pydantic models
│   ├── main.py
│   └── requirements.txt
├── frontend/               # Next.js SOC dashboard
│   ├── app/                # App Router pages
│   ├── components/         # UI components + charts
│   └── lib/                # API client + mock data
├── docker-compose.yml
├── .env.example
└── README.md
```

---

*DataGhost — Because data doesn't just disappear. It haunts you.*
#   D a t a g h o s t  
 