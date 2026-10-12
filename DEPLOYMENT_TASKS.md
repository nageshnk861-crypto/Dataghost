# DataGhost Deployment Implementation Tasks

This document contains step-by-step implementation tasks for deploying DataGhost backend to Render and configuring the frontend on Vercel.

---

## Task 1: Deploy Backend to Render

### Objective
Set up and deploy the DataGhost FastAPI backend to Render with proper environment configuration and database setup.

### Prerequisites
- GitHub account with access to DataGhost repository
- Render.com account (free tier available)
- PostgreSQL database (Render provides free options)
- Backend code committed to GitHub

### Acceptance Criteria
- ✓ Backend deployed on Render with public URL
- ✓ Health endpoint (`GET /api/health`) returns 200 response
- ✓ Environment variables correctly configured
- ✓ Database connection working (if applicable)
- ✓ CORS configured to allow frontend requests

### Step-by-Step Instructions

#### Step 1.1: Connect GitHub to Render
1. Log into [Render Dashboard](https://dashboard.render.com)
2. Click **+ New** button → Select **Web Service**
3. Click **Connect a repository** button
4. Authorize Render to access your GitHub account
5. Search for and select the `dataghost` repository
6. Click **Connect**

#### Step 1.2: Create Web Service Configuration
1. **Name**: Enter `dataghost-backend`
2. **Environment**: Select **Python 3.11**
3. **Build Command**: 
   ```bash
   pip install -r backend/requirements.txt
   ```
4. **Start Command**: 
   ```bash
   cd backend && gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
   ```
   *Alternative (if gunicorn not available):*
   ```bash
   cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. **Instance Type**: Select appropriate tier (free tier available)
6. **Region**: Select closest region to users

#### Step 1.3: Install Gunicorn (Update requirements.txt if needed)
Before deploying, ensure `gunicorn` is in `backend/requirements.txt`:
```bash
gunicorn==22.0.0
```
If not present, add it to the file.

#### Step 1.4: Configure Environment Variables
In Render dashboard, go to **Environment** tab and add:

```
DATABASE_URL=postgresql://user:password@host:5432/dataghost_prod
```
*(Get this from Render PostgreSQL setup or your database provider)*

```
SECRET_KEY=<generate-a-secure-random-string-at-least-32-characters>
```
Generate using:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENVIRONMENT=production
SERVER_PUBLIC_URL=https://<your-render-backend-url>
FRONTEND_URL=https://<your-vercel-frontend-url>
CORS_ORIGINS=["https://<your-vercel-frontend-url>", "https://www.<your-vercel-frontend-url>"]
FIREBASE_CREDENTIALS_PATH=/var/task/serviceAccountKey.json
FIREBASE_PROJECT_ID=dataghost-9431f
```

**Important CORS Configuration:**
- Include your Vercel frontend URL and www variant
- If using custom domain, include that as well
- Format must be valid JSON array

#### Step 1.5: Set Up PostgreSQL Database (Optional)
If you need a database on Render:
1. In Render Dashboard, click **+ New** → **PostgreSQL**
2. Configure database:
   - **Name**: `dataghost-db`
   - **Database**: `dataghost_prod`
   - **User**: `dataghost_user`
   - **Region**: Same as backend service
3. Copy the `Internal Database URL` for your backend
4. Add `DATABASE_URL` environment variable in backend service (Step 1.4)

#### Step 1.6: Deploy
1. Click **Create Web Service**
2. Monitor the deployment logs
3. Wait for "Deploy successful" message
4. Render will provide a public URL: `https://dataghost-backend.onrender.com`

#### Step 1.7: Handle Firebase Credentials
If your backend uses Firebase:
1. Obtain `serviceAccountKey.json` from Firebase Console
2. Add the file to your repository (or use environment variable):
   - Option A: Add to `.gitignore` and upload manually to Render
   - Option B: Store credentials as environment variable `FIREBASE_CREDENTIALS` and write to disk in startup script
3. Ensure path matches `FIREBASE_CREDENTIALS_PATH` setting

### Verification Method

#### Verify 1: Health Endpoint
```bash
curl https://dataghost-backend.onrender.com/api/health
```
**Expected Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

#### Verify 2: Check Render Logs
1. Go to Render service dashboard
2. Click **Logs** tab
3. Look for:
   - No error messages
   - Successful startup messages
   - Active connections

#### Verify 3: CORS Check
```bash
curl -H "Origin: https://<your-vercel-frontend-url>" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://dataghost-backend.onrender.com/api/health -v
```
**Expected Response Headers:**
```
Access-Control-Allow-Origin: https://<your-vercel-frontend-url>
Access-Control-Allow-Methods: GET, POST, PATCH, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type
```

#### Verify 4: Database Connection (if applicable)
1. In Render logs, check for successful database connections
2. Run a test API endpoint that accesses the database
3. Verify no connection errors in logs

### Troubleshooting Tips

| Issue | Cause | Solution |
|-------|-------|----------|
| **Build fails** | Missing dependencies | Check `backend/requirements.txt` includes all imports |
| **504 Gateway Timeout** | Service not starting | Check logs for errors in startup command |
| **CORS errors in browser** | Wrong CORS_ORIGINS | Verify frontend URL matches exactly in CORS_ORIGINS array |
| **Database connection error** | Wrong DATABASE_URL | Verify PostgreSQL credentials and host in env var |
| **Missing health endpoint** | Router not configured | Ensure `app.include_router(health.router)` in main.py |
| **Cold starts slow** | Free tier limitations | Consider upgrading instance type or enabling auto-scaling |

---

## Task 2: Configure Vercel Environment for Frontend

### Objective
Deploy frontend to Vercel with proper environment variables configured for backend integration.

### Prerequisites
- Vercel.com account
- GitHub account with access to DataGhost repository
- Backend URL from Task 1 (e.g., `https://dataghost-backend.onrender.com`)
- Firebase credentials (from Firebase Console)

### Acceptance Criteria
- ✓ Frontend deployed on Vercel with public URL
- ✓ BACKEND_URL environment variable configured (Production)
- ✓ All NEXT_PUBLIC_FIREBASE_* variables present
- ✓ Build succeeds without errors
- ✓ Frontend loads without 5xx errors

### Step-by-Step Instructions

#### Step 2.1: Connect GitHub to Vercel
1. Log into [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Add New** → **Project**
3. Click **Import Git Repository**
4. Authorize Vercel to access your GitHub account
5. Search for and select `dataghost` repository
6. Click **Import**

#### Step 2.2: Configure Project Settings
1. **Project Name**: `dataghost-frontend` (or preferred name)
2. **Framework Preset**: Select **Next.js**
3. **Root Directory**: Set to `frontend`
4. **Build Command**: Keep default or set to:
   ```bash
   npm run build
   ```
5. **Output Directory**: Keep default `.next`

#### Step 2.3: Add Environment Variables (Production)
Vercel will prompt you to add environment variables. Set them per environment:

**For Production Environment:**

1. **BACKEND_URL**
   ```
   https://dataghost-backend.onrender.com
   ```

2. **BACKEND_INTERNAL_URL** (same as BACKEND_URL for Vercel)
   ```
   https://dataghost-backend.onrender.com
   ```

3. **NEXT_PUBLIC_API_URL** (leave empty for proxy mode or set to BACKEND_URL)
   ```
   https://dataghost-backend.onrender.com
   ```

4. **Firebase Public Variables** (these must start with `NEXT_PUBLIC_`):
   ```
   NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyAuJU8NaPSMrXQ18JxsdWnjiXyZRt2m_nQ
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=dataghost-9431f.firebaseapp.com
   NEXT_PUBLIC_FIREBASE_PROJECT_ID=dataghost-9431f
   NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=dataghost-9431f.firebasestorage.app
   NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=442636564485
   NEXT_PUBLIC_FIREBASE_APP_ID=1:442636564485:web:3c93b5413684d28a7fc46c
   NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-XE9X6MTM0P
   ```

#### Step 2.4: Add Preview Environment Variables (Optional)
For preview deployments (PR previews), add same variables but set:
```
BACKEND_URL=https://dataghost-backend.onrender.com
NEXT_PUBLIC_API_URL=https://dataghost-backend.onrender.com
```

#### Step 2.5: Configure Vercel Settings
1. Go to **Settings** tab
2. **Git** section:
   - Set **Production Branch** to `main`
   - Set **Preview Branches** to deploy from PRs (optional)
3. **Domains** section:
   - Add custom domain if you have one (e.g., `app.dataghost.io`)
   - Configure DNS records as per Vercel instructions

#### Step 2.6: Deploy
1. Click **Deploy** button
2. Monitor build logs for errors
3. Wait for "Deployment successful" message
4. Vercel provides URL: `https://dataghost-frontend.vercel.app`

#### Step 2.7: Update Backend CORS Configuration
Go back to Task 1 and update backend `FRONTEND_URL` and `CORS_ORIGINS`:
```
FRONTEND_URL=https://dataghost-frontend.vercel.app
CORS_ORIGINS=["https://dataghost-frontend.vercel.app", "https://www.dataghost-frontend.vercel.app"]
```
Redeploy backend on Render.

### Verification Method

#### Verify 1: Frontend Loads
1. Visit `https://dataghost-frontend.vercel.app`
2. Page loads without 5xx errors
3. No "Build failed" message

#### Verify 2: Environment Variables Check
1. Open browser DevTools (F12)
2. Go to **Console** tab
3. Paste:
   ```javascript
   console.log(process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID)
   ```
4. Should output: `dataghost-9431f`

#### Verify 3: Build Logs Review
1. In Vercel dashboard, click on deployment
2. Go to **Deployments** tab
3. Click latest deployment
4. Verify:
   - Build completed successfully
   - No error in build output
   - Deployment status: "Ready"

#### Verify 4: API Integration Check
1. Open browser DevTools
2. Go to **Network** tab
3. Interact with API-dependent features
4. Verify API requests go to correct backend URL
5. Check response status is 200 (not 5xx)

### Troubleshooting Tips

| Issue | Cause | Solution |
|-------|-------|----------|
| **Build fails** | Missing npm dependencies | Run `npm install` locally and verify `package.json` committed |
| **Firebase undefined** | Missing NEXT_PUBLIC_ variables | Verify all NEXT_PUBLIC_FIREBASE_* vars in Vercel dashboard |
| **API calls fail** | Wrong BACKEND_URL | Verify BACKEND_URL points to correct Render service |
| **CORS error in browser** | Backend CORS not updated | Update backend CORS_ORIGINS to include Vercel URL |
| **Environment vars not loading** | Not using `process.env` correctly | Check code uses proper Next.js env access patterns |
| **Deployment timeout** | Build taking too long | Check for large dependencies or slow build steps |

---

## Task 3: Test Frontend-Backend Integration

### Objective
Verify that the frontend and backend communicate correctly and all features work in production environment.

### Prerequisites
- Backend deployed on Render (Task 1 complete)
- Frontend deployed on Vercel (Task 2 complete)
- Browser with DevTools available
- Internet connection

### Acceptance Criteria
- ✓ Backend API endpoints respond with 200 status
- ✓ Frontend pages load without errors
- ✓ No red errors in browser console
- ✓ API calls show correct URLs in Network tab
- ✓ Data flows from backend to frontend correctly

### Step-by-Step Instructions

#### Step 3.1: Test Backend Health Endpoint
```bash
curl https://dataghost-backend.onrender.com/api/health
```
**Expected:** Returns 200 with JSON response

#### Step 3.2: Verify Frontend Loads
1. Open `https://dataghost-frontend.vercel.app` in browser
2. Wait for page to fully load
3. Verify URL matches and no redirect loops occur

#### Step 3.3: Check Browser Console (No Errors)
1. Press `F12` to open DevTools
2. Click **Console** tab
3. **Expected:** No red error messages
4. **If errors exist:**
   - Look for API errors (404, 500, etc.)
   - Look for CORS errors
   - Look for missing environment variable warnings
5. Note any errors for troubleshooting

#### Step 3.4: Test API Endpoint Call
1. Keep DevTools open
2. Go to **Network** tab
3. Filter by `api` to show API requests
4. Interact with frontend feature that calls backend (e.g., load devices list)
5. Look for API request in Network tab
6. **Verify:**
   - Request URL: `https://dataghost-backend.onrender.com/api/*`
   - Method: GET, POST, etc. as expected
   - Status: 200 (success)
   - Response: Valid JSON data

#### Step 3.5: Test Specific Endpoints

**Test Devices Endpoint:**
```bash
curl -H "Authorization: Bearer <token-if-required>" \
     https://dataghost-backend.onrender.com/api/devices
```

**Test in Frontend:**
1. Navigate to `/devices` page in frontend
2. Verify data loads
3. Check Network tab for request to `/api/devices`
4. Verify response status is 200

#### Step 3.6: Test CORS Headers
1. In browser Console, run:
   ```javascript
   fetch('https://dataghost-backend.onrender.com/api/health')
     .then(r => r.json())
     .then(console.log)
     .catch(console.error)
   ```
2. **Expected:** Request succeeds and logs response
3. **If CORS error:** Backend CORS_ORIGINS not configured correctly

#### Step 3.7: Test Multiple Pages
Navigate through frontend pages and verify:
1. Pages load without errors
2. Data displays correctly
3. No blank/loading states that don't resolve
4. API calls complete with 200 status

### Verification Method

#### Verification Checklist
- [ ] Health endpoint returns 200
- [ ] Frontend page loads (no 5xx errors)
- [ ] Browser console has no red errors
- [ ] Network tab shows API calls to correct backend URL
- [ ] API responses show status 200
- [ ] Data displays on frontend page
- [ ] No CORS errors in console
- [ ] No environment variable warnings
- [ ] Multiple pages tested and working

#### Performance Check (Optional)
1. Open DevTools **Performance** tab
2. Click record
3. Interact with app for 10 seconds
4. Stop recording
5. **Check:**
   - API response times < 1000ms
   - Page load time reasonable for connection speed
   - No JavaScript errors in timeline

### Troubleshooting Tips

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| **API returns 404** | Endpoint doesn't exist | Verify backend has implemented the endpoint |
| **API returns 500** | Backend error | Check Render backend logs for exception details |
| **CORS error in console** | Backend blocking frontend domain | Update backend `CORS_ORIGINS` to include Vercel domain |
| **Blank page/loading forever** | API call hanging | Check network timeout, verify backend is running |
| **Data displays wrong** | Data transformation issue | Check frontend code parsing API response correctly |
| **Environment variable undefined** | Vercel env vars not set | Verify all NEXT_PUBLIC_* vars in Vercel dashboard |
| **Slow API response** | Backend performance issue | Check Render logs for slow queries or resource issues |
| **Mixed content error** | Loading http from https | Ensure all API URLs use https |

---

## Task 4: Handle Production Considerations

### Objective
Ensure DataGhost is production-ready with proper security, monitoring, and configuration.

### Prerequisites
- Both backend and frontend deployed
- Access to source code repository
- Access to Render and Vercel dashboards
- Firebase Console access (if using Firebase)

### Acceptance Criteria
- ✓ No secrets hardcoded in source code
- ✓ CORS properly configured for production domain
- ✓ Logging enabled for both backend and frontend
- ✓ Error monitoring set up
- ✓ Database backups configured (if applicable)

### Step-by-Step Instructions

#### Step 4.1: Audit Code for Hardcoded Secrets
1. Search repository for common secret patterns:
   ```bash
   # Search for common secret names
   grep -r "SECRET_KEY\|API_KEY\|PASSWORD\|TOKEN" --include="*.py" --include="*.js" --include="*.ts"
   
   # Search for environment examples that may have real values
   grep -r "supersecret\|changeme\|dummy" --include="*.py" --include="*.js"
   ```

2. **Checklist:**
   - [ ] No Firebase credentials in code
   - [ ] No database passwords in code
   - [ ] No SECRET_KEY in source files
   - [ ] All `.env*` files properly in `.gitignore`
   - [ ] Example files use placeholder values only

3. **If secrets found:**
   - Move to environment variables immediately
   - Rotate the compromised secrets
   - Force redeploy to clear cache
   - Audit git history for exposure duration

#### Step 4.2: Verify CORS Configuration
1. **Backend CORS check:**
   - Render dashboard → dataghost-backend service
   - Environment tab → verify `CORS_ORIGINS`
   - Should be a JSON array like:
     ```json
     ["https://dataghost-frontend.vercel.app", "https://www.dataghost-frontend.vercel.app"]
     ```
   - Should NOT include `*` (allow all)

2. **Test CORS manually:**
   ```bash
   curl -H "Origin: https://dataghost-frontend.vercel.app" \
        -H "Access-Control-Request-Method: POST" \
        -X OPTIONS \
        https://dataghost-backend.onrender.com/api/devices -v
   ```
   **Expected headers in response:**
   ```
   Access-Control-Allow-Origin: https://dataghost-frontend.vercel.app
   Access-Control-Allow-Methods: GET, POST, PATCH, DELETE
   ```

3. **Checklist:**
   - [ ] CORS_ORIGINS is JSON array (not string with `*`)
   - [ ] Production domain included
   - [ ] Wildcard `*` NOT used
   - [ ] www variant included if applicable
   - [ ] Custom domain included if applicable

#### Step 4.3: Set Up Backend Logging

**Render Logging:**
1. Go to Render dashboard → dataghost-backend service
2. Click **Logs** tab
3. Logs automatically streamed from stdout/stderr
4. Configure log retention (if available):
   - Set minimum 7 days retention
   - Export logs daily to external storage (optional)

**Backend Code Enhancement:**
1. Update `backend/app/core/config.py` to enable structured logging:
   ```python
   import logging
   
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   ```

2. Add logging to critical operations:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   
   @app.get("/api/devices")
   async def get_devices():
       logger.info("Fetching devices")
       try:
           # ... implementation
           logger.info(f"Successfully retrieved {len(devices)} devices")
       except Exception as e:
           logger.error(f"Error fetching devices: {str(e)}")
           raise
   ```

#### Step 4.4: Set Up Frontend Error Monitoring

**Vercel Built-in Monitoring:**
1. Vercel automatically captures errors
2. Go to Vercel dashboard → dataghost-frontend
3. Click **Monitoring** tab
4. Verify error tracking is enabled

**Frontend Error Logging:**
Add error boundary and logging:
```typescript
// pages/_app.tsx or _app.js
export function reportWebVitals(metric: any) {
  if (process.env.NODE_ENV === 'production') {
    console.log(`${metric.name}:`, metric.value);
    // Send to external monitoring service if desired
  }
}

// Catch unhandled errors
if (typeof window !== 'undefined') {
  window.addEventListener('error', (event) => {
    console.error('Unhandled error:', event.error);
  });
  
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
  });
}
```

#### Step 4.5: Configure Database Backups (if using PostgreSQL)

**Render PostgreSQL Backups:**
1. Go to Render dashboard → dataghost-db service
2. Click **Backups** tab
3. Enable automated backups:
   - Set frequency: Daily
   - Set retention: 7-14 days
4. Verify backup schedule is active
5. Test restore procedure (optional but recommended)

**Backup Checklist:**
- [ ] Automated backups enabled
- [ ] Backup frequency set (daily recommended)
- [ ] Retention period configured (min 7 days)
- [ ] Backup storage location verified
- [ ] Restore procedure documented

#### Step 4.6: Set Up Monitoring and Alerts

**Render Alerts:**
1. Render dashboard → dataghost-backend
2. Click **Settings** → **Alerts**
3. Configure alerts for:
   - Service down/crashes
   - High CPU usage
   - High memory usage
4. Set notification method (email, webhook, etc.)

**Vercel Monitoring:**
1. Vercel dashboard → dataghost-frontend
2. Click **Settings** → **Notifications**
3. Enable build failure notifications
4. Enable deployment error alerts

#### Step 4.7: Document Production Environment

Create `PRODUCTION_SETUP.md` documenting:
```markdown
# Production Environment Setup

## Backend (Render)
- **Service Name:** dataghost-backend
- **URL:** https://dataghost-backend.onrender.com
- **Database:** PostgreSQL on Render
- **Region:** [your-region]
- **Instance Type:** [type-selected]

## Frontend (Vercel)
- **Project Name:** dataghost-frontend
- **URL:** https://dataghost-frontend.vercel.app
- **Region:** [auto]

## Environment Variables
- Backend: [list of configured env vars]
- Frontend: [list of configured env vars]

## Monitoring & Alerts
- Backend logs: Render dashboard
- Frontend logs: Vercel dashboard
- Alerts configured for: [list]

## Backup & Recovery
- Database backups: Daily, 7-day retention
- Recovery procedure: [document steps]

## Update Procedure
1. Commit changes to main branch
2. Render auto-deploys backend
3. Vercel auto-deploys frontend
4. Monitor logs for errors
5. Verify health endpoint and API calls
```

#### Step 4.8: Security Checklist
- [ ] No secrets in code or git history
- [ ] CORS_ORIGINS doesn't use wildcard
- [ ] HTTPS enforced (both services use https://)
- [ ] Authentication enabled on sensitive endpoints
- [ ] Passwords not logged (check logs)
- [ ] Database credentials not exposed
- [ ] Firebase credentials properly restricted
- [ ] API rate limiting considered (optional)
- [ ] Input validation implemented
- [ ] SQL injection protection (SQLAlchemy parameterized queries)

### Verification Method

#### Verification Checklist
- [ ] Code audit complete, no secrets found
- [ ] CORS configuration verified (no wildcards)
- [ ] Backend logs available and accessible
- [ ] Frontend error monitoring active
- [ ] Database backups enabled and tested
- [ ] Monitoring alerts configured
- [ ] Production documentation created
- [ ] Security checklist completed
- [ ] Team notified of production URLs

#### Monitoring Verification
1. **Backend logs accessible:**
   - Render dashboard → Logs tab
   - Verify recent log entries visible
   - Verify no error patterns

2. **Frontend monitoring active:**
   - Vercel dashboard → Monitoring tab
   - Verify web vitals tracked
   - Verify error tracking active

3. **Alerts working:**
   - Render → Trigger test alert
   - Verify notification received
   - Vercel → Check alert settings enabled

### Troubleshooting Tips

| Issue | Cause | Solution |
|-------|-------|----------|
| **Secrets exposed in git** | Committed before .gitignore | Use git-filter-repo to remove from history, rotate secrets |
| **CORS still failing** | Env vars not updated after change | Restart service to pick up new env vars |
| **Logs not appearing** | Logs going to file instead of stdout | Redirect all logging to stdout |
| **Backups not running** | Not properly configured | Verify backup schedule in Render settings |
| **Alerts not triggering** | Notification method misconfigured | Test webhook/email address in settings |
| **Performance degradation** | Resource limits reached | Upgrade instance type or optimize queries |

---

## Deployment Rollback Procedure (Emergency)

### If Production Breaks

1. **Immediate:**
   - [ ] Check error logs (Render for backend, Vercel for frontend)
   - [ ] Identify which service has issue
   - [ ] Check recent deployment changes

2. **Rollback Backend:**
   - Render → dataghost-backend → Deployments
   - Find last known-good deployment
   - Click deploy to revert

3. **Rollback Frontend:**
   - Vercel → dataghost-frontend → Deployments
   - Find last known-good deployment
   - Click "Redeploy" next to that deployment

4. **Post-Incident:**
   - [ ] Document what went wrong
   - [ ] Fix the issue in code
   - [ ] Deploy again with fix
   - [ ] Verify in staging first (if available)

---

## Next Steps After Deployment

1. **Configure custom domain** (if you have one):
   - Update DNS records
   - Configure HTTPS certificate
   - Update environment variables with new URLs

2. **Set up CI/CD monitoring:**
   - Both Render and Vercel auto-deploy on main branch push
   - Monitor deployment logs after each push

3. **Plan regular updates:**
   - Weekly: Check Render/Vercel for platform updates
   - Monthly: Update Python/Node dependencies
   - Quarterly: Security audit of deployed code

4. **User communication:**
   - Share production URLs with team
   - Document login/access procedures
   - Set up user feedback channel

---

## Summary

| Task | Provider | URL | Status |
|------|----------|-----|--------|
| Backend API | Render | https://dataghost-backend.onrender.com | Pending |
| Frontend App | Vercel | https://dataghost-frontend.vercel.app | Pending |
| Database | Render PostgreSQL | Internal | Pending |
| Monitoring | Render + Vercel | Dashboards | Pending |
| Backups | Render | Automated | Pending |

Update status to ✅ as each task completes.
