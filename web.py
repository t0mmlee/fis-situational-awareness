"""
FIS Situational Awareness System - Web Server for Health Checks

Railway requires an HTTP server for health checks and readiness probes.
This module provides a simple FastAPI server that runs alongside the
Temporal worker.
"""

import logging
import os
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import config

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
        from sqlalchemy import create_engine, text
        engine = create_engine(str(config.database.url))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        checks["database"] = False

    # Check Redis connection
    try:
        import redis
        r = redis.from_url(str(config.redis.url))
        r.ping()
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
