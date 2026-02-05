# Railway Quick Start - FIS Situational Awareness

**Time to Deploy:** 15 minutes
**Platform:** https://railway.app (Tribe Internal Apps workspace)

---

## 🚀 Deploy in 5 Steps

### 1️⃣ Create Project (2 min)

1. Go to: https://railway.app
2. Select workspace: **"Tribe Internal Apps"**
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Choose: `t0mmlee/fis-situational-awareness`
5. Branch: `main` or `claude/review-codebase-VfA2A`
6. Click **"Deploy Now"**

---

### 2️⃣ Add Databases (2 min)

**PostgreSQL:**
1. Click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway auto-injects `DATABASE_URL` ✅

**Redis:**
1. Click **"+ New"** → **"Database"** → **"Redis"**
2. Railway auto-injects `REDIS_URL` ✅

---

### 3️⃣ Set Environment Variables (5 min)

Go to main app service → **Variables** tab → **"RAW Editor"**

Paste this (replace values marked with `CHANGE_ME`):

```env
# Environment
ENVIRONMENT=production

# Temporal (CHANGE THESE)
TEMPORAL__HOST=your-namespace.tmprl.cloud:7233
TEMPORAL__NAMESPACE=fis-awareness
TEMPORAL__TASK_QUEUE=fis-ingestion
TEMPORAL__API_KEY=CHANGE_ME

# Alerting (CHANGE THIS)
ALERT__CHANNEL_ID=CHANGE_ME
ALERT__SIGNIFICANCE_THRESHOLD=75

# AI (CHANGE THIS)
AI__PROVIDER=anthropic
AI__MODEL=claude-sonnet-4-5-20250929
AI__API_KEY=CHANGE_ME

# MCP Server
MCP__SERVER_PATH=uvx
MCP__SERVER_ARGS=["mcp-server-tribe"]

# FIS Configuration (Keep these)
INGESTION__INTERVAL_DAYS=3
INGESTION__SLACK_SEARCH_QUERY=FIS
INGESTION__NOTION_MAIN_HUB_ID=2c04f38daa208021ae9efbab622bc6d9
INGESTION__NOTION_STAKEHOLDERS_ID=2d84f38daa20807eaa0df706cf5438de
INGESTION__NOTION_SEARCH_TAG=FIS
INGESTION__SEC_CIK=0001136893

# Monitoring
MONITORING__LOG_LEVEL=INFO
```

Click **"Update Variables"**

---

### 4️⃣ Initialize Database (3 min)

**Option A: Via Railway CLI** (Recommended)

```bash
# Install CLI
npm install -g @railway/cli

# Login and link
railway login
railway link

# Create tables
railway run python << 'EOF'
from config import config
from models import Base
from sqlalchemy import create_engine

engine = create_engine(str(config.database.url))
Base.metadata.create_all(engine)
print("✓ Database initialized")
EOF
```

**Option B: Via Deployment** (If CLI not available)

Add to `Dockerfile` before the `CMD` line:

```dockerfile
RUN python -c "from models import Base; from sqlalchemy import create_engine; from config import config; engine = create_engine(str(config.database.url)); Base.metadata.create_all(engine)" || echo "DB init skipped"
```

Then trigger redeploy in Railway.

---

### 5️⃣ Verify Deployment (3 min)

**Check Health:**
```bash
curl https://your-app.railway.app/health
# Should return: {"status":"healthy"}
```

**Check Logs:**
1. Go to Railway → Deployments → Latest deployment
2. Look for:
   ```
   ✓ Starting web server on 0.0.0.0:8080
   ✓ Temporal worker started
   ```

**Test Workflow:**
```bash
temporal workflow start \
  --type IngestionWorkflow \
  --task-queue fis-ingestion \
  --workflow-id test-$(date +%s)
```

---

## 🎯 Required Credentials

Before deploying, get these ready:

| Credential | Where to Get | Variable Name |
|------------|--------------|---------------|
| Temporal Host | https://cloud.temporal.io | `TEMPORAL__HOST` |
| Temporal API Key | Temporal → Namespace → API Keys | `TEMPORAL__API_KEY` |
| Slack Channel ID | Slack → Channel → View details | `ALERT__CHANNEL_ID` |
| Anthropic API Key | https://console.anthropic.com | `AI__API_KEY` |

---

## ⚠️ Known Issues & Fixes

### Issue: MCP Server Won't Start in Railway

**Problem:** `uvx mcp-server-tribe` requires npm, not available in container

**Solution:** Use hosted MCP server or modify to use Slack/Notion APIs directly

**Quick Fix:** Comment out MCP-dependent code temporarily:
```python
# In agents/slack_agent.py, use direct Slack API instead of MCP
```

### Issue: Temporal Worker Not Connecting

**Fix:** Double-check these variables:
```bash
railway variables get TEMPORAL__HOST
railway variables get TEMPORAL__API_KEY
railway variables get TEMPORAL__NAMESPACE
```

Ensure format is: `your-namespace.tmprl.cloud:7233` (not `https://`)

### Issue: Database Not Initialized

**Symptoms:** Logs show `table does not exist` errors

**Fix:** Run database initialization (Step 4 above)

---

## 📊 Post-Deployment Setup

### Schedule Workflows in Temporal

**Via Temporal UI:**
1. Go to: https://cloud.temporal.io
2. Navigate to namespace: `fis-awareness`
3. Schedules tab → Create Schedule

**Ingestion Schedule:**
- ID: `fis-ingestion-schedule`
- Workflow: `ScheduledIngestionWorkflow`
- Cron: `0 0 */3 * *` (every 3 days)

**Digest Schedule:**
- ID: `weekly-digest-schedule`
- Workflow: `WeeklyDigestWorkflow`
- Cron: `0 16 * * 1` (Monday 08:00 PT = 16:00 UTC)

---

## 🔗 Important Links

After deployment, save these:

- **Railway Dashboard:** https://railway.app/project/[your-project-id]
- **Application URL:** https://[your-app].railway.app
- **Temporal UI:** https://cloud.temporal.io/namespaces/fis-awareness
- **Health Check:** https://[your-app].railway.app/health
- **Metrics:** https://[your-app].railway.app/metrics

---

## 📱 Monitor via Slack

Set up Railway → Slack integration:
1. Railway project → Settings → Integrations
2. Connect Slack
3. Choose channel: `#fis-alerts`
4. Get notified on deployments, errors, etc.

---

## 🆘 Quick Help

**View Logs:**
```bash
railway logs --tail
```

**Check Status:**
```bash
railway status
```

**Restart Service:**
```bash
railway restart
```

**Open Dashboard:**
```bash
railway open
```

**Run Command:**
```bash
railway run [command]
```

---

## 📚 Full Documentation

- **Complete Guide:** [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)
- **Setup Guide:** [GETTING_STARTED.md](GETTING_STARTED.md)
- **System Overview:** [README.md](README.md)

---

**Deployment Ready:** ✅
**Estimated Cost:** ~$20-30/month
**Time Investment:** 15 minutes setup + 5 minutes scheduling
