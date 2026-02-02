# Temporal Worker Deployment Guide

This guide explains how to deploy the Temporal worker component of the FIS Situational Awareness System.

## Architecture Overview

The system is split into two components:

1. **Web Server** (deployed on Railway)
   - FastAPI server
   - Health checks and status API
   - No background processing

2. **Temporal Worker** (needs separate deployment)
   - Connects to Temporal Cloud
   - Executes ingestion workflows every 3 days
   - Processes changes and sends alerts

## Prerequisites

Before deploying the worker, ensure you have:

- ✅ Temporal Cloud account with API key
- ✅ PostgreSQL database (can use Railway's PostgreSQL)
- ✅ Slack channel ID for alerts
- ✅ Access to Tribe MCP server

## Deployment Options

### Option 1: Railway (Recommended)

**Pros:** Simple, same platform as web service, automatic deployments

**Steps:**

1. **Create new Railway service:**
   ```
   Project Dashboard → New Service → GitHub Repo
   Select: t0mmlee/fis-situational-awareness
   ```

2. **Set environment variables:**
   ```bash
   RUN_MODE=worker

   # Temporal
   TEMPORAL__HOST=ap-northeast-1.aws.api.temporal.io:7233
   TEMPORAL__NAMESPACE=your-namespace.account-id
   TEMPORAL__API_KEY=***
   TEMPORAL__TASK_QUEUE=fis-ingestion

   # Database (copy from web service)
   DATABASE__URL=${{Postgres.DATABASE_URL}}

   # Redis (optional)
   REDIS__URL=${{Redis.REDIS_URL}}

   # MCP
   MCP__SERVER_PATH=uvx
   MCP__SERVER_ARGS=["mcp-server-tribe"]

   # Alerts
   ALERT__CHANNEL_ID=C123456789
   ALERT__SIGNIFICANCE_THRESHOLD=75

   # AI (optional)
   AI__API_KEY=***
   AI__MODEL=claude-sonnet-4-5-20250929
   ```

3. **Deploy:**
   - Railway auto-deploys on push
   - Check logs: `railway logs --service fis-worker`

4. **Verify:**
   ```bash
   # Check logs for successful connection
   railway logs --service fis-worker | grep "Temporal worker started"
   ```

**Cost:** ~$5-10/month (alongside web service)

---

### Option 2: Local Development

**Pros:** Free, easy debugging, fast iteration

**Steps:**

1. **Clone repository:**
   ```bash
   git clone https://github.com/t0mmlee/fis-situational-awareness.git
   cd fis-situational-awareness
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure `.env` file:**
   ```bash
   RUN_MODE=worker

   TEMPORAL__HOST=ap-northeast-1.aws.api.temporal.io:7233
   TEMPORAL__NAMESPACE=your-namespace.account-id
   TEMPORAL__API_KEY=your-api-key
   TEMPORAL__TASK_QUEUE=fis-ingestion

   DATABASE__URL=postgresql://... (use Railway database URL)

   ALERT__CHANNEL_ID=C123456789

   MCP__SERVER_PATH=uvx
   MCP__SERVER_ARGS=["mcp-server-tribe"]
   ```

4. **Run worker:**
   ```bash
   python main.py
   ```

5. **Verify:**
   ```
   Should see: "Temporal worker started on task queue: fis-ingestion"
   ```

**Note:** Your computer must stay running for worker to function.

---

### Option 3: AWS ECS/Fargate

**Pros:** Production-ready, auto-scaling, managed infrastructure

**Steps:**

1. **Build and push Docker image:**
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

   # Build
   docker build -t fis-worker .

   # Tag
   docker tag fis-worker:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/fis-worker:latest

   # Push
   docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/fis-worker:latest
   ```

2. **Create ECS Task Definition:**

   File: `ecs-task-definition.json`
   ```json
   {
     "family": "fis-worker",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "containerDefinitions": [{
       "name": "worker",
       "image": "YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/fis-worker:latest",
       "environment": [
         {"name": "RUN_MODE", "value": "worker"},
         {"name": "TEMPORAL__HOST", "value": "ap-northeast-1.aws.api.temporal.io:7233"},
         {"name": "TEMPORAL__NAMESPACE", "value": "your-namespace.account-id"},
         {"name": "TEMPORAL__TASK_QUEUE", "value": "fis-ingestion"},
         {"name": "MCP__SERVER_PATH", "value": "uvx"},
         {"name": "MCP__SERVER_ARGS", "value": "[\"mcp-server-tribe\"]"},
         {"name": "ALERT__SIGNIFICANCE_THRESHOLD", "value": "75"}
       ],
       "secrets": [
         {"name": "TEMPORAL__API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:temporal-api-key"},
         {"name": "DATABASE__URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:database-url"},
         {"name": "ALERT__CHANNEL_ID", "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:slack-channel-id"},
         {"name": "AI__API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:anthropic-api-key"}
       ],
       "logConfiguration": {
         "logDriver": "awslogs",
         "options": {
           "awslogs-group": "/ecs/fis-worker",
           "awslogs-region": "us-east-1",
           "awslogs-stream-prefix": "worker"
         }
       }
     }]
   }
   ```

3. **Register task definition:**
   ```bash
   aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
   ```

4. **Create ECS Service:**
   ```bash
   aws ecs create-service \
     --cluster fis-cluster \
     --service-name fis-worker \
     --task-definition fis-worker \
     --desired-count 1 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
   ```

5. **Verify:**
   ```bash
   aws ecs describe-services --cluster fis-cluster --services fis-worker
   aws logs tail /ecs/fis-worker --follow
   ```

**Cost:** ~$15-25/month (0.5 vCPU, 1GB RAM)

---

### Option 4: Azure Container Instances

**Pros:** Simple, pay-per-second, no cluster management

**Steps:**

1. **Build and push image:**
   ```bash
   # Login to ACR
   az acr login --name yourregistry

   # Build
   docker build -t fis-worker .

   # Tag
   docker tag fis-worker yourregistry.azurecr.io/fis-worker:latest

   # Push
   docker push yourregistry.azurecr.io/fis-worker:latest
   ```

2. **Deploy container:**
   ```bash
   az container create \
     --resource-group fis-rg \
     --name fis-worker \
     --image yourregistry.azurecr.io/fis-worker:latest \
     --cpu 1 \
     --memory 2 \
     --restart-policy Always \
     --environment-variables \
       RUN_MODE=worker \
       TEMPORAL__HOST=ap-northeast-1.aws.api.temporal.io:7233 \
       TEMPORAL__NAMESPACE=your-namespace.account-id \
       TEMPORAL__TASK_QUEUE=fis-ingestion \
       MCP__SERVER_PATH=uvx \
       MCP__SERVER_ARGS='["mcp-server-tribe"]' \
       ALERT__SIGNIFICANCE_THRESHOLD=75 \
     --secure-environment-variables \
       TEMPORAL__API_KEY=your-api-key \
       DATABASE__URL=postgresql://... \
       ALERT__CHANNEL_ID=C123456789 \
       AI__API_KEY=sk-ant-...
   ```

3. **Verify:**
   ```bash
   az container logs --resource-group fis-rg --name fis-worker --follow
   ```

**Cost:** ~$12-20/month (1 vCPU, 2GB RAM)

---

### Option 5: Kubernetes

**Pros:** Production-grade, highly available, auto-scaling

**Steps:**

1. **Create namespace:**
   ```bash
   kubectl create namespace fis-ai
   ```

2. **Create secrets:**
   ```bash
   # Copy template and fill in values
   cp kubernetes/secrets-template.yaml kubernetes/secrets.yaml
   # Edit secrets.yaml with real values

   # Apply secrets
   kubectl apply -f kubernetes/secrets.yaml
   ```

3. **Deploy worker:**
   ```bash
   kubectl apply -f kubernetes/worker-deployment.yaml
   ```

4. **Verify:**
   ```bash
   # Check pod status
   kubectl get pods -n fis-ai -l component=worker

   # View logs
   kubectl logs -f -n fis-ai -l component=worker

   # Check if worker connected to Temporal
   kubectl logs -n fis-ai -l component=worker | grep "Temporal worker started"
   ```

5. **Scale (optional):**
   ```bash
   kubectl scale deployment fis-worker -n fis-ai --replicas=2
   ```

**Cost:** Depends on cluster, typically $20-50/month

---

## Post-Deployment Verification

### 1. Check Worker Logs

Look for these log messages:

```
✅ Starting Temporal worker...
✅ Connecting to Temporal Cloud: ap-northeast-1.aws.api.temporal.io:7233
✅ Temporal worker started on task queue: fis-ingestion
```

### 2. Verify Temporal Connection

In Temporal Cloud UI:
- Go to Workers tab
- Should see worker connected with task queue `fis-ingestion`

### 3. Trigger Manual Workflow

Using Temporal CLI:

```bash
# Install Temporal CLI
brew install temporal  # macOS
# or download from https://github.com/temporalio/cli

# Login to Temporal Cloud
temporal login

# Trigger ingestion workflow
temporal workflow execute \
  --type IngestionWorkflow \
  --task-queue fis-ingestion \
  --workflow-id manual-ingestion-$(date +%s) \
  --address ap-northeast-1.aws.api.temporal.io:7233 \
  --namespace your-namespace.account-id
```

### 4. Check Database

Verify ingestion ran:

```sql
-- Check ingestion runs
SELECT * FROM ingestion_runs
ORDER BY run_timestamp DESC
LIMIT 5;

-- Check entity snapshots
SELECT entity_type, COUNT(*)
FROM entity_snapshots
GROUP BY entity_type;

-- Check detected changes
SELECT * FROM detected_changes
ORDER BY change_timestamp DESC
LIMIT 10;
```

### 5. Check Slack

If CRITICAL changes detected (score ≥ 75), alerts should appear in your configured Slack channel.

---

## Troubleshooting

### Worker Can't Connect to Temporal

**Error:**
```
RuntimeError: Failed client connect: transport error
```

**Solutions:**
1. Verify `TEMPORAL__API_KEY` is correct
2. Check `TEMPORAL__HOST` format: `namespace.account-id.tmprl.cloud:7233`
3. Ensure `TEMPORAL__NAMESPACE` matches: `namespace.account-id`
4. Test connectivity: `curl -v https://ap-northeast-1.aws.api.temporal.io:7233`

### Database Connection Issues

**Error:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solutions:**
1. Check `DATABASE__URL` is correct
2. Verify database is accessible from worker (firewall rules)
3. For Railway: Use internal private URL, not public URL
4. Test connection: `psql $DATABASE__URL`

### MCP Server Issues

**Error:**
```
Failed to create MCP session
```

**Solutions:**
1. Verify `uvx` is installed in container (it is in Dockerfile)
2. Check `mcp-server-tribe` is accessible
3. Verify MCP server has Slack/Notion credentials configured

### No Alerts Sent

**Possible causes:**
1. No CRITICAL changes detected (score < 75)
2. Wrong `ALERT__CHANNEL_ID`
3. Alerts deduplicated (already sent in last 24h)
4. MCP Slack tool not authenticated

**Debug:**
```sql
-- Check for high-scoring changes
SELECT * FROM detected_changes
WHERE significance_score >= 75
AND alert_sent = false
ORDER BY significance_score DESC;

-- Check alert history
SELECT * FROM alert_history
ORDER BY alert_timestamp DESC
LIMIT 10;
```

---

## Monitoring

### Temporal Cloud UI

Monitor workflows:
- https://cloud.temporal.io/namespaces/your-namespace/workflows

### Logs

**Railway:**
```bash
railway logs --service fis-worker --follow
```

**AWS:**
```bash
aws logs tail /ecs/fis-worker --follow
```

**Kubernetes:**
```bash
kubectl logs -f -n fis-ai -l component=worker
```

### Metrics

If running with web server or exposing metrics:
```bash
curl http://worker-service:9090/metrics
```

---

## Cost Comparison

| Platform | Monthly Cost | Setup Complexity | Availability |
|----------|-------------|------------------|--------------|
| Railway | $5-10 | ⭐ Easy | Standard |
| Local Dev | Free | ⭐ Easy | Manual |
| AWS ECS | $15-25 | ⭐⭐⭐ Moderate | High |
| Azure ACI | $12-20 | ⭐⭐ Easy | Standard |
| Kubernetes | $20-50 | ⭐⭐⭐⭐ Complex | Very High |

**Recommendation:** Start with Railway for simplicity, migrate to AWS/Azure for production scale.

---

## Next Steps

After deploying the worker:

1. **Schedule Regular Ingestion:**
   - Configure 3-day schedule in Temporal
   - Or trigger manually as needed

2. **Monitor Performance:**
   - Watch ingestion success rate
   - Track alert volume
   - Review significance scores

3. **Tune Configuration:**
   - Adjust `ALERT__SIGNIFICANCE_THRESHOLD` based on alert volume
   - Increase `INGESTION__INTERVAL_DAYS` if too frequent
   - Add more `INGESTION__NEWS_SOURCES` as needed

4. **Set Up Alerting:**
   - Configure Slack channel notifications
   - Add PagerDuty integration for critical alerts
   - Set up monitoring dashboards

---

## Support

For issues:
- Check logs first
- Review Temporal Cloud UI for workflow errors
- Verify all environment variables are set correctly
- Test database and MCP connectivity

For questions:
- GitHub Issues: https://github.com/t0mmlee/fis-situational-awareness/issues
- Internal: #tribe-platform-users Slack channel
