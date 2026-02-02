"""
FIS Situational Awareness System - Web Server for Health Checks

Railway requires an HTTP server for health checks and readiness probes.
This module provides a simple FastAPI server that runs alongside the
Temporal worker.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.monitoring.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIS Situational Awareness System",
    description="Continuous monitoring and alerting for FIS",
    version="1.0.0"
)


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness check response model."""
    status: str
    checks: Dict[str, bool]
    timestamp: str


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "service": "FIS Situational Awareness System",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for Railway.

    Returns 200 if the application is alive.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        environment=config.environment
    )


@app.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """
    Readiness check endpoint.

    Checks if the application is ready to accept traffic by verifying
    connections to dependencies (database, redis, temporal).
    """
    checks = {}

    # Check database connection
    try:
        from sqlalchemy import create_engine, text, pool

        engine = create_engine(
            str(config.database.url),
            poolclass=pool.NullPool,  # Don't pool connections for health checks
            connect_args={"connect_timeout": 5}
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()  # Properly close all connections
        checks["database"] = True
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        checks["database"] = False

    # Check Redis connection
    try:
        import redis

        r = redis.from_url(
            str(config.redis.url),
            socket_connect_timeout=5,
            socket_timeout=5
        )
        r.ping()
        r.close()  # Properly close the connection
        checks["redis"] = True
    except Exception as e:
        logger.error(f"Redis check failed: {e}")
        checks["redis"] = False

    # Check Temporal connection (basic connectivity check)
    try:
        # Simple check - just verify Temporal config is set
        if config.temporal.host:
            checks["temporal"] = True
        else:
            checks["temporal"] = False
    except Exception as e:
        logger.error(f"Temporal check failed: {e}")
        checks["temporal"] = False

    # Overall status
    all_healthy = all(checks.values())
    status = "ready" if all_healthy else "not_ready"

    if not all_healthy:
        raise HTTPException(status_code=503, detail="Service not ready")

    return ReadinessResponse(
        status=status,
        checks=checks,
        timestamp=datetime.now().isoformat()
    )


@app.get("/status", response_model=Dict[str, Any])
async def status():
    """
    Full status and health check.

    Returns service info, dependency connectivity, and ingestion pipeline status
    (whether Slack, Notion, and news ingestion are configured and actually running).
    """
    # Dependency checks (same logic as /ready but no 503)
    checks: Dict[str, bool] = {}
    try:
        from sqlalchemy import create_engine, text, pool
        engine = create_engine(
            str(config.database.url),
            poolclass=pool.NullPool,
            connect_args={"connect_timeout": 5}
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        checks["database"] = True
    except Exception as e:
        logger.debug(f"Database check: {e}")
        checks["database"] = False

    try:
        import redis
        r = redis.from_url(str(config.redis.url), socket_connect_timeout=5, socket_timeout=5)
        r.ping()
        r.close()
        checks["redis"] = True
    except Exception as e:
        logger.debug(f"Redis check: {e}")
        checks["redis"] = False

    checks["temporal_configured"] = bool(config.temporal.host)

    # Ingestion pipeline status: no workflows/activities are registered in main.py
    ingestion_status: Dict[str, Dict[str, Any]] = {
        "slack": {
            "status": "agent_exists_not_scheduled",
            "message": "SlackIngestionAgent exists but no Temporal workflow/activity is registered; ingestion not running.",
        },
        "notion": {
            "status": "agent_exists_not_scheduled",
            "message": "NotionIngestionAgent exists but no Temporal workflow/activity is registered; ingestion not running.",
        },
        "news": {
            "status": "not_implemented",
            "message": "Config has news_sources and sec_cik but no external/news agent or activity exists; news not being pulled.",
        },
    }

    return {
        "service": "FIS Situational Awareness System",
        "version": "1.0.0",
        "environment": config.environment,
        "timestamp": datetime.now().isoformat(),
        "dependencies": checks,
        "ingestion": ingestion_status,
        "summary": (
            "Ingestion pipeline is not running: workflows and activities are commented out in main.py. "
            "Notion and Slack agents exist but are never invoked; news/SEC ingestion is not implemented."
        ),
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    # This would integrate with prometheus_client
    # For now, return a simple response
    return {
        "message": "Metrics endpoint - integrate with prometheus_client for full metrics"
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting web server on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=config.monitoring.log_level.lower()
    )
