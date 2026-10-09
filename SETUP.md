# DataGhost — Setup & Installation Guide

Complete step-by-step guide for local development and production deployment.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Development Setup](#development-setup)
3. [Backend Configuration](#backend-configuration)
4. [Frontend Configuration](#frontend-configuration)
5. [Running Locally](#running-locally)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Android Enterprise Enrollment (Production Deployment)](#android-enterprise-enrollment-production-deployment)
9. [Docker Deployment](#docker-deployment)
10. [Production Setup](#production-setup)

---

## System Requirements

### For Development

- **OS:** Windows 10+ / macOS 10.15+ / Linux (Ubuntu 18.04+)
- **Python:** 3.9 or higher
- **Node.js:** 18.0 or higher
- **Disk Space:** 2GB (including dependencies)
- **RAM:** 4GB minimum
- **Git:** Latest version

### For Production

- All development requirements, plus:
- **PostgreSQL:** 12+ (instead of SQLite)
- **Redis:** 6+ (optional, for caching/sessions)
- **Docker:** 20+ (optional, for containerization)

---

## Development Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/dataghost.git
cd dataghost
```

### Step 2: Backend Setup

#### Windows (PowerShell)

```powershell
cd backend

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# If you get execution policy error, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt

# Verify installation (should see 93/93 tests passed)
python -m pytest tests/ -q
```

#### macOS / Linux

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m pytest tests/ -q
```

### Step 3: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Verify TypeScript (should show no errors)
npx tsc --noEmit

# Verify build
npm run build
```

### Step 4: Environment Configuration

Copy the example environment file:

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

```env
# Database (SQLite for dev, PostgreSQL for production)
DATABASE_URL=sqlite:///./dataghost.db

# Security
SECRET_KEY=your-256-bit-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# API
ALLOWED_ORIGINS=http://localhost:3000
DEBUG=True

# File Upload
MAX_UPLOAD_SIZE_MB=50
ALLOWED_FILE_TYPES=pdf,docx,txt,doc

# ML Model
ML_MODEL_PATH=./ml/model.pkl
ML_CONFIDENCE_THRESHOLD=0.6
```

Configure frontend:

```bash
cd frontend
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
```

---

## Backend Configuration

### Database Setup

**SQLite (Development — Default)**

SQLite database is created automatically on first run at `backend/dataghost.db`.

To reset:
```bash
rm backend/dataghost.db
# Restart backend — new schema created
```

To inspect:
```bash
cd backend
sqlite3 dataghost.db ".tables"
sqlite3 dataghost.db "SELECT COUNT(*) FROM incidents;"
```

**PostgreSQL (Production)**

Set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+psycopg2://username:password@localhost:5432/dataghost
```

Create the database:
```bash
createdb dataghost -U postgres
```

Run migrations (if any):
```bash
cd backend
alembic upgrade head
```

### ML Model Training

The backend includes a pre-trained model at `backend/ml/model.pkl`.

To retrain:

```bash
cd backend
python classifier/train_classifier.py
```

Expected output:
```
Loading training data...
Training classifier...
Accuracy: 85.34%
Model saved to ml/model.pkl
```

---

## Frontend Configuration

### Environment Variables

Create `frontend/.env.local`:

```bash
# API endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000

# Analytics (optional)
NEXT_PUBLIC_GA_ID=

# Feature flags (optional)
NEXT_PUBLIC_ENABLE_DARK_MODE=true
NEXT_PUBLIC_ENABLE_ANALYTICS=false
```

### Build Optimization

For production builds:

```bash
cd frontend
npm run build
npm start  # Production server
```

Static export (for CDN):
```bash
cd frontend
npm run export  # Creates .next/out/ directory
# Upload .next/out/ to CDN
```

---

## Running Locally

### Terminal 1: Backend

```bash
cd backend
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\Activate.ps1  # Windows

uvicorn main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

API docs: `http://localhost:8000/docs`

### Terminal 2: Frontend

```bash
cd frontend
npm run dev
```

Expected output:
```
  ready - started server on http://localhost:3000
```

### Terminal 3: Agent (Optional)

```bash
cd agent
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\Activate.ps1  # Windows

python dataghost_agent.py
```

Expected output:
```
Starting DataGhost Agent...
Watching directories: /Users/username/Documents, /Users/username/Desktop
Agent started. Ctrl+C to stop.
```

### Access the Application

Open browser: **`http://localhost:3000`**

**Default Login:**
- Username: `admin`
- Password: `dataghost123`

---

## Testing

### Run All Tests

```bash
cd backend
python -m pytest tests/ -v
```

Expected: `93 passed in X.XXs`

### Run Specific Test File

```bash
cd backend
python -m pytest tests/test_auth.py -v
```

### Run Tests with Coverage

```bash
cd backend
pip install pytest-cov
python -m pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html to see coverage report
```

### Run Frontend Tests (Future)

```bash
cd frontend
npm run test
```

---

## Troubleshooting

### Backend Issues

#### "ModuleNotFoundError: No module named 'fastapi'"

Backend dependencies not installed:
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

#### "Connection refused on port 8000"

Backend not running. Start it:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Or check if port is in use:
```bash
# macOS/Linux
lsof -i :8000

# Windows PowerShell
Get-NetTCPConnection -LocalPort 8000
```

#### "Database locked" error

SQLite is locked (usually by another process):
```bash
# Kill all Python processes
pkill python

# Or restart your terminal
```

#### "ML model not found"

Model file missing:
```bash
cd backend
python classifier/train_classifier.py
```

### Frontend Issues

#### "Cannot reach backend" error

Frontend API URL incorrect or backend not running:

1. Check `NEXT_PUBLIC_API_URL` in `frontend/.env.local`
   ```bash
   echo $NEXT_PUBLIC_API_URL  # Should print http://localhost:8000
   ```

2. Check backend is running:
   ```bash
   curl http://localhost:8000/docs  # Should get 200 OK
   ```

3. Clear browser cache and reload

#### "TypeScript errors"

Type checking failed:
```bash
cd frontend
npx tsc --noEmit
```

Fix errors or suppress strict mode:
```bash
# In tsconfig.json, add:
"noImplicitAny": false
```

#### "Port 3000 already in use"

Run frontend on different port:
```bash
cd frontend
npm run dev -- -p 3001
# Visit http://localhost:3001
```

#### "npm ERR! code ERESOLVE"

Dependency conflict:
```bash
cd frontend
npm install --legacy-peer-deps
```

### Common Fixes

#### Reset Everything

```bash
# Backend
cd backend
rm -rf venv dataghost.db
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend
cd frontend
rm -rf node_modules .next
npm install
npm run build

# Restart servers
```

#### Clear All Caches

```bash
# Backend cache
cd backend
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete

# Frontend cache
cd frontend
rm -rf .next out node_modules
npm install
```

#### Enable Debug Logging

Backend:
```bash
# In backend/.env
DEBUG=True

# Or run with debug flag
LOGLEVEL=DEBUG uvicorn main:app --reload
```

Frontend:
```bash
# Browser DevTools
F12 → Console → Network tabs
```

---

## Android Enterprise Enrollment (Production Deployment)

### Overview

DataGhost supports **automatic Android Enterprise Device Policy Controller (DPC) provisioning** — the official, most secure enrollment method for company-owned Android devices.

**Zero Manual Steps:**
1. Admin generates enrollment QR code in dashboard
2. Device factory reset → Setup Wizard
3. Tap screen 6× → "Set up with QR code"
4. Scan QR → DPC installs automatically
5. Device registers and appears ACTIVE in dashboard
6. Background heartbeat starts automatically every 15 minutes

**Security Guarantees:**
- ✅ Official Android Enterprise provisioning (no bypasses)
- ✅ DPC APK signature validated by Android system
- ✅ Token single-use and time-expiring (900 seconds default)
- ✅ Device registers via secure API call
- ✅ All permissions requested transparently (no silent grants)

### Prerequisites

- **Android Device:** Supports "Tap to Set Up" (factory reset with special setup mode)
- **APK Hosting:** Backend must serve signed APK at `/dataghost-agent.apk`
- **Server URL:** Backend public URL must be reachable by device
- **Network:** Device must have internet connectivity during enrollment

### Step 1: Generate Release APK with Production Signing

The debug APK is for development only. Production requires a release APK signed with your organization's key.

#### Windows

```powershell
cd mobile\android

# Generate a new keystore (if you don't have one)
# Replace yourname, email, and password with real values
$keytoolPath = "C:\Program Files\Java\jdk-*\bin\keytool.exe"
& $keytoolPath -genkeypair `
  -alias "dataghost-production" `
  -keyalg RSA `
  -keysize 2048 `
  -validity 10950 `
  -keystore keystore.jks `
  -storepass "your_keystore_password" `
  -keypass "your_key_password" `
  -dname "CN=DataGhost, OU=Security, O=YourOrg, L=City, ST=State, C=US"

# Build release APK
.\gradlew.bat assembleRelease -Pandroid.injected.signing.store.file=keystore.jks `
  -Pandroid.injected.signing.store.password="your_keystore_password" `
  -Pandroid.injected.signing.key.alias="dataghost-production" `
  -Pandroid.injected.signing.key.password="your_key_password"

# Output: app\build\outputs\apk\release\app-release.apk
```

#### macOS / Linux

```bash
cd mobile/android

# Generate a new keystore (if you don't have one)
keytool -genkeypair \
  -alias dataghost-production \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10950 \
  -keystore keystore.jks \
  -storepass your_keystore_password \
  -keypass your_key_password \
  -dname "CN=DataGhost, OU=Security, O=YourOrg, L=City, ST=State, C=US"

# Build release APK
./gradlew assembleRelease \
  -Pandroid.injected.signing.store.file=keystore.jks \
  -Pandroid.injected.signing.store.password="your_keystore_password" \
  -Pandroid.injected.signing.key.alias="dataghost-production" \
  -Pandroid.injected.signing.key.password="your_key_password"

# Output: app/build/outputs/apk/release/app-release.apk
```

**IMPORTANT:** Store the keystore file and passwords securely. You'll need them for all future releases.

### Step 2: Extract Certificate SHA-256 Checksum

The Android system validates the DPC APK signature using a SHA-256 checksum. This must match `ANDROID_DPC_CERT_CHECKSUM` in backend config.

```bash
cd mobile/android

# For release APK
apksigner verify --print-certs app/build/outputs/apk/release/app-release.apk
```

Output:
```
Signer #1 certificate DN: CN=DataGhost, OU=Security, O=YourOrg, ...
Signer #1 certificate SHA-256 digest: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6...
```

**Convert SHA-256 to base64url format (no padding):**

```bash
# SHA-256 hex: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
# Convert to bytes → base64 → remove padding

# Using Python:
python -c "
import base64
sha256_hex = 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6'  # Replace with your SHA-256
sha256_bytes = bytes.fromhex(sha256_hex)
base64_str = base64.b64encode(sha256_bytes).decode()
base64url = base64_str.replace('+', '-').replace('/', '_').rstrip('=')
print(f'Base64url: {base64url}')
"
```

Output: `oEK0v2z9Hsw3DZ8FzCP1m8XQAx4kymZ-uFSGS9Py7LY`

### Step 3: Configure Backend

Update `backend/.env`:

```env
# Public server URL (must be reachable by device)
SERVER_PUBLIC_URL=https://yourdomain.com

# APK checksum (base64url, no padding) from Step 2
ANDROID_DPC_CERT_CHECKSUM=oEK0v2z9Hsw3DZ8FzCP1m8XQAx4kymZ-uFSGS9Py7LY

# Optional: APK download timeout
ANDROID_DPC_DOWNLOAD_TIMEOUT_SECONDS=60

# Optional: Enrollment token expiration
ENROLLMENT_TOKEN_EXPIRATION_SECONDS=900
```

### Step 4: Host the APK

The backend serves the signed APK at `GET /dataghost-agent.apk`. Configure where it should load from:

**Option A: Copy APK to backend static directory**

```bash
# After building release APK:
cp mobile/android/app/build/outputs/apk/release/app-release.apk \
   backend/static/dataghost-agent.apk
```

**Option B: Configure APK path in backend config**

Edit `backend/config.py`:

```python
# Paths checked in order:
ANDROID_APK_PATHS = [
    "static/dataghost-agent.apk",
    "mobile/android/app/build/outputs/apk/release/app-release.apk",
    "mobile/android/app/build/outputs/apk/debug/app-debug.apk",
]
```

### Step 5: Verify APK Hosting

```bash
# Test the endpoint
curl -v https://yourdomain.com/dataghost-agent.apk \
  -H "Accept: application/vnd.android.package-archive"

# Expected response:
# HTTP/1.1 200 OK
# Content-Type: application/vnd.android.package-archive
# Content-Length: 6721743
# (binary APK data)
```

### Step 6: Production Deployment Checklist

Before launching Android enrollment in production:

- [ ] Release APK built with production signing key
- [ ] APK checksum extracted and configured in `ANDROID_DPC_CERT_CHECKSUM`
- [ ] `SERVER_PUBLIC_URL` set to production domain (https, not http)
- [ ] APK hosted at `https://yourdomain.com/dataghost-agent.apk`
- [ ] Certificate is valid and not self-signed (or device has CA trust configured)
- [ ] Backend API tests passing: `pytest backend/tests/test_android_enterprise_enrollment.py -v`
- [ ] Manual test: Generate QR code, scan on device, verify enrollment completes
- [ ] Heartbeat verified: Check backend logs for device heartbeat POSTs after registration

### Step 7: Admin Workflow

**For IT Administrators:**

1. **Log in to DataGhost dashboard** → `https://yourdomain.com`
2. **Navigate:** Devices → Add Device
3. **Select:** Android → Automatic Enrollment (⚡ PRIMARY)
4. **Choose:** Fully Managed Device Owner (🌟 RECOMMENDED) or Work Profile
5. **Generate QR Code** → Display on screen
6. **Device Administrator:** Factory reset device
7. **Device Setup Wizard:** Tap 6× on setup screen
8. **Select:** "Set up with QR code"
9. **Scan QR** with device camera
10. **Device:** Automatically downloads DPC, installs, registers
11. **Dashboard:** Device appears ACTIVE within ~10 seconds
12. **Verification:** Device heartbeat visible in logs

### Step 8: Troubleshooting Android Enrollment

#### Device won't scan QR code

- Ensure QR code is displayed on a bright screen
- QR code should be at least 4cm × 4cm
- Try scanning from 15-30cm distance
- Device camera may need Android 9.0+ for Setup QR scanning

#### "Device not connecting to server" error

- Check `SERVER_PUBLIC_URL` is reachable from device
- Verify device has internet connectivity
- Check DNS resolution: `nslookup yourdomain.com` from device
- Firewall: Ensure HTTPS port 443 is open

#### "APK signature verification failed"

- Verify APK checksum matches `ANDROID_DPC_CERT_CHECKSUM`
- Ensure APK is signed with the correct certificate
- Rebuild APK and re-verify checksum

#### Device shows "PENDING" but never completes

- Check backend logs for enrollment errors
- Verify DPC receiver is listed in manifest: `DataGhostDeviceAdminReceiver`
- Check device battery level (low battery may delay registration)
- Retry enrollment: generate new QR code

#### Device is "ACTIVE" but no heartbeat

- Check device has background restrictions disabled
- Verify WorkManager is allowed in app permissions
- Check backend logs for 404 on heartbeat endpoint

---

## Docker Deployment

### Prerequisites

- Docker 20+
- Docker Compose 1.29+

### Quick Start

```bash
# Copy environment file
cp .env.example .env

# Start all services
docker compose up --build

# Wait 30 seconds for services to start
```

Services:
- **Backend:** `http://localhost:8000`
- **Frontend:** `http://localhost:3000`
- **Database:** PostgreSQL (internal)
- **Redis:** Cache (internal)

### Docker Compose Breakdown

```yaml
services:
  db:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: dataghost

  redis:
    image: redis:7

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+psycopg2://postgres:postgres@db:5432/dataghost
      REDIS_URL: redis://redis:6379
    depends_on:
      - db
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - backend
```

### Useful Docker Commands

```bash
# Stop containers
docker compose down

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Rebuild after code changes
docker compose up --build

# Access container shell
docker exec -it dataghost-backend bash

# Check database
docker exec -it dataghost-db psql -U postgres -d dataghost
```

---

## Production Setup

### 1. Environment Variables

Create `backend/.env`:

```env
# Database
DATABASE_URL=postgresql+psycopg2://user:password@prod-db:5432/dataghost

# Security
SECRET_KEY=generate-a-strong-256-bit-key-with-openssl
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# API
ALLOWED_ORIGINS=https://yourdomain.com
DEBUG=False

# File Upload
MAX_UPLOAD_SIZE_MB=50

# ML Model
ML_MODEL_PATH=/app/ml/model.pkl
```

Generate secure secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Database Migration

```bash
# Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE dataghost;"

# Create application user
psql -U postgres -c "CREATE USER dataghost_user WITH PASSWORD 'strong_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE dataghost TO dataghost_user;"

# Run schema migrations (if any)
alembic upgrade head
```

### 3. SSL/TLS Setup

```bash
# Generate self-signed certificate (development only)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Or use Let's Encrypt (production)
sudo certbot certonly --standalone -d yourdomain.com
```

### 4. Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/dataghost

upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:3000;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Backend API
    location /api {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/dataghost /etc/nginx/sites-enabled/
sudo nginx -t  # Test config
sudo systemctl restart nginx
```

### 5. Process Management (Systemd)

Backend service: `/etc/systemd/system/dataghost-backend.service`

```ini
[Unit]
Description=DataGhost Backend
After=network.target postgresql.service

[Service]
Type=notify
User=dataghost
WorkingDirectory=/opt/dataghost/backend
Environment="PATH=/opt/dataghost/backend/venv/bin"
ExecStart=/opt/dataghost/backend/venv/bin/gunicorn main:app --workers 4 --bind 127.0.0.1:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start:
```bash
sudo systemctl daemon-reload
sudo systemctl start dataghost-backend
sudo systemctl enable dataghost-backend
```

Check status:
```bash
sudo systemctl status dataghost-backend
sudo journalctl -u dataghost-backend -f
```

### 6. Backup Strategy

```bash
# Database backup (daily)
pg_dump dataghost > /backups/dataghost-$(date +%Y-%m-%d).sql

# File storage backup (if storing files on disk)
rsync -av /opt/dataghost/uploads /backups/
```

### 7. Monitoring & Logging

Application logs:
```bash
# Backend
tail -f /var/log/dataghost/backend.log

# Frontend (if using container)
docker logs -f dataghost-frontend
```

System monitoring:
```bash
# CPU/Memory usage
htop

# Disk space
df -h

# Open connections
netstat -an | grep 8000
```

---

## Next Steps

1. Start backend and frontend locally (see [Running Locally](#running-locally))
2. Upload a test file via the Scanner page
3. Verify scan results appear in the dashboard
4. Run tests: `cd backend && python -m pytest tests/ -v`
5. Read [DEMO.md](./DEMO.md) for demo scenario
6. Deploy to production when ready

---

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review API docs: `http://localhost:8000/docs`
3. Check logs: `docker compose logs -f`

