#!/bin/bash
# FIS Situational Awareness System - Quick Setup Script
# This script automates the initial setup process

set -e  # Exit on error

echo "================================================"
echo "FIS SITUATIONAL AWARENESS SYSTEM - SETUP"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running from correct directory
if [ ! -f "main.py" ]; then
    echo -e "${RED}✗ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

echo "Step 1: Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.11"

if (( $(echo "$PYTHON_VERSION >= $REQUIRED_VERSION" | bc -l) )); then
    echo -e "${GREEN}✓ Python $PYTHON_VERSION installed${NC}"
else
    echo -e "${RED}✗ Python $REQUIRED_VERSION or higher required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

echo ""
echo "Step 2: Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment already exists${NC}"
fi

echo ""
echo "Step 3: Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""
echo "Step 4: Checking for .env file..."
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ No .env file found. Creating template...${NC}"
    cat > .env << 'EOF'
# Environment
ENVIRONMENT=development
DEBUG=false

# Database (PostgreSQL)
DATABASE__URL=postgresql://fis_user:fis_pass@localhost:5432/fis_awareness

# Redis Cache
REDIS__URL=redis://localhost:6379/0

# Temporal Workflow Engine
TEMPORAL__HOST=localhost:7233
TEMPORAL__NAMESPACE=default
TEMPORAL__TASK_QUEUE=fis-ingestion

# Tribe MCP Server
MCP__SERVER_PATH=uvx
MCP__SERVER_ARGS=["mcp-server-tribe"]

# Alerting (CHANGE THIS!)
ALERT__CHANNEL_ID=CHANGE_ME
ALERT__SIGNIFICANCE_THRESHOLD=75

# AI/LLM (CHANGE THIS!)
AI__PROVIDER=anthropic
AI__MODEL=claude-sonnet-4-5-20250929
AI__API_KEY=CHANGE_ME

# Monitoring
MONITORING__LOG_LEVEL=INFO
EOF
    echo -e "${YELLOW}⚠ .env file created. You MUST edit it and set:${NC}"
    echo "   - ALERT__CHANNEL_ID (your Slack channel ID)"
    echo "   - AI__API_KEY (your Anthropic API key)"
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

echo ""
echo "Step 5: Checking Docker..."
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker installed${NC}"

    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✓ Docker Compose installed${NC}"
    else
        echo -e "${RED}✗ Docker Compose not found${NC}"
        echo "  Install: https://docs.docker.com/compose/install/"
        exit 1
    fi
else
    echo -e "${RED}✗ Docker not found${NC}"
    echo "  Install: https://docs.docker.com/get-docker/"
    exit 1
fi

echo ""
echo "Step 6: Creating docker-compose.yml..."
if [ ! -f "docker-compose.yml" ]; then
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
      - "7233:7233"
      - "8233:8233"
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
    echo -e "${GREEN}✓ docker-compose.yml created${NC}"
else
    echo -e "${YELLOW}⚠ docker-compose.yml already exists${NC}"
fi

echo ""
echo "Step 7: Starting infrastructure..."
docker-compose up -d

echo ""
echo "Waiting for services to be healthy (30 seconds)..."
sleep 30

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Infrastructure started${NC}"
else
    echo -e "${RED}✗ Infrastructure failed to start${NC}"
    echo "Check logs: docker-compose logs"
    exit 1
fi

echo ""
echo "Step 8: Initializing database..."
python << 'PYTHON_EOF'
import sys
from config import config
from models import Base
from sqlalchemy import create_engine

try:
    engine = create_engine(str(config.database.url))
    Base.metadata.create_all(engine)
    print("✓ Database tables created")
except Exception as e:
    print(f"✗ Database initialization failed: {e}")
    sys.exit(1)
PYTHON_EOF

echo ""
echo "Step 9: Running tests..."
python test_application.py > /tmp/test_results.txt 2>&1
if grep -q "100%" /tmp/test_results.txt; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Some tests failed (this may be okay if MCP not configured)${NC}"
    grep "FAIL" /tmp/test_results.txt || true
fi

echo ""
echo "================================================"
echo "SETUP COMPLETE!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env file and set:"
echo "   - ALERT__CHANNEL_ID (your Slack channel ID)"
echo "   - AI__API_KEY (your Anthropic API key)"
echo ""
echo "2. Configure MCP server (see GETTING_STARTED.md Phase 5)"
echo ""
echo "3. Start the application:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "4. Trigger test workflow:"
echo "   temporal workflow start --type IngestionWorkflow --task-queue fis-ingestion"
echo ""
echo "Useful URLs:"
echo "  - Temporal UI: http://localhost:8080"
echo "  - Application: http://localhost:8080"
echo ""
echo "Documentation:"
echo "  - Complete guide: GETTING_STARTED.md"
echo "  - Weekly digest: WEEKLY_DIGEST.md"
echo "  - Main README: README.md"
echo ""
