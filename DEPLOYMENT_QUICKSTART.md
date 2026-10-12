# DataGhost Deployment Quick Start

**Fast track to production in ~30 minutes. Follow this step-by-step if you have accounts ready.**

---

## Prerequisites Checklist (Before You Start)

- [ ] Render.com account created
- [ ] Vercel.com account created
- [ ] GitHub repository connected to both services
- [ ] PostgreSQL database details (if using external DB)
- [ ] Firebase credentials ready
- [ ] All code committed to `main` branch

**Time to complete:** 5-10 minutes
**Ready?** → Continue below

---

## Phase 1: Deploy Backend (10 minutes)

### 1. Create Render Service
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **+ New** → **Web Service**
3. Select your `dataghost` repository
4. Fill in:
   - **Name:** `dataghost-backend`
   - **Environment:** Python 3.11
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000`
   - **Region:** Your preferred region
5. Click **Create Web Service**

### 2. Add Environment Variables (While deploying)
Service is building. While waiting, add environment variables:

1. Go to **Environment** tab
2. Add these variables:

```
DATABASE_URL=postgresql://user:pass@host:5432/db
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_urlsafe(32))">
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENVIRONMENT=production
SERVER_PUBLIC_URL=https://dataghost-backend.onrender.com
FRONTEND_URL=https://dataghost-frontend.vercel.app
CORS_ORIGINS=["https://dataghost-frontend.vercel.app"]
FIREBASE_PROJECT_ID=dataghost-9431f
```

3. Click **Deploy** to apply changes

### 3. Verify Backend (1 minute)
```bash
# Wait for deployment to complete, then test:
curl https://dataghost-backend.onrender.com/api/health

# Expected: {"status": "healthy", ...}
```

✅ **Backend deployed!** Note the URL: `https://dataghost-backend.onrender.com`

---

## Phase 2: Deploy Frontend (10 minutes)

### 1. Create Vercel Project
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Add New** → **Project**
3. Click **Import Git Repository**
4. Select `dataghost` repository
5. Configure:
   - **Project Name:** `dataghost-frontend`
   - **Framework:** Next.js
   - **Root Directory:** `frontend`
6. Click **Import**

### 2. Add Environment Variables
Before clicking Deploy, add environment variables:

**Environment:** Production

```
BACKEND_URL=https://dataghost-backend.onrender.com
BACKEND_INTERNAL_URL=https://dataghost-backend.onrender.com
NEXT_PUBLIC_API_URL=https://dataghost-backend.onrender.com
NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyAuJU8NaPSMrXQ18JxsdWnjiXyZRt2m_nQ
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=dataghost-9431f.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=dataghost-9431f
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=dataghost-9431f.firebasestorage.app
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=442636564485
NEXT_PUBLIC_FIREBASE_APP_ID=1:442636564485:web:3c93b5413684d28a7fc46c
NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-XE9X6MTM0P
```

3. Click **Deploy**

### 3. Verify Frontend (1 minute)
1. Wait for deployment to complete
2. Click the deployment URL
3. Frontend should load without errors
4. Open DevTools (F12) → Console
5. No red errors should appear

✅ **Frontend deployed!** Note the URL: `https://dataghost-frontend.vercel.app`

---

## Phase 3: Connect Frontend to Backend (5 minutes)

### 1. Update Backend CORS
1. Go back to Render dashboard → `dataghost-backend`
2. Click **Environment**
3. Update:
   - `FRONTEND_URL=https://dataghost-frontend.vercel.app`
   - `CORS_ORIGINS=["https://dataghost-frontend.vercel.app"]`
4. Click **Deploy** to apply

### 2. Wait for Backend to Redeploy (2 minutes)
Monitor the **Deployments** tab for completion

### 3. Test Integration (2 minutes)
```bash
# Test that frontend can reach backend
curl https://dataghost-backend.onrender.com/api/health

# Open frontend and check console for errors
# No CORS errors should appear
```

✅ **Integration complete!**

---

## Phase 4: Final Verification (5 minutes)

### Checklist
- [ ] Backend URL responds: `https://dataghost-backend.onrender.com/api/health` → 200
- [ ] Frontend loads: `https://dataghost-frontend.vercel.app` → no 5xx errors
- [ ] Browser console has NO red errors
- [ ] Network tab shows API calls to correct backend URL
- [ ] API responses show status 200
- [ ] At least one API call returns data

### Test Each
1. **Backend Health:**
   ```bash
   curl https://dataghost-backend.onrender.com/api/health
   ```
   ✅ Returns 200 with JSON

2. **Frontend Loads:**
   - Visit `https://dataghost-frontend.vercel.app`
   - ✅ Page loads without 5xx

3. **No Console Errors:**
   - Open DevTools (F12)
   - Go to Console tab
   - ✅ No red error messages

4. **API Calls Work:**
   - Open Network tab
   - Interact with frontend
   - ✅ API requests go to `https://dataghost-backend.onrender.com/api/*`
   - ✅ Responses show status 200

---

## 🎉 Deployment Complete!

| Component | URL |
|-----------|-----|
| **Backend** | https://dataghost-backend.onrender.com |
| **Frontend** | https://dataghost-frontend.vercel.app |
| **Health Check** | https://dataghost-backend.onrender.com/api/health |

---

## Next Steps

### Immediate (Required)
1. [ ] Share URLs with team
2. [ ] Document in team wiki/Slack
3. [ ] Update any external docs/links
4. [ ] Monitor logs for errors (next 24 hours)

### Soon (Recommended)
1. [ ] Set up custom domain
2. [ ] Configure monitoring/alerts
3. [ ] Set up backups
4. [ ] Document deployment procedure
5. [ ] Review DEPLOYMENT_TASKS.md for production hardening

### Later (Optional)
1. [ ] Set up CI/CD notifications
2. [ ] Configure staging environment
3. [ ] Set up performance monitoring
4. [ ] Plan rollback procedure

---

## Troubleshooting Quick Fixes

### Backend build fails
```bash
# Ensure backend/requirements.txt has all dependencies
# Check Python 3.11 compatibility
# Review build logs in Render dashboard
```

### Frontend build fails
```bash
# Ensure Node version compatible with Next.js
# Check npm install works locally
# Review build logs in Vercel dashboard
```

### CORS errors in browser
```bash
# Verify CORS_ORIGINS in Render backend matches frontend URL exactly
# Redeploy backend to apply changes
# Check Network tab for CORS response headers
```

### API returns 404
```bash
# Verify backend implements the endpoint
# Check API prefix: /api/*
# Review backend logs in Render
```

### API returns 500
```bash
# Check Render backend logs for errors
# Verify DATABASE_URL is correct
# Verify FIREBASE_CREDENTIALS_PATH is accessible
```

### Frontend returns blank page
```bash
# Check browser console for errors
# Verify all NEXT_PUBLIC_* variables are set
# Check Vercel build logs for errors
```

---

## Still Stuck?

### Read These Files
1. **DEPLOYMENT_TASKS.md** - Detailed instructions
2. **DEPLOYMENT_CHECKLIST.md** - Verification checklist
3. **DEPLOYMENT_CONFIG_REFERENCE.md** - Configuration examples

### Debug Commands
```bash
# Test backend health
curl -v https://dataghost-backend.onrender.com/api/health

# Test CORS
curl -H "Origin: https://dataghost-frontend.vercel.app" \
     https://dataghost-backend.onrender.com/api/health -v

# Check frontend loads
curl https://dataghost-frontend.vercel.app | head -50

# View service logs (Render CLI)
render logs --service dataghost-backend --follow
```

### Support Links
- Render Support: https://render-status.com
- Vercel Support: https://vercel.com/support
- FastAPI Docs: https://fastapi.tiangolo.com
- Next.js Docs: https://nextjs.org/docs

---

## Success! 🚀

Your DataGhost application is now live in production.

**Share with your team:**
- Frontend: https://dataghost-frontend.vercel.app
- Backend API: https://dataghost-backend.onrender.com
- Health Check: https://dataghost-backend.onrender.com/api/health

**Don't forget to:**
- Monitor logs daily for first week
- Keep backups configured
- Review security settings
- Plan maintenance windows

---

## Optional: Custom Domain

If you have a custom domain:

### Render (Backend)
1. Render dashboard → Settings → Domains
2. Add custom domain
3. Update DNS records per instructions
4. Update `SERVER_PUBLIC_URL` in environment variables

### Vercel (Frontend)
1. Vercel dashboard → Settings → Domains
2. Add custom domain
3. Update DNS records per instructions
4. Update `FRONTEND_URL` in backend environment variables

---

**Deployment Time:** ~30 minutes
**Success Rate:** High ✅
**Support:** See above links or review DEPLOYMENT_TASKS.md

Enjoy your production deployment! 🎉
