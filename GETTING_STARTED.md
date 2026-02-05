# Getting Started - Complete Setup Guide

This guide walks through **everything** needed to get the FIS Situational Awareness System running from scratch.

---

## 🚨 Current Status

**System Status:** ❌ NOT OPERATIONAL

**Blocking Issues:**
- Dependencies not installed
- No environment configuration
- Infrastructure not running (PostgreSQL, Redis, Temporal, MCP)
- Database not initialized
- Weak entity extraction (regex instead of AI)

---

## ✅ Step-by-Step Setup

### **Phase 1: Install Dependencies** (5 minutes)

#### 1.1 Install Python Dependencies

```bash
cd /home/user/fis-situational-awareness

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed fastapi-0.109.0 sqlalchemy-2.0.25 temporalio-1.5.0 ...
```

**Verify installation:**
```bash
python -c "import sqlalchemy, fastapi, temporalio, mcp; print('✓ All imports successful')"
```

---

### **Phase 2: Configure Environment** (10 minutes)

#### 2.1 Create Environment File

Create `.env` file in project root:

```bash
cat > .env << 'EOF'
# Environment
ENVIRONMENT=development
DEBUG=false

# Database (PostgreSQL)
DATABASE__URL=postgresql://fis_user:fis_pass@localhost:5432/fis_awareness
DATABASE__POOL_SIZE=10
DATABASE__MAX_OVERFLOW=20
DATABASE__ECHO=false

# Redis Cache
REDIS__URL=redis://localhost:6379/0
REDIS__TTL_SECONDS=3600

# Temporal Workflow Engine
TEMPORAL__HOST=localhost:7233
TEMPORAL__NAMESPACE=default
TEMPORAL__TASK_QUEUE=fis-ingestion
# TEMPORAL__API_KEY=  # Only needed for Temporal Cloud

# Tribe MCP Server
MCP__SERVER_PATH=uvx
MCP__SERVER_ARGS=["mcp-server-tribe"]

# Ingestion Settings
INGESTION__INTERVAL_DAYS=3
INGESTION__BATCH_SIZE=100
INGESTION__MAX_RETRIES=3

# Slack Configuration
INGESTION__SLACK_SEARCH_QUERY=FIS
INGESTION__SLACK_CHANNELS=[]

# Notion Configuration
INGESTION__NOTION_MAIN_HUB_ID=2c04f38daa208021ae9efbab622bc6d9
INGESTION__NOTION_STAKEHOLDERS_ID=2d84f38daa20807eaa0df706cf5438de
INGESTION__NOTION_SEARCH_TAG=FIS

# External Sources
INGESTION__SEC_CIK=0001136893
INGESTION__NEWS_SOURCES=["bloomberg.com","reuters.com","wsj.com","ft.com"]

# Alerting
ALERT__CHANNEL_ID=C07V7EXAMPLE123  # CHANGE THIS to your Slack channel
ALERT__SIGNIFICANCE_THRESHOLD=75
ALERT__DEDUP_WINDOW_HOURS=24
ALERT__MAX_ALERTS_PER_DAY=20

# AI/LLM (for entity extraction)
AI__PROVIDER=anthropic
AI__MODEL=claude-sonnet-4-5-20250929
AI__API_KEY=sk-ant-CHANGE_THIS  # CHANGE THIS to your Anthropic API key
AI__TEMPERATURE=0.0
AI__MAX_TOKENS=4000

# Monitoring
MONITORING__PROMETHEUS_PORT=9090
MONITORING__LOG_LEVEL=INFO
MONITORING__LOG_FORMAT=json
EOF
```

#### 2.2 Update Required Values

**You MUST change these values:**

1. **ALERT__CHANNEL_ID** - Get your Slack channel ID:
   ```bash
   # In Slack, right-click channel → View channel details → Copy Channel ID
   # Example: C07V7ABCD123
   ```

2. **AI__API_KEY** - Get your Anthropic API key:
   ```bash
   # Go to: https://console.anthropic.com/settings/keys
   # Create new key, copy it
   # Example: sk-ant-api03-ABC123...
   ```

3. **DATABASE__URL** (optional) - If using different database credentials

---

### **Phase 3: Start Infrastructure** (10 minutes)

#### 3.1 Create Docker Compose File

Create `docker-compose.yml`:

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: fis-postgres
    environment:
      POSTGRES_USER: fis_user
      POSTGRES_PASSWORD: fis_pass
      POSTGRES_DB: fis_awareness
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fis_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: fis-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  temporal:
    image: temporalio/auto-setup:1.22.4
    container_name: fis-temporal
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=temporal-postgres
      - DYNAMIC_CONFIG_FILE_PATH=config/dynamicconfig/development-sql.yaml
    ports:
      - "7233:7233"   # gRPC
      - "8233:8233"   # Web UI
    depends_on:
      temporal-postgres:
        condition: service_healthy

  temporal-postgres:
    image: postgres:15
    container_name: fis-temporal-postgres
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal
      POSTGRES_DB: temporal
    ports:
      - "5433:5432"
    volumes:
      - temporal_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U temporal"]
      interval: 10s
      timeout: 5s
      retries: 5

  temporal-ui:
    image: temporalio/ui:2.21.3
    container_name: fis-temporal-ui
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
      - TEMPORAL_CORS_ORIGINS=http://localhost:3000
    ports:
      - "8080:8080"
    depends_on:
      - temporal

volumes:
  postgres_data:
  redis_data:
  temporal_postgres_data:
EOF
```

#### 3.2 Start Services

```bash
# Start all infrastructure
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# Check logs if any issues
docker-compose logs -f postgres
docker-compose logs -f temporal
```

**Expected output:**
```
NAME                 STATUS              PORTS
fis-postgres         Up (healthy)        0.0.0.0:5432->5432/tcp
fis-redis            Up (healthy)        0.0.0.0:6379->6379/tcp
fis-temporal         Up                  0.0.0.0:7233->7233/tcp, 0.0.0.0:8233->8233/tcp
fis-temporal-ui      Up                  0.0.0.0:8080->8080/tcp
```

#### 3.3 Verify Services

```bash
# Test PostgreSQL
psql postgresql://fis_user:fis_pass@localhost:5432/fis_awareness -c "SELECT 1;"

# Test Redis
redis-cli ping
# Expected: PONG

# Test Temporal
curl -s http://localhost:8233/api/v1/namespaces | grep -q "default" && echo "✓ Temporal running"

# Open Temporal UI in browser
echo "Temporal UI: http://localhost:8080"
```

---

### **Phase 4: Initialize Database** (5 minutes)

#### 4.1 Create Database Tables

```bash
# Install alembic if not already installed
pip install alembic

# Check if migrations directory exists
ls -la | grep -q "alembic" || echo "⚠ Alembic not configured"
```

**If alembic directory doesn't exist**, create tables manually:

```bash
python << 'EOF'
import sys
sys.path.insert(0, '/home/user/fis-situational-awareness')

from config import config
from models import Base
from sqlalchemy import create_engine

# Create engine
engine = create_engine(str(config.database.url))

# Create all tables
print("Creating database tables...")
Base.metadata.create_all(engine)
print("✓ All tables created successfully")

# Verify tables
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"\nTables created: {', '.join(tables)}")
EOF
```

**Expected output:**
```
Creating database tables...
✓ All tables created successfully

Tables created: ingestion_runs, entity_snapshots, detected_changes, alert_history
```

#### 4.2 Verify Database Schema

```bash
psql postgresql://fis_user:fis_pass@localhost:5432/fis_awareness << 'EOF'
\dt
\d entity_snapshots
\d detected_changes
EOF
```

---

### **Phase 5: Configure MCP Server** (10 minutes)

#### 5.1 Install Tribe MCP Server

```bash
# Install via uvx
uvx mcp-server-tribe --help

# Or install globally
pip install mcp-server-tribe
```

#### 5.2 Configure MCP Access Tokens

The Tribe MCP server needs access to Slack and Notion. Create config file:

```bash
mkdir -p ~/.config/mcp-server-tribe

cat > ~/.config/mcp-server-tribe/config.json << 'EOF'
{
  "slack": {
    "token": "xoxb-YOUR-SLACK-BOT-TOKEN",
    "user_token": "xoxp-YOUR-SLACK-USER-TOKEN"
  },
  "notion": {
    "token": "secret_YOUR-NOTION-INTEGRATION-TOKEN"
  }
}
EOF
```

**Get tokens:**

1. **Slack Bot Token** (xoxb-...):
   - Go to: https://api.slack.com/apps
   - Create app or select existing
   - OAuth & Permissions → Install to Workspace
   - Copy "Bot User OAuth Token"
   - Required scopes: `channels:history`, `channels:read`, `chat:write`, `search:read`

2. **Slack User Token** (xoxp-...):
   - Same app → OAuth & Permissions
   - Install to get "User OAuth Token"
   - Required for searching private channels

3. **Notion Integration Token**:
   - Go to: https://www.notion.so/my-integrations
   - Create new integration
   - Copy "Internal Integration Token"
   - Share FIS pages with this integration

#### 5.3 Test MCP Server

```bash
# Test MCP server can start
uvx mcp-server-tribe << 'EOF'
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
EOF

# Should see initialization response (not error)
```

---

### **Phase 6: Run Tests** (5 minutes)

#### 6.1 Run Application Tests

```bash
# Activate venv if not already
source venv/bin/activate

# Run full test suite
python test_application.py
```

**Expected output:**
```
✓ PASS: Import config
✓ PASS: Import models
✓ PASS: Import web
...
Total Tests: 17
Passed: 17 (100%)
```

#### 6.2 Run Digest Tests

```bash
python test_digest.py
```

**Expected output:**
```
✓ PASS: Import Test
✓ PASS: Structure Test
✓ PASS: Significance Scoring Test
✓ PASS: Workflow Registration Test
✓ PASS: Activity Registration Test

Total: 5/5 tests passed (100%)
```

---

### **Phase 7: Start the Application** (2 minutes)

#### 7.1 Run the System

```bash
# Make sure you're in venv
source venv/bin/activate

# Start the application
python main.py
```

**Expected output:**
```
INFO - Starting FIS Situational Awareness System
INFO - Environment: development
INFO - Temporal host: localhost:7233
INFO - Database: postgresql://fis_user:***@localhost:5432/fis_awareness
INFO - Starting web server on 0.0.0.0:8080
INFO - Starting Temporal worker...
INFO - Temporal worker started on task queue: fis-ingestion
INFO - All services started successfully
```

#### 7.2 Verify System is Running

In separate terminal:

```bash
# Test web server
curl http://localhost:8080/health
# Expected: {"status":"healthy","timestamp":"..."}

# Test Temporal worker
temporal workflow list --task-queue fis-ingestion
```

---

### **Phase 8: Trigger First Ingestion** (5 minutes)

#### 8.1 Manual Workflow Trigger

```bash
# Trigger ingestion workflow
temporal workflow start \
  --type IngestionWorkflow \
  --task-queue fis-ingestion \
  --workflow-id "manual-test-$(date +%s)"

# Watch workflow progress
temporal workflow show --workflow-id manual-test-<timestamp>

# Or use Temporal UI
echo "Open: http://localhost:8080"
```

#### 8.2 Verify Results

```bash
# Check database for ingested entities
psql postgresql://fis_user:fis_pass@localhost:5432/fis_awareness << 'EOF'
SELECT source, status, items_ingested, run_timestamp
FROM ingestion_runs
ORDER BY run_timestamp DESC
LIMIT 5;

SELECT entity_type, COUNT(*)
FROM entity_snapshots
GROUP BY entity_type;
EOF
```

#### 8.3 Trigger Weekly Digest

```bash
# Test digest generation
temporal workflow start \
  --type WeeklyDigestWorkflow \
  --task-queue fis-ingestion \
  --workflow-id "test-digest-$(date +%s)"

# Check Slack for digest message
```

---

### **Phase 9: Schedule Recurring Jobs** (5 minutes)

#### 9.1 Create Ingestion Schedule (Every 3 Days)

```bash
temporal schedule create \
  --schedule-id fis-ingestion-schedule \
  --workflow-type ScheduledIngestionWorkflow \
  --task-queue fis-ingestion \
  --interval "3d"
```

#### 9.2 Create Digest Schedule (Monday 08:00 PT)

```bash
temporal schedule create \
  --schedule-id weekly-digest-schedule \
  --workflow-type WeeklyDigestWorkflow \
  --task-queue fis-ingestion \
  --calendar '{"dayOfWeek":[1],"hour":[16],"minute":[0]}' \
  --timezone "America/Los_Angeles"
```

#### 9.3 Verify Schedules

```bash
# List all schedules
temporal schedule list

# Check schedule details
temporal schedule describe --schedule-id weekly-digest-schedule
```

---

## 🎯 Verification Checklist

After completing all steps, verify:

- [ ] Dependencies installed (`pip list | grep temporalio`)
- [ ] `.env` file created with valid API keys
- [ ] Docker containers running (`docker-compose ps`)
- [ ] PostgreSQL accessible (`psql -c "SELECT 1;"`)
- [ ] Redis accessible (`redis-cli ping`)
- [ ] Temporal accessible (UI at http://localhost:8080)
- [ ] Database tables created (`\dt` in psql)
- [ ] MCP server configured (tokens in config)
- [ ] Tests passing (`python test_application.py`)
- [ ] Application running (`curl localhost:8080/health`)
- [ ] Worker registered (visible in Temporal UI)
- [ ] Ingestion workflow completed successfully
- [ ] Entities stored in database (`SELECT COUNT(*) FROM entity_snapshots`)
- [ ] Schedules created (`temporal schedule list`)

---

## 🚨 Common Issues & Solutions

### Issue: "No module named 'pydantic_settings'"

**Solution:**
```bash
pip install pydantic-settings
```

### Issue: "Can't connect to PostgreSQL"

**Solution:**
```bash
# Check container is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart if needed
docker-compose restart postgres
```

### Issue: "Temporal worker not connecting"

**Solution:**
```bash
# Check Temporal is running
docker-compose logs temporal

# Verify namespace exists
temporal namespace list

# Create if missing
temporal namespace create default
```

### Issue: "MCP server not found"

**Solution:**
```bash
# Install MCP server
pip install mcp-server-tribe

# Or use uvx
uvx mcp-server-tribe --version

# Update .env if path is different
MCP__SERVER_PATH=/path/to/mcp-server-tribe
```

### Issue: "Slack API errors"

**Solution:**
```bash
# Verify token has correct scopes
# Go to: https://api.slack.com/apps → Your App → OAuth & Permissions

# Required scopes:
# - channels:history
# - channels:read
# - chat:write
# - search:read

# Re-install app if scopes changed
```

### Issue: "Notion integration not working"

**Solution:**
```bash
# 1. Verify integration token
# 2. Go to Notion pages
# 3. Click "..." → Add connections → Select your integration
# 4. Token must have access to FIS pages
```

---

## 📊 System Monitoring

### Health Checks

```bash
# Application health
curl http://localhost:8080/health

# Application readiness
curl http://localhost:8080/ready

# Prometheus metrics
curl http://localhost:9090/metrics
```

### Temporal Monitoring

- **Web UI**: http://localhost:8080
- **Workflows**: See all running/completed workflows
- **Task Queues**: Check worker status
- **Schedules**: View scheduled jobs

### Database Monitoring

```bash
# Recent ingestion runs
psql postgresql://fis_user:fis_pass@localhost:5432/fis_awareness << 'EOF'
SELECT
  source,
  status,
  items_ingested,
  items_changed,
  run_timestamp
FROM ingestion_runs
ORDER BY run_timestamp DESC
LIMIT 10;
EOF

# Entity counts
psql postgresql://fis_user:fis_pass@localhost:5432/fis_awareness << 'EOF'
SELECT
  entity_type,
  COUNT(*) as count,
  MAX(snapshot_timestamp) as latest
FROM entity_snapshots
GROUP BY entity_type;
EOF

# Recent changes
psql postgresql://fis_user:fis_pass@localhost:5432/fis_awareness << 'EOF'
SELECT
  entity_type,
  change_type,
  significance_level,
  significance_score,
  change_timestamp
FROM detected_changes
ORDER BY change_timestamp DESC
LIMIT 10;
EOF
```

---

## 🚀 Next Steps

Once the system is running:

1. **Monitor first few runs** - Check Temporal UI for workflow execution
2. **Verify Slack alerts** - Ensure critical changes trigger notifications
3. **Review digest format** - Check Monday's digest in Slack
4. **Adjust thresholds** - Tune significance scores based on noise level
5. **Expand sources** - Add more Slack channels, Notion pages

---

## 📚 Additional Resources

- [README.md](README.md) - Main documentation
- [WEEKLY_DIGEST.md](WEEKLY_DIGEST.md) - Digest feature details
- [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md) - Deployment status
- [Temporal Documentation](https://docs.temporal.io/)
- [MCP Server Tribe](https://github.com/modelcontextprotocol/servers)
