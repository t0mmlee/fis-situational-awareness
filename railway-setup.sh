#!/bin/bash

# Railway Deployment Setup Script
# This script automates Railway CLI setup and environment configuration

set -e

echo "🚂 FIS Situational Awareness System - Railway Setup"
echo "=================================================="
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "⚠️  Railway CLI not found. Installing..."
    npm install -g @railway/cli
    echo "✅ Railway CLI installed"
else
    echo "✅ Railway CLI already installed"
fi

# Login to Railway
echo ""
echo "📝 Logging into Railway..."
railway login

# Initialize project
echo ""
echo "🏗️  Initializing Railway project..."
if [ ! -f ".railway" ]; then
    railway init
else
    echo "✅ Railway project already initialized"
fi

# Link to project
echo ""
echo "🔗 Linking to Railway project..."
railway link

# Add PostgreSQL
echo ""
read -p "Add PostgreSQL database? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 Adding PostgreSQL..."
    railway add --database postgres
    echo "✅ PostgreSQL added"
fi

# Add Redis
echo ""
read -p "Add Redis cache? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 Adding Redis..."
    railway add --database redis
    echo "✅ Redis added"
fi

# Set environment variables
echo ""
echo "🔧 Setting environment variables..."
echo "Please provide the following information:"

read -p "Temporal host (e.g., your-namespace.tmprl.cloud:7233): " TEMPORAL_HOST
read -p "Temporal namespace (default: fis-awareness): " TEMPORAL_NAMESPACE
TEMPORAL_NAMESPACE=${TEMPORAL_NAMESPACE:-fis-awareness}

read -p "Slack alert channel ID (e.g., C123456789): " ALERT_CHANNEL_ID

read -p "Anthropic API key (for AI entity extraction): " -s AI_API_KEY
echo ""

# Set variables via Railway CLI
railway variables set TEMPORAL__HOST="$TEMPORAL_HOST"
railway variables set TEMPORAL__NAMESPACE="$TEMPORAL_NAMESPACE"
railway variables set TEMPORAL__TASK_QUEUE="fis-ingestion"
railway variables set ALERT__CHANNEL_ID="$ALERT_CHANNEL_ID"
railway variables set ALERT__SIGNIFICANCE_THRESHOLD="75"
railway variables set INGESTION__INTERVAL_DAYS="3"
railway variables set AI__PROVIDER="anthropic"
railway variables set AI__MODEL="claude-sonnet-4-5-20250929"
railway variables set AI__API_KEY="$AI_API_KEY"
railway variables set ENVIRONMENT="production"
railway variables set MONITORING__LOG_LEVEL="INFO"

# FIS-specific configuration
railway variables set INGESTION__NOTION_MAIN_HUB_ID="2c04f38daa208021ae9efbab622bc6d9"
railway variables set INGESTION__NOTION_STAKEHOLDERS_ID="2d84f38daa20807eaa0df706cf5438de"
railway variables set INGESTION__NOTION_SEARCH_TAG="FIS"
railway variables set INGESTION__SLACK_SEARCH_QUERY="FIS"
railway variables set INGESTION__SEC_CIK="0001136893"

echo "✅ Environment variables set"

# Run database migrations
echo ""
read -p "Run database migrations? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗄️  Running Alembic migrations..."
    railway run alembic upgrade head
    echo "✅ Database migrations complete"
fi

# Deploy application
echo ""
read -p "Deploy application now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Deploying application..."
    railway up
    echo "✅ Deployment initiated"
fi

echo ""
echo "=================================================="
echo "✅ Railway setup complete!"
echo ""
echo "Next steps:"
echo "1. View logs: railway logs --tail"
echo "2. Check status: railway status"
echo "3. View dashboard: railway open"
echo "4. View application: railway domain"
echo ""
echo "📚 Full documentation: RAILWAY_DEPLOYMENT_GUIDE.md"
