# FIS Situational Awareness System

An autonomous system that continuously monitors Fidelity National Information Services (FIS) across internal and external sources, detects material changes, and alerts stakeholders via Slack when critical thresholds are exceeded.

## Overview

This system maintains situational awareness on FIS by:
- **Ingesting** data every 3 days from Slack, Notion, and external sources (news, SEC filings)
- **Detecting** material changes (leadership, program status, risks, timelines, external events)
- **Scoring** significance of each change (0-100 scale)
- **Alerting** stakeholders in Slack when CRITICAL changes occur (score ≥ 75)

**Key Features:**
- ✅ MCP-First: All internal integrations via Tribe MCP server (no direct APIs)
- ✅ Incremental: Optimized for delta detection, not full re-ingestion
- ✅ Auditable: Complete trail of ingestions, changes, and alert decisions
- ✅ Extensible: Add new MCP tools without architectural changes
- ✅ Enterprise-Grade: Idempotent, resilient, observable

## Architecture

```
Temporal Scheduler → Ingestion Agents (Slack, Notion, External)
                   → Normalization → State Manager (PostgreSQL)
                   → Change Detector → Significance Scorer
                   → Alert Manager → Slack (#fis-situational-awareness)
```

See [Architecture Documentation](FIS_Situational_Awareness_System_Architecture.md) for detailed design.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Temporal.io server
- Tribe MCP server access
- Azure AKS cluster (for production deployment)

## Installation

### Local Development

1. **Clone repository:**
```bash
git clone <repository-url>
cd fis_situational_awareness
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize database:**
```bash
python -m alembic upgrade head
```

6. **Start Temporal server:**
```bash
# In a separate terminal
temporal server start-dev
```

7. **Run the application:**
```bash
python -m fis_situational_awareness.main
```

### Docker Deployment

1. **Build Docker image:**
```bash
docker build -t tribeai/fis-situational-awareness:latest .
```

2. **Run with Docker Compose:**
```bash
docker-compose up -d
```

### Kubernetes Deployment

1. **Create namespace:**
```bash
kubectl create namespace fis-ai
```

2. **Create secrets:**
```bash
kubectl create secret generic postgres-secret \
  --from-literal=connection_string="postgresql://user:pass@host:5432/db" \
  -n fis-ai

kubectl create secret generic slack-secret \
  --from-literal=alert_channel_id="C123456789" \
  -n fis-ai

kubectl create secret generic ai-secret \
  --from-literal=api_key="your-anthropic-api-key" \
  -n fis-ai
```

3. **Deploy application:**
```bash
kubectl apply -f kubernetes/deployment.yaml
```

4. **Verify deployment:**
```bash
kubectl get pods -n fis-ai
kubectl logs -f deployment/fis-situational-awareness -n fis-ai
```

## Configuration

Configuration is managed via environment variables and can be set in `.env` file or Kubernetes secrets.

### Core Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ENVIRONMENT` | Environment (development/production) | `development` | No |
| `DATABASE__URL` | PostgreSQL connection string | - | Yes |
| `REDIS__URL` | Redis connection string | `redis://localhost:6379/0` | No |
| `TEMPORAL__HOST` | Temporal server host | `localhost:7233` | Yes |
| `ALERT__CHANNEL_ID` | Slack channel ID for alerts | - | Yes |
| `ALERT__SIGNIFICANCE_THRESHOLD` | Min score for alerts | `75` | No |
| `INGESTION__INTERVAL_DAYS` | Days between ingestion | `3` | No |

See `config.py` for full configuration options.

### Deployment Modes

The application supports three deployment modes via the `RUN_MODE` environment variable:

#### 1. **Web Server Only** (Recommended for Railway/PaaS)

```bash
RUN_MODE=web
```

**What it does:**
- ✅ Starts FastAPI web server on port 8080
- ✅ Health check endpoint (`/health`)
- ✅ Status endpoint (`/status`) - shows ingestion pipeline status
- ✅ Metrics endpoint (`/metrics`) - Prometheus metrics
- ❌ Does NOT start Temporal worker (no ingestion runs)

**Use cases:**
- Railway deployments (web-only container)
- Health check/status API servers
- Development/testing without Temporal
- When Temporal Cloud credentials are not available

**Configuration:**
```toml
# railway.toml
[deploy.env]
RUN_MODE = "web"
```

#### 2. **Temporal Worker Only**

```bash
RUN_MODE=worker
```

**What it does:**
- ❌ Does NOT start web server
- ✅ Starts Temporal worker for ingestion workflows
- ✅ Executes scheduled ingestions every 3 days
- ✅ Processes changes and sends alerts

**Use cases:**
- Separate worker containers
- Background processing services
- When you have a separate health check mechanism

**Requirements:**
- Temporal server must be accessible
- For Temporal Cloud: `TEMPORAL__API_KEY` must be set
- Database and MCP server must be accessible

#### 3. **Both Web + Worker** (Default)

```bash
RUN_MODE=both  # or omit RUN_MODE entirely
```

**What it does:**
- ✅ Starts web server (port 8080)
- ✅ Starts Temporal worker (in separate process)
- ✅ Full functionality

**Use cases:**
- Local development
- Single-container deployments
- Kubernetes pods with proper resources

**Resource Requirements:**
- CPU: 2+ cores recommended
- Memory: 2GB+ recommended
- Handles both HTTP requests and background processing

### Railway-Specific Configuration

For Railway deployments, the system defaults to **web-only mode** via `railway.toml`:

```toml
[deploy.env]
RUN_MODE = "web"
```

This prevents connection errors when Temporal Cloud is not configured. To run the Temporal worker:

1. **Option A:** Deploy worker separately
   - Create a second Railway service
   - Set `RUN_MODE=worker`
   - Configure Temporal Cloud credentials

2. **Option B:** Use external worker
   - Run worker on your infrastructure (AWS, Azure, on-prem)
   - Keep Railway for web server only

### Temporal Cloud Connection

When running the worker with Temporal Cloud:

```bash
# Required environment variables
TEMPORAL__HOST=<namespace>.<account-id>.tmprl.cloud:7233
TEMPORAL__NAMESPACE=<namespace>.<account-id>
TEMPORAL__API_KEY=<your-api-key>
```

**Connection Errors:**

If you see:
```
RuntimeError: Failed client connect: transport error
```

Check:
1. ✅ `TEMPORAL__API_KEY` is set correctly
2. ✅ `TEMPORAL__HOST` format: `namespace.account-id.tmprl.cloud:7233`
3. ✅ Network connectivity to Temporal Cloud
4. ✅ Namespace exists and is active

**Quick Fix:**
Set `RUN_MODE=web` to bypass worker connection errors.

## Usage

### Manual Ingestion Trigger

To trigger ingestion manually (outside of scheduled 3-day cycle):

```bash
python -m fis_situational_awareness.cli ingest
```

### View Recent Changes

```bash
python -m fis_situational_awareness.cli changes --since 2026-01-20
```

### View Alert History

```bash
python -m fis_situational_awareness.cli alerts --limit 10
```

### Test Alert Formatting

```bash
python -m fis_situational_awareness.cli test-alert
```

## Monitoring

### Prometheus Metrics

Metrics are exposed on port 9090 (`/metrics` endpoint):

- `ingestion_duration_seconds` - Time taken for each ingestion cycle
- `ingestion_items_count` - Number of items ingested per source
- `changes_detected_count` - Number of changes detected by significance level
- `alerts_sent_count` - Number of alerts sent
- `errors_count` - Number of errors by type

### Grafana Dashboards

Import the provided Grafana dashboard (`monitoring/grafana-dashboard.json`) to visualize:
- System health
- Ingestion success rates
- Change detection trends
- Alert volume

### Logs

Logs are structured JSON and can be aggregated using:
- **Azure Log Analytics** (for Azure deployments)
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **CloudWatch** (for AWS deployments)

Example log query (PostgreSQL):
```sql
SELECT * FROM ingestion_runs
WHERE status = 'failed'
ORDER BY run_timestamp DESC
LIMIT 10;
```

## Data Sources

### Internal Sources (via Tribe MCP)

**Slack:**
- All channels mentioning "FIS"
- Messages, threads, reactions, files
- User profile updates

**Notion:**
- FIS Strategic Enterprise AI Delivery Plan (main hub)
- FIS Stakeholders Database
- All pages tagged with 'FIS'

### External Sources

**News Monitoring:**
- Bloomberg, Reuters, WSJ, Financial Times
- FIS-related press releases and announcements

**SEC Filings:**
- 8-K (current events: M&A, executive changes)
- 10-K/10-Q (annual/quarterly reports)
- DEF 14A (proxy statements)
- Form 4 (insider trading)

## Alert Examples

### Critical Alert: Executive Change

```
🚨 FIS Situational Awareness Alert 🚨

What Changed:
Stephanie Ferris appointed as Chief Executive Officer & President

Significance: CRITICAL (Score: 95/100)

Why It Matters:
CEO appointment signals strategic leadership change. Former COO/CAO
with payments background (Vantiv/Worldpay). This may impact FIS's
strategic direction and technology priorities.

Context Impact:
• Executive Leadership
• Strategic Decision-Making
• Tribe AI Engagement Sponsorship

Source:
• https://investors.fisglobal.com/news-releases/2026-01-15
• https://sec.gov/edgar/...

Detected: January 15, 2026 10:45 AM EST
───────────────────────────────
React with ✅ to acknowledge this alert.
```

### Critical Alert: Program Blocked

```
🚨 FIS Situational Awareness Alert 🚨

What Changed:
Agent Factory CDD MVP status changed from "In Progress" to "Blocked"

Significance: CRITICAL (Score: 85/100)

Why It Matters:
Core deliverable for Phase 1 (Q1 2026) is now blocked. This may
jeopardize the January 31 target completion date and impact overall
program timeline.

Context Impact:
• Program: Agent Factory
• Phase 1 Milestone: First Production Agent
• Stakeholders: Gotham Pasupuleti (AI Program Lead)

Source:
• notion://2764f38daa208195a0d0d79d3a67eb3d
• slack://C123456789/1738165123.456789

Detected: January 29, 2026 2:15 PM EST
───────────────────────────────
React with ✅ to acknowledge this alert.
```

## Troubleshooting

### Ingestion Failures

**Symptom:** Ingestion runs failing with MCP connection errors

**Solution:**
1. Verify Tribe MCP server is accessible
2. Check MCP authentication credentials
3. Review MCP server logs: `kubectl logs -f mcp-server-pod`

### Database Connection Issues

**Symptom:** PostgreSQL connection timeouts

**Solution:**
1. Verify database is accessible: `psql <connection-string>`
2. Check connection pool settings in config
3. Review database logs for errors

### Missing Alerts

**Symptom:** Expected alerts not sent to Slack

**Solution:**
1. Check significance threshold: `SELECT * FROM detected_changes WHERE significance_score >= 75`
2. Verify Slack channel ID is correct
3. Check alert_history for deduplication: `SELECT * FROM alert_history ORDER BY alert_timestamp DESC`
4. Review MCP Slack tool logs

## Development

### Running Tests

```bash
pytest tests/ -v --cov=fis_situational_awareness
```

### Code Quality

```bash
# Type checking
mypy fis_situational_awareness/

# Linting
flake8 fis_situational_awareness/
black --check fis_situational_awareness/

# Format code
black fis_situational_awareness/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Security

### Secrets Management

- Store all secrets in Azure Key Vault (production)
- Never commit secrets to version control
- Use Kubernetes secrets for deployment
- Rotate secrets regularly (quarterly)

### Access Control

- MCP server handles Slack/Notion authentication
- Application runs with least-privilege service account
- Network policies restrict pod-to-pod communication

### Data Privacy

- Respect Slack/Notion data retention policies
- No PII storage beyond what's necessary
- Audit logs encrypted at rest
- GDPR/CCPA compliance considerations

## Performance Tuning

### Ingestion Optimization

- Use incremental ingestion (only fetch new data)
- Batch MCP requests where possible
- Cache frequently accessed data in Redis
- Adjust `batch_size` in config for optimal throughput

### Database Optimization

```sql
-- Create indexes for common queries
CREATE INDEX idx_entity_snapshots_type_id ON entity_snapshots(entity_type, entity_id);
CREATE INDEX idx_detected_changes_timestamp ON detected_changes(change_timestamp);
CREATE INDEX idx_alert_history_timestamp ON alert_history(alert_timestamp);

-- Vacuum and analyze regularly
VACUUM ANALYZE entity_snapshots;
VACUUM ANALYZE detected_changes;
```

### Scaling

- Horizontal scaling: Increase replica count in Kubernetes
- Vertical scaling: Adjust resource requests/limits
- Database: Use read replicas for queries

## Roadmap

### Short-Term (3-6 Months)
- [ ] Gmail integration (when Tribe MCP connector available)
- [ ] Sentiment analysis for Slack/news
- [ ] Trend visualization dashboard
- [ ] Custom alert preferences per user

### Long-Term (6-12 Months)
- [ ] Predictive analytics (risk forecasting)
- [ ] Natural language query interface
- [ ] Multi-customer support
- [ ] Integration with Tribe's Client Portal

## Support

For issues, questions, or feature requests:
- **Internal:** Post in #tribe-platform-users Slack channel
- **GitHub:** Open an issue at <repository-url>/issues
- **Email:** support@tribe.ai

## License

Proprietary - Tribe AI Inc. © 2026

## Contributors

- Tribe AI Engineering Team
- FIS Program Leadership

## Changelog

### Version 1.0.0 (2026-01-30)
- Initial release
- Slack and Notion ingestion via Tribe MCP
- External monitoring (news, SEC)
- Change detection and significance scoring
- Slack alerting with deduplication
- Kubernetes deployment configuration
