# DataGhost Deployment Configuration Reference

Quick reference for common deployment configurations, commands, and troubleshooting.

---

## Backend Requirements for Render

### requirements.txt (Production)
Ensure your `backend/requirements.txt` includes:

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
alembic==1.14.0
pytest==8.3.4
httpx==0.28.1
firebase-admin>=6.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.1
python-multipart==0.0.20
gunicorn==22.0.0  # IMPORTANT: Add this for Render
```

### Render Start Command Options

**Option 1: Using Gunicorn (Recommended)**
```bash
cd backend && gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

**Option 2: Direct Uvicorn**
```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Option 3: With Reload Disabled (Production)**
```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload=false --workers 4
```

---

## Backend Environment Variables - Production Template

```bash
# Database Configuration
DATABASE_URL=postgresql://dataghost_user:password@render-postgres-host.internal:5432/dataghost_prod

# Security
SECRET_KEY=use-python-secrets-module-to-generate-32-char-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Environment
ENVIRONMENT=production
APP_NAME=DataGhost API

# Server URL (used in QR codes, enrollment links)
SERVER_PUBLIC_URL=https://dataghost-backend.onrender.com

# CORS Configuration (Production)
CORS_ORIGINS=["https://dataghost-frontend.vercel.app", "https://www.dataghost-frontend.vercel.app"]
FRONTEND_URL=https://dataghost-frontend.vercel.app

# Firebase
FIREBASE_CREDENTIALS_PATH=/var/task/serviceAccountKey.json
FIREBASE_PROJECT_ID=dataghost-9431f

# API Prefix
API_PREFIX=/api

# Logging
LOG_LEVEL=INFO
```

### Generating Secure SECRET_KEY

```bash
# Option 1: Python secrets module
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 2: OpenSSL
openssl rand -base64 32

# Option 3: Using urandom
python -c "import os; print(os.urandom(32).hex())"
```

---

## Frontend Environment Variables - Vercel Production Template

### Environment Variables to Add in Vercel Dashboard

```
BACKEND_URL=https://dataghost-backend.onrender.com
BACKEND_INTERNAL_URL=https://dataghost-backend.onrender.com
NEXT_PUBLIC_API_URL=https://dataghost-backend.onrender.com

# Firebase Config (from Firebase Console)
NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyAuJU8NaPSMrXQ18JxsdWnjiXyZRt2m_nQ
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=dataghost-9431f.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=dataghost-9431f
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=dataghost-9431f.firebasestorage.app
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=442636564485
NEXT_PUBLIC_FIREBASE_APP_ID=1:442636564485:web:3c93b5413684d28a7fc46c
NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-XE9X6MTM0P
```

### Frontend Build & Start Commands

**Build Command:**
```bash
npm run build
```

**Output Directory:**
```
.next
```

**Install Command (if needed):**
```bash
npm install
```

---

## CORS Configuration Examples

### Correct CORS_ORIGINS (Production)
```json
["https://dataghost-frontend.vercel.app", "https://www.dataghost-frontend.vercel.app"]
```

### CORS_ORIGINS with Custom Domain
```json
["https://app.dataghost.io", "https://www.app.dataghost.io", "https://dataghost-frontend.vercel.app"]
```

### CORS Configuration in FastAPI (backend/app/core/config.py)

```python
from pydantic_settings import BaseSettings
from typing import List
import json

class Settings(BaseSettings):
    app_name: str = "DataGhost"
    app_env: str = "development"
    cors_origins: str = '["http://localhost:3000"]'
    
    @property
    def cors_origin_list(self) -> List[str]:
        """Parse CORS origins from environment variable"""
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### CORS Middleware in FastAPI (backend/app/main.py)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,  # Cache preflight requests for 1 hour
)
```

---

## Database Configuration

### PostgreSQL on Render

**Connection String Format:**
```
postgresql://username:password@host:5432/database_name
```

**Example:**
```
postgresql://dataghost_user:secure_password@oregon-postgres.render.com:5432/dataghost_prod
```

**SQLAlchemy Connection (backend code):**
```python
from sqlalchemy import create_engine

# Read from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Test connections before using
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Max overflow connections
)
```

### Database Migrations (Alembic)

**First time setup on production:**
```bash
# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

**After code changes:**
```bash
# Create migration
alembic revision --autogenerate -m "Description of changes"

# Apply to production
alembic upgrade head
```

---

## Testing Deployment Locally Before Production

### Test Backend Build Locally
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run server
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

### Test Frontend Build Locally
```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Start production build
npm start
```

### Environment Variable Testing
```bash
# Create .env.production.local in frontend/
BACKEND_URL=https://dataghost-backend.onrender.com
NEXT_PUBLIC_API_URL=https://dataghost-backend.onrender.com
# ... other vars

# Build with production env
npm run build
```

---

## Common curl Commands for Testing

### Test Health Endpoint
```bash
curl https://dataghost-backend.onrender.com/api/health
```

### Test with CORS Headers
```bash
curl -H "Origin: https://dataghost-frontend.vercel.app" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://dataghost-backend.onrender.com/api/health -v
```

### Test with Authentication (if required)
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://dataghost-backend.onrender.com/api/devices
```

### Test from Frontend URL (simulating frontend request)
```bash
curl -H "Origin: https://dataghost-frontend.vercel.app" \
     https://dataghost-backend.onrender.com/api/health
```

---

## Monitoring Commands

### View Backend Logs (Render CLI)
```bash
# Install Render CLI
npm install -g @render-com/cli

# Login
render login

# Stream logs
render logs --service dataghost-backend --follow

# View recent logs
render logs --service dataghost-backend --lines 100
```

### View Frontend Build Logs (Vercel CLI)
```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# View deployment logs
vercel logs --follow

# View error logs
vercel logs --until 1h --type error
```

---

## Environment Variable Validation Scripts

### Bash Script to Validate Backend Env Vars
```bash
#!/bin/bash
# Check backend environment variables

required_vars=(
    "DATABASE_URL"
    "SECRET_KEY"
    "ALGORITHM"
    "ACCESS_TOKEN_EXPIRE_MINUTES"
    "ENVIRONMENT"
    "SERVER_PUBLIC_URL"
    "CORS_ORIGINS"
    "FIREBASE_PROJECT_ID"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Missing: $var"
    else
        echo "✓ $var is set"
    fi
done
```

### JavaScript to Validate Frontend Env Vars
```javascript
// Check frontend environment variables

const requiredVars = [
    'NEXT_PUBLIC_FIREBASE_API_KEY',
    'NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN',
    'NEXT_PUBLIC_FIREBASE_PROJECT_ID',
    'NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET',
    'NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID',
    'NEXT_PUBLIC_FIREBASE_APP_ID',
    'NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID',
];

requiredVars.forEach(varName => {
    if (!process.env[varName]) {
        console.error(`❌ Missing: ${varName}`);
    } else {
        console.log(`✓ ${varName} is set`);
    }
});
```

---

## Troubleshooting Command Reference

### Test Database Connection
```bash
# Using psql (if installed)
psql "postgresql://user:password@host:5432/database"

# From Python
python -c "from sqlalchemy import create_engine; \
engine = create_engine('DATABASE_URL'); \
conn = engine.connect(); \
print('Connected!'); \
conn.close()"
```

### Test CORS Issue
```bash
# Test preflight request
curl -X OPTIONS \
  -H "Origin: https://dataghost-frontend.vercel.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: content-type" \
  https://dataghost-backend.onrender.com/api/health -v

# Look for Access-Control-Allow-Origin in response headers
```

### Check Build Logs
```bash
# Render: Check build logs for package installation errors
# Vercel: Check build logs for npm/Next.js build errors

# Common issues:
# - Missing dependencies in requirements.txt or package.json
# - Python version mismatch
# - Node version mismatch
# - Environment variables not set during build
```

### Debug Frontend API Calls
```javascript
// In browser console
fetch('https://dataghost-backend.onrender.com/api/health')
  .then(r => {
    console.log('Status:', r.status);
    console.log('Headers:', r.headers);
    return r.json();
  })
  .then(console.log)
  .catch(console.error);
```

---

## Firebase Deployment Configuration

### Firebase Service Account for Backend

**Option 1: File-based (recommended for local, not production)**
1. Get `serviceAccountKey.json` from Firebase Console
2. Add to `.gitignore`: `backend/serviceAccountKey.json`
3. Add to Render environment:
   ```
   FIREBASE_CREDENTIALS_PATH=/var/task/serviceAccountKey.json
   ```

**Option 2: Environment variable-based**
1. Get service account JSON from Firebase Console
2. Store as environment variable: `FIREBASE_CREDENTIALS_JSON`
3. In code:
   ```python
   import os
   import json
   import firebase_admin
   from firebase_admin import credentials
   
   creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
   creds_dict = json.loads(creds_json)
   creds = credentials.Certificate(creds_dict)
   firebase_admin.initialize_app(creds)
   ```

### Restrict Firebase Credentials

In Firebase Console:
1. Go to **Project Settings** → **Service Accounts**
2. Generate new private key
3. Restrict usage to backend service only
4. Rotate keys regularly (monthly recommended)
5. Delete old keys after rotation

---

## Performance Optimization Tips

### Backend
- Enable connection pooling (PostgreSQL)
- Use Gunicorn with appropriate worker count: `workers = 2 * (CPU cores) + 1`
- Enable caching headers for static content
- Use database query optimization and indexing

### Frontend
- Enable Vercel automatic optimization
- Use Next.js image optimization
- Enable incremental static regeneration (ISR) if applicable
- Minify and compress assets (automatic with Next.js)

---

## Monitoring & Alerting Setup

### Render Monitoring
```bash
# Set up webhooks for deployment notifications
# Settings → Notifications → Add webhook

# Webhook URL format:
# POST https://your-service.example.com/webhooks/render
# with deployment status payload
```

### Vercel Monitoring
```bash
# Configure in vercel.json:
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "env": {
    "PRODUCTION": {
      "value": "true"
    }
  }
}
```

---

## Rollback Commands

### Render CLI Rollback
```bash
# List deployments
render deployments --service dataghost-backend

# Redeploy specific deployment
render redeploy --deployment DEPLOYMENT_ID
```

### Vercel CLI Rollback
```bash
# List deployments
vercel list deployments

# Promote a previous deployment
vercel --prod --target DEPLOYMENT_URL
```

---

## Security Checklist Commands

### Check for Hardcoded Secrets
```bash
# Search for common secret patterns
grep -r "SECRET\|PASSWORD\|API_KEY\|TOKEN" --include="*.py" --include="*.js" --include="*.ts"

# Search for suspicious values
grep -r "abc123\|test123\|dummy\|fake" --include="*.py" --include="*.js"

# Check git history
git log --all -S "SECRET_KEY" -p

# Check git secrets installed
git secrets --install
git secrets --register-aws
git secrets --scan
```

---

## Support Resources

- **Render Documentation:** https://render.com/docs
- **Vercel Documentation:** https://vercel.com/docs
- **FastAPI Documentation:** https://fastapi.tiangolo.com
- **Next.js Documentation:** https://nextjs.org/docs
- **PostgreSQL Documentation:** https://www.postgresql.org/docs
- **Firebase Documentation:** https://firebase.google.com/docs

---

## Emergency Contacts & Support

| Service | Support | Priority |
|---------|---------|----------|
| Render | Status Page + Support | https://render-status.com |
| Vercel | Support Dashboard | https://vercel.com/support |
| Firebase | Support Channel | https://firebase.google.com/support |
| GitHub | Issues & Support | https://github.com/support |

