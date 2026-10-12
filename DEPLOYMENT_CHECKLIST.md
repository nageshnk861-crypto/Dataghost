# DataGhost Deployment Checklist

Quick reference checklist for deploying DataGhost to production. Detailed instructions are in `DEPLOYMENT_TASKS.md`.

---

## Pre-Deployment Setup

- [ ] GitHub repository up to date
- [ ] All code committed and pushed to main branch
- [ ] Backend `requirements.txt` updated with dependencies
- [ ] Frontend `package.json` and `package-lock.json` up to date
- [ ] Environment variables documented in `.env.example` files
- [ ] No secrets hardcoded in source code
- [ ] Tests passing locally
- [ ] Build successful locally (`npm run build` for frontend, `pip install -r requirements.txt` for backend)

---

## Task 1: Deploy Backend to Render

### GitHub Connection
- [ ] Render account created
- [ ] GitHub authorized with Render
- [ ] DataGhost repository connected

### Web Service Configuration
- [ ] Service name set to `dataghost-backend`
- [ ] Python 3.11 selected
- [ ] Build command: `pip install -r backend/requirements.txt`
- [ ] Start command configured (gunicorn or uvicorn)
- [ ] Instance type selected
- [ ] Region selected

### Environment Variables Set
- [ ] `DATABASE_URL` configured
- [ ] `SECRET_KEY` set (generated securely)
- [ ] `ALGORITHM=HS256`
- [ ] `ACCESS_TOKEN_EXPIRE_MINUTES=1440`
- [ ] `ENVIRONMENT=production`
- [ ] `SERVER_PUBLIC_URL` set to Render service URL
- [ ] `FRONTEND_URL` set to Vercel frontend URL (will update in Step 2.7)
- [ ] `CORS_ORIGINS` configured as JSON array
- [ ] `FIREBASE_CREDENTIALS_PATH` set
- [ ] `FIREBASE_PROJECT_ID` set

### Deployment
- [ ] Service deployed successfully
- [ ] Backend URL obtained: `https://dataghost-backend.onrender.com`
- [ ] No deployment errors in logs

### Verification
- [ ] Health endpoint returns 200: `curl https://dataghost-backend.onrender.com/api/health`
- [ ] CORS headers present in response
- [ ] Render logs show successful startup
- [ ] No error messages in logs

---

## Task 2: Configure Vercel Frontend

### GitHub Connection
- [ ] Vercel account created
- [ ] GitHub authorized with Vercel
- [ ] DataGhost repository connected to Vercel

### Project Configuration
- [ ] Project name set to `dataghost-frontend`
- [ ] Framework preset: Next.js
- [ ] Root directory: `frontend`
- [ ] Build command configured
- [ ] Output directory: `.next`

### Environment Variables - Production
- [ ] `BACKEND_URL=https://dataghost-backend.onrender.com`
- [ ] `BACKEND_INTERNAL_URL=https://dataghost-backend.onrender.com`
- [ ] `NEXT_PUBLIC_API_URL=https://dataghost-backend.onrender.com`
- [ ] `NEXT_PUBLIC_FIREBASE_API_KEY` set
- [ ] `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` set
- [ ] `NEXT_PUBLIC_FIREBASE_PROJECT_ID` set
- [ ] `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` set
- [ ] `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` set
- [ ] `NEXT_PUBLIC_FIREBASE_APP_ID` set
- [ ] `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID` set

### Environment Variables - Preview (Optional)
- [ ] Preview env vars set (same as production)

### Vercel Settings
- [ ] Production branch: `main`
- [ ] Preview branches configured (optional)
- [ ] Custom domain added (if applicable)

### Deployment
- [ ] Frontend deployed successfully
- [ ] Frontend URL obtained: `https://dataghost-frontend.vercel.app`
- [ ] No deployment errors in build logs

### Verification
- [ ] Frontend loads at Vercel URL
- [ ] Build completed successfully
- [ ] Environment variables loaded correctly

### Backend Update (From Step 2.7)
- [ ] Backend `FRONTEND_URL` updated to Vercel URL
- [ ] Backend `CORS_ORIGINS` updated to include Vercel URL
- [ ] Backend redeployed on Render

---

## Task 3: Frontend-Backend Integration Testing

### Health Check
- [ ] Backend health endpoint responds: `https://dataghost-backend.onrender.com/api/health`
- [ ] Status: 200
- [ ] Response includes: `{"status": "healthy", ...}`

### Frontend Loading
- [ ] Frontend page loads: `https://dataghost-frontend.vercel.app`
- [ ] Page displays content (not 5xx error)
- [ ] No 404 errors

### Browser Console
- [ ] Open DevTools (F12)
- [ ] Console tab has no red errors
- [ ] No CORS error messages
- [ ] No undefined environment variable warnings
- [ ] Firebase config loaded correctly

### Network Tab Testing
- [ ] Open Network tab in DevTools
- [ ] Filter by `api`
- [ ] Trigger an API call from frontend
- [ ] Verify request URL: `https://dataghost-backend.onrender.com/api/*`
- [ ] Verify response status: 200
- [ ] Verify response is valid JSON

### Specific Endpoint Tests
- [ ] Test `/api/health` endpoint
- [ ] Test `/api/devices` endpoint (or other main endpoint)
- [ ] Test frontend page that uses that endpoint
- [ ] Verify data displays correctly

### CORS Verification
- [ ] No CORS errors in console
- [ ] Response has correct `Access-Control-Allow-Origin` header
- [ ] CORS headers include frontend URL

### Multiple Pages
- [ ] Test at least 3 different frontend pages
- [ ] Each page loads without errors
- [ ] API calls succeed
- [ ] Data displays correctly

---

## Task 4: Production Considerations

### Code Security Audit
- [ ] Search for hardcoded secrets: `grep -r "SECRET_KEY\|API_KEY\|PASSWORD" --include="*.py" --include="*.js"`
- [ ] No Firebase credentials in code
- [ ] No database passwords in code
- [ ] All `.env*` files in `.gitignore`
- [ ] Example files use placeholder values only
- [ ] Git history checked for exposed secrets (if concerned)

### CORS Configuration
- [ ] Backend `CORS_ORIGINS` is JSON array (not string)
- [ ] Production domain included
- [ ] Wildcard `*` NOT used
- [ ] www variant included (if applicable)
- [ ] Custom domain included (if applicable)

### Backend Logging
- [ ] Logging configured in code
- [ ] Render logs accessible: Render dashboard → Logs tab
- [ ] Recent log entries visible
- [ ] No continuous error patterns
- [ ] Structured logging format set up (optional but recommended)

### Frontend Error Monitoring
- [ ] Vercel Monitoring tab shows data
- [ ] Error tracking active
- [ ] Web vitals tracked
- [ ] Build failure notifications enabled

### Database Backups (if PostgreSQL used)
- [ ] Automated backups enabled
- [ ] Backup frequency: Daily
- [ ] Retention period: 7-14 days
- [ ] Backup storage location verified
- [ ] Restore procedure tested (optional)

### Monitoring & Alerts
- [ ] Render service-down alerts configured
- [ ] Render CPU/memory alerts configured
- [ ] Vercel build failure notifications enabled
- [ ] Alert notification method tested (email/webhook)

### Documentation
- [ ] `PRODUCTION_SETUP.md` created with:
  - [ ] Service names and URLs
  - [ ] Environment variables list
  - [ ] Monitoring setup details
  - [ ] Backup procedures
  - [ ] Update/deployment procedure
  - [ ] Rollback procedure
  - [ ] Team contact information

### Final Security Checklist
- [ ] No secrets in code
- [ ] CORS properly restricted
- [ ] HTTPS enforced on all endpoints
- [ ] Authentication enabled (if applicable)
- [ ] Passwords not logged
- [ ] API rate limiting considered
- [ ] Input validation implemented
- [ ] SQL injection protection via parameterized queries
- [ ] Team notified of production deployment

---

## Post-Deployment

### Immediate (First Hour)
- [ ] Monitor backend logs for errors
- [ ] Monitor frontend logs for errors
- [ ] Test all critical user flows
- [ ] Verify database connectivity
- [ ] Check API response times

### First Day
- [ ] Collect user feedback on performance
- [ ] Review deployment alerts
- [ ] Verify backups running successfully
- [ ] Document any issues encountered
- [ ] Update team on deployment status

### First Week
- [ ] Monitor error rates and patterns
- [ ] Verify backups can be restored (test restore)
- [ ] Check resource usage trends
- [ ] Plan for optimization if needed
- [ ] Schedule follow-up maintenance window

---

## Deployment Dates & Notes

| Component | Deployed Date | URL | Notes |
|-----------|---------------|----|-------|
| Backend | | | |
| Frontend | | | |
| Database | | | |
| Custom Domain | | | |

---

## Deployment Contacts

| Role | Name | Email | Phone |
|------|------|-------|-------|
| Backend Owner | | | |
| Frontend Owner | | | |
| DevOps/Infrastructure | | | |
| On-Call Support | | | |

---

## Rollback Procedure (Emergency Only)

If production breaks:

1. **Identify Issue:**
   - [ ] Check Render backend logs
   - [ ] Check Vercel frontend logs
   - [ ] Check recent deployments
   - [ ] Identify which service has issue

2. **Rollback Backend (if needed):**
   - [ ] Render → dataghost-backend → Deployments
   - [ ] Find last known-good deployment
   - [ ] Click deploy button to revert
   - [ ] Monitor logs for successful rollback
   - [ ] Verify health endpoint works

3. **Rollback Frontend (if needed):**
   - [ ] Vercel → dataghost-frontend → Deployments
   - [ ] Find last known-good deployment
   - [ ] Click "Redeploy" button
   - [ ] Monitor logs for successful rollback
   - [ ] Verify frontend loads

4. **Post-Rollback:**
   - [ ] Document what went wrong
   - [ ] Fix issue in code on development branch
   - [ ] Test fix thoroughly locally
   - [ ] Deploy fix again with monitoring
   - [ ] Team communications about incident

---

## Success Criteria

All items checked ✓ = **Deployment Complete**

- Frontend and backend deployed to production
- All services responding with 200 status codes
- API communication working without errors
- Zero CORS errors in production
- Monitoring and alerts configured
- Backups configured and tested
- Team notified and documentation updated
- No secrets in source code
- Security and production requirements met
