# Railway Deployment Guide - FIS Situational Awareness System

**Deployment Target:** Railway.app (Tribe Internal Apps Workspace)
**Estimated Time:** 20-30 minutes
**Cost:** ~$20-30/month (Hobby plan)

---

## 🚂 Quick Deploy to Railway

### Prerequisites

- GitHub repository with this code pushed
- Railway account with access to "Tribe Internal Apps" workspace
- Slack channel ID for alerts
- Anthropic API key
- MCP server configuration (Slack + Notion tokens)

---

## Step-by-Step Deployment

### Step 1: Access Railway Dashboard

1. Go to: https://railway.app
2. Sign in with your account
3. Click workspace dropdown (top left)
4. Select **"Tribe Internal Apps"** workspace

---

### Step 2: Create New Project

1. Click **"New Project"** button
2. Select **"Deploy from GitHub repo"**
3. Choose repository: `t0mmlee/fis-situational-awareness`
4. Select branch: `main` (or `claude/review-codebase-VfA2A` if deploying this branch)
5. Click **"Deploy Now"**

Railway will automatically:
- Detect `Dockerfile` and use it for build
- Use `Procfile` for start command
- Read `railway.toml` for configuration

---

### Step 3: Add PostgreSQL Database

1. In your project dashboard, click **"+ New"**
2. Select **"Database"**
3. Choose **"PostgreSQL"**
4. Railway will create database and auto-inject `DATABASE_URL` variable

**Verify:**
- Go to **PostgreSQL service** → **Variables** tab
- You should see: `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, etc.

---

### Step 4: Add Redis Cache

1. Click **"+ New"** again
2. Select **"Database"**
3. Choose **"Redis"**
4. Railway will create Redis and auto-inject `REDIS_URL` variable

**Verify:**
- Go to **Redis service** → **Variables** tab
- You should see: `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`

---

### Step 5: Configure Environment Variables

Go to your **main application service** → **Variables** tab

Click **"+ New Variable"** and add these (one by one):

#### Required Variables

```bash
# Environment
ENVIRONMENT=production
DEBUG=false

# Database (should already be set by Railway)
# DATABASE__URL=${{Postgres.DATABASE_URL}}  # Railway auto-injects this

# Redis (should already be set by Railway)
# REDIS__URL=${{Redis.REDIS_URL}}  # Railway auto-injects this

# Temporal (CHANGE THESE)
TEMPORAL__HOST=your-namespace.tmprl.cloud:7233
TEMPORAL__NAMESPACE=fis-awareness
TEMPORAL__TASK_QUEUE=fis-ingestion
# TEMPORAL__API_KEY=your-temporal-cloud-key  # Add if using Temporal Cloud

# Alerting (REQUIRED - CHANGE THIS)
ALERT__CHANNEL_ID=C07V7ABC123
ALERT__SIGNIFICANCE_THRESHOLD=75
ALERT__DEDUP_WINDOW_HOURS=24

# AI/LLM (REQUIRED - CHANGE THIS)
AI__PROVIDER=anthropic
AI__MODEL=claude-sonnet-4-5-20250929
AI__API_KEY=sk-ant-api03-YOUR_KEY_HERE
AI__TEMPERATURE=0.0
AI__MAX_TOKENS=4000

# MCP Server
MCP__SERVER_PATH=uvx
MCP__SERVER_ARGS=["mcp-server-tribe"]

# Ingestion Settings
INGESTION__INTERVAL_DAYS=3
INGESTION__BATCH_SIZE=100
INGESTION__SLACK_SEARCH_QUERY=FIS
INGESTION__NOTION_MAIN_HUB_ID=2c04f38daa208021ae9efbab622bc6d9
INGESTION__NOTION_STAKEHOLDERS_ID=2d84f38daa20807eaa0df706cf5438de
INGESTION__NOTION_SEARCH_TAG=FIS
INGESTION__SEC_CIK=0001136893

# Monitoring
MONITORING__LOG_LEVEL=INFO
MONITORING__PROMETHEUS_PORT=9090
```

**Quick Copy-Paste Method:**

Railway also supports **"Raw Editor"** mode:
1. Click **"RAW Editor"** toggle (top right of Variables section)
2. Paste all variables at once (format: `KEY=value`, one per line)
3. Click **"Update Variables"**

---

### Step 6: Set Up Temporal Connection

You need a Temporal instance for workflow orchestration.

#### Option A: Use Temporal Cloud (Recommended)

1. Go to: https://cloud.temporal.io
2. Create namespace: `fis-awareness`
3. Get connection details:
   - Namespace address: `your-namespace.tmprl.cloud:7233`
   - API key (from Namespace settings → API Keys)

4. In Railway, set:
   ```bash
   TEMPORAL__HOST=your-namespace.tmprl.cloud:7233
   TEMPORAL__NAMESPACE=fis-awareness
   TEMPORAL__API_KEY=your-api-key
   ```

#### Option B: Self-Hosted Temporal

If you have a self-hosted Temporal server:
```bash
TEMPORAL__HOST=your-temporal-server.com:7233
TEMPORAL__NAMESPACE=default
# No API key needed
```

---

### Step 7: Configure MCP Server Access

The app needs MCP server for Slack/Notion access.

**Problem:** Railway doesn't easily support running MCP server as sidecar.

**Solution Options:**

#### Option A: Use Hosted MCP Server (Recommended)

If Tribe has a hosted MCP server:
```bash
MCP__SERVER_PATH=https://mcp.tribe.ai
MCP__SERVER_ARGS=[]
```

#### Option B: Run MCP Server Separately

Deploy MCP server as separate Railway service:

1. Create new service in Railway
2. Deploy: https://github.com/modelcontextprotocol/servers
3. Configure with Slack/Notion tokens
4. Get service URL
5. Point main app to it:
   ```bash
   MCP__SERVER_PATH=https://mcp-server-production.up.railway.app
   ```

#### Option C: Embed MCP Config (Quick but Less Secure)

Add MCP tokens directly as environment variables:
```bash
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_USER_TOKEN=xoxp-your-token
NOTION_TOKEN=secret_your-token
```

Then modify code to use these directly instead of MCP server.

---

### Step 8: Initialize Database

Once deployed, you need to create database tables.

**Method 1: Railway CLI (Recommended)**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Run database initialization
railway run python -c "
from config import config
from models import Base
from sqlalchemy import create_engine

engine = create_engine(str(config.database.url))
Base.metadata.create_all(engine)
print('✓ Database tables created')
"
```

**Method 2: Add to Dockerfile (Automatic)**

Add this to `Dockerfile` before `CMD`:
```dockerfile
# Add before CMD line
RUN python -c "from models import Base; from sqlalchemy import create_engine; from config import config; engine = create_engine(str(config.database.url)); Base.metadata.create_all(engine)" || true
```

Then redeploy.

**Method 3: Manual SQL**

1. Go to PostgreSQL service → **Data** tab
2. Click **"Connect"** and open database client
3. Run schema creation manually

---

### Step 9: Configure Health Checks

Railway automatically uses `/health` endpoint (configured in `railway.toml`).

**Verify:**
1. Go to application service → **Settings** tab
2. Scroll to **"Health Check"** section
3. Should show:
   - Path: `/health`
   - Timeout: 300s
   - Status: ✓ Passing (after deployment)

---

### Step 10: Set Up Custom Domain (Optional)

1. Go to application service → **Settings** tab
2. Scroll to **"Domains"** section
3. Click **"Generate Domain"** (gets Railway subdomain)
   - Or click **"Custom Domain"** to use your own

---

### Step 11: Deploy and Monitor

1. Go to **Deployments** tab
2. Latest deployment should be running
3. Click deployment to see logs

**Check logs for:**
```
INFO - Starting FIS Situational Awareness System
INFO - Environment: production
INFO - Starting web server on 0.0.0.0:8080
INFO - Starting Temporal worker...
INFO - Temporal worker started on task queue: fis-ingestion
INFO - All services started successfully
```

**Test health endpoint:**
```bash
curl https://your-app.railway.app/health
# Should return: {"status":"healthy","timestamp":"..."}
```

---

### Step 12: Schedule Workflows

Once deployed and running, set up schedules:

#### Via Temporal Cloud UI

1. Go to: https://cloud.temporal.io
2. Navigate to your namespace
3. Go to **"Schedules"** tab
4. Click **"Create Schedule"**

**Schedule 1: Ingestion (Every 3 Days)**
```yaml
Schedule ID: fis-ingestion-schedule
Workflow Type: ScheduledIngestionWorkflow
Task Queue: fis-ingestion
Schedule: Every 3 days
Cron: 0 0 */3 * *
```

**Schedule 2: Weekly Digest (Monday 08:00 PT)**
```yaml
Schedule ID: weekly-digest-schedule
Workflow Type: WeeklyDigestWorkflow
Task Queue: fis-ingestion
Schedule: Weekly on Monday at 08:00 PT
Cron: 0 16 * * 1
Timezone: America/Los_Angeles
```

#### Via Temporal CLI

```bash
# Install Temporal CLI
brew install temporal

# Or: curl -sSf https://temporal.download/cli.sh | sh

# Connect to your namespace
temporal env set --env prod --namespace fis-awareness --address your-namespace.tmprl.cloud:7233

# Create ingestion schedule
temporal schedule create \
  --schedule-id fis-ingestion-schedule \
  --workflow-type ScheduledIngestionWorkflow \
  --task-queue fis-ingestion \
  --interval 3d

# Create weekly digest schedule
temporal schedule create \
  --schedule-id weekly-digest-schedule \
  --workflow-type WeeklyDigestWorkflow \
  --task-queue fis-ingestion \
  --cron "0 16 * * 1" \
  --timezone America/Los_Angeles
```

---

## 🔍 Verification Checklist

After deployment, verify everything works:

### 1. Application Health
```bash
curl https://your-app.railway.app/health
# Expected: {"status":"healthy",...}

curl https://your-app.railway.app/ready
# Expected: {"status":"ready",...}
```

### 2. Temporal Connection
- Check Railway logs for: `"Temporal worker started on task queue: fis-ingestion"`
- Go to Temporal UI → Workers → Should see worker online

### 3. Database Connection
```bash
# Via Railway CLI
railway run python -c "
from config import config
from sqlalchemy import create_engine, text

engine = create_engine(str(config.database.url))
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM ingestion_runs'))
    print(f'✓ Database connected. Ingestion runs: {result.scalar()}')
"
```

### 4. Trigger Test Workflow
```bash
# Via Temporal CLI
temporal workflow start \
  --type IngestionWorkflow \
  --task-queue fis-ingestion \
  --workflow-id manual-test-$(date +%s)

# Watch execution
temporal workflow show --workflow-id manual-test-<timestamp>
```

### 5. Check Slack Integration
- Trigger workflow that would create CRITICAL change
- Verify alert appears in Slack channel

---

## 📊 Monitoring in Railway

### View Logs
1. Go to application service
2. Click **"Deployments"** tab
3. Click latest deployment
4. Logs stream in real-time

### View Metrics
1. Go to application service
2. Click **"Metrics"** tab
3. See CPU, Memory, Network usage

### Set Up Alerts
1. Go to **"Observability"** tab
2. Click **"Create Alert"**
3. Configure for:
   - High error rate
   - High memory usage
   - Deployment failures

---

## 🔧 Troubleshooting

### Issue: Deployment Fails

**Check:**
1. Build logs in Railway dashboard
2. Look for missing dependencies or build errors

**Common fixes:**
- Ensure `Dockerfile` is in root directory
- Check `requirements.txt` has all dependencies
- Verify Python version in Dockerfile matches requirements

### Issue: Worker Not Connecting to Temporal

**Check logs for:**
```
ERROR - Failed to connect to Temporal
```

**Fix:**
1. Verify `TEMPORAL__HOST` is correct
2. Check `TEMPORAL__API_KEY` if using Temporal Cloud
3. Ensure Temporal namespace exists
4. Test connection manually:
   ```bash
   railway run python -c "
   from temporalio.client import Client
   import asyncio

   async def test():
       client = await Client.connect('your-namespace.tmprl.cloud:7233')
       print('✓ Connected to Temporal')

   asyncio.run(test())
   "
   ```

### Issue: Database Connection Fails

**Check:**
1. `DATABASE__URL` variable is set
2. PostgreSQL service is running
3. Database tables are created

**Fix:**
```bash
# Check database URL
railway variables get DATABASE__URL

# Verify connection
railway run python -c "
from sqlalchemy import create_engine
engine = create_engine('$DATABASE_URL')
with engine.connect() as conn:
    print('✓ Database connected')
"
```

### Issue: MCP Server Not Accessible

**Symptoms:**
- Slack/Notion ingestion fails
- Logs show MCP connection errors

**Fix:**
- If using `uvx mcp-server-tribe`, it won't work in Railway (no npm)
- Switch to hosted MCP server or deploy separately
- Or: Modify code to use Slack/Notion APIs directly (not ideal)

### Issue: Out of Memory

**Symptoms:**
- Railway shows high memory usage
- App restarts frequently

**Fix:**
1. Upgrade Railway plan (Hobby → Pro)
2. Or optimize memory:
   ```bash
   # In Railway variables
   DATABASE__POOL_SIZE=5  # Reduce from 10
   DATABASE__MAX_OVERFLOW=10  # Reduce from 20
   ```

---

## 💰 Cost Estimation

### Railway Pricing

**Hobby Plan** (~$5/month base + usage):
- Application: ~$5/month
- PostgreSQL: ~$5/month
- Redis: ~$5/month
- **Total: ~$15-20/month**

**Pro Plan** (~$20/month base + usage):
- Better performance
- More resources
- **Total: ~$30-40/month**

### Temporal Cloud Pricing

- Free tier: 200 actions/month
- Standard: ~$200/month
- **Recommendation:** Use free tier for testing, upgrade if needed

### Anthropic API

- Claude Sonnet: $3 per million input tokens
- Estimated: ~$5-10/month for entity extraction

**Total Monthly Cost: ~$20-30/month** (Hobby) or **~$40-50/month** (Pro)

---

## 🚀 Post-Deployment

### 1. Test End-to-End Flow

```bash
# Trigger ingestion
temporal workflow start --type IngestionWorkflow --task-queue fis-ingestion

# Check database for results
railway run python -c "
from config import config
from sqlalchemy import create_engine, text
engine = create_engine(str(config.database.url))
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM entity_snapshots'))
    print(f'Entities ingested: {result.scalar()}')
"

# Trigger digest
temporal workflow start --type WeeklyDigestWorkflow --task-queue fis-ingestion

# Check Slack for digest message
```

### 2. Configure Monitoring

Set up Slack notifications for Railway deployments:
1. Railway dashboard → Project settings
2. Integrations → Slack
3. Connect to #fis-alerts channel

### 3. Document for Team

Share with team:
- Railway project URL
- Temporal namespace URL
- Slack alert channel
- How to trigger manual workflows
- How to view logs

---

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app/)
- [Temporal Cloud Documentation](https://docs.temporal.io/cloud/)
- [Application Documentation](README.md)
- [Setup Guide](GETTING_STARTED.md)
- [Roadmap](ROADMAP.md)

---

## 🆘 Support

**For Railway issues:**
- Railway Discord: https://discord.gg/railway
- Railway GitHub: https://github.com/railwayapp/nixpacks

**For Application issues:**
- Check logs in Railway dashboard
- Review [GETTING_STARTED.md](GETTING_STARTED.md) troubleshooting
- Check Temporal UI for workflow errors

---

**Last Updated:** February 5, 2026
**Deployment Status:** Ready for Railway ✅
