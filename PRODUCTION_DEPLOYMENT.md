# Production Deployment Guide

## 🚀 Deploy Study Sharper to Production

This guide walks you through deploying your backend and frontend to production.

---

## Prerequisites

- ✅ All Phases 1-6 complete
- ✅ GitHub repository set up
- ✅ Supabase project created
- ✅ OpenRouter API key
- ✅ Code tested locally

---

## Part 1: Backend Deployment (Render)

### Step 1: Prepare Backend

1. **Update requirements.txt** (if needed):
```bash
cd Study_Sharper_Backend
pip freeze > requirements.txt
```

2. **Commit and push to GitHub**:
```bash
git add .
git commit -m "Prepare for production deployment"
git push origin main
```

### Step 2: Deploy to Render

1. **Go to [Render.com](https://render.com)** and sign in
2. **Click "New +" → "Web Service"**
3. **Connect your GitHub repository**
4. **Configure the service:**

**Basic Settings:**
- Name: `studysharper-backend`
- Region: Choose closest to your users
- Branch: `main`
- Root Directory: `Study_Sharper_Backend`
- Runtime: `Python 3`

**Build & Deploy:**
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Instance Type:**
- Free tier for testing
- Starter ($7/month) for production

### Step 3: Add Environment Variables

In Render dashboard, add these environment variables:

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# OpenRouter
OPENROUTER_API_KEY=your-openrouter-key

# CORS (update with your frontend URL)
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-app-git-main.vercel.app

# Admin
ADMIN_TOKEN=your-secure-admin-token

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_PER_HOUR=100

# Environment
ENVIRONMENT=production
```

### Step 4: Deploy

1. Click **"Create Web Service"**
2. Wait for deployment (3-5 minutes)
3. Note your backend URL: `https://studysharper-backend.onrender.com`

### Step 5: Verify Backend

Test the health endpoint:
```bash
curl https://studysharper-backend.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "studysharper_backend",
  "version": "1.0.0",
  "environment": "production",
  "components": {
    "database": "healthy",
    "monitoring": "healthy",
    "rate_limiting": "enabled",
    "sse_streaming": "enabled"
  }
}
```

---

## Part 2: Frontend Deployment (Vercel)

### Step 1: Prepare Frontend

1. **Update environment variables**:

Create `Study_Sharper_Frontend/.env.production`:
```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
NEXT_PUBLIC_BACKEND_URL=https://studysharper-backend.onrender.com
```

2. **Commit and push**:
```bash
cd Study_Sharper_Frontend
git add .
git commit -m "Configure for production"
git push origin main
```

### Step 2: Deploy to Vercel

1. **Go to [Vercel.com](https://vercel.com)** and sign in
2. **Click "Add New..." → "Project"**
3. **Import your GitHub repository**
4. **Configure the project:**

**Framework Preset:** Next.js
**Root Directory:** `Study_Sharper_Frontend`
**Build Command:** `npm run build`
**Output Directory:** `.next`

### Step 3: Add Environment Variables

In Vercel dashboard, add:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
NEXT_PUBLIC_BACKEND_URL=https://studysharper-backend.onrender.com
```

### Step 4: Deploy

1. Click **"Deploy"**
2. Wait for build (2-3 minutes)
3. Note your frontend URL: `https://your-app.vercel.app`

### Step 5: Update Backend CORS

Go back to Render and update `ALLOWED_ORIGINS`:
```bash
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-app-git-main-yourname.vercel.app
```

Redeploy backend for changes to take effect.

---

## Part 3: Database Setup

### Apply Migrations to Production

1. **Go to Supabase Dashboard**
2. **SQL Editor**
3. **Run each migration file** from `Study_Sharper_Frontend/migrations/`:
   - `001_pgvector_setup.sql`
   - `002_embedding_triggers.sql`
   - `003_add_notes_columns.sql`
   - ... (all migration files)
   - `010_monitoring_tables.sql` (Phase 6)

### Verify Tables

Run in SQL Editor:
```sql
-- Check all tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;
```

Should see:
- `agent_executions`
- `flashcards`
- `flashcard_sets`
- `notes`
- `folders`
- etc.

---

## Part 4: Post-Deployment Testing

### Test Backend Endpoints

```bash
# Health check
curl https://studysharper-backend.onrender.com/health

# Test AI endpoint (should get rate limited after 10)
curl -X POST https://studysharper-backend.onrender.com/api/ai/process-stream \
  -H "Content-Type: application/json" \
  -d '{
    "type": "flashcard_generation",
    "user_id": "test-user",
    "message": "Create flashcards about biology",
    "options": {"count": 3, "difficulty": "easy", "content": "Biology test"}
  }'
```

### Test Frontend

1. Visit your Vercel URL
2. Sign up / Log in
3. Create a note
4. Generate flashcards
5. Verify real-time streaming works

### Test Monitoring

```powershell
# Check metrics (replace with your admin token and backend URL)
$adminToken = "your-admin-token"
$backendUrl = "https://studysharper-backend.onrender.com"

Invoke-WebRequest -Uri "$backendUrl/api/admin/metrics?hours=1&admin_token=$adminToken" | Select-Object -Expand Content
```

---

## Part 5: Monitoring Setup

### Set Up Alerts

**Render:**
1. Go to your service dashboard
2. Enable "Deploy Notifications"
3. Add webhook for Slack/Discord (optional)

**Supabase:**
1. Database → Settings → Monitoring
2. Set up alerts for:
   - High CPU usage
   - Storage limits
   - Connection limits

### Daily Monitoring Routine

Check these daily:
```bash
# 1. Health check
curl https://studysharper-backend.onrender.com/health

# 2. System metrics
curl "https://studysharper-backend.onrender.com/api/admin/metrics?hours=24&admin_token=YOUR_TOKEN"

# 3. Recent errors
curl "https://studysharper-backend.onrender.com/api/admin/errors?limit=10&admin_token=YOUR_TOKEN"
```

---

## Part 6: Cost Optimization

### Expected Monthly Costs

**Infrastructure:**
- Render (Starter): $7/month
- Vercel (Hobby): $0/month
- Supabase (Free): $0/month (upgrade at ~50k rows)

**AI Services (1000 active users):**
- OpenRouter (Haiku): ~$100-300/month
- OpenRouter (Sonnet): ~$50-150/month
- Total: ~$157-457/month

**Per User Cost:** $0.16-$0.46/month

### Reduce Costs

1. **Use Haiku more**: Default to cheaper model
2. **Cache responses**: Store common queries
3. **Optimize prompts**: Shorter = cheaper
4. **Batch requests**: Process multiple together
5. **Set token limits**: Cap max tokens per request

---

## Part 7: Scaling Strategy

### When to Scale

Scale when you see:
- Response times >5 seconds consistently
- Error rate >5%
- Database connections maxed out
- Memory/CPU consistently >80%

### Scaling Options

**Backend (Render):**
- Upgrade to Standard ($25/month) - 2GB RAM
- Upgrade to Pro ($85/month) - 4GB RAM
- Add horizontal scaling (multiple instances)

**Database (Supabase):**
- Upgrade to Pro ($25/month) - Better performance
- Add read replicas for scaling reads
- Optimize indexes for slow queries

**Frontend (Vercel):**
- Pro plan ($20/month) - Better performance
- Edge functions for faster responses
- Image optimization

---

## Part 8: Troubleshooting

### Backend Not Starting

**Check:**
1. Render logs for errors
2. Environment variables set correctly
3. Database connection working
4. Python version compatible

**Fix:**
```bash
# Check logs in Render dashboard
# Verify all env vars present
# Test database connection in Supabase
```

### Frontend Build Failing

**Check:**
1. Vercel build logs
2. Environment variables set
3. Dependencies installed correctly
4. TypeScript errors

**Fix:**
```bash
# Run build locally first
cd Study_Sharper_Frontend
npm run build

# Fix any errors before deploying
```

### CORS Errors

**Check:**
1. `ALLOWED_ORIGINS` includes frontend URL
2. Both production and preview URLs included
3. No trailing slashes in URLs

**Fix:**
```bash
# Update in Render
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-app-git-main.vercel.app
```

### Rate Limiting Too Strict

**Adjust in Render:**
```bash
RATE_LIMIT_PER_MINUTE=20  # Increase from 10
RATE_LIMIT_PER_HOUR=200   # Increase from 100
```

### High Costs

**Check:**
1. Token usage per request
2. Which models being used
3. Unnecessary retries
4. Caching effectiveness

**Optimize:**
- Use Haiku for more tasks
- Add response caching
- Reduce prompt sizes
- Optimize validation thresholds

---

## Part 9: Security Checklist

### Pre-Launch Security

- [ ] All secrets in environment variables (not code)
- [ ] Admin token is strong and secret
- [ ] CORS restricted to your domains only
- [ ] Rate limiting enabled
- [ ] Database RLS policies enabled
- [ ] API keys rotated from development
- [ ] HTTPS enforced (automatic on Render/Vercel)
- [ ] Input validation on all endpoints
- [ ] SQL injection protection (using Supabase client)
- [ ] XSS protection (React default)

### Post-Launch Security

- [ ] Monitor for unusual activity
- [ ] Review access logs weekly
- [ ] Rotate API keys quarterly
- [ ] Update dependencies monthly
- [ ] Backup database regularly
- [ ] Test disaster recovery

---

## Part 10: Rollback Plan

### If Something Goes Wrong

**Backend Rollback:**
1. Go to Render dashboard
2. "Manual Deploy" → Select previous commit
3. Click "Deploy"

**Frontend Rollback:**
1. Go to Vercel dashboard
2. Deployments → Find previous working deployment
3. Click "..." → "Promote to Production"

**Database Rollback:**
1. Supabase → Database → Backups
2. Restore from backup (Pro plan only)
3. Or manually revert migrations

---

## Part 11: Launch Checklist

### Pre-Launch
- [ ] All tests passing locally
- [ ] Database migrations applied
- [ ] Environment variables configured
- [ ] Backend deployed and healthy
- [ ] Frontend deployed and working
- [ ] CORS configured correctly
- [ ] Rate limiting tested
- [ ] Monitoring endpoints working
- [ ] Admin access verified
- [ ] Error tracking set up

### Launch Day
- [ ] Final smoke test all features
- [ ] Monitor logs closely
- [ ] Check error rates
- [ ] Verify performance metrics
- [ ] Test with real users
- [ ] Have rollback plan ready

### Post-Launch (First Week)
- [ ] Daily health checks
- [ ] Monitor costs
- [ ] Review error logs
- [ ] Check user feedback
- [ ] Optimize based on metrics
- [ ] Document any issues

---

## 🎉 You're Live!

Your Study Sharper platform is now in production with:

✅ **Scalable backend** on Render
✅ **Fast frontend** on Vercel  
✅ **Robust database** on Supabase
✅ **AI-powered features** via OpenRouter
✅ **Full monitoring** and observability
✅ **Rate limiting** for protection
✅ **Production-ready** architecture

---

## 📞 Support Resources

**Render:**
- Docs: https://render.com/docs
- Status: https://status.render.com
- Support: support@render.com

**Vercel:**
- Docs: https://vercel.com/docs
- Status: https://vercel-status.com
- Support: support@vercel.com

**Supabase:**
- Docs: https://supabase.com/docs
- Status: https://status.supabase.com
- Support: support@supabase.io

**OpenRouter:**
- Docs: https://openrouter.ai/docs
- Status: Check dashboard
- Support: support@openrouter.ai

---

## 📊 Success Metrics

Track these KPIs:

**Technical:**
- Uptime: >99.5%
- Response time: <2s average
- Error rate: <1%
- Success rate: >95%

**Business:**
- Active users
- Content generated
- User retention
- Feature adoption

**Cost:**
- Cost per user
- Token usage trends
- Infrastructure costs
- ROI on AI features

---

**Congratulations on your production deployment!** 🚀🎉

Your students now have access to a world-class AI-powered learning platform!
